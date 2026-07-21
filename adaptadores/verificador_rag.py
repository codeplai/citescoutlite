import lancedb
from puertos.verificador_regulatorio import VerificadorRegulatorio

class VerificadorRAG(VerificadorRegulatorio):
    def __init__(self, db_path: str = "vectores"):
        self.db_path = db_path
        
    def verificar(self, insumo_en: str, insumo_es: str) -> str:
        try:
            db = lancedb.connect(self.db_path)
            if "normativas" not in db.table_names():
                return "RAG Normativo: Base documental no inicializada."
                
            tabla = db.open_table("normativas")
            
            # Usar FTS (Full Text Search) con la version en español
            resultados = tabla.search(insumo_es, query_type="fts").limit(2).to_list()
            
            if not resultados:
                return f"RAG Normativo: No se encontraron normas locales específicas para '{insumo_es}'."
                
            normas = []
            for res in resultados:
                fuente = res.get("fuente", "Desconocida")
                titulo = res.get("titulo", "")
                texto = res.get("texto", "")
                normas.append(f"- {fuente} ({titulo}): {texto}")
                
            return "RAG Normativo (Codex/DIGESA/EFSA):\n" + "\n".join(normas)
            
        except Exception as e:
            print(f"Error en RAG normativo FTS: {e}")
            return f"RAG Normativo: Error de búsqueda ({e})."
