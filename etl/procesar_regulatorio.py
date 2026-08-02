"""
TIER 6 · T6.3: Indexa el corpus regulatorio en LanceDB.

Une eCFR (T6.1) + DIGESA (T6.2), genera embeddings bge-m3 y crea la tabla
`regulatorio` con métrica cosine, igual que la tabla `productos` de TIER 4.

Sustituye a la tabla `normativas` (4 filas de demo, búsqueda FTS) que venía de
S1. `adaptadores/verificador_rag.py` usa `regulatorio` si existe y cae a
`normativas` si no.

Salida: vectores/regulatorio.lance
"""
import json
import sys
import time
from pathlib import Path

import lancedb

from adaptadores.modelo_embeddings import get_modelo, DIMENSIONES, dispositivo

ECFR = "datasets/2026-07/ecfr_aditivos.json"
DIGESA = "datasets/2026-07/digesa_normas.json"
DB = "vectores"
TABLA = "regulatorio"
MANIFEST = "datasets/2026-07/manifest.json"


def cargar(ruta: str) -> list[dict]:
    p = Path(ruta)
    if not p.exists():
        print(f"[REG] {ruta} no existe, se omite")
        return []
    with open(p, encoding="utf-8") as f:
        docs = json.load(f)
    print(f"[REG] {ruta}: {len(docs)} documentos")
    return docs


def main() -> int:
    documentos = cargar(ECFR) + cargar(DIGESA)
    if not documentos:
        print("[REG] FALLO: no hay corpus que indexar. Ejecuta primero "
              "etl.procesar_ecfr y etl.procesar_digesa.")
        return 1

    print(f"[REG] Total: {len(documentos)} documentos")
    print(f"[REG] Cargando bge-m3 en {dispositivo().upper()}...")
    modelo = get_modelo()

    # El título lleva la denominación de la norma (p.ej. "L-Cysteine",
    # "Directiva Sanitaria..."), que es justo por lo que se busca.
    textos = [f"{d['titulo']} {d['texto']}" for d in documentos]

    print(f"[REG] Generando {len(textos)} embeddings...")
    inicio = time.time()
    embeddings = modelo.encode(textos, batch_size=16, show_progress_bar=False)
    print(f"[REG] Listo en {time.time() - inicio:.1f}s")

    filas = []
    for d, emb in zip(documentos, embeddings):
        filas.append({
            "id": d["id"],
            "titulo": d["titulo"],
            "texto": d["texto"],
            "cita": d.get("cita", ""),
            "fuente": d["fuente"],
            "fuente_url": d["fuente_url"],
            "fecha_publicacion": d.get("fecha_publicacion") or "",
            "tipo": d["tipo"],
            "embedding": emb.tolist(),
        })

    db = lancedb.connect(DB)
    try:
        db.drop_table(TABLA)
    except Exception:
        pass

    tabla = db.create_table(TABLA, data=filas, mode="create")
    print(f"[REG] Tabla '{TABLA}': {tabla.count_rows()} filas")

    # Con ~330 filas el IVF-PQ no tiene datos para entrenar particiones y
    # LanceDB puede rechazarlo. No es un problema: a esta escala la búsqueda
    # exacta es instantánea.
    try:
        from lancedb.index import IvfPq
        tabla.create_index("embedding", config=IvfPq(distance_type="cosine"))
        print("[REG] Índice IVF-PQ (cosine) creado")
    except Exception as e:
        print(f"[REG] Sin índice ANN ({type(e).__name__}); "
              f"búsqueda exacta cosine, suficiente a esta escala")

    # Manifest
    try:
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)

        por_tipo = {}
        for d in documentos:
            por_tipo[d["tipo"]] = por_tipo.get(d["tipo"], 0) + 1

        manifest["regulatorio"] = {
            "tabla": TABLA,
            "modelo": "BAAI/bge-m3",
            "dimensiones": DIMENSIONES,
            "metrica": "cosine",
            "filas": tabla.count_rows(),
            "documentos_por_tipo": por_tipo,
            "palabras_totales": sum(len(d["texto"].split()) for d in documentos),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(MANIFEST, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
        print("[REG] Manifest actualizado")
    except Exception as e:
        print(f"[REG] WARN manifest: {type(e).__name__}: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
