"""
TIER 5 (S2): Búsqueda vectorial real sobre LanceDB + bge-m3.

Reemplaza la búsqueda FTS de S1. El índice lo genera etl/tier4_gpu.py:
tabla `productos` en vectores/, columna `embedding` (1024-dim), índice IvfPq
con métrica COSINE.

Gate P03: p95 < 2 s sobre 100+ queries (ver test/test_latency.py).
"""
from puertos.catalogo_productos import CatalogoProductos
from dominio.resultado_busqueda import ResultadoBusqueda
from dominio.producto_existente import ProductoExistente
from adaptadores.modelo_embeddings import get_modelo
import datetime
import lancedb
import time

# Columnas que necesita el dominio. Excluye `embedding` a propósito: traer 1024
# floats por fila multiplica el payload sin que nadie aguas abajo lo use.
_COLUMNAS = ["id", "nombre", "categoria", "ingredientes", "url",
             "fecha_dato", "marca", "pais", "fuente"]

# Singleton de proceso: abrir la tabla no es gratis y, junto con el modelo
# compartido, es lo que hace alcanzable el gate p95 < 2 s.
_tabla = None
_tabla_filtrar_demo = None


def _get_tabla(db_path: str):
    """Abre la tabla `productos` una sola vez por proceso."""
    global _tabla, _tabla_filtrar_demo
    if _tabla is None:
        db = lancedb.connect(db_path)
        # lancedb 0.36 devuelve un objeto paginado, no una lista.
        listado = db.list_tables()
        nombres = getattr(listado, "tables", listado)
        if "productos" not in nombres:
            return None
        _tabla = db.open_table("productos")
        # Se evalúa una vez. Solo filtramos si hay DEMO que excluir y además
        # queda algo real; si todo fuera DEMO, filtrar devolvería cero.
        n_demo = _tabla.count_rows(filter="fuente = 'DEMO'")
        _tabla_filtrar_demo = 0 < n_demo < _tabla.count_rows()
    return _tabla


def _reset_cache():
    """Invalida el singleton de tabla. Solo para tests que reindexan."""
    global _tabla, _tabla_filtrar_demo
    _tabla = None
    _tabla_filtrar_demo = None


def _a_fecha(valor) -> datetime.date | None:
    """Convierte fecha_dato (timestamp Unix int64) a date. Nunca inventa."""
    if not valor:
        return None
    try:
        if isinstance(valor, (int, float)):
            return datetime.datetime.fromtimestamp(valor).date()
        return datetime.datetime.fromisoformat(str(valor)).date()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


class BusquedaLanceDB(CatalogoProductos):
    def __init__(self, db_path: str = "vectores", excluir_demo: bool = True):
        self.db_path = db_path
        self.excluir_demo = excluir_demo

    def buscar(self, sinonimos: list[str], k: int = 30) -> ResultadoBusqueda:
        try:
            tabla = _get_tabla(self.db_path)
            if tabla is None:
                return ResultadoBusqueda(productos=[], n_directos=0)

            query_text = " ".join(sinonimos)
            # Los vectores indexados no están normalizados, pero la distancia
            # coseno es invariante a la escala, así que no hace falta normalizar.
            query_vector = get_modelo().encode(query_text).tolist()

            start_time = time.time()
            consulta = (
                tabla.search(query_vector, vector_column_name="embedding")
                .metric("cosine")
                .select(_COLUMNAS)
            )
            # Solo filtramos DEMO si el snapshot mezcla fuentes reales y demo.
            if self.excluir_demo and _tabla_filtrar_demo:
                consulta = consulta.where("fuente != 'DEMO'", prefilter=True)

            resultados = consulta.limit(k).to_list()
            latencia_ms = (time.time() - start_time) * 1000

            productos_existentes = []
            for res in resultados:
                distancia = res.get("_distance")
                productos_existentes.append(ProductoExistente(
                    # La columna es `id`; `id_fuente` queda como fallback por si
                    # se reindexa con el esquema del dominio.
                    id_fuente=res.get("id") or res.get("id_fuente") or "Unknown",
                    nombre=res.get("nombre", "Unknown"),
                    categoria=res.get("categoria", "") or "Unknown",
                    # El snapshot no derivó este campo (queda en False para todas
                    # las filas); buscar_productos.py lo recalcula contra los
                    # sinónimos reales. Default conservador: False, no True.
                    usa_insumo_directo=res.get("usa_insumo_directo", False),
                    fecha_dato=_a_fecha(res.get("fecha_dato")),
                    ingredientes=res.get("ingredientes", "") or "",
                    url=res.get("url", "") or "",
                    similitud=round(1 - distancia, 4) if distancia is not None else None,
                ))

            if latencia_ms > 2000:
                print(f"[PERF] Búsqueda lenta: {latencia_ms:.0f}ms (gate P03: <2000ms)")

            # n_directos lo recalcula casos_de_uso/etapas/buscar_productos.py
            # contra los sinónimos; aquí no hay con qué derivarlo honestamente.
            return ResultadoBusqueda(productos=productos_existentes, n_directos=0)
        except Exception as e:
            print(f"Error en búsqueda LanceDB con embeddings: {e}")
            return ResultadoBusqueda(productos=[], n_directos=0)


def medir_latencia_p95(num_samples: int = 100, k: int = 30,
                       db_path: str = "vectores") -> dict:
    """
    Mide la latencia de búsqueda end-to-end (encode + ANN) para el gate P03.

    Excluye la carga del modelo y la apertura de la tabla vía warm-up: eso ocurre
    una vez al arrancar el proceso, no por consulta.
    """
    import statistics

    queries = [
        ["arándano", "blueberry"],
        ["palta", "aguacate", "avocado"],
        ["espárrago", "asparagus"],
        ["mango"],
        ["quinua", "quinoa"],
    ]
    catalogo = BusquedaLanceDB(db_path=db_path)

    catalogo.buscar(queries[0], k=k)  # warm-up

    latencias = []
    for i in range(num_samples):
        t0 = time.perf_counter()
        catalogo.buscar(queries[i % len(queries)], k=k)
        latencias.append((time.perf_counter() - t0) * 1000)

    latencias_ord = sorted(latencias)
    metricas = {
        "n": num_samples,
        "media_ms": statistics.mean(latencias),
        "p50_ms": latencias_ord[int(0.50 * (num_samples - 1))],
        "p95_ms": latencias_ord[int(0.95 * (num_samples - 1))],
        "p99_ms": latencias_ord[int(0.99 * (num_samples - 1))],
        "min_ms": latencias_ord[0],
        "max_ms": latencias_ord[-1],
    }

    print(f"[LATENCY] n={metricas['n']} | media {metricas['media_ms']:.1f}ms | "
          f"p50 {metricas['p50_ms']:.1f}ms | p95 {metricas['p95_ms']:.1f}ms | "
          f"p99 {metricas['p99_ms']:.1f}ms")
    print(f"[LATENCY] min {metricas['min_ms']:.1f}ms | max {metricas['max_ms']:.1f}ms")
    print(f"[LATENCY] Gate P03 (p95 < 2000ms): "
          f"{'PASA' if metricas['p95_ms'] < 2000 else 'FALLA'}")

    return metricas


if __name__ == "__main__":
    medir_latencia_p95()
