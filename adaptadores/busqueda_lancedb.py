from puertos.catalogo_productos import CatalogoProductos
from dominio.resultado_busqueda import ResultadoBusqueda
from dominio.producto_existente import ProductoExistente
import datetime
import lancedb
import time

class BusquedaLanceDB(CatalogoProductos):
    def __init__(self, db_path: str = "vectores"):
        self.db_path = db_path
        self.model = None

    def _get_model(self):
        """Lazy load del modelo de embeddings."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer("BAAI/bge-m3")
        return self.model

    def buscar(self, sinonimos: list[str], k: int = 30) -> ResultadoBusqueda:
        try:
            db = lancedb.connect(self.db_path)
            if "productos" not in db.table_names():
                return ResultadoBusqueda(productos=[], n_directos=0)

            tabla = db.open_table("productos")

            query_text = " ".join(sinonimos)
            model = self._get_model()
            query_vector = model.encode(query_text).tolist()

            start_time = time.time()
            resultados = tabla.search(query_vector).limit(k).to_list()
            latencia_ms = (time.time() - start_time) * 1000

            productos_existentes = []
            n_directos = 0

            for res in resultados:
                fecha_str = res.get("fecha_dato")
                fecha_dato = None
                if fecha_str:
                    try:
                        if isinstance(fecha_str, int):
                            fecha_dato = datetime.datetime.fromtimestamp(fecha_str).date()
                        else:
                            fecha_dato = datetime.datetime.fromisoformat(fecha_str).date()
                    except (ValueError, TypeError):
                        fecha_dato = None

                p = ProductoExistente(
                    id_fuente=res.get("id_fuente", "Unknown"),
                    nombre=res.get("nombre", "Unknown"),
                    categoria=res.get("categoria", "Unknown"),
                    usa_insumo_directo=res.get("usa_insumo_directo", True),
                    fecha_dato=fecha_dato,
                    ingredientes=res.get("ingredientes", ""),
                    url=res.get("url", "")
                )

                productos_existentes.append(p)

                if res.get("usa_insumo_directo", True):
                    n_directos += 1

            if latencia_ms > 2000:
                print(f"[PERF] Búsqueda lenta: {latencia_ms:.0f}ms (p95 goal: <2000ms)")

            return ResultadoBusqueda(
                productos=productos_existentes,
                n_directos=n_directos
            )
        except Exception as e:
            print(f"Error en búsqueda LanceDB con embeddings: {e}")
            return ResultadoBusqueda(productos=[], n_directos=0)
