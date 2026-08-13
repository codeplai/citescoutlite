"""
S8 - Lo que decide que entra en la cuarentena.

Son las tres piezas nuevas del camino de N3, y las tres son puras: no tocan red
ni base de datos. Cada caso de aqui salio de una pagina real, no de una
suposicion sobre como deberian venir los datos.
"""

import json

import pytest

from casos_de_uso.agente.agente import corresponde_al_insumo
from casos_de_uso.agente.datos_estructurados import (a_decimal,
                                                     extraer_productos)
from casos_de_uso.agente.grounding_check import GroundingChecker


def _script(payload: dict | list) -> str:
    return (f'<html><head><script type="application/ld+json">'
            f'{json.dumps(payload)}</script></head><body>x</body></html>')


# ---------------------------------------------------------------------------
# JSON-LD: las formas que usa cada plataforma
# ---------------------------------------------------------------------------

def test_producto_plano():
    """La forma canonica: Product con offers.price. Es la de Falabella."""
    html = _script({"@type": "Product", "name": "Quinua Tottus 1 Kg",
                    "offers": {"@type": "Offer", "price": "15.2",
                               "priceCurrency": "PEN"}})
    ofertas = extraer_productos(html)
    assert len(ofertas) == 1
    assert ofertas[0].producto.nombre == "Quinua Tottus 1 Kg"
    assert ofertas[0].producto.precio == 15.2
    assert ofertas[0].producto.moneda == "PEN"


def test_producto_dentro_de_graph():
    """WooCommerce y Yoast meten todo en @graph.

    Sin recorrer esa clave, media web quedaba como 'sin Product': fue lo que
    paso con vega.pe y ecoandino en el primer sondeo.
    """
    html = _script({"@context": "https://schema.org", "@graph": [
        {"@type": "Organization", "name": "Tienda"},
        {"@type": "Product", "name": "Quinua en grano",
         "offers": {"price": "4.50", "priceCurrency": "PEN"}},
    ]})
    ofertas = extraer_productos(html)
    assert [o.producto.nombre for o in ofertas] == ["Quinua en grano"]
    assert ofertas[0].producto.precio == 4.5


def test_precio_en_price_specification():
    """VTEX (Metro, Wong) no pone `price` sino priceSpecification."""
    html = _script({"@type": "Product", "name": "Arandano 500 g",
                    "offers": {"@type": "AggregateOffer",
                               "priceCurrency": "PEN",
                               "priceSpecification": {"@type": "UnitPriceSpecification",
                                                      "price": 14.99}}})
    ofertas = extraer_productos(html)
    assert ofertas[0].producto.precio == 14.99


def test_low_price_de_una_agregada():
    html = _script({"@type": "Product", "name": "Cacao",
                    "offers": {"@type": "AggregateOffer", "lowPrice": 20,
                               "priceCurrency": "PEN"}})
    assert extraer_productos(html)[0].producto.precio == 20.0


def test_pagina_de_categoria_da_varias():
    """Vega devuelve tres quinuas distintas en una sola URL."""
    html = _script([
        {"@type": "Product", "name": "Quinua VEGA 400g",
         "offers": {"price": 6, "priceCurrency": "PEN"}},
        {"@type": "Product", "name": "Quinua TIMONEL 500g",
         "offers": {"price": 7.5, "priceCurrency": "PEN"}},
    ])
    assert len(extraer_productos(html)) == 2


def test_no_duplica_la_misma_ficha():
    """El tema y el plugin de SEO publican el mismo producto dos veces."""
    ficha = {"@type": "Product", "name": "Quinua",
             "offers": {"price": 4.5, "priceCurrency": "PEN"}}
    html = _script([ficha, dict(ficha)])
    assert len(extraer_productos(html)) == 1


def test_sin_precio_no_es_oferta():
    html = _script({"@type": "Product", "name": "Quinua sin precio"})
    assert extraer_productos(html) == []


def test_sin_precio_si_entra_cuando_no_se_exige():
    """Las gondolas del informe piden lo contrario que la cuarentena: una fila
    con «sin dato» en el precio sigue diciendo que ese producto se vende en esa
    tienda, y eso es mas que no enseñar nada."""
    html = _script({"@type": "Product", "name": "Bio Quinoa 500g",
                    "gtin13": "7610000000001"})
    ofertas = extraer_productos(html, exigir_precio=False)

    assert [o.producto.nombre for o in ofertas] == ["Bio Quinoa 500g"]
    assert ofertas[0].producto.precio is None
    # Lo demas de la ficha se conserva: sin precio no es sin datos.
    assert ofertas[0].producto.ean == "7610000000001"


def test_sin_nombre_no_entra_nunca():
    """El nombre es lo unico que identifica la fila; sin el no hay oferta ni
    aunque se afloje el precio."""
    html = _script({"@type": "Product", "offers": {"price": 4.5,
                                                   "priceCurrency": "PEN"}})
    assert extraer_productos(html, exigir_precio=False) == []


# ---------------------------------------------------------------------------
# El codigo de barras
#
# Se leia y se tiraba: el nodo traia `gtin13` y `ean` salia siempre a None por
# la via de JSON-LD. Era la perdida mas cara del extractor, porque el EAN es lo
# unico que identifica el MISMO producto en dos tiendas —el nombre cambia de
# una a otra— y sin el la tabla de gondola es una lista, no una comparacion.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("clave", ["gtin13", "gtin14", "gtin12", "gtin8", "gtin"])
def test_el_gtin_llega_al_ean(clave):
    """schema.org tiene una clave por longitud de codigo; todas son el mismo
    dato para lo que aqui interesa."""
    html = _script({"@type": "Product", "name": "Quinoa 500g", clave: "4001234567890",
                    "offers": {"price": 4.99, "priceCurrency": "EUR"}})
    assert extraer_productos(html)[0].producto.ean == "4001234567890"


def test_el_gtin_de_la_oferta_tambien_vale():
    """Shopify y algunos temas de WooCommerce lo declaran dentro de la Offer."""
    html = _script({"@type": "Product", "name": "Quinoa 500g",
                    "offers": {"price": 5.5, "priceCurrency": "CHF",
                               "gtin13": "7610000000001"}})
    assert extraer_productos(html)[0].producto.ean == "7610000000001"


def test_manda_el_mas_especifico_cuando_hay_varios():
    html = _script({"@type": "Product", "name": "Quinoa", "gtin13": "4001234567890",
                    "gtin8": "12345670",
                    "offers": {"price": 4.99, "priceCurrency": "EUR"}})
    assert extraer_productos(html)[0].producto.ean == "4001234567890"


@pytest.mark.parametrize("valor", ["", "N/A", "0", "sin código", 4001234567890.0, None])
def test_lo_que_no_parece_un_codigo_de_barras_se_descarta(valor):
    """Sin EAN la fila sale igual; solo no se empareja con nada.

    Guardarlo tal cual seria peor: la tabla marca como «el mismo producto en
    otra tienda» las filas que comparten EAN, y un valor basura repetido —un
    '0', un 'N/A'— emparejaria productos distintos y la comparacion, que es el
    entregable, diria algo falso. El float esta en la lista porque un gtin
    numerico en JSON no cabe exacto en un double y str() lo dejaria en
    '4001234567890.0'.
    """
    html = _script({"@type": "Product", "name": "Quinoa", "gtin13": valor,
                    "offers": {"price": 4.99, "priceCurrency": "EUR"}})
    assert extraer_productos(html)[0].producto.ean is None


def test_un_gtin_con_separadores_se_limpia():
    """Alguna ficha lo publica con guiones."""
    html = _script({"@type": "Product", "name": "Quinoa", "gtin13": "400-1234-567890",
                    "offers": {"price": 4.99, "priceCurrency": "EUR"}})
    assert extraer_productos(html)[0].producto.ean == "4001234567890"


def test_sin_gtin_el_ean_queda_vacio():
    html = _script({"@type": "Product", "name": "Quinua",
                    "offers": {"price": 4.5, "priceCurrency": "PEN"}})
    assert extraer_productos(html)[0].producto.ean is None


def test_json_roto_no_revienta():
    """Una pagina con JSON-LD malformado es normal; no puede tumbar el barrido."""
    html = ('<script type="application/ld+json">{"@type": "Product",</script>'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Cacao","offers":{"price":20,'
            '"priceCurrency":"PEN"}}</script>')
    assert [o.producto.nombre for o in extraer_productos(html)] == ["Cacao"]


def test_sin_html_devuelve_vacio():
    assert extraer_productos("") == []
    assert extraer_productos("<html><body>nada</body></html>") == []


def test_la_evidencia_contiene_el_valor():
    """La evidencia es el nodo, no un recorte del principio del HTML.

    En Vega el JSON-LD empieza en el caracter 202.210: con un prefijo de 6.000
    el grounding no habria tenido nada contra lo que verificar.
    """
    relleno = "<p>relleno</p>" * 2000
    ficha = json.dumps({"@type": "Product", "name": "Quinua",
                        "offers": {"price": 4.5, "priceCurrency": "PEN"}})
    html = (f'<html><body>{relleno}'
            f'<script type="application/ld+json">{ficha}</script>'
            f'</body></html>')
    assert html.index("application/ld+json") > 6000, "el relleno no basta"

    oferta = extraer_productos(html)[0]
    assert "4.5" in oferta.evidencia
    assert "Quinua" in oferta.evidencia


@pytest.mark.parametrize("crudo,esperado", [
    ("15.2", 15.2),
    (15.2, 15.2),
    (20, 20.0),
    ("S/ 24.90", 24.9),
    ("1.234,50", 1234.5),     # separador europeo
    ("1,234.50", 1234.5),     # separador anglosajon
    ("7,50", 7.5),            # coma decimal
    ("", None),
    (None, None),
    ("gratis", None),
])
def test_lectura_de_precio(crudo, esperado):
    assert a_decimal(crudo) == esperado


# ---------------------------------------------------------------------------
# Relevancia: una pagina de categoria publica TODO su catalogo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre,insumo,esperado", [
    ("Arandanos rojos deshidratado - 1 kg", "arandano", True),
    ("Arándano Blueberry 500 g", "arandano", True),   # con tilde
    ("MACA ANDINA EN POLVO", "maca", True),           # en mayusculas
    ("Café orgánico tostado", "cafe", True),
    # Los tres que se colaron de una tienda colombiana buscando 'maca'.
    ("HARINA DE ARROZ INTEGRAL", "maca", False),
    ("HARINA DE LENTEJA", "maca", False),
    ("HARINA DE SOYA PROTEICA", "maca", False),
    ("Pack Premium CATA- Caja Negra", "cafe", False),
    ("", "maca", False),
    ("Maca", "", False),
    # El aleman compone palabras, y el termino queda pegado DETRAS. Estos tres
    # se descartaban estando bien extraidos, con su precio, y el log decia
    # "no es Quinoa" de productos que eran exactamente eso.
    ("Bio-Weissquinoa - 500 g - Rapunzel", "Quinoa", True),
    ("Bioquinoa Tricolore 500g", "Quinoa", True),
    ("Waldheidelbeeren 200g", "Heidelbeeren", True),
    # Y el compuesto por delante seguia funcionando, que es el caso frecuente.
    ("Quinoamehl 1kg", "Quinoa", True),
    # Aflojar por el final no puede colar lo que no es: el termino tiene que
    # cerrar palabra, no aparecer en medio de cualquier sitio.
    ("Harina de trigo", "Quinoa", False),
])
def test_corresponde_al_insumo(nombre, insumo, esperado):
    assert corresponde_al_insumo(nombre, insumo) is esperado


# ---------------------------------------------------------------------------
# Grounding: comparar numeros por valor, no por como estan escritos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("extraido,en_pagina", [
    (6.0, '"price": 6'),          # el caso de Vega
    (24.9, "S/ 24.90"),
    (15.2, '"price": "15.2"'),
    (1234.5, "1,234.50"),
])
def test_grounding_acepta_el_mismo_numero_escrito_distinto(extraido, en_pagina):
    """Comparaba como texto y daba por inventado un precio que si estaba.

    Cada falso negativo de estos es una oferta buena que la regla
    `grounding_ok` de S7 —que esta activa— rechazaba.
    """
    assert GroundingChecker()._buscar_en_html(en_pagina, extraido) is True


def test_grounding_sigue_rechazando_un_precio_que_no_esta():
    assert GroundingChecker()._buscar_en_html('"price": 6', 99.5) is False
