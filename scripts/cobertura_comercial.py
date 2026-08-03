#!/usr/bin/env python
"""
TIER 1 · T1.1 (S4): cobertura comercial del snapshot.

Mide sobre las 29.054 filas de `productos_merged.json` qué fracción de cada campo
del contrato `ProductoEnMercado` (T1.3) trae dato real, y vuelca el resultado al
`manifest.json`. Los números ya estaban medidos a mano el 2026-08-02; este script
los vuelve auditables y reproducibles.

Dos decisiones que conviene no deshacer:

1. **Escribe en `cobertura_comercial`, clave de primer nivel.** `etl.finalizar_manifest`
   regenera `estadisticas` entera en cada corrida (finalizar_manifest.py:142-143):
   lo que se escriba ahí dentro se pierde en el próximo cierre de snapshot.

2. **`presentacion`, `precio` y `canal` se declaran a 0 %, no se omiten.** El ETL de
   S2 proyectó el CSV de OFF a 9 campos y descartó `quantity`, `packaging` y `stores`
   en la descarga (cargar_off_bulk.py:135-146); el export original (~9 GB) ya no está
   en disco y no se re-descarga. Un 0 % declarado es el hueco que llena el nivel 3 del
   puerto `DescubrimientoComercial`. Una columna ausente sería el hueco escondido.

Uso:
    uv run python scripts/cobertura_comercial.py
"""

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

DATASET = Path("datasets/2026-07")
PRODUCTOS = DATASET / "productos_merged.json"
MANIFEST = DATASET / "manifest.json"

# Campos que el snapshot sí trae.
CAMPOS_PRESENTES = ["nombre", "url", "fecha_dato", "marca", "categoria", "pais"]

# Campos del contrato que el snapshot no trae. Ver nota 2 del docstring.
CAMPOS_AUSENTES = ["presentacion", "precio", "canal"]

# Campos de texto donde el mojibake es visible para el usuario. Baseline de T2.2,
# cuyo gate exige 0.
CAMPOS_TEXTO = ["nombre", "marca", "pais"]

# No-datos disfrazados: la celda tiene contenido, pero el contenido es "no sé".
# La lista canónica vive en etl.limpiar_texto porque la comparten el adaptador
# de T3.2 (que los convierte a None) y el validador P04 de T5.1 (que falla si
# los encuentra). Medirla aquí dice si P04 tendrá trabajo real.
from etl.limpiar_texto import SIN_DATO as DISFRAZADOS

REEMPLAZO = "�"  # el rombo con interrogante de `Espa�a`


def es_no_dato(valor) -> bool:
    """True si la celda está vacía: None, cadena vacía o solo espacios."""
    if valor is None:
        return True
    if isinstance(valor, (int, float, bool)):
        return False
    return not str(valor).strip()


def es_disfrazado(valor) -> bool:
    """True si la celda tiene contenido pero el contenido es un no-dato."""
    if valor is None or isinstance(valor, (int, float, bool)):
        return False
    return str(valor).strip().lower() in DISFRAZADOS


def pct(n: int, total: int) -> float:
    return round(100.0 * n / total, 1) if total else 0.0


def es_pct(valor: float) -> str:
    """Porcentaje con coma decimal, como en el plan."""
    return f"{valor:.1f}".replace(".", ",") + " %"


def medir(productos: list[dict]) -> dict:
    total = len(productos)
    con_dato = {c: 0 for c in CAMPOS_PRESENTES}
    disfrazados = {c: 0 for c in CAMPOS_PRESENTES}
    mojibake = {c: 0 for c in CAMPOS_TEXTO}
    variantes_pais: Counter[str] = Counter()
    por_fuente: Counter[str] = Counter()

    for p in productos:
        por_fuente[str(p.get("id_fuente", "")).split(":")[0] or "?"] += 1

        for campo in CAMPOS_PRESENTES:
            valor = p.get(campo)
            if not es_no_dato(valor):
                con_dato[campo] += 1
            if es_disfrazado(valor):
                disfrazados[campo] += 1

        for campo in CAMPOS_TEXTO:
            if REEMPLAZO in str(p.get(campo) or ""):
                mojibake[campo] += 1

        pais = str(p.get("pais") or "").strip()
        if pais:
            variantes_pais[pais] += 1

    campos = {}
    for campo in CAMPOS_PRESENTES:
        n, falso = con_dato[campo], disfrazados[campo]
        campos[campo] = {
            "con_dato": n,
            "cobertura_pct": pct(n, total),
            # Cobertura descontando las celdas que solo aparentan tener dato.
            # Es la cifra que P04 considerará verdadera en T5.1.
            "disfrazados": falso,
            "cobertura_neta_pct": pct(n - falso, total),
            "presente_en_snapshot": True,
        }

    for campo in CAMPOS_AUSENTES:
        campos[campo] = {
            "con_dato": 0,
            "cobertura_pct": 0.0,
            "disfrazados": 0,
            "cobertura_neta_pct": 0.0,
            "presente_en_snapshot": False,
            "motivo": "descartado en la descarga (etl/cargar_off_bulk.py:135-146); "
                      "el export original (~9 GB) ya no está en disco. Lo llena el "
                      "nivel 3 de DescubrimientoComercial",
        }

    return {
        "medido_en": datetime.now(timezone.utc).isoformat(),
        "fuente": str(PRODUCTOS).replace("\\", "/"),
        "filas": total,
        "por_fuente": dict(por_fuente),
        "campos": campos,
        "pais": {
            "variantes_distintas": len(variantes_pais),
            "filas_sin_pais": total - con_dato["pais"],
            "top_15": variantes_pais.most_common(15),
            # El plan S4 §T1.1 dice 1.578 variantes; son 1.577 reales más la
            # cadena vacía de las 127 filas sin país, que se contó como una
            # variante más. El gate de T2.1 se mide sobre las 1.577.
            "nota": "normalización a ISO-3166 en T2.1, aplicada al leer; "
                    "el snapshot no se reescribe",
        },
        "mojibake": {
            "por_campo": mojibake,
            "filas_afectadas": sum(mojibake.values()),
            "nota": "baseline previo a T2.2, cuyo gate exige 0",
        },
    }


def imprimir(cob: dict) -> None:
    total = cob["filas"]
    print(f"\n[COBERTURA] {total:,} filas · {cob['por_fuente']}\n")
    print(f"  {'Campo':<14} {'Con dato':>9} {'Cobertura':>11} {'Disfrazados':>12}")
    print(f"  {'-' * 14} {'-' * 9} {'-' * 11} {'-' * 12}")

    for campo, d in cob["campos"].items():
        marca = "" if d["presente_en_snapshot"] else "  ← no existe en el snapshot"
        print(f"  {campo:<14} {d['con_dato']:>9,} {es_pct(d['cobertura_pct']):>11} "
              f"{d['disfrazados']:>12,}{marca}")

    p = cob["pais"]
    print(f"\n[PAÍS] {p['variantes_distintas']:,} variantes distintas → T2.1")
    for valor, n in p["top_15"][:8]:
        print(f"       {n:>7,}  {valor}")

    m = cob["mojibake"]
    estado = "OK" if m["filas_afectadas"] == 0 else "→ T2.2"
    print(f"\n[MOJIBAKE] {m['filas_afectadas']:,} celdas con '{REEMPLAZO}' "
          f"{m['por_campo']}  {estado}")


def main() -> int:
    if not PRODUCTOS.exists():
        print(f"[COBERTURA] No existe {PRODUCTOS}")
        return 1
    if not MANIFEST.exists():
        print(f"[COBERTURA] No existe {MANIFEST}")
        return 1

    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))
    cobertura = medir(productos)
    imprimir(cobertura)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["cobertura_comercial"] = cobertura
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\n[COBERTURA] OK -> {MANIFEST} (clave 'cobertura_comercial')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
