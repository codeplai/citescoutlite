"""
TIER 7 · T7.3: E2E del snapshot S2.

Recorre el flujo completo tal como queda al cerrar la semana: datos en disco ->
índice vectorial -> búsqueda -> corpus regulatorio -> manifest verificable.

Requiere el pipeline de TIER 2-7 ejecutado. Se corre con pytest o directo:
    python test/test_e2e_s2.py
"""
import hashlib
import json
from pathlib import Path

import lancedb

from adaptadores.busqueda_lancedb import BusquedaLanceDB
from adaptadores.modelo_embeddings import DIMENSIONES
from casos_de_uso.etapas.buscar_productos import _detectar_uso_directo

DATASET = Path("datasets/2026-07")
MANIFEST = DATASET / "manifest.json"

MIN_PRODUCTOS = 250  # gate del plan; el snapshot real tiene ~29.000

INSUMOS = {
    "arándano": ["arándano", "arandano", "blueberry", "blueberries"],
    "palta": ["palta", "aguacate", "avocado", "avocados"],
    "espárrago": ["espárrago", "esparrago", "asparagus"],
    "mango": ["mango", "mangoes"],
    "quinua": ["quinua", "quinoa"],
}


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_e2e_datos_en_disco():
    """Los archivos del snapshot existen y tienen contenido."""
    for archivo in ["productos_merged.json", "ecfr_aditivos.json",
                    "digesa_normas.json", "manifest.json"]:
        ruta = DATASET / archivo
        assert ruta.exists(), f"Falta {archivo}"
        assert ruta.stat().st_size > 0, f"{archivo} vacío"

    productos = json.loads((DATASET / "productos_merged.json").read_text(encoding="utf-8"))
    assert len(productos) >= MIN_PRODUCTOS, f"Solo {len(productos)} productos"
    print(f"PASS: snapshot con {len(productos):,} productos")


def test_e2e_indice_vectorial():
    """La tabla `productos` está indexada y cubre todo el snapshot."""
    productos = json.loads((DATASET / "productos_merged.json").read_text(encoding="utf-8"))

    db = lancedb.connect("vectores")
    tabla = db.open_table("productos")

    assert tabla.count_rows() == len(productos), (
        f"Índice desincronizado: {tabla.count_rows()} filas indexadas frente a "
        f"{len(productos)} en productos_merged.json"
    )

    fila = tabla.head(1).to_pylist()[0]
    assert len(fila["embedding"]) == DIMENSIONES

    # Ambas fuentes deben estar representadas en el índice.
    assert tabla.count_rows(filter="fuente = 'OFF'") > 0, "Sin productos OFF"
    assert tabla.count_rows(filter="fuente = 'USDA'") > 0, "Sin productos USDA"

    print(f"PASS: {tabla.count_rows():,} filas indexadas "
          f"({DIMENSIONES}-dim), OFF + USDA presentes")


def test_e2e_busqueda_los_5_insumos():
    """Búsqueda de los 5 insumos con resultados trazables."""
    catalogo = BusquedaLanceDB()

    for insumo, sinonimos in INSUMOS.items():
        resultado = catalogo.buscar(sinonimos, k=30)
        productos = resultado.productos
        assert productos, f"Sin resultados para {insumo}"

        for p in productos:
            assert p.fecha_dato is not None, f"{p.id_fuente} sin fecha_dato"
            assert p.url, f"{p.id_fuente} sin url"
            assert p.id_fuente not in ("", "Unknown"), "id_fuente sin mapear"

        n_directos = sum(1 for p in productos
                         if _detectar_uso_directo(p.ingredientes, sinonimos))
        print(f"PASS: {insumo}: {len(productos)} resultados, "
              f"{n_directos} directos")


def test_e2e_corpus_regulatorio():
    """El corpus regulatorio de TIER 6 está indexado."""
    db = lancedb.connect("vectores")
    nombres = getattr(db.list_tables(), "tables", db.list_tables())
    assert "regulatorio" in nombres, "Falta la tabla regulatorio"

    tabla = db.open_table("regulatorio")
    assert tabla.count_rows() > 0
    print(f"PASS: corpus regulatorio con {tabla.count_rows()} pasajes")


def test_e2e_manifest_sha256_coincide():
    """
    El manifest no solo declara SHA256: se recalculan y deben coincidir.

    Un manifest con hashes obsoletos es peor que no tenerlos, porque da una
    garantía de reproducibilidad que no se cumple.
    """
    manifest = _manifest()
    assert manifest.get("fecha_descarga"), "Falta fecha_descarga"

    fuentes = manifest.get("fuentes", {})
    assert fuentes, "Manifest sin fuentes"

    for archivo, meta in fuentes.items():
        ruta = DATASET / archivo
        assert ruta.exists(), f"{archivo} declarado pero ausente"
        assert "sha256" in meta, f"{archivo} sin sha256"

        h = hashlib.sha256()
        with open(ruta, "rb") as f:
            for bloque in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloque)

        assert h.hexdigest() == meta["sha256"], (
            f"{archivo}: sha256 del manifest no coincide con el archivo. "
            f"Corre `python -m etl.finalizar_manifest`."
        )
        assert ruta.stat().st_size == meta["tamaño_bytes"], f"{archivo}: tamaño distinto"

    print(f"PASS: {len(fuentes)} fuentes con sha256 verificado")


def test_e2e_estadisticas_coinciden_con_los_datos():
    """
    Las estadísticas del manifest reflejan el snapshot real.

    Regresión: hasta TIER 6 el manifest declaraba 89 productos y
    `espárrago: 0` mientras el índice tenía 29.054.
    """
    manifest = _manifest()
    est = manifest.get("estadisticas", {})
    productos = json.loads((DATASET / "productos_merged.json").read_text(encoding="utf-8"))

    assert est.get("total_productos") == len(productos), (
        f"Manifest declara {est.get('total_productos')} productos, "
        f"el archivo tiene {len(productos)}"
    )
    assert est.get("productos_sin_fecha_dato") == 0, "Hay productos sin fecha_dato"
    assert est.get("productos_sin_url") == 0, "Hay productos sin url"

    for insumo, n in est.get("coverage_por_insumo", {}).items():
        assert n > 0, f"Cobertura 0 para {insumo}"

    print(f"PASS: manifest coherente ({est['total_productos']:,} productos, "
          f"cobertura > 0 en los 5 insumos)")


def test_e2e_golden_set_5_de_5():
    """El golden set de T7.1 pasa completo."""
    from evals.runner_s2 import main as runner

    assert runner() == 0, "El golden set no pasa 5/5"
    print("PASS: golden set 5/5")


if __name__ == "__main__":
    test_e2e_datos_en_disco()
    test_e2e_indice_vectorial()
    test_e2e_busqueda_los_5_insumos()
    test_e2e_corpus_regulatorio()
    test_e2e_manifest_sha256_coincide()
    test_e2e_estadisticas_coinciden_con_los_datos()
    test_e2e_golden_set_5_de_5()
    print("\nTIER 7: E2E workflow PASSED")
