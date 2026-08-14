"""
Gate T4 — mapeo de categoría, orquestación, concurrencia y caché.

El agente de EE. UU. se sustituye por un doble en toda la suite. No es por
ahorrar: es que T4 no aporta nada nuevo sobre el eCFR —eso ya lo probó T1— y en
cambio sí tiene que demostrar tres cosas que solo se ven con un doble delante:
que los aditivos se evalúan **a la vez**, que la caché **evita la segunda
llamada**, y que un `SIN_DATO` **no se cachea**.
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest

from casos_de_uso.analizar_aditivos_mercados import (
    TTL_CACHE,
    AnalizadorAditivos,
)
from dominio.analisis_aditivos import MERCADOS, EvaluacionMercado
from etl.analizar_ingredientes import codigos_aditivos
from etl.mapear_categoria import MAPA, mapear, normalizar, segmentos

URL = "https://www.ecfr.gov/current/title-21"


def _celda(mercado="US", veredicto="SI", **cambios):
    base = dict(
        mercado=mercado, autorizado=veredicto, referencia_texto="21 CFR § 1",
        referencia_url=URL, cita_literal="texto de la norma",
        origen={"US": "AGENTE_ECFR", "EU": "ANEXO_II",
                "CODEX": "CURADO_CODEX"}[mercado])
    if veredicto == "SIN_DATO":
        base["cita_literal"] = ""
    return EvaluacionMercado(**{**base, **cambios})


class AgenteDoble:
    """Cuenta llamadas y tarda lo que se le diga."""

    def __init__(self, tardanza=0.0, veredicto="SI"):
        self.llamadas: list[tuple] = []
        self._tardanza = tardanza
        self._veredicto = veredicto

    async def evaluar(self, termino_en, matriz_en=None, nombre_es=None):
        self.llamadas.append((termino_en, matriz_en))
        if self._tardanza:
            await asyncio.sleep(self._tardanza)
        return _celda("US", self._veredicto)


class EvaluadorDoble:
    def __init__(self, mercado, veredicto="SI"):
        self._mercado, self._veredicto = mercado, veredicto

    def evaluar(self, *args, **kwargs):
        return _celda(self._mercado, self._veredicto)


class CacheDoble(dict):
    def __init__(self):
        super().__init__()
        self.lecturas = self.escrituras = 0

    def obtener(self, clave):
        self.lecturas += 1
        return self.get(clave)

    def guardar(self, clave, valor, **extra):
        self.escrituras += 1
        self[clave] = valor


def _analizador(**cambios):
    base = dict(agente_us=AgenteDoble(),
                evaluador_ue=EvaluadorDoble("EU"),
                evaluador_codex=EvaluadorDoble("CODEX"))
    return AnalizadorAditivos(**{**base, **cambios})


class TestCodigosINS:
    """Las etiquetas peruanas declaran por código, no por nombre.

    Medido el 2026-08-14 sobre la góndola de las cadenas de Perú: **21 de 30
    fichas con lista de ingredientes usan códigos INS**, y el lector de nombres
    no encontraba ni uno. Sin esto, la columna de análisis de esas tablas sería
    un botón que abre una pestaña vacía.
    """

    def test_lee_la_forma_peruana_con_parentesis(self):
        assert codigos_aditivos("Leudante sin 500(ii), acidez sin 341(i)") == \
               ["E341(i)", "E500(ii)"]

    def test_lee_la_forma_peruana_sin_parentesis(self):
        """«INS 322i» y «INS 322(i)» son lo mismo y tienen que salir igual."""
        assert codigos_aditivos("INS 322i") == codigos_aditivos("INS 322(i)")

    def test_acepta_ins_sin_y_e(self):
        for prefijo in ("INS", "SIN", "E"):
            assert codigos_aditivos(f"conservante {prefijo} 202") == ["E202"]

    def test_los_romanos_van_entre_parentesis_y_las_letras_pegadas(self):
        """No es cosmético: el corpus agrupa los romanos y separa las letras.

        E500(i) y E500(ii) son especificaciones del mismo aditivo y el Anexo II
        las junta bajo «E 500»; E150a-d son cuatro caramelos distintos. Emitir
        «E500i» produciría una clave que no casa con nada.
        """
        assert codigos_aditivos("INS 500i") == ["E500(i)"]
        assert codigos_aditivos("INS 150d") == ["E150d"]

    def test_la_conjuncion_castellana_no_se_pega_al_codigo(self):
        """«E 330 y E 202» daba «E330y», un aditivo que no existe."""
        assert codigos_aditivos("Contiene E 330 y E 202") == ["E202", "E330"]

    def test_sin_seguido_de_palabra_no_es_un_aditivo(self):
        """«sin azúcares añadidos» y «sin gluten» aparecen en media góndola."""
        assert codigos_aditivos("sin azucares anadidos, sin gluten") == []

    def test_un_numero_con_unidad_no_es_un_aditivo(self):
        assert codigos_aditivos("500 mg de sodio por porcion") == []

    def test_los_numeros_fuera_del_rango_del_codex_se_ignoran(self):
        """Los aditivos del Codex empiezan en 100."""
        assert codigos_aditivos("INS 050") == []

    def test_sin_texto_no_hay_codigos(self):
        assert codigos_aditivos(None) == [] and codigos_aditivos("") == []

    def test_no_repite(self):
        assert codigos_aditivos("sin 500(ii) ... otra vez sin 500(ii)") == ["E500(ii)"]


class TestLecturaMixta:
    """Nombre y código son dos formas de escribir lo mismo, y pueden convivir."""

    @pytest.mark.asyncio
    async def test_el_mismo_aditivo_por_nombre_y_por_codigo_no_se_duplica(self):
        """«Lecitina de soya (INS 322)» son dos lecturas de un solo aditivo.

        Sin deduplicar saldrían dos tarjetas idénticas y se pagarían dos
        consultas al agente por la misma pregunta.
        """
        r = await _analizador().analizar(
            "OFF:1", "X", "Lecitina de soya (INS 322), azucar")
        assert len(r.aditivos) == 1

    @pytest.mark.asyncio
    async def test_se_leen_los_dos_a_la_vez(self):
        r = await _analizador().analizar(
            "OFF:1", "X", "pectina, Antioxidante sin 321, acido citrico")
        numeros = {a.e_number for a in r.aditivos}
        assert numeros == {"E440", "E321", "E330"}


# --- T4.4: el mapeo de categoría -----------------------------------------

class TestMapeoCategoria:
    def test_normaliza_las_etiquetas_crudas_de_off(self):
        """`en:baby-food` es la misma categoría que `Baby food`."""
        assert normalizar("en:baby-food") == "baby food"

    def test_la_ruta_se_recorre_de_lo_concreto_a_lo_general(self):
        """OFF la escribe al revés y el último segmento es el que más dice."""
        assert segmentos("Snacks, Sweet snacks, Biscuits")[0] == "biscuits"

    def test_lo_especifico_gana_a_lo_amplio(self):
        """«Snacks, Sweet snacks, Biscuits» es bollería (07.2), no aperitivo."""
        assert mapear("Snacks, Sweet snacks, Biscuits").codigo_ue == "07.2"

    def test_un_segmento_amplio_mapea_igual_si_no_hay_nada_mejor(self):
        cat = mapear("Snacks")
        assert cat.codigo_ue == "15.1"
        assert cat.nivel == "amplio"

    def test_las_etiquetas_nulas_no_cuentan_como_categoria(self):
        """`undefined` es OFF diciendo «no lo sé», no una categoría."""
        assert mapear("undefined").codigo_ue is None
        assert mapear(None).codigo_ue is None

    def test_recuerda_de_que_segmento_salio(self):
        """Sin esto, la nota del asterisco no puede decir qué se dedujo."""
        assert mapear("Groceries, Jams").segmento == "jams"

    def test_todo_lo_mapeado_esta_marcado_como_deducido(self):
        assert mapear("Jams").deducida
        assert not mapear("").deducida

    def test_el_mapa_no_apunta_a_codigos_inventados(self):
        """Cada destino tiene que existir entre las 116 del Anexo II."""
        pytest.importorskip("lxml")
        from adaptadores.corpus_anexo_ii import RUTA_JSON

        if not RUTA_JSON.exists():
            pytest.skip("sin Anexo II ingerido")
        from adaptadores.corpus_anexo_ii import CorpusAnexoII

        reales = set(CorpusAnexoII().categorias)
        malos = {s: v[0] for s, v in MAPA.items() if v[0] not in reales}
        assert not malos, f"códigos inexistentes: {malos}"


# --- T4.2: orquestación ---------------------------------------------------

class TestOrquestacion:
    @pytest.mark.asyncio
    async def test_un_producto_sin_aditivos_no_es_un_error(self):
        """El 49,8 % del snapshot. Etiqueta limpia, no hueco."""
        r = await _analizador().analizar("OFF:1", "Agua", "Agua mineral")
        assert r.aditivos == []

    @pytest.mark.asyncio
    async def test_sin_texto_de_ingredientes_tampoco(self):
        r = await _analizador().analizar("OFF:1", "X", None)
        assert r.aditivos == [] and r.no_reconocidos == []

    @pytest.mark.asyncio
    async def test_cada_aditivo_trae_los_tres_mercados_en_orden(self):
        r = await _analizador().analizar(
            "OFF:1", "Mermelada", "Fresa, pectina, acido citrico", "Jams")
        assert len(r.aditivos) == 2
        for ad in r.aditivos:
            assert [e.mercado for e in ad.evaluaciones] == list(MERCADOS)

    @pytest.mark.asyncio
    async def test_lo_reconocido_no_aparece_como_no_reconocido(self):
        """Regresión: «Ácido cítrico» no casaba con «acido citrico» sin tildes.

        El ingrediente salía en `no_reconocidos` después de haberse reconocido,
        así que la pestaña decía a la vez que lo conocía y que no.
        """
        r = await _analizador().analizar(
            "OFF:1", "X", "Fresas, acido citrico, agua", "Jams")
        assert "acido citrico" not in [n.lower() for n in r.no_reconocidos]
        assert "Fresas" in r.no_reconocidos

    @pytest.mark.asyncio
    async def test_un_mercado_sin_mecanismo_es_sin_dato_no_prohibido(self):
        r = await _analizador(evaluador_codex=None).analizar(
            "OFF:1", "X", "pectina", "Jams")
        codex = r.aditivos[0].por_mercado("CODEX")
        assert codex.autorizado == "SIN_DATO"
        assert "No se consultó" in codex.nota


class TestAsterisco:
    """Una categoría deducida no puede sostener un `SI` rotundo."""

    @pytest.mark.asyncio
    async def test_la_categoria_deducida_degrada_el_si(self):
        r = await _analizador().analizar("OFF:1", "X", "pectina", "Jams")
        for e in r.aditivos[0].evaluaciones:
            assert e.autorizado == "SI_CONDICIONADO"
            assert "se dedujo" in e.nota

    @pytest.mark.asyncio
    async def test_sin_categoria_no_se_degrada_nada(self):
        """No hay deducción que avisar; el veredicto llega tal cual."""
        r = await _analizador().analizar("OFF:1", "X", "pectina", None)
        assert r.aditivos[0].por_mercado("US").autorizado == "SI"

    @pytest.mark.asyncio
    async def test_un_no_no_se_afloja_por_la_categoria(self):
        """Degradar un «no autorizado» a «quizá» aflojaría lo que no conviene."""
        r = await _analizador(
            evaluador_ue=EvaluadorDoble("EU", "NO")).analizar(
            "OFF:1", "X", "pectina", "Jams")
        assert r.aditivos[0].por_mercado("EU").autorizado == "NO"


class TestConcurrencia:
    @pytest.mark.asyncio
    async def test_los_aditivos_se_evaluan_a_la_vez(self):
        """El número que arregla la latencia de T1.

        Cinco aditivos a 0,2 s en serie serían 1,0 s. En paralelo, ~0,2 s. Con
        los 15-36 s reales del agente, la diferencia es entre 3 minutos y 36
        segundos, que es la diferencia entre poder enseñar la pestaña y no.
        """
        agente = AgenteDoble(tardanza=0.2)
        inicio = time.perf_counter()
        r = await _analizador(agente_us=agente).analizar(
            "OFF:1", "X",
            "pectina, goma xantana, acido citrico, lecitina, goma guar")
        transcurrido = time.perf_counter() - inicio

        assert len(r.aditivos) == 5
        assert transcurrido < 0.5, f"parece serie: {transcurrido:.2f}s"


class TestCache:
    @pytest.mark.asyncio
    async def test_la_segunda_consulta_no_vuelve_a_llamar_al_agente(self):
        agente, cache = AgenteDoble(), CacheDoble()
        analizador = _analizador(agente_us=agente, cache=cache)

        await analizador.analizar("OFF:1", "A", "pectina", "Jams")
        assert len(agente.llamadas) == 1

        inicio = time.perf_counter()
        await analizador.analizar("OFF:2", "B", "pectina", "Jams")
        assert len(agente.llamadas) == 1, "el agente se llamó dos veces"
        assert (time.perf_counter() - inicio) * 1000 < 100

    @pytest.mark.asyncio
    async def test_la_clave_es_el_par_aditivo_matriz_no_el_producto(self):
        """Dos productos distintos con el mismo aditivo comparten respuesta."""
        agente, cache = AgenteDoble(), CacheDoble()
        analizador = _analizador(agente_us=agente, cache=cache)
        await analizador.analizar("OFF:1", "A", "pectina", "Jams")
        await analizador.analizar("OFF:2", "B", "pectina", "Groceries, Jams")
        assert len(agente.llamadas) == 1

    @pytest.mark.asyncio
    async def test_distinta_matriz_es_distinta_pregunta(self):
        agente, cache = AgenteDoble(), CacheDoble()
        analizador = _analizador(agente_us=agente, cache=cache)
        await analizador.analizar("OFF:1", "A", "pectina", "Jams")
        await analizador.analizar("OFF:2", "B", "pectina", "Sodas")
        assert len(agente.llamadas) == 2

    @pytest.mark.asyncio
    async def test_sin_dato_no_se_cachea(self):
        """Un timeout de un minuto no puede vaciar la celda un trimestre."""
        agente, cache = AgenteDoble(veredicto="SIN_DATO"), CacheDoble()
        analizador = _analizador(agente_us=agente, cache=cache)
        await analizador.analizar("OFF:1", "A", "pectina", "Jams")
        assert cache.escrituras == 0

        await analizador.analizar("OFF:2", "B", "pectina", "Jams")
        assert len(agente.llamadas) == 2, "se volvió a preguntar, como debe"

    @pytest.mark.asyncio
    async def test_una_entrada_caducada_se_vuelve_a_preguntar(self):
        agente, cache = AgenteDoble(), CacheDoble()
        analizador = _analizador(agente_us=agente, cache=cache)
        await analizador.analizar("OFF:1", "A", "pectina", "Jams")

        clave = next(iter(cache))
        vieja = datetime.now(timezone.utc) - TTL_CACHE - timedelta(days=1)
        cache[clave]["verificado_en"] = vieja.isoformat()

        await analizador.analizar("OFF:2", "B", "pectina", "Jams")
        assert len(agente.llamadas) == 2

    @pytest.mark.asyncio
    async def test_una_cache_corrupta_no_tumba_el_analisis(self):
        """Se ignora la entrada y se pregunta, que es lo que pasaría sin caché."""
        agente, cache = AgenteDoble(), CacheDoble()
        analizador = _analizador(agente_us=agente, cache=cache)
        cache["ecfr:pectin|jam"] = {"esto": "no es una evaluación"}
        r = await analizador.analizar("OFF:1", "A", "pectina", "Jams")
        assert r.aditivos[0].por_mercado("US").autorizado == "SI_CONDICIONADO"
