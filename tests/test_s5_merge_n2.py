"""
S5.5 - Merge de N2: del catálogo de Bright Data a filas del mapa comercial.

`descubrir_n2` esperaba los webhooks, veía llegar los datos y devolvía lista
vacía con un TODO. El parseo del JSON no faltaba —lo hace el webhook, que
además deduplica— lo que faltaba era recoger lo guardado y darle forma de
ProductoEnMercado.
"""

import os
import tempfile
from datetime import datetime

import pytest

from adaptadores.catalogo_dedup import CatalogoDedup
from dominio.mapa_comercial import MapaComercial
from dominio.producto_catalogo import FieldWithSource, ProductoCatalogo


@pytest.fixture
def catalogo(monkeypatch):
    """Catálogo en un SQLite temporal, no en el agroscout.db versionado."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "test.db")
        monkeypatch.setenv("AGROSCOUT_DB_PATH", ruta)
        yield CatalogoDedup(ruta)


def _producto(ean="7501234567890", tienda="amazon", url="https://tienda.example/p/1",
              precio="24.90", insumo="quinua", transporte="N2_BRIGHT_DATA"):
    return ProductoCatalogo(
        ean=ean,
        sku=f"SKU-{ean}",
        nombre="Quinua Organica 500g",
        marca=FieldWithSource(valor="Andes Gold", source=transporte),
        precio=FieldWithSource(valor=precio, source=transporte) if precio else None,
        tienda_id=tienda,
        transporte=transporte,
        url=url,
        insumo_query=insumo,
    )


def test_get_by_insumo_filtra_por_transporte(catalogo):
    """La lectura de N2 no debe arrastrar lo que dejaron N1 o Scrapling."""
    catalogo.save_or_merge(_producto(ean="111", transporte="N2_BRIGHT_DATA"))
    catalogo.save_or_merge(_producto(ean="222", transporte="N1_SCRAPLING"))

    solo_n2 = catalogo.get_by_insumo("quinua", transporte="N2_BRIGHT_DATA")
    todos = catalogo.get_by_insumo("quinua")

    assert [p.ean for p in solo_n2] == ["111"]
    assert len(todos) == 2


def test_get_by_insumo_no_mezcla_insumos(catalogo):
    catalogo.save_or_merge(_producto(ean="111", insumo="quinua"))
    catalogo.save_or_merge(_producto(ean="222", insumo="cacao"))

    assert [p.ean for p in catalogo.get_by_insumo("cacao")] == ["222"]


def test_convierte_a_filas_del_mapa(catalogo, monkeypatch):
    from adaptadores.descubrimiento_cascada import DescubrimientoCascada

    catalogo.save_or_merge(_producto(ean="7501234567890", tienda="costco"))
    cascada = DescubrimientoCascada()
    cascada.catalogo_dedup = catalogo

    productos = cascada._recoger_n2_del_catalogo("quinua")

    assert len(productos) == 1
    p = productos[0]
    assert p.fuente == "BRIGHT_DATA"
    assert p.producto_id == "BD:costco:7501234567890"
    assert p.nombre == "Quinua Organica 500g"
    assert p.marca == "Andes Gold"
    # El precio de gondola: el hueco que el MVP declaraba y que N2 llena.
    assert p.precio_rango == "24.90"


def test_descarta_filas_sin_url_y_las_cuenta(catalogo):
    """url es obligatoria en el mapa; una fila sin ella no puede publicarse."""
    from adaptadores.descubrimiento_cascada import DescubrimientoCascada

    catalogo.save_or_merge(_producto(ean="111", url="https://ok.example/p"))
    catalogo.save_or_merge(_producto(ean="222", url=""))
    cascada = DescubrimientoCascada()
    cascada.catalogo_dedup = catalogo

    productos = cascada._recoger_n2_del_catalogo("quinua")

    assert len(productos) == 1
    assert cascada.descartadas["n2_url_invalida"] == 1


def test_sin_datos_de_n2_devuelve_vacio(catalogo):
    from adaptadores.descubrimiento_cascada import DescubrimientoCascada

    cascada = DescubrimientoCascada()
    cascada.catalogo_dedup = catalogo

    assert cascada._recoger_n2_del_catalogo("quinua") == []


def test_el_resumen_cuenta_los_precios_que_si_hay(catalogo):
    """sin_dato.precio estaba fijado al total; con N2 hay filas con precio."""
    from adaptadores.descubrimiento_cascada import DescubrimientoCascada

    catalogo.save_or_merge(_producto(ean="111", precio="24.90"))
    catalogo.save_or_merge(_producto(ean="222", precio=None))
    cascada = DescubrimientoCascada()
    cascada.catalogo_dedup = catalogo

    mapa = MapaComercial(insumo="quinua",
                         productos=cascada._recoger_n2_del_catalogo("quinua"))
    resumen = mapa.resumen_para_llm()

    assert resumen["total_productos"] == 2
    assert resumen["sin_dato"]["precio"] == 1
    # Presentacion y canal siguen sin cubrirse por ninguna fuente.
    assert resumen["sin_dato"]["presentacion"] == 2
