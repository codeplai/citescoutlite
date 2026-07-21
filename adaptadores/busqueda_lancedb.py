from puertos.catalogo_productos import CatalogoProductos
from dominio.resultado_busqueda import ResultadoBusqueda
from dominio.producto_existente import ProductoExistente
import datetime
import lancedb

class BusquedaLanceDB(CatalogoProductos):
    def __init__(self, db_path: str = "vectores"):
        self.db_path = db_path
        
    def buscar(self, sinonimos: list[str], k: int = 30) -> ResultadoBusqueda:
        try:
            db = lancedb.connect(self.db_path)
            if "productos" not in db.table_names():
                return ResultadoBusqueda(productos=[], n_directos=0)
                
            tabla = db.open_table("productos")
            
            # Usar FTS (Full Text Search) combinando sinonimos
            query = " ".join(sinonimos)
            
            resultados = tabla.search(query, query_type="fts").limit(k).to_list()
            
            productos_existentes = []
            n_directos = 0
            
            for res in resultados:
                p = ProductoExistente(
                    id_fuente=res.get("id_fuente", "Unknown"),
                    nombre=res.get("nombre", "Unknown"),
                    categoria=res.get("categoria", "Unknown"),
                    usa_insumo_directo=res.get("usa_insumo_directo", True),
                    fecha_dato=datetime.date.today(),
                    ingredientes=res.get("ingredientes", ""),
                    url=res.get("url", "")
                )
                
                productos_existentes.append(p)
                
                if res.get("usa_insumo_directo", True):
                    n_directos += 1
                    
            return ResultadoBusqueda(
                productos=productos_existentes,
                n_directos=n_directos
            )
        except Exception as e:
            print(f"Error en búsqueda LanceDB FTS: {e}")
            return ResultadoBusqueda(productos=[], n_directos=0)
