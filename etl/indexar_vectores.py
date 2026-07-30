import json
import os
import lancedb
import time

def main():
    print("Iniciando indexación con embeddings bge-m3 en LanceDB...")

    from sentence_transformers import SentenceTransformer

    productos = []

    if os.path.exists("data/off_productos.json"):
        with open("data/off_productos.json", "r", encoding="utf-8") as f:
            productos.extend(json.load(f))

    if os.path.exists("data/usda_productos.json"):
        with open("data/usda_productos.json", "r", encoding="utf-8") as f:
            productos.extend(json.load(f))

    if not productos:
        print("No hay productos para indexar.")
        return

    print(f"Cargando modelo bge-m3...")
    model = SentenceTransformer("BAAI/bge-m3")

    print(f"Generando embeddings para {len(productos)} productos...")

    textos = [f"{p['nombre']} {p['categoria']} {p['ingredientes']}" for p in productos]
    embeddings = model.encode(textos, show_progress_bar=True)

    print(f"Conectando a LanceDB...")
    db = lancedb.connect("vectores")

    data_lancedb = []
    for i, p in enumerate(productos):
        data_lancedb.append({
            "id_fuente": p["id_fuente"],
            "nombre": p["nombre"],
            "categoria": p["categoria"],
            "ingredientes": p["ingredientes"],
            "url": p["url"],
            "usa_insumo_directo": p["usa_insumo_directo"],
            "fecha_dato": p.get("fecha_dato"),
            "vector": embeddings[i].tolist()
        })

    print(f"Creando tabla en LanceDB...")
    tabla = db.create_table("productos", data=data_lancedb, mode="overwrite")

    print(f"Creando índice vectorial...")
    tabla.create_index(metric="cosine", num_partitions=4)

    print(f"\nIndexación completada!")
    print(f"  Tabla 'productos': {tabla.count_rows()} registros")
    print(f"  Dimensión de embeddings: {len(embeddings[0])}")
    print(f"  Métrica: cosine")

if __name__ == "__main__":
    main()
