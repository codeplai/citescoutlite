"""
Indexación incremental de la tabla `productos`.

Añade a LanceDB solo los productos de `productos_merged.json` que todavía no
están indexados, comparando por `id`. Evita repetir las horas de cómputo de
TIER 4: cuando entró USDA en TIER 7 había que embeber 818 productos nuevos,
no los 29.054 del snapshot completo.

Uso:
    python -m etl.indexar_incremental
    python -m etl.indexar_incremental --dry-run
"""
import json
import sys
import time
from pathlib import Path

import lancedb

from adaptadores.modelo_embeddings import (
    get_modelo, limpiar_datasets_fantasma, DIMENSIONES, dispositivo,
)

MERGED = "datasets/2026-07/productos_merged.json"
DB = "vectores"
TABLA = "productos"
LOTE = 32


def ids_indexados(tabla) -> set[str]:
    """Ids ya presentes en la tabla."""
    filas = tabla.search().select(["id"]).limit(tabla.count_rows()).to_list()
    return {f["id"] for f in filas}


def main(dry_run: bool = False) -> int:
    productos = json.loads(Path(MERGED).read_text(encoding="utf-8"))
    print(f"[INC] Snapshot: {len(productos):,} productos")

    db = lancedb.connect(DB)
    nombres = getattr(db.list_tables(), "tables", db.list_tables())
    if TABLA not in nombres:
        print(f"[INC] La tabla '{TABLA}' no existe. Corre primero etl.tier4_gpu.")
        return 1

    tabla = db.open_table(TABLA)
    existentes = ids_indexados(tabla)
    print(f"[INC] Ya indexados: {len(existentes):,}")

    nuevos = [p for p in productos if p["id_fuente"] not in existentes]
    print(f"[INC] Pendientes: {len(nuevos):,}")

    if not nuevos:
        print("[INC] Nada que hacer: el índice ya está al día.")
        return 0

    por_fuente = {}
    for p in nuevos:
        f = p["id_fuente"].split(":")[0]
        por_fuente[f] = por_fuente.get(f, 0) + 1
    print(f"[INC] Por fuente: {por_fuente}")

    if dry_run:
        print("[INC] --dry-run: no se indexa nada.")
        return 0

    print(f"[INC] Cargando bge-m3 en {dispositivo().upper()}...")
    modelo = get_modelo()

    # Mismo texto que usó TIER 4 (etl/tier4_gpu.py): nombre + ingredientes.
    textos = [f"{p.get('nombre', '')} {p.get('ingredientes', '')}" for p in nuevos]

    inicio = time.time()
    embeddings = modelo.encode(textos, batch_size=LOTE, show_progress_bar=False)
    print(f"[INC] {len(nuevos)} embeddings en {time.time() - inicio:.1f}s")

    filas = []
    for p, emb in zip(nuevos, embeddings):
        filas.append({
            "id": p["id_fuente"],
            "nombre": p.get("nombre", ""),
            "categoria": p.get("categoria", ""),
            "ingredientes": p.get("ingredientes", ""),
            "url": p.get("url", ""),
            # La columna es int64 no nulo; sin fecha real se indexa 0 y la
            # búsqueda lo traduce a None (nunca a la fecha de hoy).
            "fecha_dato": p.get("fecha_dato") or 0,
            "marca": p.get("marca", ""),
            "pais": p.get("pais", ""),
            "fuente": p["id_fuente"].split(":")[0],
            "embedding": emb.tolist(),
        })

    # `encode()` deja un paquete `datasets` fantasma en sys.modules (la carpeta
    # del repo) que hace fallar la escritura de LanceDB. Ver la función.
    limpiar_datasets_fantasma()
    tabla.add(filas)
    print(f"[INC] Tabla '{TABLA}': {tabla.count_rows():,} filas")

    # Las filas nuevas entran sin indexar y se resuelven por escaneo lineal;
    # reconstruir el índice las incorpora al IVF-PQ.
    try:
        from lancedb.index import IvfPq
        tabla.create_index("embedding", config=IvfPq(distance_type="cosine"),
                           replace=True)
        print("[INC] Índice IVF-PQ (cosine) reconstruido")
    except Exception as e:
        print(f"[INC] WARN índice: {type(e).__name__}: {str(e)[:100]}")

    assert len(filas[0]["embedding"]) == DIMENSIONES
    return 0


if __name__ == "__main__":
    sys.exit(main(dry_run="--dry-run" in sys.argv))
