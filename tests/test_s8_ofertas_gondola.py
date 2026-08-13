"""
S8 - La tabla de góndola: a cuánto se vende hoy, tienda por tienda.

Tres cosas que importan más que el resto:

1. **Que fallar aquí no tumbe la consulta.** La góndola es una fuente entre
   varias; que una tienda no responda no puede dejar sin informe a quien
   preguntó por la composición de un insumo.
2. **Que el precio original no se pise.** La cifra en soles viaja aparte, con
   su tasa, su fecha y su fuente, o no es auditable.
3. **Que `buscar_sync` funcione desde dentro de un bucle de eventos.** Es
   exactamente donde se va a llamar —la etapa 2b corre dentro de la petición—
   y es donde un `asyncio.run` mal puesto revienta.
"""

import asyncio

import pytest

from adaptadores.ofertas_gondola import OfertasGondola, _conversion_de
from casos_de_uso.agente.schemas import ProductoSchema


class OfertaCruda:
    """Lo que devuelve CatalogoVTEX: producto + procedencia."""

    def __init__(self, nombre, precio, tienda, ean=None, stock=None,
                 moneda="PEN"):
        self.producto = ProductoSchema(
            nombre=nombre, precio=precio, moneda=moneda, ean=ean, stock=stock,
            marca="Marca", unidad="un", categoria="Granos")
        self.fuente_url = f"https://{tienda.lower()}.pe/{nombre}/p"
        self.evidencia = "{}"
        self.tienda = tienda


class CatalogoFalso:
    def __init__(self, ofertas=None, revienta=False):
        self._ofertas = ofertas or []
        self.revienta = revienta
        self.llamadas = []

    def buscar_sync(self, insumo, limite=5):
        self.llamadas.append((insumo, limite))
        if self.revienta:
            raise RuntimeError("las cuatro tiendas dieron timeout")
        return self._ofertas


class CambioFalso:
    """Doble del tipo de cambio. 4,0 soles por euro, cifra redonda a propósito."""

    def __init__(self, tasa=4.0, falla=False):
        self.tasa = tasa
        self.falla = falla

    def a_soles(self, precio, moneda):
        if self.falla or precio is None:
            return None

        class R:
            pass

        r = R()
        r.precio_pen = round(precio * self.tasa, 2)
        r.tasa = self.tasa
        r.moneda_origen = moneda
        r.fecha_tasa = "2026-08-12"
        r.fuente = "BCRP - TC Euro (S/ por Euro) - Venta"
        return r


def _gondola(ofertas=None, revienta=False, cambio=None):
    return OfertasGondola(catalogo=CatalogoFalso(ofertas, revienta),
                          cambio=cambio or CambioFalso())


# ---------------------------------------------------------------------------
# Fallar aquí no puede tumbar la consulta
# ---------------------------------------------------------------------------

def test_si_las_tiendas_no_responden_la_tabla_sale_vacia():
    """Degradar a «sin dato», nunca a error (ADR-001)."""
    assert _gondola(revienta=True).de_peru("quinua") == []


def test_un_fallo_se_anota(caplog):
    with caplog.at_level("ERROR"):
        _gondola(revienta=True).de_peru("quinua")
    assert any("tiendas peruanas" in r.message for r in caplog.records)


def test_sin_insumo_no_se_consulta_nada():
    catalogo = CatalogoFalso()
    OfertasGondola(catalogo=catalogo, cambio=CambioFalso()).de_peru("")
    assert catalogo.llamadas == []


# ---------------------------------------------------------------------------
# El mapeo
# ---------------------------------------------------------------------------

def test_lleva_lo_que_hace_falta_para_comparar():
    ofertas = _gondola([OfertaCruda("Quinua 500g", 8.5, "Wong",
                                    ean="7751130000714", stock=12)]).de_peru("quinua")

    o = ofertas[0]
    assert o.nombre == "Quinua 500g"
    assert o.tienda == "Wong"
    assert o.ean == "7751130000714"
    assert o.stock == 12
    assert o.procedencia == "vtex:Wong"
    assert o.capturado_en  # un precio sin fecha no dice nada


def test_el_precio_original_no_se_pisa():
    ofertas = _gondola([OfertaCruda("Quinua", 8.5, "Wong")]).de_peru("quinua")
    assert ofertas[0].precio == 8.5
    assert ofertas[0].moneda == "PEN"


# ---------------------------------------------------------------------------
# La conversión
# ---------------------------------------------------------------------------

class TestConversion:
    def test_en_soles_la_conversion_es_la_identidad(self):
        """Se rellena igual, para que la columna en soles no tenga huecos."""
        pen, conv = _conversion_de(8.5, "PEN", CambioFalso())
        assert pen == 8.5
        assert conv.tasa == 1.0
        assert conv.moneda_origen == "PEN"

    def test_una_moneda_de_fuera_se_convierte_con_su_tasa(self):
        pen, conv = _conversion_de(10.0, "EUR", CambioFalso(tasa=4.0))
        assert pen == 40.0
        assert conv.tasa == 4.0
        assert conv.moneda_origen == "EUR"

    def test_la_conversion_viaja_con_su_fecha_y_su_fuente(self):
        """Una cifra convertida sin la tasa con la que se convirtió no es
        auditable: dentro de un mes nadie podría reconstruirla."""
        _, conv = _conversion_de(10.0, "EUR", CambioFalso())
        assert conv.fecha_tasa == "2026-08-12"
        assert "BCRP" in conv.fuente

    def test_sin_tasa_no_se_inventa_una(self):
        pen, conv = _conversion_de(10.0, "EUR", CambioFalso(falla=True))
        assert pen is None and conv is None

    def test_sin_precio_no_hay_conversion(self):
        assert _conversion_de(None, "PEN", CambioFalso()) == (None, None)

    def test_una_oferta_sin_tasa_conserva_su_precio_original(self):
        """La columna en soles queda vacía; la oferta no se descarta."""
        ofertas = _gondola([OfertaCruda("Quinoa", 10.0, "Rewe", moneda="EUR")],
                           cambio=CambioFalso(falla=True)).de_peru("quinua")
        assert ofertas[0].precio == 10.0
        assert ofertas[0].precio_pen is None


# ---------------------------------------------------------------------------
# El orden es lo que convierte la lista en una comparación
# ---------------------------------------------------------------------------

class TestOrden:
    def test_el_mismo_ean_cae_en_filas_contiguas(self):
        """El nombre del producto cambia de una cadena a otra; el código de
        barras no. Si las dos filas no quedan juntas, hay que buscarlas."""
        ofertas = _gondola([
            OfertaCruda("Quinua tricolor 454g", 15.7, "Wong", ean="742832801140"),
            OfertaCruda("Otra cosa", 9.0, "Metro", ean="111"),
            OfertaCruda("Quinua Tricolor Bolsa 454 g", 15.0, "Metro", ean="742832801140"),
        ]).de_peru("quinua")

        eans = [o.ean for o in ofertas]
        assert eans == ["111", "742832801140", "742832801140"]

    def test_y_dentro_del_mismo_ean_manda_el_precio(self):
        ofertas = _gondola([
            OfertaCruda("A", 15.7, "Wong", ean="742832801140"),
            OfertaCruda("B", 15.0, "Metro", ean="742832801140"),
        ]).de_peru("quinua")
        assert [o.tienda for o in ofertas] == ["Metro", "Wong"]

    def test_las_que_no_tienen_ean_van_al_final(self):
        """No se pueden emparejar con nada, así que no estorban arriba."""
        ofertas = _gondola([
            OfertaCruda("Sin codigo", 5.0, "Makro"),
            OfertaCruda("Con codigo", 99.0, "Wong", ean="999"),
        ]).de_peru("quinua")
        assert [o.nombre for o in ofertas] == ["Con codigo", "Sin codigo"]


# ---------------------------------------------------------------------------
# El puente síncrono, que es donde esto se puede romper de verdad
# ---------------------------------------------------------------------------

class CatalogoAsincronoFalso:
    """Imita a CatalogoVTEX: sólo tiene `buscar` asíncrono."""

    async def buscar(self, insumo, limite=5):
        await asyncio.sleep(0)
        return [OfertaCruda("Quinua", 8.5, "Wong", ean="1")]


def test_buscar_sync_funciona_dentro_de_un_bucle_de_eventos():
    """La etapa 2b es síncrona pero corre DENTRO de la petición, es decir con
    un bucle ya en marcha. Un `asyncio.run` puesto sin más ahí lanza
    'cannot be called from a running event loop', y es justo el sitio donde se
    va a llamar."""
    from adaptadores.catalogo_vtex import CatalogoVTEX

    catalogo = CatalogoVTEX()
    catalogo.buscar = CatalogoAsincronoFalso().buscar

    async def desde_dentro_del_bucle():
        return catalogo.buscar_sync("quinua")

    ofertas = asyncio.run(desde_dentro_del_bucle())
    assert len(ofertas) == 1
    assert ofertas[0].tienda == "Wong"


# ---------------------------------------------------------------------------
# La etapa 2b
# ---------------------------------------------------------------------------

class TestEtapa2b:
    def _interpretado(self):
        from dominio.insumo import InsumoInterpretado
        return InsumoInterpretado(insumo_normalizado="quinua", reconocible=True,
                                  sinonimos_busqueda=["quinoa"], terminos_ingles=["quinoa"])

    def _dependencias(self, ofertas):
        from casos_de_uso.dependencias import Dependencias
        return Dependencias(redactor=None, catalogo=None, cache=None,
                            informes=None, auditoria=None, ofertas=ofertas)

    def test_el_mapa_lleva_las_ofertas(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola = _gondola([OfertaCruda("Quinua", 8.5, "Wong", ean="1")])
        mapa = mapear_comercio(self._dependencias(gondola), self._interpretado())

        assert len(mapa.ofertas_peru) == 1
        assert mapa.ofertas_peru[0].tienda == "Wong"

    def test_sin_adaptador_de_ofertas_la_etapa_corre_igual(self):
        """Es el modo en que arman Dependencias los tests deterministas de S2."""
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        mapa = mapear_comercio(self._dependencias(None), self._interpretado())
        assert mapa.ofertas_peru == []

    def test_van_en_su_propia_lista_y_no_entre_los_productos(self):
        """`productos` viene de OpenFoodFacts y dice qué existe; esto dice a
        cuánto se vende. Fundirlas haría creer que son comparables."""
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola = _gondola([OfertaCruda("Quinua", 8.5, "Wong")])
        mapa = mapear_comercio(self._dependencias(gondola), self._interpretado())

        assert mapa.productos == []
        assert len(mapa.ofertas_peru) == 1
