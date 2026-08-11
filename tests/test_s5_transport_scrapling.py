"""
S5.1 - ScraplingTransport: que no mienta mientras no este implementado.

El transporte no se puede implementar todavia (falta la dependencia
`scrapling` y SCRAPLING_API_KEY). Lo que estos tests fijan es que se comporte
como lo que es —algo no configurado— en vez de simular exito: devolvia HTML
inventado con status SUCCESS, que al conectarlo al barrido habria contado esas
tiendas como verificadas e inflado la cobertura declarada de P14.
"""

import pytest

from adaptadores.transport_scrapling import ScraplingTransport, TransportStatus


@pytest.mark.asyncio
async def test_buscar_no_simula_exito():
    transport = ScraplingTransport()

    html, status = await transport.buscar(
        url="https://tienda.example/buscar", query="quinua", tienda_id="shopify_dynamic")

    assert status == TransportStatus.NOT_CONFIGURED
    assert status != TransportStatus.SUCCESS
    assert html == ""


@pytest.mark.asyncio
async def test_buscar_no_devuelve_html_inventado():
    """El HTML de mentira llevaba dentro la url y la query."""
    transport = ScraplingTransport()

    html, _ = await transport.buscar(
        url="https://tienda.example/buscar", query="quinua", tienda_id="x")

    assert "Scrapling" not in html
    assert "quinua" not in html


@pytest.mark.asyncio
async def test_test_connection_no_da_por_bueno_lo_que_no_hay():
    assert await ScraplingTransport().test_connection() is False


def test_no_declara_tiendas_de_ejemplo_como_soportadas():
    """Devolvia shop.example.com y spa.example.com como si fueran reales."""
    soportadas = ScraplingTransport().get_tiendas_soportadas()

    assert soportadas == []
    assert not any("example.com" in t for t in soportadas)


@pytest.mark.asyncio
async def test_con_cliente_si_usa_el_camino_real():
    """El dia que haya SDK, buscar() debe renderizar y devolver SUCCESS."""
    class ClienteFalso:
        async def render_page(self, url, headless=True):
            return "<html>producto</html>"

    transport = ScraplingTransport()
    transport.client = ClienteFalso()
    transport.rate_limit_delay = 0  # no esperar 10s en un test

    html, status = await transport.buscar(
        url="https://tienda.example/p", query="quinua", tienda_id="x")

    assert status == TransportStatus.SUCCESS
    assert html == "<html>producto</html>"
