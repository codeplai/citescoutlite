"""
S8 - La góndola suiza. Lo que la distingue de las otras dos, que es lo que
puede romperse:

1. **Solo entran tiendas suizas.** Es lo específico de este mercado: se busca
   en alemán, y una búsqueda en alemán devuelve sobre todo tiendas alemanas.
   Sin la guarda, la tabla rotulada «Suiza» traería rewe.de con precios en
   euros. Una fila con la etiqueta de un país que no es el suyo es peor que
   una tabla vacía: la vacía se declara, la equivocada se lee como dato.
2. **Se busca con el término alemán**, el mismo que Alemania: Migros, Coop y
   Piccantino publican en alemán. Sin término no se llama al agente.
3. **Las tres góndolas no se pisan.** Alemania y Suiza van las dos por agente
   pero con país y plantilla distintos; con una ranura compartida, la primera
   consulta decidiría en qué país busca la otra.
4. **El franco no lo publica el BCRP.** Su conversión sale del respaldo no
   oficial, y eso tiene que sobrevivir hasta la fila: es la diferencia con el
   euro y lo que la tabla tiene que poder marcar.
"""

import asyncio

import pytest

from adaptadores.catalogo_suiza import MONEDA, es_tienda_suiza, nombre_de_tienda
from adaptadores.ofertas_gondola import OfertasGondola
from casos_de_uso.agente.schemas import ProductoSchema


class OfertaCruda:
    """Lo que devuelve un conector de góndola: producto + procedencia."""

    def __init__(self, nombre, precio, tienda, ean=None, stock=None, moneda="CHF",
                 url=None):
        self.producto = ProductoSchema(
            nombre=nombre, precio=precio, moneda=moneda, ean=ean, stock=stock,
            marca="Marke", unidad="g", categoria="Getreide")
        self.fuente_url = url or f"https://{tienda.lower()}.ch/p/{nombre}"
        self.evidencia = "{}"
        self.tienda = tienda


class CatalogoFalso:
    """Doble de CatalogoSuiza. Registra con qué se le llamó."""

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
    """4,15 soles por franco, que es el orden de magnitud real.

    La fuente dice «no oficial» a propósito, y no es decoración: el BCRP **no
    publica serie de franco suizo** —se barrieron PD04630PD-PD04680PD—, así que
    esta es la única procedencia que puede tener una fila suiza, y la tabla la
    marca. Un doble que dijera «BCRP» probaría un caso que no existe.
    """

    def __init__(self, tasa=4.149443, falla=False,
                 fuente="exchangerate-api.com (no oficial)"):
        self.tasa = tasa
        self.falla = falla
        self.fuente = fuente

    def a_soles(self, precio, moneda):
        if self.falla or precio is None:
            return None

        class R:
            pass

        r = R()
        r.precio_pen = round(precio * self.tasa, 2)
        r.tasa = self.tasa
        r.moneda_origen = moneda
        r.fecha_tasa = "2026-08-13"
        r.fuente = self.fuente
        return r


def _gondola(ofertas=None, revienta=False, cambio=None):
    """La góndola con el conector suizo doblado.

    Las otras dos ranuras se rellenan con dobles vacíos y no se dejan en None:
    con None, cada `de_*` construye su conector de verdad y sale a la red. En
    la alemana eso además lanzaría el agente —minutos y gasto de modelo— cada
    vez que se ejecutara este archivo.
    """
    catalogo = CatalogoFalso(ofertas, revienta)
    gondola = OfertasGondola(catalogo=CatalogoFalso([]),
                             cambio=cambio or CambioFalso(),
                             catalogo_de=CatalogoFalso([]),
                             catalogo_ch=catalogo)
    return gondola, catalogo


# ---------------------------------------------------------------------------
# La guarda de mercado: lo específico de Suiza
# ---------------------------------------------------------------------------

class TestEsTiendaSuiza:
    @pytest.mark.parametrize("url", [
        "https://www.migros.ch/de/product/123",
        "https://www.coop.ch/de/p/quinoa",
        "https://www.piccantino.ch/quinoa",
        "https://shop.migros.ch/p/1",
        "https://biomarkt-huber.ch/p/1",
    ])
    def test_las_suizas_pasan(self, url):
        assert es_tienda_suiza(url)

    @pytest.mark.parametrize("url", [
        "https://www.zwicky.swiss/de/shop/detail/d/bio-quinoa-weiss-knospe",
        "https://tienda.swiss/p/1",
    ])
    def test_el_tld_punto_swiss_tambien(self, url):
        """`.swiss` estaba fuera y costo la unica oferta buena de la pasada del
        2026-08-13: zwicky.swiss se descarto «por no ser de una tienda suiza».
        Es un dominio restringido que administra la Confederacion, asi que como
        senal de pais es mas fuerte que `.ch`, no mas debil."""
        assert es_tienda_suiza(url)

    @pytest.mark.parametrize("url", [
        "https://www.rewe.de/produkte/quinoa",
        "https://www.amazon.de/dp/B01",
        "https://www.alnatura.de/de-de/produkte/x",
        "https://shop.rewe.de/p/quinoa/123",
    ])
    def test_las_alemanas_no(self, url):
        """Es el caso que motiva la guarda: se busca en alemán y el mercado
        alemán domina esos resultados. Sin esto, la tabla «Suiza» sería en
        buena parte alemana, con precios en euros."""
        assert not es_tienda_suiza(url)

    def test_sin_url_no_pasa_y_no_revienta(self):
        assert not es_tienda_suiza("")


class TestNombreDeTienda:
    @pytest.mark.parametrize("url,esperado", [
        ("https://www.migros.ch/de/product/123", "Migros"),
        ("https://www.coop.ch/de/p/quinoa", "Coop"),
        ("https://www.piccantino.ch/quinoa", "Piccantino"),
        ("https://shop.migros.ch/p/1", "Migros"),
    ])
    def test_las_conocidas_salen_con_su_nombre(self, url, esperado):
        assert nombre_de_tienda(url) == esperado

    def test_una_desconocida_sale_con_su_dominio(self):
        """Mejor el dominio que «tienda suiza»: es información real y quien lee
        el informe puede ir a comprobarla."""
        assert nombre_de_tienda("https://www.biomarkt-huber.ch/p/1") == "biomarkt-huber.ch"

    def test_sin_url_no_revienta(self):
        assert nombre_de_tienda("") == "tienda desconocida"


# ---------------------------------------------------------------------------
# Sin término alemán no se busca: esta consulta cuesta dinero
# ---------------------------------------------------------------------------

class TestTerminoAleman:
    def test_sin_termino_no_se_llama_al_agente(self):
        gondola, catalogo = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")])
        assert gondola.de_suiza("arandano", "") == []
        assert catalogo.llamadas == []

    def test_sin_insumo_tampoco(self):
        gondola, catalogo = _gondola()
        assert gondola.de_suiza("", "Quinoa") == []
        assert catalogo.llamadas == []

    def test_se_busca_con_el_termino_no_con_el_insumo(self):
        gondola, catalogo = _gondola([OfertaCruda("Heidelbeeren 200g", 4.9, "Coop")])
        gondola.de_suiza("arandano", "Heidelbeeren")

        termino, _, insumo = catalogo.llamadas[0]
        assert termino == "Heidelbeeren"
        # El insumo viaja igualmente: es la etiqueta del run para la auditoría.
        assert insumo == "arandano"

    def test_falta_de_termino_se_anota(self, caplog):
        with caplog.at_level("INFO"):
            _gondola()[0].de_suiza("arandano", "")
        assert any("gondola suiza" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Fallar aquí tampoco puede tumbar la consulta
# ---------------------------------------------------------------------------

def test_si_el_agente_revienta_la_tabla_sale_vacia():
    """ADR-001: degradar a «sin dato», nunca a error."""
    gondola, _ = _gondola(revienta=True)
    assert gondola.de_suiza("quinua", "Quinoa") == []


def test_el_fallo_se_anota(caplog):
    gondola, _ = _gondola(revienta=True)
    with caplog.at_level("ERROR"):
        gondola.de_suiza("quinua", "Quinoa")
    assert any("tiendas suizas" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# La procedencia: de dónde salió la fila
# ---------------------------------------------------------------------------

def test_la_procedencia_dice_agente():
    """Suiza llega tras una búsqueda web y, cuando no hay JSON-LD, una
    extracción con modelo. Etiquetarla como lectura de catálogo sería falso en
    el único campo que distingue las dos rutas."""
    gondola, _ = _gondola([OfertaCruda("Quinoa Tricolore", 5.5, "Migros")])
    assert gondola.de_suiza("quinua", "Quinoa")[0].procedencia == "agente:Migros"


# ---------------------------------------------------------------------------
# Las tres góndolas comparten objeto pero no conector
# ---------------------------------------------------------------------------

class TestRanurasSeparadas:
    def test_suiza_no_usa_el_catalogo_peruano_ni_el_aleman(self):
        gondola, suiza = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")])
        peru, alemania = gondola._catalogo, gondola._catalogo_de

        gondola.de_suiza("quinua", "Quinoa")

        assert peru.llamadas == []
        assert alemania.llamadas == []
        assert len(suiza.llamadas) == 1

    def test_alemania_no_usa_el_catalogo_suizo(self):
        """Van las dos por agente, y con una ranura compartida la primera
        consulta decidiría en qué país busca la otra."""
        gondola, suiza = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")])
        gondola.de_alemania("quinua", "Quinoa")

        assert suiza.llamadas == []
        assert len(gondola._catalogo_de.llamadas) == 1

    def test_las_tres_en_la_misma_consulta_no_se_mezclan(self):
        from tests.test_s8_ofertas_alemania import OfertaCruda as CrudaDE
        from tests.test_s8_ofertas_gondola import OfertaCruda as CrudaPE

        gondola, _ = _gondola([OfertaCruda("Quinoa 500g", 5.5, "Migros", ean="3")])
        gondola._catalogo = CatalogoFalso([CrudaPE("Quinua 500g", 8.5, "Wong", ean="1")])
        gondola._catalogo_de = CatalogoFalso([CrudaDE("Quinoa 500g", 4.99, "REWE", ean="2")])

        pe = gondola.de_peru("quinua")
        de = gondola.de_alemania("quinua", "Quinoa")
        ch = gondola.de_suiza("quinua", "Quinoa")

        assert [o.tienda for o in pe] == ["Wong"]
        assert [o.tienda for o in de] == ["REWE"]
        assert [o.tienda for o in ch] == ["Migros"]
        assert (pe[0].moneda, de[0].moneda, ch[0].moneda) == ("PEN", "EUR", "CHF")


# ---------------------------------------------------------------------------
# Francos: la conversión, su procedencia y su ausencia
# ---------------------------------------------------------------------------

class TestFrancos:
    def test_el_precio_se_convierte_y_el_original_no_se_pisa(self):
        gondola, _ = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")])
        o = gondola.de_suiza("quinua", "Quinoa")[0]

        assert o.precio == 5.5 and o.moneda == "CHF"
        assert o.precio_pen == 22.82
        assert o.conversion.moneda_origen == "CHF"

    def test_la_conversion_declara_que_no_es_oficial(self):
        """El BCRP no publica franco suizo, así que esta cifra en soles NO sale
        del banco central. Que la fila lo diga es lo que permite a la tabla
        marcarla: una columna «S/» que mezcla banco central y agregador sin
        distinguirlos es justo lo que este informe evita en todo lo demás."""
        gondola, _ = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")])
        c = gondola.de_suiza("quinua", "Quinoa")[0].conversion

        assert "no oficial" in c.fuente
        assert not c.fuente.startswith("BCRP")
        assert c.fecha_tasa == "2026-08-13"

    def test_sin_tasa_la_oferta_conserva_su_precio_en_francos(self):
        gondola, _ = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")],
                              cambio=CambioFalso(falla=True))
        o = gondola.de_suiza("quinua", "Quinoa")[0]

        assert o.precio == 5.5 and o.moneda == "CHF"
        assert o.precio_pen is None and o.conversion is None


# ---------------------------------------------------------------------------
# El orden, que ahora comparten las TRES tablas
# ---------------------------------------------------------------------------

def test_el_mismo_ean_cae_en_filas_contiguas_y_manda_el_precio():
    """`_ordenadas` es lo que convierte la lista en comparación, y la tercera
    tabla tiene que ordenar igual que las otras dos."""
    gondola, _ = _gondola([
        OfertaCruda("Quinoa Tricolore 500g", 6.9, "Migros", ean="7610000000001"),
        OfertaCruda("Anderes", 2.0, "Coop", ean="111"),
        OfertaCruda("Quinoa dreifarbig 500g", 5.5, "Coop", ean="7610000000001"),
        OfertaCruda("Ohne Code", 1.0, "Piccantino"),
    ])
    ofertas = gondola.de_suiza("quinua", "Quinoa")

    assert [o.ean for o in ofertas] == ["111", "7610000000001", "7610000000001", None]
    # Dentro del mismo EAN manda el precio: la fila barata primero.
    assert [o.tienda for o in ofertas[1:3]] == ["Coop", "Migros"]


# ---------------------------------------------------------------------------
# El conector: el puente síncrono, el idioma y el filtro de país
# ---------------------------------------------------------------------------

class AgenteFalso:
    """Imita a AgenteInvestigadorComercial: solo tiene `ejecutar` asíncrono."""

    def __init__(self, fichas=None, moneda=None):
        # (url, nombre). Por defecto, una tienda suiza.
        self.fichas = fichas or [("https://www.migros.ch/de/product/1", "Quinoa Bio 500g")]
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

        extracciones = []
        for url, nombre in self.fichas:
            e = Extraccion()
            e.producto = ProductoSchema(nombre=nombre, precio=5.5, moneda=self.moneda)
            e.fuente_url = url
            e.html_capturado = "{}"
            extracciones.append(e)

        class Resultado:
            pass

        r = Resultado()
        r.productos_encontrados = extracciones
        r.errores = []
        r.tiempo_total_ms = 1234
        return r


class TestCatalogoSuiza:
    def test_buscar_sync_funciona_dentro_de_un_bucle_de_eventos(self):
        """La etapa 2b es síncrona pero corre DENTRO de la petición, con un
        bucle ya en marcha. Un `asyncio.run` puesto sin más ahí lanza 'cannot
        be called from a running event loop'."""
        from adaptadores.catalogo_suiza import CatalogoSuiza

        catalogo = CatalogoSuiza(agente=AgenteFalso())

        async def desde_dentro_del_bucle():
            return catalogo.buscar_sync("Quinoa")

        ofertas = asyncio.run(desde_dentro_del_bucle())
        assert len(ofertas) == 1
        assert ofertas[0].tienda == "Migros"

    def test_se_busca_en_aleman_y_en_suiza(self):
        from adaptadores.catalogo_suiza import CatalogoSuiza
        from casos_de_uso.agente.agente import PLANTILLA_BUSQUEDA_CH

        agente = AgenteFalso()
        CatalogoSuiza(agente=agente).buscar_sync("Quinoa", 5, "quinua")

        llamada = agente.llamadas[0]
        assert llamada["termino"] == "Quinoa"
        assert llamada["plantilla"] == PLANTILLA_BUSQUEDA_CH
        # El país es lo único que separa esta búsqueda de la alemana: la
        # plantilla y el idioma son los mismos.
        assert llamada["pais"] == "Schweiz"

    def test_las_tiendas_alemanas_no_entran_en_la_tabla_suiza(self):
        from adaptadores.catalogo_suiza import CatalogoSuiza

        agente = AgenteFalso(fichas=[
            ("https://www.rewe.de/produkte/quinoa", "Quinoa Bio 500g"),
            ("https://www.migros.ch/de/product/1", "Quinoa Bio 500g"),
            ("https://www.amazon.de/dp/B01", "Quinoa 1kg"),
        ])
        ofertas = CatalogoSuiza(agente=agente).buscar_sync("Quinoa")

        assert [o.tienda for o in ofertas] == ["Migros"]

    def test_el_descarte_por_pais_se_anota(self, caplog):
        """Una tabla vacía no dice si hay que afinar la búsqueda o si el
        producto no se vende allí. El log sí."""
        from adaptadores.catalogo_suiza import CatalogoSuiza

        agente = AgenteFalso(fichas=[("https://www.rewe.de/p/quinoa", "Quinoa")])
        with caplog.at_level("INFO"):
            ofertas = CatalogoSuiza(agente=agente).buscar_sync("Quinoa")

        assert ofertas == []
        assert any("no ser de una tienda suiza" in r.message for r in caplog.records)

    def test_el_limite_cuenta_ofertas_suizas_no_fichas_descartadas(self):
        """Si el límite se aplicara antes del filtro, dos tiendas alemanas en
        cabeza dejarían la tabla vacía teniendo ofertas suizas detrás."""
        from adaptadores.catalogo_suiza import CatalogoSuiza

        agente = AgenteFalso(fichas=[
            ("https://www.rewe.de/p/a", "Quinoa A"),
            ("https://www.edeka.de/p/b", "Quinoa B"),
            ("https://www.coop.ch/de/p/c", "Quinoa C"),
        ])
        ofertas = CatalogoSuiza(agente=agente).buscar_sync("Quinoa", 2)

        assert [o.tienda for o in ofertas] == ["Coop"]

    def test_sin_moneda_en_la_ficha_se_asume_la_del_mercado(self):
        """Es una propiedad del mercado —tiendas suizas vendiendo en Suiza—, no
        una deducción sobre la página."""
        from adaptadores.catalogo_suiza import CatalogoSuiza

        catalogo = CatalogoSuiza(agente=AgenteFalso(moneda=None))
        assert catalogo.buscar_sync("Quinoa")[0].producto.moneda == MONEDA

    def test_si_la_ficha_declara_moneda_manda_la_ficha(self):
        """Una tienda suiza que publique en euros existe —varias sirven a la
        UE— y sobrescribirlo a CHF convertiría mal la cifra."""
        from adaptadores.catalogo_suiza import CatalogoSuiza

        catalogo = CatalogoSuiza(agente=AgenteFalso(moneda="EUR"))
        assert catalogo.buscar_sync("Quinoa")[0].producto.moneda == "EUR"

    def test_sin_termino_no_se_llama_al_agente(self):
        from adaptadores.catalogo_suiza import CatalogoSuiza

        agente = AgenteFalso()
        assert CatalogoSuiza(agente=agente).buscar_sync("") == []
        assert agente.llamadas == []

    def test_no_se_exige_precio_para_entrar_en_la_tabla(self):
        """La gondola pide lo contrario que la cuarentena: alli una fila sin
        precio ocupa un hueco de revision manual sin traer el dato que motiva
        revisarla; aqui «este producto se vende en esta tienda» ya es
        informacion, y la columna tiene su «sin dato» para el resto."""
        from adaptadores.catalogo_suiza import CatalogoSuiza

        agente = AgenteFalso()
        CatalogoSuiza(agente=agente).buscar_sync("Quinoa")
        assert agente.llamadas[0]["exigir_precio"] is False


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

    def test_el_mapa_lleva_las_ofertas_suizas(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, _ = _gondola([OfertaCruda("Quinoa Bio", 5.5, "Migros")])
        mapa = mapear_comercio(self._dependencias(gondola), self._interpretado())

        assert len(mapa.ofertas_suiza) == 1
        assert mapa.ofertas_suiza[0].tienda == "Migros"

    def test_van_en_su_propia_lista_y_no_con_las_otras(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, _ = _gondola([OfertaCruda("Quinoa Bio", 5.5, "Migros")])
        mapa = mapear_comercio(self._dependencias(gondola), self._interpretado())

        assert mapa.ofertas_peru == []
        assert mapa.ofertas_alemania == []
        assert len(mapa.ofertas_suiza) == 1

    def test_se_consulta_con_el_mismo_termino_aleman_que_alemania(self):
        """No hay `terminos_suizo`: Migros, Coop y Piccantino publican en
        alemán y es la región lingüística más grande del país."""
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, suiza = _gondola([OfertaCruda("Heidelbeeren", 4.9, "Coop")])
        mapear_comercio(self._dependencias(gondola),
                        self._interpretado(aleman=["Heidelbeeren", "Blaubeeren"]))

        assert suiza.llamadas[0][0] == "Heidelbeeren"

    def test_sin_termino_aleman_la_etapa_corre_igual(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        gondola, suiza = _gondola([OfertaCruda("Quinoa", 5.5, "Migros")])
        mapa = mapear_comercio(self._dependencias(gondola),
                               self._interpretado(aleman=[]))

        assert mapa.ofertas_suiza == []
        assert suiza.llamadas == []

    def test_sin_adaptador_de_ofertas_la_etapa_corre_igual(self):
        from casos_de_uso.etapas.mapear_comercio import mapear_comercio

        mapa = mapear_comercio(self._dependencias(None), self._interpretado())
        assert mapa.ofertas_suiza == []
