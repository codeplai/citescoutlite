"""
S8 - El conector al catalogo de las cadenas peruanas.

El nodo de `_NODO_REAL` es la respuesta literal de Metro para 'kiwicha',
recortada a los campos que el conector lee. Se conserva tal cual porque trae
justo el caso que mas importa: `AvailableQuantity` viene a 99.999, que no es
stock sino la cifra centinela de VTEX para "hay de sobra".

Nada de aqui sale a la red: las respuestas se sirven con un transporte de
prueba de httpx.
"""

import json

import httpx
import pytest

from adaptadores import catalogo_vtex
from adaptadores.catalogo_vtex import (CatalogoVTEX, _a_producto, _categoria_de,
                                       _es_departamento_excluido, _evidencia_de)
from casos_de_uso.agente.grounding_check import GroundingChecker

_NODO_REAL = {
    "productName": "Galletas Integrales con Kiwicha Unión 195g",
    "brand": "Unión",
    "categories": ["/Abarrotes/Galletas, Snacks y Golosinas/Galletas/",
                   "/Abarrotes/Galletas, Snacks y Golosinas/",
                   "/Abarrotes/"],
    "link": "https://www.metro.pe/galletas-integrales-con-kiwicha-uni-n-195g-57233006/p",
    "productReference": "57233006",
    "items": [{
        "nameComplete": "Galletas Integrales con Kiwicha Unión 195g",
        "ean": "7752056002936",
        "measurementUnit": "un",
        "unitMultiplier": 1.0,
        "sellers": [{"commertialOffer": {
            "Price": 6.5, "ListPrice": 6.5, "PriceWithoutDiscount": 6.5,
            "AvailableQuantity": 99999, "IsAvailable": True}}],
    }],
}


def _con_stock(cantidad):
    """El mismo nodo con otra cantidad disponible."""
    nodo = json.loads(json.dumps(_NODO_REAL))
    nodo["items"][0]["sellers"][0]["commertialOffer"]["AvailableQuantity"] = cantidad
    return nodo


# ---------------------------------------------------------------------------
# Mapeo del nodo a producto
# ---------------------------------------------------------------------------

def test_mapea_los_campos_del_catalogo():
    p = _a_producto(_NODO_REAL, "PEN")
    assert p.nombre == "Galletas Integrales con Kiwicha Unión 195g"
    assert p.precio == 6.5
    assert p.moneda == "PEN"
    assert p.marca == "Unión"
    assert p.ean == "7752056002936"
    assert p.unidad == "un"


def test_la_categoria_es_la_mas_especifica():
    """VTEX las da de la mas profunda a la mas general; vale la primera."""
    assert _categoria_de(_NODO_REAL["categories"]) == "Galletas"
    assert _categoria_de([]) is None
    assert _categoria_de(None) is None


def test_la_moneda_la_pone_la_tienda():
    """El API no la declara; es una propiedad de la cadena, no del nodo."""
    assert "priceCurrency" not in json.dumps(_NODO_REAL)
    assert _a_producto(_NODO_REAL, "PEN").moneda == "PEN"


# ---------------------------------------------------------------------------
# Stock: es el dato que le falta a la regla `stock_minimo` de S7
# ---------------------------------------------------------------------------

def test_stock_centinela_no_se_guarda_como_unidades():
    """99.999 no son bolsas de galletas: es el "hay de sobra" de VTEX.

    Guardarlo como stock haria que `stock_minimo` diera por bueno cualquier
    producto de estas cadenas, que es peor que no tener el dato.
    """
    assert _a_producto(_NODO_REAL, "PEN").stock is None


def test_stock_real_si_se_guarda():
    assert _a_producto(_con_stock(12), "PEN").stock == 12


def test_sin_existencias_no_es_un_stock_de_cero():
    """0 significa agotado, no "quedan cero unidades comprables"."""
    assert _a_producto(_con_stock(0), "PEN").stock is None


# ---------------------------------------------------------------------------
# Nodos que no dan una oferta utilizable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mutacion", [
    {"items": []},
    {"productName": None, "items": [{"sellers": [{"commertialOffer": {"Price": 6.5}}]}]},
])
def test_nodo_incompleto_se_descarta(mutacion):
    assert _a_producto({**_NODO_REAL, **mutacion}, "PEN") is None


def test_sin_vendedor_no_hay_precio():
    nodo = json.loads(json.dumps(_NODO_REAL))
    nodo["items"][0]["sellers"] = []
    assert _a_producto(nodo, "PEN") is None


def test_precio_cero_se_descarta():
    """Un 0 en VTEX es "no disponible para venta", no una ganga."""
    nodo = json.loads(json.dumps(_NODO_REAL))
    nodo["items"][0]["sellers"][0]["commertialOffer"]["Price"] = 0
    assert _a_producto(nodo, "PEN") is None


# ---------------------------------------------------------------------------
# Departamentos que no venden comida
# ---------------------------------------------------------------------------

def test_el_motorola_arandano_cae_por_su_categoria():
    """Plaza Vea vende un movil cuyo COLOR es arandano; por nombre casa.

    Lo unico que lo delata es donde vive.
    """
    assert _es_departamento_excluido(["/Tecnología/Telefonía/Smartphones/"])


def test_un_alimento_no_cae():
    assert not _es_departamento_excluido(_NODO_REAL["categories"])


def test_sin_categorias_no_se_descarta():
    """Ante la duda se deja pasar: lo resuelve quien revisa la cuarentena."""
    assert not _es_departamento_excluido(None)
    assert not _es_departamento_excluido([])


# ---------------------------------------------------------------------------
# Evidencia y grounding
# ---------------------------------------------------------------------------

def test_la_evidencia_respalda_el_precio_y_el_nombre():
    """La regresion que costo dos veces: el precio fuera del recorte.

    Vive en `items[].sellers[].commertialOffer`, detras de imagenes y
    especificaciones. Guardando el nodo recortado se quedaba fuera, y el
    grounding daba por inventado un precio que la tienda si publica.
    """
    item = _NODO_REAL["items"][0]
    oferta = item["sellers"][0]["commertialOffer"]
    evidencia = _evidencia_de(_NODO_REAL, item, oferta)

    producto = _a_producto(_NODO_REAL, "PEN")
    resultado = GroundingChecker().verificar(evidencia, producto.model_dump())
    assert resultado.passed
    assert resultado.errores == []


def test_la_evidencia_lleva_el_stock_aunque_no_se_guarde():
    """El centinela no va al producto, pero si a la evidencia.

    Quien revise la cuarentena tiene que poder ver que la cifra era 99.999 y
    por que no se convirtio en un stock.
    """
    item = _NODO_REAL["items"][0]
    evidencia = json.loads(
        _evidencia_de(_NODO_REAL, item, item["sellers"][0]["commertialOffer"]))
    assert evidencia["AvailableQuantity"] == 99999
    assert "consultado_en" in evidencia


# ---------------------------------------------------------------------------
# La consulta a las tiendas
# ---------------------------------------------------------------------------

def _servir(monkeypatch, por_host):
    """Sirve `por_host[host]` sin salir a la red."""
    def manejador(peticion: httpx.Request) -> httpx.Response:
        return por_host[peticion.url.host]

    transporte = httpx.MockTransport(manejador)
    original = httpx.AsyncClient
    monkeypatch.setattr(catalogo_vtex.httpx, "AsyncClient",
                        lambda **kw: original(transport=transporte, **kw))


_OK_206 = httpx.Response(206, json=[_NODO_REAL])
_TIENDAS = {"www.metro.pe": ("Metro", "PEN"), "www.wong.pe": ("Wong", "PEN")}


@pytest.mark.asyncio
async def test_206_es_una_respuesta_buena(monkeypatch):
    """VTEX pagina: lo normal es Partial Content, no 200."""
    _servir(monkeypatch, {"www.metro.pe": _OK_206})
    ofertas = await CatalogoVTEX(tiendas={"www.metro.pe": ("Metro", "PEN")}).buscar("kiwicha")
    assert len(ofertas) == 1
    assert ofertas[0].tienda == "Metro"
    assert ofertas[0].fuente_url == _NODO_REAL["link"]


@pytest.mark.asyncio
async def test_una_tienda_caida_no_arrastra_a_las_demas(monkeypatch):
    """Son fuentes independientes; quedarse sin Metro porque Wong dio un 500
    seria perder datos por nada."""
    _servir(monkeypatch, {"www.metro.pe": _OK_206,
                          "www.wong.pe": httpx.Response(500, text="boom")})
    ofertas = await CatalogoVTEX(tiendas=_TIENDAS).buscar("kiwicha")
    assert [o.tienda for o in ofertas] == ["Metro"]


@pytest.mark.asyncio
async def test_una_tienda_que_ni_responde_tampoco(monkeypatch):
    def manejador(peticion):
        if peticion.url.host == "www.wong.pe":
            raise httpx.ConnectTimeout("sin respuesta")
        return _OK_206

    original = httpx.AsyncClient
    monkeypatch.setattr(catalogo_vtex.httpx, "AsyncClient",
                        lambda **kw: original(transport=httpx.MockTransport(manejador), **kw))
    ofertas = await CatalogoVTEX(tiendas=_TIENDAS).buscar("kiwicha")
    assert [o.tienda for o in ofertas] == ["Metro"]


@pytest.mark.asyncio
async def test_html_en_vez_de_json_no_revienta(monkeypatch):
    """Si la ruta cambia y devuelve la tienda, no se intenta leer como JSON."""
    _servir(monkeypatch, {"www.metro.pe": httpx.Response(
        200, text="<html>portada</html>", headers={"content-type": "text/html"})})
    assert await CatalogoVTEX(tiendas={"www.metro.pe": ("Metro", "PEN")}).buscar("x") == []


@pytest.mark.asyncio
async def test_lo_que_no_es_el_insumo_se_descarta(monkeypatch):
    """El buscador de VTEX es generoso: para 'arandano' devolvio un movil."""
    movil = {**_NODO_REAL,
             "productName": 'Smartphone MOTOROLA G17 6.8" 4GB 128GB Arándano',
             "categories": ["/Tecnología/Telefonía/"]}
    _servir(monkeypatch, {"www.metro.pe": httpx.Response(206, json=[movil])})
    assert await CatalogoVTEX(tiendas={"www.metro.pe": ("Metro", "PEN")}).buscar("arandano") == []


@pytest.mark.asyncio
async def test_sin_insumo_no_se_consulta_nada(monkeypatch):
    def manejador(peticion):
        raise AssertionError("no deberia salir ninguna peticion")

    original = httpx.AsyncClient
    monkeypatch.setattr(catalogo_vtex.httpx, "AsyncClient",
                        lambda **kw: original(transport=httpx.MockTransport(manejador), **kw))
    assert await CatalogoVTEX().buscar("") == []
