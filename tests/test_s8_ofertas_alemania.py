"""
S8 - La góndola alemana. Lo que la distingue de la peruana, que es lo que puede
romperse:

1. **Se busca en alemán.** El insumo llega en castellano y el filtro por nombre
   descartaría cualquier ficha alemana. Sin término no se llama al agente: una
   búsqueda que garantiza cero resultados no merece pagarse, y esta cuesta.
2. **La procedencia dice de dónde salió.** 'agente:REWE', no 'vtex:REWE'. Una
   lectura de catálogo y una extracción con modelo no valen lo mismo, y la
   columna existe para poder distinguirlas.
3. **Las dos góndolas no se pisan.** Comparten objeto pero no conector; si
   compartieran ranura, la primera llamada decidiría el conector de las dos.
4. **El precio en euros sobrevive a un BCRP caído.** Es el caso que en Perú no
   se da nunca, porque allí la conversión es la identidad.
"""

import asyncio

import pytest

from adaptadores.catalogo_alemania import MONEDA, nombre_de_tienda
from adaptadores.ofertas_gondola import OfertasGondola
from casos_de_uso.agente.schemas import ProductoSchema


class OfertaCruda:
    """Lo que devuelve un conector de góndola: producto + procedencia."""

    def __init__(self, nombre, precio, tienda, ean=None, stock=None, moneda="EUR",
                 url=None):
        self.producto = ProductoSchema(
            nombre=nombre, precio=precio, moneda=moneda, ean=ean, stock=stock,
            marca="Marke", unidad="g", categoria="Getreide")
        self.fuente_url = url or f"https://{tienda.lower()}.de/p/{nombre}"
        self.evidencia = "{}"
        self.tienda = tienda


class CatalogoFalso:
    """Doble de CatalogoAlemania. Registra con qué se le llamó."""

    def __init__(self, ofertas=None, revienta=False):
        self._ofertas = ofertas or []
        self.revienta = revienta
        self.llamadas = []

    def buscar_sync(self, termino, limite=5, insumo=None):
        self.llamadas.append((termino, limite, insumo))
        if self.revienta:
            raise RuntimeError("Tavily no respondió")
        return self._ofertas


class CambioFalso:
    """4,0 soles por euro, cifra redonda a propósito."""

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
    """La góndola con el conector alemán doblado.

    Las otras dos ranuras se rellenan con dobles vacíos y no se dejan en None.
    Con None, cada `de_*` construye su conector de verdad y sale a la red —lo
    que hizo caer este archivo la primera vez que se ejecutó, trayendo 20
    ofertas reales de Makro—. Un test de la góndola alemana no puede depender
    de que Wong esté en pie.

    La suiza importa **más** que la peruana, y por eso está aquí y no solo en
    su propio archivo: `TestEtapa2b` llama a `mapear_comercio`, que desde S8
    consulta las tres góndolas con el mismo término alemán. Sin este doble,
    cuatro tests de este archivo lanzarían el agente suizo de verdad: minutos
    de espera y gasto de modelo en cada pasada de la suite.
    """
    catalogo = CatalogoFalso(ofertas, revienta)
    gondola = OfertasGondola(catalogo=CatalogoFalso([]),
                             cambio=cambio or CambioFalso(),
                             catalogo_de=catalogo,
                             catalogo_ch=CatalogoFalso([]))
    return gondola, catalogo


# ---------------------------------------------------------------------------
# Sin término alemán no se busca: esta consulta cuesta dinero
# ---------------------------------------------------------------------------

class TestTerminoAleman:
    def test_sin_termino_no_se_llama_al_agente(self):
        """El insumo va en castellano y el filtro por nombre descartaría todo.
        Gastar búsqueda y extracciones para garantizar cero ofertas es peor que
        no llamar."""
        gondola, catalogo = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")])
        assert gondola.de_alemania("arandano", "") == []
        assert catalogo.llamadas == []

    def test_sin_insumo_tampoco(self):
        gondola, catalogo = _gondola()
        assert gondola.de_alemania("", "Quinoa") == []
        assert catalogo.llamadas == []

    def test_se_busca_con_el_termino_no_con_el_insumo(self):
        gondola, catalogo = _gondola([OfertaCruda("Heidelbeeren 200g", 3.49, "REWE")])
        gondola.de_alemania("arandano", "Heidelbeeren")

        termino, _, insumo = catalogo.llamadas[0]
        assert termino == "Heidelbeeren"
        # El insumo viaja igualmente: es la etiqueta del run para la auditoría.
        assert insumo == "arandano"

    def test_falta_de_termino_se_anota(self, caplog):
        with caplog.at_level("INFO"):
            _gondola()[0].de_alemania("arandano", "")
        assert any("termino aleman" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Fallar aquí tampoco puede tumbar la consulta
# ---------------------------------------------------------------------------

def test_si_el_agente_revienta_la_tabla_sale_vacia():
    """ADR-001: degradar a «sin dato», nunca a error."""
    gondola, _ = _gondola(revienta=True)
    assert gondola.de_alemania("quinua", "Quinoa") == []


def test_el_fallo_se_anota(caplog):
    gondola, _ = _gondola(revienta=True)
    with caplog.at_level("ERROR"):
        gondola.de_alemania("quinua", "Quinoa")
    assert any("tiendas alemanas" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# La procedencia: de dónde salió la fila
# ---------------------------------------------------------------------------

class TestProcedencia:
    def test_dice_agente_y_no_vtex(self):
        """Estaba fijado a 'vtex:' en `_a_dominio`. Una oferta de REWE llega
        tras una búsqueda web y una extracción con modelo; etiquetarla como
        lectura de catálogo sería falso en el único campo que lo distingue."""
        gondola, _ = _gondola([OfertaCruda("Quinoa Tricolore", 4.99, "REWE")])
        ofertas = gondola.de_alemania("quinua", "Quinoa")
        assert ofertas[0].procedencia == "agente:REWE"

    def test_la_peruana_sigue_diciendo_vtex(self):
        """El refactor del prefijo no puede haber cambiado la ruta de Perú."""
        from tests.test_s8_ofertas_gondola import OfertaCruda as CrudaPE, CatalogoFalso as CatPE

        gondola = OfertasGondola(catalogo=CatPE([CrudaPE("Quinua", 8.5, "Wong")]),
                                 cambio=CambioFalso())
        assert gondola.de_peru("quinua")[0].procedencia == "vtex:Wong"


# ---------------------------------------------------------------------------
# Las dos góndolas comparten objeto pero no conector
# ---------------------------------------------------------------------------

class TestRanurasSeparadas:
    def test_alemania_no_usa_el_catalogo_peruano(self):
        from tests.test_s8_ofertas_gondola import CatalogoFalso as CatPE

        peru = CatPE([])
        gondola, alemania = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")])
        gondola._catalogo = peru

        gondola.de_alemania("quinua", "Quinoa")
        assert peru.llamadas == []
        assert len(alemania.llamadas) == 1

    def test_peru_no_usa_el_catalogo_aleman(self):
        """Con una sola ranura, la primera llamada decidía el conector de las
        dos: Perú acabaría preguntándole al agente."""
        from tests.test_s8_ofertas_gondola import OfertaCruda as CrudaPE, CatalogoFalso as CatPE

        peru = CatPE([CrudaPE("Quinua", 8.5, "Wong")])
        gondola, alemania = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")])
        gondola._catalogo = peru

        ofertas = gondola.de_peru("quinua")
        assert [o.tienda for o in ofertas] == ["Wong"]
        assert alemania.llamadas == []

    def test_las_dos_en_la_misma_consulta_no_se_mezclan(self):
        from tests.test_s8_ofertas_gondola import OfertaCruda as CrudaPE, CatalogoFalso as CatPE

        peru = CatPE([CrudaPE("Quinua 500g", 8.5, "Wong", ean="1")])
        gondola, _ = _gondola([OfertaCruda("Quinoa 500g", 4.99, "REWE", ean="2")])
        gondola._catalogo = peru

        pe = gondola.de_peru("quinua")
        de = gondola.de_alemania("quinua", "Quinoa")

        assert [o.tienda for o in pe] == ["Wong"]
        assert [o.tienda for o in de] == ["REWE"]
        assert pe[0].moneda == "PEN" and de[0].moneda == "EUR"


# ---------------------------------------------------------------------------
# Euros: la conversión y, sobre todo, su ausencia
# ---------------------------------------------------------------------------

class TestEuros:
    def test_el_precio_se_convierte_y_el_original_no_se_pisa(self):
        gondola, _ = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")])
        o = gondola.de_alemania("quinua", "Quinoa")[0]

        assert o.precio == 4.99 and o.moneda == "EUR"
        assert o.precio_pen == 19.96
        assert o.conversion.moneda_origen == "EUR"
        assert o.conversion.tasa == 4.0

    def test_la_conversion_viaja_con_su_fecha_y_su_fuente(self):
        """Una cifra convertida sin la tasa con la que se convirtió no es
        auditable: el informe de CITE tiene que aguantar esa pregunta meses
        después."""
        gondola, _ = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")])
        c = gondola.de_alemania("quinua", "Quinoa")[0].conversion
        assert c.fecha_tasa == "2026-08-12"
        assert "BCRP" in c.fuente

    def test_sin_tasa_la_oferta_conserva_su_precio_en_euros(self):
        """Es el caso que en Perú no se da nunca. La columna en soles queda
        vacía; la oferta NO se descarta y el euro sigue ahí para que la tabla
        pueda pintarlo."""
        gondola, _ = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")],
                              cambio=CambioFalso(falla=True))
        o = gondola.de_alemania("quinua", "Quinoa")[0]

        assert o.precio == 4.99 and o.moneda == "EUR"
        assert o.precio_pen is None and o.conversion is None


# ---------------------------------------------------------------------------
# El orden, que ahora comparten las dos tablas
# ---------------------------------------------------------------------------

class TestOrden:
    def test_el_mismo_ean_cae_en_filas_contiguas(self):
        gondola, _ = _gondola([
            OfertaCruda("Quinoa Tricolore 500g", 5.49, "REWE", ean="4001234567890"),
            OfertaCruda("Anderes", 2.0, "Edeka", ean="111"),
            OfertaCruda("Quinoa dreifarbig 500g", 4.99, "Edeka", ean="4001234567890"),
        ])
        eans = [o.ean for o in gondola.de_alemania("quinua", "Quinoa")]
        assert eans == ["111", "4001234567890", "4001234567890"]

    def test_y_dentro_del_mismo_ean_manda_el_precio(self):
        gondola, _ = _gondola([
            OfertaCruda("A", 5.49, "REWE", ean="400"),
            OfertaCruda("B", 4.99, "Edeka", ean="400"),
        ])
        assert [o.tienda for o in gondola.de_alemania("q", "Quinoa")] == ["Edeka", "REWE"]

    def test_las_que_no_tienen_ean_van_al_final(self):
        gondola, _ = _gondola([
            OfertaCruda("Ohne Code", 1.0, "Alnatura"),
            OfertaCruda("Mit Code", 99.0, "REWE", ean="999"),
        ])
        assert [o.nombre for o in gondola.de_alemania("q", "Quinoa")] == [
            "Mit Code", "Ohne Code"]


# ---------------------------------------------------------------------------
# El nombre de la tienda sale de la URL
# ---------------------------------------------------------------------------

class TestNombreDeTienda:
    @pytest.mark.parametrize("url,esperado", [
        ("https://www.rewe.de/produkte/quinoa", "REWE"),
        ("https://shop.rewe.de/p/quinoa/123", "REWE"),
        ("https://www.edeka.de/eh/quinoa", "Edeka"),
        ("https://www.alnatura.de/de-de/produkte/x", "Alnatura"),
    ])
    def test_las_conocidas_salen_con_su_nombre(self, url, esperado):
        assert nombre_de_tienda(url) == esperado

    def test_una_desconocida_sale_con_su_dominio(self):
        """Mejor el dominio que «tienda alemana»: es información real y quien
        lee el informe puede ir a comprobarla."""
        assert nombre_de_tienda("https://www.biomarkt-mueller.de/p/1") == "biomarkt-mueller.de"

    def test_sin_url_no_revienta(self):
        assert nombre_de_tienda("") == "tienda desconocida"


# ---------------------------------------------------------------------------
# El puente síncrono y la moneda del mercado
# ---------------------------------------------------------------------------

class AgenteFalso:
    """Imita a AgenteInvestigadorComercial: solo tiene `ejecutar` asíncrono."""

    def __init__(self, moneda=None):
        self.moneda = moneda
        self.llamadas = []

    async def ejecutar(self, insumo, pais, termino=None, plantilla=None,
                       exigir_precio=True):
        await asyncio.sleep(0)
        self.llamadas.append({"insumo": insumo, "pais": pais,
                              "termino": termino, "plantilla": plantilla,
                              "exigir_precio": exigir_precio})

        class Extraccion:
            pass

        e = Extraccion()
        e.producto = ProductoSchema(nombre="Quinoa Bio 500g", precio=4.99,
                                    moneda=self.moneda)
        e.fuente_url = "https://www.rewe.de/p/quinoa"
        e.html_capturado = "{}"

        class Resultado:
            pass

        r = Resultado()
        r.productos_encontrados = [e]
        r.errores = []
        r.tiempo_total_ms = 1234
        return r


class TestCatalogoAlemania:
    def test_buscar_sync_funciona_dentro_de_un_bucle_de_eventos(self):
        """La etapa 2b es síncrona pero corre DENTRO de la petición, con un
        bucle ya en marcha. Un `asyncio.run` puesto sin más ahí lanza 'cannot
        be called from a running event loop'."""
        from adaptadores.catalogo_alemania import CatalogoAlemania

        catalogo = CatalogoAlemania(agente=AgenteFalso())

        async def desde_dentro_del_bucle():
            return catalogo.buscar_sync("Quinoa")

        ofertas = asyncio.run(desde_dentro_del_bucle())
        assert len(ofertas) == 1
        assert ofertas[0].tienda == "REWE"

    def test_se_busca_en_aleman(self):
        """Tavily devuelve lo que se le pide en el idioma en que se le pide.
        Una consulta en castellano sobre tiendas alemanas trae artículos de
        prensa, no fichas con precio."""
        from adaptadores.catalogo_alemania import CatalogoAlemania
        from casos_de_uso.agente.agente import PLANTILLA_BUSQUEDA_DE

        agente = AgenteFalso()
        CatalogoAlemania(agente=agente).buscar_sync("Quinoa", 5, "quinua")

        llamada = agente.llamadas[0]
        assert llamada["termino"] == "Quinoa"
        assert llamada["plantilla"] == PLANTILLA_BUSQUEDA_DE
        assert llamada["pais"] == "Deutschland"

    def test_sin_moneda_en_la_ficha_se_asume_la_del_mercado(self):
        """Es una propiedad del mercado —tiendas alemanas vendiendo en
        Alemania—, no una deducción sobre la página."""
        from adaptadores.catalogo_alemania import CatalogoAlemania

        catalogo = CatalogoAlemania(agente=AgenteFalso(moneda=None))
        assert catalogo.buscar_sync("Quinoa")[0].producto.moneda == MONEDA

    def test_si_la_ficha_declara_moneda_manda_la_ficha(self):
        """Un producto en francos suizos en una tienda alemana existe, y
        sobrescribirlo a EUR convertiría mal la cifra."""
        from adaptadores.catalogo_alemania import CatalogoAlemania

        catalogo = CatalogoAlemania(agente=AgenteFalso(moneda="CHF"))
        assert catalogo.buscar_sync("Quinoa")[0].producto.moneda == "CHF"

    def test_sin_termino_no_se_llama_al_agente(self):
        from adaptadores.catalogo_alemania import CatalogoAlemania

        agente = AgenteFalso()
        assert CatalogoAlemania(agente=agente).buscar_sync("") == []
        assert agente.llamadas == []


# ---------------------------------------------------------------------------
# La etapa 2b
# ---------------------------------------------------------------------------

class TestEtapa2b:
    def _interpretado(self, aleman=None):
        from dominio.insumo import InsumoInterpretado
        return InsumoInterpretado(
            insumo_normalizado="quinua", reconocible=True,
            sinonimos_busqueda=["quinoa"], terminos_ingles=["quinoa"],
            terminos_aleman=aleman if aleman is not None else ["Quinoa"])

    def _dependencias(self, ofertas):
        from casos_de_uso.dependencias import Dependencias
        return Dependencias(redactor=None, catalogo=None, cache=None,
                            informes=None, auditoria=None, ofertas=ofertas)

    def test_el_mapa_lleva_las_ofertas_alemanas(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, _ = _gondola([OfertaCruda("Quinoa Bio", 4.99, "REWE")])
        mapa = mapear_comercio(self._dependencias(gondola), self._interpretado())

        assert len(mapa.ofertas_alemania) == 1
        assert mapa.ofertas_alemania[0].tienda == "REWE"

    def test_van_en_su_propia_lista_y_no_con_las_peruanas(self):
        """Dos listas y no una con columna «país»: se leen por separado, y
        mezclarlas obligaría a filtrar para leer cualquiera de las dos."""
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, _ = _gondola([OfertaCruda("Quinoa Bio", 4.99, "REWE")])
        mapa = mapear_comercio(self._dependencias(gondola), self._interpretado())

        assert mapa.ofertas_peru == []
        assert len(mapa.ofertas_alemania) == 1

    def test_sin_termino_aleman_la_etapa_corre_igual(self):
        """El modelo puede no saber traducir el insumo. La tabla alemana sale
        vacía y el resto del informe no se entera."""
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, catalogo = _gondola([OfertaCruda("Quinoa", 4.99, "REWE")])
        mapa = mapear_comercio(self._dependencias(gondola),
                               self._interpretado(aleman=[]))

        assert mapa.ofertas_alemania == []
        assert catalogo.llamadas == []

    def test_sin_adaptador_de_ofertas_la_etapa_corre_igual(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        mapa = mapear_comercio(self._dependencias(None), self._interpretado())
        assert mapa.ofertas_alemania == []
