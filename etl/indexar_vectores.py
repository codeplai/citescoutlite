import json
import os
import lancedb

def main():
    print("Iniciando indexación (FTS) en LanceDB...")
    
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
        
    print(f"Indexando {len(productos)} productos...")
    
    db = lancedb.connect("vectores")
    
    data_lancedb = []
    for p in productos:
        texto = f"{p['nombre']} {p['categoria']} {p['ingredientes']}"
        data_lancedb.append({
            "id_fuente": p["id_fuente"],
            "nombre": p["nombre"],
            "categoria": p["categoria"],
            "ingredientes": p["ingredientes"],
            "url": p["url"],
            "usa_insumo_directo": p["usa_insumo_directo"],
            "fecha_dato": p.get("fecha_dato"),
            "texto_busqueda": texto
        })
        
    # Crear o sobreescribir la tabla
    tabla = db.create_table("productos", data=data_lancedb, mode="overwrite")
    
    # Crear índice Full Text Search (FTS) en la columna 'texto_busqueda'
    tabla.create_fts_index("texto_busqueda")
    
    print(f"Indexación completada. Tabla 'productos' contiene {tabla.count_rows()} registros.")

if __name__ == "__main__":
    main()
