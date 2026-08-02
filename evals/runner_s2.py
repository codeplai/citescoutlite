"""
TIER 7 · T7.1: ejecutor del golden set S2.

Corre los 5 casos de `evals/set_dorado.yaml` contra el índice real y exige 5/5.
Además de los mínimos de cobertura, verifica la trazabilidad de cada resultado
(id, url y fecha reales), que es el criterio "cero valores inventados" del MVP.

    python -m evals.runner_s2
    python -m evals.runner_s2 --verbose
"""
import sys
from pathlib import Path

import yaml

from adaptadores.busqueda_lancedb import BusquedaLanceDB
from casos_de_uso.etapas.buscar_productos import _detectar_uso_directo

SET = "evals/set_dorado.yaml"


def evaluar_caso(catalogo, caso: dict, k: int, verbose: bool = False) -> tuple[bool, list[str]]:
    esperado = caso["esperado"]
    sinonimos = caso["sinonimos"]

    resultado = catalogo.buscar(sinonimos, k=k)
    productos = resultado.productos

    # Misma derivación que casos_de_uso/etapas/buscar_productos.py
    n_directos = sum(1 for p in productos
                     if _detectar_uso_directo(p.ingredientes, sinonimos))
    informe_parcial = n_directos <= 2  # casos_de_uso/evaluar_insumo.py:26

    fallos = []
    if len(productos) < esperado["min_coincidencias"]:
        fallos.append(f"coincidencias {len(productos)} < {esperado['min_coincidencias']}")
    if n_directos < esperado["min_directos"]:
        fallos.append(f"n_directos {n_directos} < {esperado['min_directos']}")
    if informe_parcial != esperado["informe_parcial"]:
        fallos.append(f"informe_parcial {informe_parcial} != {esperado['informe_parcial']}")

    # Trazabilidad: ningún dato inventado.
    sin_fecha = [p.id_fuente for p in productos if p.fecha_dato is None]
    sin_url = [p.id_fuente for p in productos if not p.url]
    sin_id = [p.nombre for p in productos if p.id_fuente in ("", "Unknown")]
    if sin_fecha:
        fallos.append(f"{len(sin_fecha)} productos sin fecha_dato")
    if sin_url:
        fallos.append(f"{len(sin_url)} productos sin url")
    if sin_id:
        fallos.append(f"{len(sin_id)} productos sin id_fuente")

    if verbose:
        fuentes = {}
        for p in productos:
            f = p.id_fuente.split(":")[0]
            fuentes[f] = fuentes.get(f, 0) + 1
        print(f"      resultados={len(productos)} n_directos={n_directos} "
              f"fuentes={fuentes}")
        for p in productos[:2]:
            print(f"      · {p.id_fuente} sim={p.similitud} {p.fecha_dato} "
                  f"{p.nombre[:45]}")

    return not fallos, fallos


def main(set_file: str = SET, verbose: bool = False) -> int:
    config = yaml.safe_load(Path(set_file).read_text(encoding="utf-8"))
    k = config.get("k", 30)
    casos = config["casos"]

    print(f"Golden set S2 · snapshot {config.get('version')} · k={k}")
    print("=" * 70)

    catalogo = BusquedaLanceDB()
    pasan = 0

    for caso in casos:
        ok, fallos = evaluar_caso(catalogo, caso, k, verbose)
        simbolo = "PASS" if ok else "FALL"
        print(f"[{simbolo}] {caso['id']:14} {caso['texto']}")
        if verbose:
            print(f"      ({caso['verificacion']})")
        for f in fallos:
            print(f"       -> {f}")
        pasan += ok

    print("=" * 70)
    print(f"Resultado: {pasan}/{len(casos)} casos pasan")
    return 0 if pasan == len(casos) else 1


if __name__ == "__main__":
    sys.exit(main(verbose="--verbose" in sys.argv))
