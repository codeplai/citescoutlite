import json
import os
import lancedb

def indexar_normativas():
    print("Iniciando indexación (FTS) de normativas locales en LanceDB...")
    
    normativas = []
    
    filepath = "data/normativas_codex.json"
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            normativas = json.load(f)
            
    if not normativas:
        print("No hay normativas para indexar.")
        return
        
    print(f"Indexando {len(normativas)} normas...")
    
    db = lancedb.connect("vectores")
    
    data_lancedb = []
    for i, n in enumerate(normativas):
        texto_busqueda = f"{n['fuente']} {n['titulo']} {n['texto']}"
        data_lancedb.append({
            "id": i,
            "fuente": n["fuente"],
            "titulo": n["titulo"],
            "texto": n["texto"],
            "texto_busqueda": texto_busqueda
        })
        
    tabla = db.create_table("normativas", data=data_lancedb, mode="overwrite")
    tabla.create_fts_index("texto_busqueda")
    
    print(f"Indexación completada. Tabla 'normativas' contiene {tabla.count_rows()} registros.")

if __name__ == "__main__":
    indexar_normativas()
