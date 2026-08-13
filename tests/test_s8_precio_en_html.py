"""
S8 - El rescate del precio que `trafilatura` tira.

Los casos salen de las tres tiendas suizas que trajo el agente el 2026-08-13,
no de suposiciones sobre como deberian venir las paginas. En dos de ellas el
precio viajaba en el HTML descargado y se tiraba antes de enseñarselo al
modelo; el modelo devolvia `precio=None` con razon y la extraccion se pagaba
igual.

Lo que puede romperse, y por eso esta cubierto:

1. **Que el rescate no dispare cuando no hace falta.** Si el texto principal ya
   trae precio, tocarlo solo puede empeorarlo.
2. **Que el cero no sirva de ancla.** zwicky trae dos `0,00 CHF` antes del
   precio bueno; anclarse ahi gasta la ventana en la parte que no interesa.
3. **Que el nombre siga llegando.** El precio se rescata del HTML, pero el
   nombre vive en el texto de trafilatura: si el compuesto se lleva por delante
   el texto, se cambia un hueco por otro.
4. **Que no se invente un precio donde no lo hay.** Sin importe en la respuesta
   inicial, se devuelve el texto tal cual y el agente falla honestamente.
"""

import pytest

from casos_de_uso.agente.precio_en_html import (a_texto_plano,
                                                fragmentos_con_importe,
                                                texto_para_el_modelo,
                                                tiene_importe)

LIMITE = 6000


# ---------------------------------------------------------------------------
# Que cuenta como importe
# ---------------------------------------------------------------------------

class TestReconocerImportes:
    @pytest.mark.parametrize("texto", [
        "8,05 CHF",            # zwicky.swiss, medido
        "7.70 CHF",            # green-shop.ch, medido
        "22.00\nCHF",          # wengerfarms.ch: el importe y la moneda en
                               # lineas distintas. La primera sonda no lo vio y
                               # dio la tienda por renderizada con JavaScript.
        "CHF 5.50",
        "Fr. 8.05",            # la forma suiza, moneda delante
        "EUR 3.49",
        "3,49 €",
        "S/ 24.90",
        "US$ 7.64",
        "1.234,50 EUR",        # con separador de miles
    ])
    def test_los_precios_de_verdad_se_reconocen(self, texto):
        assert tiene_importe(texto)

    @pytest.mark.parametrize("texto", [
        "",
        "Quinoa Bio 500 g",
        "500 g",
        "Artikelnummer 123456",
        "2026",
        "18.30 Fr",            # una hora en aleman ('Freitag'), no un precio.
                               # Por eso `Fr.` solo vale delante del importe.
        "0,00 CHF",            # hay importe, pero cero no es precio rescatable
    ])
    def test_lo_que_no_es_precio_no_cuela(self, texto):
        assert not tiene_importe(texto)


# ---------------------------------------------------------------------------
# El HTML a texto legible
# ---------------------------------------------------------------------------

class TestTextoPlano:
    def test_los_scripts_no_entran(self):
        """Su contenido minificado esta lleno de numeros que casarian con el
        patron sin ser precios."""
        html = ('<script>var p = {"total": 99.99, "moneda": "CHF"};</script>'
                '<p>Quinoa</p>')
        plano = a_texto_plano(html)
        assert "99.99" not in plano
        assert "Quinoa" in plano

    def test_las_lineas_vacias_se_tiran(self):
        """Una tarjeta de producto son decenas de divs anidados. Sin limpiar,
        la ventana alrededor del precio se gastaba casi entera en espacios y
        llegaba sin el nombre al lado."""
        html = "<div><div><span></span></div><p>  Quinoa  </p><div></div><b>8,05 CHF</b></div>"
        assert a_texto_plano(html) == "Quinoa\n8,05 CHF"

    def test_las_entidades_se_traducen(self):
        assert "8,05 €" in a_texto_plano("<p>8,05 &euro;</p>")

    def test_sin_html_no_revienta(self):
        assert a_texto_plano("") == ""


# ---------------------------------------------------------------------------
# Los fragmentos: precio con su contexto
# ---------------------------------------------------------------------------

class TestFragmentos:
    def test_el_nombre_viaja_con_el_precio(self):
        """Es el objetivo entero: un `8,05 CHF` suelto no se puede emparejar
        con nada, y el modelo no tendria como saber de que producto es."""
        html = ("<div><h1>Bio Quinoa weiss Knospe 500g</h1>"
                "<span>8,05 CHF</span><small>Einheit: 500 g</small></div>")
        fragmento = fragmentos_con_importe(html)[0]
        assert "Bio Quinoa weiss Knospe 500g" in fragmento
        assert "8,05 CHF" in fragmento

    def test_el_cero_no_es_ancla(self):
        """zwicky trae dos `0,00 CHF` —envio y descuento— antes del precio
        real. Anclarse en ellos gasta los fragmentos en la parte inutil."""
        assert fragmentos_con_importe("<p>Versandkosten 0,00 CHF</p>") == []

    def test_una_pagina_sin_importes_no_da_fragmentos(self):
        assert fragmentos_con_importe("<p>Quinoa Bio 500 g</p>") == []

    def test_dos_precios_juntos_no_se_parten(self):
        """El precio tachado y el vigente tienen que leerse juntos: el prompt
        pide 'el que se cobra hoy' y eso solo se decide viendo los dos."""
        html = ("<div><p>Quinoa Geschenkset</p>"
                "<span>Ursprunglicher Preis war: 55.70 CHF</span>"
                "<span>Aktueller Preis ist: 53.70 CHF</span></div>")
        fragmentos = fragmentos_con_importe(html)
        assert len(fragmentos) == 1
        assert "55.70 CHF" in fragmentos[0] and "53.70 CHF" in fragmentos[0]

    def test_hay_tope_de_fragmentos(self):
        """Una pagina de categoria puede traer decenas de importes y la ventana
        del modelo es finita."""
        html = "".join(f"<div>Producto {i}<span>{i + 1}.50 CHF</span></div>"
                       for i in range(40))
        assert len(fragmentos_con_importe(html)) <= 6


# ---------------------------------------------------------------------------
# Lo que acaba viendo el modelo
# ---------------------------------------------------------------------------

class TestTextoParaElModelo:
    def test_si_el_texto_ya_trae_precio_no_se_toca(self):
        """El camino normal —Peru, y las fichas que trafilatura lee bien—. El
        rescate solo puede empeorar lo que ya funcionaba."""
        texto = "Quinua Organica 500g\nS/ 15.90\nStock disponible"
        lectura, rescatado = texto_para_el_modelo(texto, "<p>otra cosa</p>", LIMITE)

        assert rescatado is False
        assert lectura == texto

    def test_si_falta_el_precio_se_rescata_del_html(self):
        texto = "Bio Quinoa weiss Knospe 500g\nQuinoa ist ein Gansefussgewachs."
        html = ("<div><h1>Bio Quinoa weiss Knospe 500g</h1>"
                "<span>8,05 CHF</span><small>Inkl. MwSt.</small></div>")
        lectura, rescatado = texto_para_el_modelo(texto, html, LIMITE)

        assert rescatado is True
        assert "8,05 CHF" in lectura

    def test_el_nombre_sobrevive_al_rescate(self):
        """El precio sale del HTML pero el nombre vive en el texto principal.
        Sustituir uno por otro cambiaria un hueco por otro."""
        texto = "Bio Quinoa weiss Knospe 500g\nDescripcion larga del producto."
        html = "<div><span>8,05 CHF</span></div>"
        lectura, _ = texto_para_el_modelo(texto, html, LIMITE)

        assert "Bio Quinoa weiss Knospe 500g" in lectura
        assert "8,05 CHF" in lectura

    def test_sin_precio_en_ninguna_parte_no_se_inventa_nada(self):
        """Lo pinta JavaScript. Se devuelve el texto tal cual y el agente falla
        honestamente, en vez de mandar 6.000 caracteres de HTML por si suena la
        flauta."""
        texto = "Quinoa\nDescripcion"
        lectura, rescatado = texto_para_el_modelo(texto, "<p>Quinoa</p>", LIMITE)

        assert rescatado is False
        assert lectura == texto

    def test_se_respeta_el_limite(self):
        texto = "Quinoa " * 2000
        html = "<div>Quinoa Bio<span>8,05 CHF</span></div>"
        lectura, rescatado = texto_para_el_modelo(texto, html, LIMITE)

        assert rescatado is True
        assert len(lectura) <= LIMITE
        # Y el precio no puede ser lo que se cae por el recorte: es el motivo
        # de haber vuelto a componer el texto.
        assert "8,05 CHF" in lectura

    def test_sin_texto_principal_sigue_rescatando(self):
        """Hay fichas donde trafilatura devuelve vacio del todo."""
        lectura, rescatado = texto_para_el_modelo(
            "", "<div>Quinoa Bio<span>8,05 CHF</span></div>", LIMITE)

        assert rescatado is True
        assert "8,05 CHF" in lectura
