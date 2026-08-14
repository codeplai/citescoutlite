"""
Gate T1 — el agente regulatorio de EE. UU.

Tres capas, y el reparto no es casual:

1. **Puras.** Ordenación, grounding y mapeo a veredicto. Sin red y sin modelo:
   son las que fijan la política, y la política tiene que poder comprobarse sin
   pagar una llamada ni depender de que la FDA esté en pie.
2. **Corpus.** Contra el fichero de 21,6 MB. Se saltan si no está descargado.
3. **Gate.** Los dos casos de `acido1.pptx` y `acido2.pptx`, de punta a punta.
   Cuestan red y modelo, así que van marcados `integracion`.

El caso que más vigila esta suite es el **falso positivo del grounding**: un
número que el modelo devuelve y que no está en la norma. Es el único fallo de
este módulo que produciría un dato regulatorio inventado con aspecto de
verificado, y por eso tiene tres tests para él solo.
"""

import re

import pytest
from pydantic import ValidationError

from adaptadores.agente_ecfr import (
    AgenteECFR,
    Candidata,
    LecturaSeccion,
    _numero_en,
    _sin_dato,
    _url_de,
)
from adaptadores.corpus_ecfr import RUTA_POR_DEFECTO, CorpusECFR, SeccionCFR
from dominio.analisis_aditivos import (
    MERCADOS,
    AditivoEvaluado,
    AnalisisIngredientes,
    EvaluacionMercado,
)

# Un trozo real de §172.120, con la tabla ya aplanada como la deja `_a_texto`.
TEXTO_EDTA = (
    "§ 172.120 Calcium disodium EDTA. The food additive calcium disodium EDTA "
    "may be safely used in designated foods for the purposes and in accordance "
    "with the conditions prescribed, as follows: (b) It is used or intended for "
    "use as follows: (1) Alone, in the following foods at not to exceed the "
    "levels prescribed, calculated as the anhydrous compound: Food Limitation "
    "(parts per million) Use Cabbage, pickled 220 Promote color, flavor, and "
    "texture retention. Canned carbonated soft drinks 33 Promote flavor "
    "retention. Cucumbers pickled 220 Promote color, flavor, and texture "
    "retention. Egg product that is hard-cooked 1,200 Preservative."
)

SECCION_EDTA = SeccionCFR(
    seccion="172.120", parte="172",
    encabezado="§ 172.120 Calcium disodium EDTA.", texto=TEXTO_EDTA)

SECCION_SORBICO = SeccionCFR(
    seccion="182.3089", parte="182",
    encabezado="§ 182.3089 Sorbic acid.",
    texto="§ 182.3089 Sorbic acid. (a) Product. Sorbic acid. (b) Conditions of "
          "use. This substance is generally recognized as safe when used in "
          "accordance with good manufacturing practice.")


def _lectura(**cambios) -> LecturaSeccion:
    base = dict(cobertura="ALIMENTO_NOMBRADO", alimento_nombrado="Cucumbers pickled",
                limite_valor=220.0, limite_unidad="ppm",
                cita_literal="Cucumbers pickled 220 Promote color, flavor, and "
                             "texture retention.")
    return LecturaSeccion(**{**base, **cambios})


class TestURL:
    def test_construye_la_forma_larga_que_citan_los_pptx(self):
        """La URL tiene que ser la que una persona reconoce al pegarla."""
        url = _url_de({"title": "21", "chapter": "I", "subchapter": "B",
                       "part": "172", "subpart": "B", "section": "172.120"})
        assert url == ("https://www.ecfr.gov/current/title-21/chapter-I/"
                       "subchapter-B/part-172/subpart-B/section-172.120")

    def test_omite_los_niveles_que_no_vienen(self):
        url = _url_de({"title": "21", "part": "182", "section": "182.3089"})
        assert url.endswith("/title-21/part-182/section-182.3089")


class TestNumeroEn:
    """El grounding compara por valor, no por texto. Aquí está el porqué."""

    def test_el_float_del_modelo_casa_con_el_entero_de_la_norma(self):
        """La norma escribe `220`; el modelo devuelve 220.0."""
        assert _numero_en(TEXTO_EDTA.lower(), 220.0)

    def test_casa_con_separador_de_millares(self):
        """`1,200` en la norma es 1200 para el modelo."""
        assert _numero_en(TEXTO_EDTA.lower(), 1200.0)

    def test_un_numero_que_no_esta_no_casa(self):
        """El caso que importa: una cifra plausible que la norma no dice."""
        assert not _numero_en(TEXTO_EDTA.lower(), 365.0)


class TestOrdenacion:
    """La ponderación es multiplicativa a propósito. Ver PESO_PARTE."""

    def test_el_score_manda_sobre_la_parte(self):
        """El fallo medido el 2026-08-13, con sus cifras reales.

        Agrupando por parte, `White mineral oil` (§172.878, score 9,3) salía por
        delante de `Sorbic acid` (§182.3089, score 31,5) solo por estar en la
        parte 172. Se pagaban tres lecturas al modelo para acabar en la que
        estaba clarísima desde el principio.
        """
        ruido = Candidata(seccion="172.878", parte="172",
                          encabezado="White mineral oil", url="u", score=9.3)
        buena = Candidata(seccion="182.3089", parte="182",
                          encabezado="Sorbic acid", url="u", score=31.5)
        assert AgenteECFR._ordenar([ruido, buena])[0].seccion == "182.3089"

    def test_a_puntuacion_pareja_la_norma_de_identidad_cede(self):
        """`French dressing` habla del alimento; §172.120, del aditivo."""
        identidad = Candidata(seccion="169.115", parte="169",
                              encabezado="French dressing", url="u", score=13.0)
        aditivo = Candidata(seccion="172.120", parte="172",
                            encabezado="Calcium disodium EDTA", url="u", score=12.0)
        assert AgenteECFR._ordenar([identidad, aditivo])[0].seccion == "172.120"

    def test_las_partes_ajenas_pesan_menos(self):
        ajena = Candidata(seccion="1.1", parte="1", encabezado="", url="u", score=20.0)
        gras = Candidata(seccion="182.3089", parte="182", encabezado="", url="u", score=10.0)
        assert AgenteECFR._ordenar([ajena, gras])[0].seccion == "182.3089"

    def test_deduplica_quedandose_con_el_score_mas_alto(self):
        """El buscador devuelve una fila por versión de la sección.

        §172.878 salía dos veces (9,3 y 9,0) y cada repetida se comía una de las
        tres lecturas del presupuesto para releer el mismo texto.
        """
        a = Candidata(seccion="172.878", parte="172", encabezado="", url="u", score=9.0)
        b = Candidata(seccion="172.878", parte="172", encabezado="", url="u", score=9.3)
        ordenadas = AgenteECFR._ordenar([a, b])
        assert len(ordenadas) == 1
        assert ordenadas[0].score == 9.3


class TestGrounding:
    """D-2. La regla que separa buscar en la web de inventar con estilo."""

    def test_pasa_cuando_la_cita_y_la_cifra_estan_en_la_norma(self):
        pasa, motivo = AgenteECFR.grounding(SECCION_EDTA, _lectura())
        assert pasa, motivo

    def test_rechaza_una_cita_parafraseada(self):
        """Suena igual y no está escrito así. No pasa."""
        pasa, motivo = AgenteECFR.grounding(SECCION_EDTA, _lectura(
            cita_literal="Los pepinos encurtidos admiten 220 ppm de EDTA"))
        assert not pasa
        assert "cita no está" in motivo

    def test_rechaza_una_cifra_que_la_norma_no_dice(self):
        """El fallo caro: 365 es el límite del Codex, no el del CFR.

        Un modelo que mezcla lo que leyó con lo que sabe produce justo esto: una
        cifra correcta en otro sitio, colocada bajo una cita del CFR.
        """
        pasa, motivo = AgenteECFR.grounding(SECCION_EDTA, _lectura(limite_valor=365.0))
        assert not pasa
        assert "365" in motivo

    def test_rechaza_un_alimento_que_no_aparece(self):
        pasa, motivo = AgenteECFR.grounding(SECCION_EDTA, _lectura(
            alimento_nombrado="Passion fruit pulp"))
        assert not pasa
        assert "Passion fruit pulp" in motivo

    def test_rechaza_cuando_no_hay_cita(self):
        pasa, motivo = AgenteECFR.grounding(SECCION_EDTA, _lectura(cita_literal=""))
        assert not pasa

    def test_los_espacios_de_mas_no_tumban_una_cita_buena(self):
        """El XML del CFR trae saltos de línea donde el modelo pone un espacio."""
        pasa, _ = AgenteECFR.grounding(SECCION_EDTA, _lectura(
            cita_literal="Cucumbers   pickled\n220   Promote color"))
        assert pasa

    def test_bpm_sin_cifra_pasa_igual(self):
        """Sin `limite_valor` no hay número que comprobar, solo la cita."""
        pasa, motivo = AgenteECFR.grounding(SECCION_SORBICO, LecturaSeccion(
            cobertura="GENERAL", limite_unidad="BPM",
            cita_literal="generally recognized as safe when used in accordance "
                         "with good manufacturing practice"))
        assert pasa, motivo


class TestVeredicto:
    """El mapeo de lo que la norma dice a lo que el informe publica."""

    def test_gras_general_es_si_sin_asterisco(self):
        """Caso 1 de los PPTX: sórbico en EE. UU. es SÍ, no SÍ*."""
        assert AgenteECFR._veredicto(
            _lectura(cobertura="GENERAL"), "passion fruit pulp") == "SI"

    def test_alimento_nombrado_es_si_sin_asterisco(self):
        """Caso 2: §172.120 nombra los pepinos, así que la cobertura es directa."""
        assert AgenteECFR._veredicto(_lectura(), "pickled cucumbers") == "SI"

    def test_otros_alimentos_es_no_condicionado_y_no_prohibido(self):
        """La distinción que sostiene el asterisco.

        Que el aditivo esté autorizado para otras categorías **no es una
        prohibición**. Es el caso de la pulpa en la UE, y colapsarlo a `NO`
        haría decir al informe que algo está prohibido cuando no lo está.
        """
        assert AgenteECFR._veredicto(
            _lectura(cobertura="OTROS_ALIMENTOS"), "passion fruit pulp") == "NO_CONDICIONADO"

    def test_sin_matriz_no_se_puede_afirmar_que_no_esta_cubierto(self):
        """No se buscó en la lista, así que no se puede decir que no estaba."""
        assert AgenteECFR._veredicto(
            _lectura(cobertura="OTROS_ALIMENTOS"), None) == "SI_CONDICIONADO"

    def test_sin_matriz_un_alimento_nombrado_queda_condicionado(self):
        assert AgenteECFR._veredicto(_lectura(), None) == "SI_CONDICIONADO"

    def test_prohibido_es_no(self):
        assert AgenteECFR._veredicto(_lectura(cobertura="PROHIBIDO"), "x") == "NO"

    def test_no_trata_es_sin_dato(self):
        assert AgenteECFR._veredicto(_lectura(cobertura="NO_TRATA"), "x") == "SIN_DATO"


class TestSinDato:
    def test_no_promete_una_seccion_que_no_verifico(self):
        """Apunta al título, no a una sección: es donde seguiría una persona."""
        e = _sin_dato("sorbic acid", "la búsqueda no devolvió nada")
        assert e.autorizado == "SIN_DATO"
        assert e.limite_valor is None
        assert str(e.referencia_url).rstrip("/").endswith("title-21")

    def test_sin_dato_no_puede_traer_limite(self):
        """Invariante del contrato: sin dato es sin dato, no 'sin límite'."""
        with pytest.raises(ValidationError):
            EvaluacionMercado(
                mercado="US", autorizado="SIN_DATO", limite_valor=220.0,
                referencia_texto="x", referencia_url="https://e.gov",
                origen="AGENTE_ECFR")


class TestContrato:
    def test_un_veredicto_exige_su_cita(self):
        """D-2 como invariante del tipo, no como buena intención."""
        with pytest.raises(ValidationError, match="sin cita literal"):
            EvaluacionMercado(
                mercado="US", autorizado="SI", limite_valor=220.0,
                limite_unidad="ppm", referencia_texto="21 CFR § 172.120",
                referencia_url="https://www.ecfr.gov/current/title-21",
                cita_literal="", origen="AGENTE_ECFR")

    def test_faltar_un_mercado_no_es_una_lista_corta(self):
        """Una tarjeta que falta se lee como 'no aplica'. No es lo mismo."""
        solo_us = EvaluacionMercado(
            mercado="US", autorizado="SI", limite_unidad="BPM",
            referencia_texto="21 CFR § 182.3089",
            referencia_url="https://www.ecfr.gov/current/title-21",
            cita_literal="generally recognized as safe", origen="AGENTE_ECFR")
        with pytest.raises(ValidationError, match="SIN_DATO"):
            AditivoEvaluado(nombre="Ácido sórbico", evaluaciones=[solo_us])

    def test_limite_interno_es_el_minimo_de_los_que_autorizan(self):
        """Paso 6 de la metodología: una formulación para varios destinos."""
        aditivo = _tres_mercados(us=1000.0, codex=365.0, eu=None)
        assert aditivo.limite_interno == 365.0
        assert aditivo.limite_interno_unidad == "mg/kg"

    def test_bpm_no_vota_en_el_minimo(self):
        """Sin cifra no hay techo; contarlo como 0 o infinito rompe el mínimo."""
        aditivo = _tres_mercados(us="BPM", codex=1000.0, eu=None)
        assert aditivo.limite_interno == 1000.0

    def test_un_mercado_que_prohibe_no_aporta_limite(self):
        """Su respuesta es reformular, no un número bajo."""
        aditivo = _tres_mercados(us=220.0, codex=365.0, eu="NO")
        assert aditivo.limite_interno == 220.0
        assert aditivo.exige_reformular

    def test_sin_ninguna_cifra_el_limite_interno_es_none(self):
        aditivo = _tres_mercados(us="BPM", codex=None, eu=None)
        assert aditivo.limite_interno is None

    def test_analisis_sin_aditivos_es_valido(self):
        """El 49,8 % del snapshot. Etiqueta limpia, no error."""
        a = AnalisisIngredientes(producto_id="OFF:1", producto_nombre="Agua")
        assert a.aditivos == []
        assert not a.hay_prohibiciones


def _celda(mercado, valor, *, origen="CURADO_CODEX") -> EvaluacionMercado:
    """Una celda de prueba. `valor` es cifra, 'BPM', 'NO' o None."""
    comun = dict(mercado=mercado, referencia_texto=f"ref {mercado}",
                 referencia_url="https://www.ecfr.gov/current/title-21",
                 origen=origen)
    if valor == "NO":
        return EvaluacionMercado(autorizado="NO", cita_literal="prohibido", **comun)
    if valor == "BPM":
        return EvaluacionMercado(autorizado="SI", limite_unidad="BPM",
                                 cita_literal="good manufacturing practice", **comun)
    if valor is None:
        return EvaluacionMercado(autorizado="SIN_DATO", **comun)
    return EvaluacionMercado(autorizado="SI", limite_valor=valor,
                             limite_unidad="mg/kg", cita_literal="límite", **comun)


def _tres_mercados(*, us, codex, eu) -> AditivoEvaluado:
    return AditivoEvaluado(
        nombre="Prueba",
        evaluaciones=[_celda(m, v) for m, v in zip(MERCADOS, (us, codex, eu))])


# --- Capa 2: contra el corpus de 21,6 MB ---------------------------------

corpus_descargado = pytest.mark.skipif(
    not RUTA_POR_DEFECTO.exists(),
    reason="Sin corpus del eCFR; ejecuta `python -m etl.ingerir_ecfr`")


@pytest.fixture(scope="module")
def corpus():
    """Se parsea una vez por módulo: 21,6 MB no se releen por test."""
    return CorpusECFR()


@corpus_descargado
class TestCorpus:
    def test_trae_la_parte_172_que_le_faltaba_al_rag(self, corpus):
        """El corpus RAG anterior tenía 336 secciones y ninguna de la 172."""
        assert corpus.partes().get("172", 0) > 100

    def test_edta_con_su_tabla_de_alimentos(self, corpus):
        """La fila exacta que cita `acido2.pptx`."""
        seccion = corpus.seccion("172.120")
        assert seccion is not None
        assert "Cucumbers pickled 220" in seccion.texto

    def test_sorbico_es_gras_por_buenas_practicas(self, corpus):
        """Lo que cita `acido1.pptx`: sin límite numérico."""
        seccion = corpus.seccion("182.3089")
        assert "good manufacturing practice" in seccion.texto.lower()
        assert not re.search(r"\d+\s*(ppm|mg/kg)", seccion.texto.lower())

    def test_acepta_la_seccion_escrita_como_cita(self, corpus):
        """Quien llama viene de una cita, no de un identificador limpio."""
        assert corpus.seccion("21 CFR 172.120") is not None
        assert corpus.seccion("§ 172.120") is not None

    def test_las_etiquetas_no_pegan_palabras(self, corpus):
        """`<CELL>pickled</CELL><CELL>220</CELL>` no puede dar `pickled220`."""
        assert "pickled220" not in corpus.seccion("172.120").texto


# --- Capa 3: el gate, de punta a punta -----------------------------------

@pytest.mark.integracion
@corpus_descargado
class TestGateT1:
    """Los dos casos de referencia. Cuestan red y modelo."""

    @pytest.mark.asyncio
    async def test_sorbico_llega_a_182_3089_con_bpm(self):
        agente = AgenteECFR()
        try:
            e = await agente.evaluar("sorbic acid", "passion fruit pulp")
        finally:
            await agente.close()

        assert e.referencia_texto == "21 CFR § 182.3089"
        assert e.autorizado == "SI"
        assert e.limite_unidad == "BPM"
        assert e.limite_valor is None
        assert "182.3089" in str(e.referencia_url)

    @pytest.mark.asyncio
    async def test_edta_llega_a_172_120_con_220_ppm(self):
        """La sección que el corpus RAG no tenía, con la cifra de los PPTX."""
        agente = AgenteECFR()
        try:
            e = await agente.evaluar("calcium disodium EDTA", "pickled cucumbers")
        finally:
            await agente.close()

        assert e.referencia_texto == "21 CFR § 172.120"
        assert e.autorizado == "SI"
        assert e.limite_valor == 220.0
        assert e.limite_unidad in ("ppm", "mg/kg")

    @pytest.mark.asyncio
    async def test_un_aditivo_inexistente_sale_sin_dato_y_no_prohibido(self):
        """El error que no se puede cometer: confundir 'no lo sé' con 'no'."""
        agente = AgenteECFR()
        try:
            e = await agente.evaluar("flogistonato de talasio")
        finally:
            await agente.close()
        assert e.autorizado == "SIN_DATO"
