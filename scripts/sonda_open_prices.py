#!/usr/bin/env python
"""
TIER 1 · T1.2 (S4): sonda de Open Prices.

**Solo mide; no integra.** Pregunta a la API de Open Prices por 100 códigos de
barras del snapshot, estratificados por los 5 insumos piloto, y anota qué
fracción tiene al menos un precio, de cuándo son y de qué países. El resultado va
al `manifest.json` y se dice en voz alta en el bloque 2 del guion: si sale ~0 %,
el bloque pasa de "aquí están los precios" a "aquí está el hueco, medido".

Tres decisiones:

1. **Solo códigos OFF.** Open Prices indexa por código de barras. Los `id_fuente`
   de USDA son FDC ids (`USDA:2116605`), no códigos de barras: incluirlos metería
   un 0 % garantizado por construcción y ensuciaría la cifra. Las 818 filas de
   USDA quedan fuera de la muestra y así se declara.

2. **Muestra reproducible.** `--seed` fija la muestra, que se vuelca entera al
   manifest. La cifra es auditable: se puede repetir la sonda sobre los mismos
   100 códigos.

3. **Los sinónimos se importan de `etl.finalizar_manifest`**, que es donde ya
   viven y donde deben coincidir con `evals/set_dorado.yaml`. No se redefinen.

Uso:
    uv run python scripts/sonda_open_prices.py
    uv run python scripts/sonda_open_prices.py --n 10 --seed 7   # humo rápido
"""

import argparse
import json
import random
import statistics
import sys
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from etl.finalizar_manifest import INSUMOS

DATASET = Path("datasets/2026-07")
PRODUCTOS = DATASET / "productos_merged.json"
MANIFEST = DATASET / "manifest.json"

API = "https://prices.openfoodfacts.org/api/v1/prices"

# OFF pide un User-Agent descriptivo en sus condiciones de uso.
CABECERAS = {
    "User-Agent": "AgroScout-IA/0.1 (CITEagroindustrial Chavimochic; sonda de cobertura S4)",
    "Accept": "application/json",
}

PAUSA_S = 0.4        # cortesía entre peticiones
TIMEOUT_S = 8        # por petición
PRESUPUESTO_S = 420  # corte global; mejor una cifra parcial declarada que un cuelgue


def barcodes_por_insumo(productos: list[dict], por_insumo: int,
                        semilla: int) -> dict[str, list[str]]:
    """Muestra estratificada de códigos OFF, uno por insumo, sin repetir código."""
    candidatos: dict[str, list[str]] = {k: [] for k in INSUMOS}

    for p in productos:
        id_fuente = str(p.get("id_fuente", ""))
        if not id_fuente.startswith("OFF:"):
            continue
        codigo = id_fuente.split(":", 1)[1].strip()
        if not codigo.isdigit() or len(codigo) < 8:
            continue

        texto = (f"{p.get('nombre', '')} {p.get('ingredientes', '')} "
                 f"{p.get('categoria', '')}").lower()
        for insumo, sinonimos in INSUMOS.items():
            if any(s in texto for s in sinonimos):
                candidatos[insumo].append(codigo)

    rng = random.Random(semilla)
    muestra: dict[str, list[str]] = {}
    ya_vistos: set[str] = set()

    for insumo, codigos in candidatos.items():
        unicos = sorted(set(codigos) - ya_vistos)
        rng.shuffle(unicos)
        elegidos = unicos[:por_insumo]
        ya_vistos.update(elegidos)
        muestra[insumo] = elegidos
        if len(elegidos) < por_insumo:
            print(f"[SONDA] {insumo}: solo {len(elegidos)} códigos únicos "
                  f"disponibles (se pedían {por_insumo})")

    return muestra


def pais_de(precio: dict) -> str | None:
    """País del precio, o None si el precio no lo trae.

    No se cae de vuelta a `currency`: una moneda no es un país y mezclarlas en el
    mismo contador produce listas como `{'FR': 4, 'EUR': 1}`, donde una de las
    entradas no es lo que el rótulo dice. Los precios sin país se cuentan aparte.
    """
    loc = precio.get("location") or {}
    for clave in ("osm_address_country_code", "osm_address_country"):
        valor = loc.get(clave)
        if valor:
            return str(valor).upper()
    return None


def consultar(codigo: str, sesion: requests.Session) -> dict:
    """Un código → {precios, error}. Nunca lanza: un fallo de red es un dato."""
    try:
        r = sesion.get(API, params={"product_code": codigo, "size": 50},
                       headers=CABECERAS, timeout=TIMEOUT_S)
        if r.status_code == 429:
            time.sleep(5)
            r = sesion.get(API, params={"product_code": codigo, "size": 50},
                           headers=CABECERAS, timeout=TIMEOUT_S)
        if r.status_code != 200:
            return {"precios": [], "error": f"HTTP {r.status_code}"}
        cuerpo = r.json()
        return {"precios": cuerpo.get("items", []), "error": None}
    except Exception as e:
        return {"precios": [], "error": f"{type(e).__name__}: {e}"}


def control_positivo(sesion: requests.Session) -> dict:
    """¿Sabe la sonda reconocer un precio cuando lo hay?

    Pide precios sin filtro, toma un `product_code` real de la respuesta y lo
    vuelve a pedir CON el filtro que usa la sonda. Sin este control, un 0 % por
    cambio de esquema en la API sería indistinguible de un 0 % real, y el 0 % es
    justamente la cifra que se va a decir en voz alta en el CDR.
    """
    try:
        r = sesion.get(API, params={"size": 5}, headers=CABECERAS, timeout=TIMEOUT_S)
        if r.status_code != 200:
            return {"ok": False, "motivo": f"HTTP {r.status_code} sin filtro"}
        cuerpo = r.json()
        items = cuerpo.get("items", [])
        if not items:
            return {"ok": False, "motivo": "la API no devuelve precios ni sin filtro"}

        codigo = (items[0].get("product") or {}).get("code") or items[0].get("product_code")
        if not codigo:
            return {"ok": False, "motivo": "no se pudo extraer un product_code de control"}

        r2 = sesion.get(API, params={"product_code": codigo, "size": 50},
                        headers=CABECERAS, timeout=TIMEOUT_S)
        hallados = len(r2.json().get("items", []))
        return {
            "ok": hallados > 0,
            "codigo_control": codigo,
            "precios_hallados": hallados,
            "total_precios_en_base": cuerpo.get("total"),
            "motivo": None if hallados else "el filtro product_code no devuelve nada",
        }
    except Exception as e:
        return {"ok": False, "motivo": f"{type(e).__name__}: {e}"}


def sondear(muestra: dict[str, list[str]]) -> dict:
    hoy = date.today()
    total = con_precio = errores = consultados = sin_pais = 0
    antiguedades: list[int] = []
    paises: Counter[str] = Counter()
    monedas: Counter[str] = Counter()
    por_insumo: dict[str, dict] = {}
    detalle_errores: Counter[str] = Counter()

    inicio = time.monotonic()
    sesion = requests.Session()
    agotado = False

    control = control_positivo(sesion)
    if control["ok"]:
        print(f"[SONDA] Control positivo OK: código {control['codigo_control']} "
              f"devuelve {control['precios_hallados']} precios · "
              f"{control['total_precios_en_base']:,} precios en la base")
    else:
        print(f"[SONDA] ⚠ CONTROL POSITIVO FALLIDO: {control['motivo']}")
        print("[SONDA]   Un 0 % de esta corrida NO es interpretable como dato.")

    for insumo, codigos in muestra.items():
        aciertos = vistos = 0
        for codigo in codigos:
            if time.monotonic() - inicio > PRESUPUESTO_S:
                agotado = True
                break

            total += 1
            vistos += 1
            resultado = consultar(codigo, sesion)

            if resultado["error"]:
                errores += 1
                detalle_errores[resultado["error"]] += 1
            else:
                consultados += 1

            precios = resultado["precios"]
            if precios:
                con_precio += 1
                aciertos += 1
                for pr in precios:
                    if pr.get("date"):
                        try:
                            d = datetime.strptime(str(pr["date"])[:10], "%Y-%m-%d").date()
                            antiguedades.append((hoy - d).days)
                        except ValueError:
                            pass
                    p = pais_de(pr)
                    if p:
                        paises[p] += 1
                    else:
                        sin_pais += 1
                    if pr.get("currency"):
                        monedas[str(pr["currency"])] += 1

            time.sleep(PAUSA_S)

        por_insumo[insumo] = {
            "consultados": vistos,
            "con_precio": aciertos,
            "pct": round(100.0 * aciertos / vistos, 1) if vistos else 0.0,
        }
        if agotado:
            break

    return {
        "medido_en": datetime.now(timezone.utc).isoformat(),
        "endpoint": API,
        "control_positivo": control,
        "codigos_consultados": total,
        "respuestas_ok": consultados,
        "errores": errores,
        "detalle_errores": dict(detalle_errores),
        "presupuesto_agotado": agotado,
        "con_al_menos_un_precio": con_precio,
        "pct_con_precio": round(100.0 * con_precio / total, 1) if total else 0.0,
        "antiguedad_dias": {
            "mediana": int(statistics.median(antiguedades)) if antiguedades else None,
            "min": min(antiguedades) if antiguedades else None,
            "max": max(antiguedades) if antiguedades else None,
            "n_precios": len(antiguedades),
        },
        "paises": dict(paises.most_common(15)),
        "precios_sin_pais": sin_pais,
        "monedas": dict(monedas.most_common(10)),
        "por_insumo": por_insumo,
        "alcance": "solo códigos OFF; las 818 filas USDA no tienen código de "
                   "barras (son FDC ids) y quedan fuera de la muestra",
        "decision": "T1.2 mide, no integra. La integración de precio queda fuera "
                    "del MVP (PLAN-TIERS-S4-MVP.md §0)",
    }


def imprimir(s: dict, muestra: dict) -> None:
    print(f"\n[SONDA] {s['codigos_consultados']} códigos · "
          f"{s['respuestas_ok']} respuestas OK · {s['errores']} errores")
    if s["presupuesto_agotado"]:
        print(f"[SONDA] ⚠ presupuesto de {PRESUPUESTO_S}s agotado: cifra PARCIAL")
    if s["detalle_errores"]:
        print(f"[SONDA] errores: {s['detalle_errores']}")

    print(f"\n[SONDA] Con al menos un precio: {s['con_al_menos_un_precio']}"
          f"/{s['codigos_consultados']} = {s['pct_con_precio']} %")

    for insumo, d in s["por_insumo"].items():
        print(f"        {insumo:<12} {d['con_precio']:>3}/{d['consultados']:<3} "
              f"{d['pct']:>5} %")

    a = s["antiguedad_dias"]
    if a["mediana"] is not None:
        print(f"\n[SONDA] Antigüedad: mediana {a['mediana']} d · "
              f"rango {a['min']}–{a['max']} d · {a['n_precios']} precios")
        print(f"[SONDA] Países: {s['paises']} · sin país: {s['precios_sin_pais']}")
        print(f"[SONDA] Monedas: {s['monedas']}")
    else:
        print("\n[SONDA] Sin precios: no hay antigüedad ni países que informar.")
        print("        Esta es la cifra del bloque 2 del guion: el hueco, medido.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Sonda de cobertura de Open Prices")
    ap.add_argument("--n", type=int, default=100, help="códigos totales (def. 100)")
    ap.add_argument("--seed", type=int, default=20260802, help="semilla de la muestra")
    args = ap.parse_args()

    if not PRODUCTOS.exists():
        print(f"[SONDA] No existe {PRODUCTOS}")
        return 1

    por_insumo = max(1, args.n // len(INSUMOS))
    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))
    muestra = barcodes_por_insumo(productos, por_insumo, args.seed)

    n_real = sum(len(v) for v in muestra.values())
    print(f"[SONDA] Muestra: {n_real} códigos OFF ({por_insumo}/insumo), "
          f"semilla {args.seed}")

    resultado = sondear(muestra)
    resultado["semilla"] = args.seed
    resultado["muestra"] = muestra  # la muestra completa, para poder repetirla
    imprimir(resultado, muestra)

    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        manifest["sonda_open_prices"] = resultado
        MANIFEST.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"\n[SONDA] OK -> {MANIFEST} (clave 'sonda_open_prices')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
