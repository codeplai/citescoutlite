"""
TIER 5 (S2): Gate P03 — búsqueda vectorial p95 < 2 s, sin datos inventados.

Requiere el índice de TIER 4 (vectores/productos.lance, 28.236 filas bge-m3).
Se ejecuta con pytest o directamente: python test/test_latency.py
"""
from adaptadores.busqueda_lancedb import BusquedaLanceDB, medir_latencia_p95

UMBRAL_P95_MS = 2000

INSUMOS_PILOTO = {
    "arándano": ["arándano", "blueberry"],
    "palta": ["palta", "aguacate", "avocado"],
    "espárrago": ["espárrago", "asparagus"],
    "mango": ["mango"],
    "quinua": ["quinua", "quinoa"],
}

FUENTES_REALES = ("OFF", "USDA")


def test_p95_latencia_bajo_2s():
    """P03: p95 < 2 s sobre 100 queries (excluye carga del modelo)."""
    metricas = medir_latencia_p95(num_samples=100)
    assert metricas["p95_ms"] < UMBRAL_P95_MS, (
        f"p95 {metricas['p95_ms']:.1f}ms excede el SLA de {UMBRAL_P95_MS}ms"
    )
    print(f"PASS: p95 {metricas['p95_ms']:.1f}ms < {UMBRAL_P95_MS}ms")


def test_resultados_trazables_y_sin_demo():
    """P03/P04: cero valores inventados; cada producto con id, url y fecha reales."""
    catalogo = BusquedaLanceDB()
    resultado = catalogo.buscar(INSUMOS_PILOTO["arándano"], k=10)

    assert len(resultado.productos) >= 3, (
        f"Solo {len(resultado.productos)} resultados para arándano"
    )

    for p in resultado.productos:
        fuente = p.id_fuente.split(":")[0]
        # Regresión: la columna en LanceDB es `id`, no `id_fuente`. Si se vuelve
        # a leer la clave equivocada, todos los ids caen a "Unknown".
        assert p.id_fuente != "Unknown", "id_fuente sin mapear desde LanceDB"
        assert fuente != "DEMO", f"Dato DEMO en resultados: {p.id_fuente}"
        assert fuente in FUENTES_REALES, f"Fuente inesperada: {fuente}"
        assert p.fecha_dato is not None, f"fecha_dato nula en {p.id_fuente}"
        assert p.url, f"url vacía en {p.id_fuente}"
        assert p.similitud is not None, f"similitud ausente en {p.id_fuente}"

    print(f"PASS: {len(resultado.productos)} productos trazables, sin DEMO")


def test_cobertura_5_insumos_piloto():
    """P03: los 5 insumos piloto devuelven resultados."""
    catalogo = BusquedaLanceDB()

    for insumo, sinonimos in INSUMOS_PILOTO.items():
        resultado = catalogo.buscar(sinonimos, k=5)
        assert len(resultado.productos) > 0, f"Sin resultados para '{insumo}'"
        print(f"PASS: {insumo}: {len(resultado.productos)} resultados "
              f"(top sim={resultado.productos[0].similitud})")


if __name__ == "__main__":
    test_p95_latencia_bajo_2s()
    test_resultados_trazables_y_sin_demo()
    test_cobertura_5_insumos_piloto()
    print("\nTIER 5: todos los tests PASSED (gate P03 verde)")
