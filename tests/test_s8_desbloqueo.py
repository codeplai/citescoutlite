"""
S8 - Web Unlocker como reserva ante un 403.

Existe porque el agente perdía ofertas por no poder entrar, no porque no las
hubiera: medido sobre 'Quinoa', dos de las tres URL que abrió devolvieron 403
—idealo.de y rewe.de— y la góndola alemana salió vacía.

Lo que estos tests fijan:

1. **Solo se reintenta un bloqueo.** Un 404 no mejora por pasar por un proxy, y
   cada petición cuesta dinero.
2. **Nunca lanza.** Sin clave, sin zona o con respuesta vacía, el agente sigue
   como antes. Es ADR-001 otra vez: degradar a «sin dato», nunca a error.
3. **El fallo de zona no es silencioso.** Bright Data lo devuelve como HTTP 200
   con cuerpo vacío, que sin mirar la cabecera parece una página en blanco.
"""

import asyncio

import httpx
import pytest

from adaptadores.desbloqueo_brightdata import DesbloqueoBrightData, ZONA_POR_DEFECTO
from casos_de_uso.agente.agente import _es_bloqueo


def _error_http(codigo: int) -> httpx.HTTPStatusError:
    peticion = httpx.Request("GET", "https://www.rewe.de/shop/c/quinoa")
    respuesta = httpx.Response(codigo, request=peticion)
    return httpx.HTTPStatusError(f"Client error '{codigo}'", request=peticion,
                                 response=respuesta)


class TestQueCuentaComoBloqueo:
    @pytest.mark.parametrize("codigo", [403, 429, 503])
    def test_los_muros_se_reintentan(self, codigo):
        assert _es_bloqueo(_error_http(codigo)) is True

    @pytest.mark.parametrize("codigo", [404, 500, 410])
    def test_lo_que_no_es_un_muro_no(self, codigo):
        """Un 404 es una ausencia: el proxy no va a crear la página."""
        assert _es_bloqueo(_error_http(codigo)) is False

    def test_tambien_lo_detecta_si_llega_envuelto(self):
        """El fallo puede llegar ya envuelto por otra capa."""
        assert _es_bloqueo(RuntimeError("URL fetch error: Client error '403 Forbidden'"))

    def test_no_confunde_un_id_de_la_url_con_un_codigo(self):
        """403 dentro de un identificador no es un 403 de respuesta."""
        assert _es_bloqueo(RuntimeError("fetch error (https://x.de/p/200403404_-quinoa)")) is False


class RespuestaFalsa:
    def __init__(self, texto="", codigo=200, cabeceras=None):
        self.text = texto
        self.status_code = codigo
        self.headers = cabeceras or {}


class ClienteFalso:
    """Doble de httpx.AsyncClient con la interfaz de contexto asíncrono."""

    def __init__(self, respuesta=None, revienta=False):
        self.respuesta = respuesta
        self.revienta = revienta
        self.llamadas = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.llamadas.append(json)
        if self.revienta:
            raise httpx.ConnectError("sin ruta al host")
        return self.respuesta


def _desbloqueo(monkeypatch, respuesta=None, revienta=False, **kw):
    cliente = ClienteFalso(respuesta, revienta)
    monkeypatch.setattr("adaptadores.desbloqueo_brightdata.httpx.AsyncClient",
                        lambda **_: cliente)
    d = DesbloqueoBrightData(api_key=kw.pop("api_key", "clave-de-prueba"), **kw)
    return d, cliente


class TestDesbloqueo:
    def test_devuelve_el_html_cuando_funciona(self, monkeypatch):
        d, _ = _desbloqueo(monkeypatch, RespuestaFalsa("<html>Quinoa 4,99 €</html>"))
        assert asyncio.run(d.descargar("https://www.rewe.de/x")) == "<html>Quinoa 4,99 €</html>"

    def test_pide_la_zona_y_el_formato_crudo(self, monkeypatch):
        """La zona va explícita: si se dejara al valor por defecto, este test
        leería `BRIGHT_DATA_ZONE` del entorno de quien lo ejecute y pasaría o
        fallaría según la máquina."""
        d, cliente = _desbloqueo(monkeypatch, RespuestaFalsa("<html/>"),
                                 zona="zona-de-prueba")
        asyncio.run(d.descargar("https://www.rewe.de/x"))
        assert cliente.llamadas[0] == {"zone": "zona-de-prueba",
                                       "url": "https://www.rewe.de/x", "format": "raw"}

    def test_sin_configurar_cae_a_la_zona_por_defecto(self, monkeypatch):
        monkeypatch.delenv("BRIGHT_DATA_ZONE", raising=False)
        d, cliente = _desbloqueo(monkeypatch, RespuestaFalsa("<html/>"))
        asyncio.run(d.descargar("https://www.rewe.de/x"))
        assert cliente.llamadas[0]["zone"] == ZONA_POR_DEFECTO

    def test_sin_clave_no_llama_a_nadie(self, monkeypatch):
        d, cliente = _desbloqueo(monkeypatch, RespuestaFalsa("<html/>"), api_key="")
        assert asyncio.run(d.descargar("https://www.rewe.de/x")) is None
        assert cliente.llamadas == []

    def test_el_fallo_de_zona_devuelve_none_y_se_explica(self, monkeypatch, caplog):
        """Bright Data lo manda como HTTP 200 con cuerpo vacío: sin leer la
        cabecera parece que la página estaba en blanco. Es el estado real de la
        cuenta hoy —`can_make_requests: false`, `zone_not_found`—."""
        r = RespuestaFalsa("", 200, {"x-brd-err-code": "client_10002",
                                     "x-brd-err-msg": "zone not found"})
        d, _ = _desbloqueo(monkeypatch, r)
        with caplog.at_level("WARNING"):
            assert asyncio.run(d.descargar("https://www.rewe.de/x")) is None
        assert any("client_10002" in m.message for m in caplog.records)

    def test_una_respuesta_vacia_sin_motivo_tampoco_pasa(self, monkeypatch):
        d, _ = _desbloqueo(monkeypatch, RespuestaFalsa("   "))
        assert asyncio.run(d.descargar("https://www.rewe.de/x")) is None

    def test_si_la_red_falla_devuelve_none(self, monkeypatch):
        """Que el proxy no responda no puede tumbar la consulta."""
        d, _ = _desbloqueo(monkeypatch, revienta=True)
        assert asyncio.run(d.descargar("https://www.rewe.de/x")) is None

    def test_solo_avisa_una_vez_por_proceso(self, monkeypatch, caplog):
        """Tres URL por consulta y muchas consultas: un aviso por intento
        llenaría el log de la misma línea."""
        r = RespuestaFalsa("", 200, {"x-brd-err-code": "client_10002"})
        d, _ = _desbloqueo(monkeypatch, r)
        with caplog.at_level("WARNING"):
            for _ in range(4):
                asyncio.run(d.descargar("https://www.rewe.de/x"))
        assert sum("client_10002" in m.message for m in caplog.records) == 1


class DesbloqueoFalso:
    def __init__(self, html=None):
        self.html = html
        self.urls = []

    async def descargar(self, url):
        self.urls.append(url)
        return self.html


class TestIntegracionConElAgente:
    """`descargar()` reintenta el 403 y deja pasar lo demás."""

    def _agente(self, desbloqueo, codigo):
        from casos_de_uso.agente.agente import AgenteInvestigadorComercial

        a = AgenteInvestigadorComercial.__new__(AgenteInvestigadorComercial)
        a.desbloqueo = desbloqueo

        class Http:
            async def get(self, url, **kw):
                raise _error_http(codigo)

        a.http_client = Http()
        return a

    def _descargar(self, monkeypatch, agente, url="https://www.rewe.de/x"):
        async def sin_limite(_u):
            return None

        monkeypatch.setattr("casos_de_uso.agente.agente.check_rate_limit", sin_limite)
        monkeypatch.setattr("casos_de_uso.agente.agente.record_request_success", lambda _u: None)
        monkeypatch.setattr("casos_de_uso.agente.agente.record_request_failure", lambda _u: None)
        return asyncio.run(agente.descargar(url))

    def test_un_403_se_reintenta_y_se_recupera(self, monkeypatch):
        d = DesbloqueoFalso("<html>Quinoa Bio 500g 4,99 €</html>")
        crudo, texto = self._descargar(monkeypatch, self._agente(d, 403))
        assert "Quinoa" in crudo
        assert d.urls == ["https://www.rewe.de/x"]

    def test_un_404_no_gasta_proxy(self, monkeypatch):
        d = DesbloqueoFalso("<html/>")
        with pytest.raises(RuntimeError):
            self._descargar(monkeypatch, self._agente(d, 404))
        assert d.urls == []

    def test_si_el_desbloqueo_tampoco_puede_manda_el_error_original(self, monkeypatch):
        """Se conserva el fallo de la tienda, que dice más que uno del proxy."""
        d = DesbloqueoFalso(None)
        with pytest.raises(RuntimeError, match="403"):
            self._descargar(monkeypatch, self._agente(d, 403))
        assert d.urls == ["https://www.rewe.de/x"]

    def test_sin_desbloqueo_configurado_el_agente_funciona_igual(self, monkeypatch):
        with pytest.raises(RuntimeError, match="403"):
            self._descargar(monkeypatch, self._agente(None, 403))
