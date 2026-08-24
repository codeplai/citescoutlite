"""
Etapa 2b - Alemania y Suiza dejan de ir en fila india.

Medido antes del cambio, ejecucion fa76f0ca ('galletas de quinua'):

    etapa 2b .................... 199.792 ms   de 203 s de la consulta entera
      de_peru (API VTEX) ........  10.100 ms   18 ofertas
      Alemania + Suiza (agente) . ~190.000 ms   0 ofertas cada una

Las dos europeas van por agente porque ninguna cadena de esos mercados publica
precio abierto, y se lanzaban una detras de otra dentro de una peticion
sincrona. No comparten nada, asi que en serie no se ganaba nada: solo se
sumaban los relojes.

El tope es de la PAREJA y no de cada una, porque lo que hay que acotar es lo
que tarda /consultas, y eso es reloj de pared.
"""

import time

import pytest

from casos_de_uso import dependencias as mod_dependencias
from casos_de_uso.etapas import mapear_comercio as mod
from casos_de_uso.etapas.mapear_comercio import _gondolas_por_agente


class OfertasFalsas:
    """Dos gondolas que solo saben dormir y decir cuando arrancaron."""

    def __init__(self, tarda_de=0.0, tarda_ch=0.0, revienta=None):
        self.tarda_de, self.tarda_ch, self.revienta = tarda_de, tarda_ch, revienta
        self.arranques = {}

    def de_alemania(self, insumo, termino):
        self.arranques["de"] = time.monotonic()
        if self.revienta == "de":
            raise RuntimeError("la tienda alemana se cayo")
        time.sleep(self.tarda_de)
        return [f"DE:{termino}"]

    def de_suiza(self, insumo, termino):
        self.arranques["ch"] = time.monotonic()
        if self.revienta == "ch":
            raise RuntimeError("la tienda suiza se cayo")
        time.sleep(self.tarda_ch)
        return [f"CH:{termino}"]


def _deps(ofertas):
    return mod_dependencias.Dependencias(
        redactor=None, catalogo=None, cache=None, informes=None,
        auditoria=None, ofertas=ofertas)


class TestEnParalelo:
    def test_el_reloj_es_el_de_la_mas_lenta_no_la_suma(self):
        ofertas = OfertasFalsas(tarda_de=0.6, tarda_ch=0.6)
        inicio = time.monotonic()
        de, ch = _gondolas_por_agente(_deps(ofertas), "quinua", "Quinoa")
        transcurrido = time.monotonic() - inicio

        assert de == ["DE:Quinoa"] and ch == ["CH:Quinoa"]
        # En serie serian 1,2 s. Se deja margen para maquinas cargadas, pero no
        # tanto como para que la suma pase por debajo del listón.
        assert transcurrido < 1.0, f"parece que siguen en serie: {transcurrido:.2f} s"

    def test_arrancan_a_la_vez(self):
        ofertas = OfertasFalsas(tarda_de=0.4, tarda_ch=0.4)
        _gondolas_por_agente(_deps(ofertas), "quinua", "Quinoa")
        assert abs(ofertas.arranques["de"] - ofertas.arranques["ch"]) < 0.3


class TestTope:
    def test_la_que_se_pasa_del_tope_entrega_vacio(self, monkeypatch):
        monkeypatch.setenv(mod.VARIABLE_TOPE, "0.3")
        ofertas = OfertasFalsas(tarda_de=0.0, tarda_ch=5.0)

        inicio = time.monotonic()
        de, ch = _gondolas_por_agente(_deps(ofertas), "quinua", "Quinoa")
        transcurrido = time.monotonic() - inicio

        # La rapida se conserva: el tope recorta la espera, no el informe.
        assert de == ["DE:Quinoa"]
        assert ch == []
        # Y sobre todo: no se queda esperando al hilo que ya no interesa.
        # Sin `shutdown(wait=False)` esto tardaria los 5 s completos.
        assert transcurrido < 2.0, f"el tope no corto la espera: {transcurrido:.2f} s"


class TestDegradacion:
    def test_una_gondola_rota_no_tumba_la_otra(self):
        de, ch = _gondolas_por_agente(
            _deps(OfertasFalsas(revienta="de")), "quinua", "Quinoa")
        assert de == []
        assert ch == ["CH:Quinoa"]

    def test_sin_adaptador_de_ofertas_no_hay_gondolas(self):
        assert _gondolas_por_agente(_deps(None), "quinua", "Quinoa") == ([], [])

    def test_respeta_los_interruptores_de_api_main(self):
        """`AGROSCOUT_GONDOLA_DE=0` sustituye el atributo de la instancia.

        Si esto dejara de pasar por `d.ofertas.de_alemania`, el freno de mano
        de api/main.py quedaria puesto pero sin efecto, y el gasto volveria sin
        que nadie lo hubiera decidido.
        """
        ofertas = OfertasFalsas()
        ofertas.de_alemania = lambda insumo, termino: []   # el interruptor
        de, ch = _gondolas_por_agente(_deps(ofertas), "quinua", "Quinoa")
        assert de == []
        assert ch == ["CH:Quinoa"]


class TestLecturaDelTope:
    """El tope se lee del entorno en cada consulta, no al importar el modulo.

    `api/main.py` importa este modulo en su bloque de imports y llama a
    `load_dotenv()` despues. Leyendolo al importar, lo que se escribiera en
    `.env` no llegaria nunca: el freno estaria puesto en el fichero y suelto en
    el proceso.
    """

    def test_toma_el_valor_del_entorno(self, monkeypatch):
        monkeypatch.setenv(mod.VARIABLE_TOPE, "12.5")
        assert mod._tope_segundos() == 12.5

    def test_sin_variable_usa_el_de_siempre(self, monkeypatch):
        monkeypatch.delenv(mod.VARIABLE_TOPE, raising=False)
        assert mod._tope_segundos() == mod.TOPE_GONDOLAS_AGENTE_S

    def test_un_valor_ilegible_no_tumba_la_consulta(self, monkeypatch):
        monkeypatch.setenv(mod.VARIABLE_TOPE, "noventa")
        assert mod._tope_segundos() == mod.TOPE_GONDOLAS_AGENTE_S
