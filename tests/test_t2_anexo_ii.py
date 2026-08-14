"""
Gate T2 — el Anexo II de la UE.

Dos capas: puras (la lógica de derivación y de restricción, sin fichero) y de
corpus (contra el JSON ingerido, que se salta si no está). No hay capa de
integración porque **este tier no sale a la red ni llama al modelo**: esa es
justamente la decisión D-1 del plan.

Los tests que más importan aquí no son los que comprueban que algo se encuentra,
sino los tres que comprueban que **no** se afirma de más:

- `test_el_alginico_no_es_un_fosfato` — la derivación de rangos por aritmética
  metería el E 400 dentro de «E 338-452».
- `test_el_sorbico_no_es_un_polialcohol` — regresión del fallo que tuvo el
  parser de la Parte C: el troceado por offsets metía el E 200 en el Grupo IV.
- `test_la_pulpa_no_se_da_por_excluida_sola` — «pulpa» no es «puré»; que lo sea
  es un juicio y este módulo no juzga.
"""

import time

import pytest

from adaptadores.corpus_anexo_ii import (
    RUTA_JSON,
    CorpusAnexoII,
    _dosis,
    _es_miembro,
    _normaliza_e,
    _nucleo,
    _subcadena_comun,
)
from adaptadores.evaluador_ue import EvaluadorUE, analizar_restriccion, terminos

# La restricción real de E 200-203 en la categoría 04.2.4.1. Es el caso 1 de
# `acido1.pptx` y la frase sobre la que gira todo este tier.
RESTRICCION_04_2_4_1 = (
    "solo preparados de fruta y verdura, incluidos los preparados a base de "
    "algas, las salsas a base de frutas y el áspic, excepto el puré, la mousse, "
    "la compota, las ensaladas y los productos similares en conserva")


class TestDerivacionDeRangos:
    """Los rangos del Anexo II son designaciones colectivas, no intervalos."""

    def test_el_sorbico_pertenece_a_su_familia(self):
        assert _es_miembro("Ácido sórbico", "Ácido sórbico y sorbatos")

    def test_el_sorbato_potasico_tambien(self):
        """El nombre no coincide con el del rango, la familia sí."""
        assert _es_miembro("Sorbato potásico", "Ácido sórbico y sorbatos")

    def test_el_alginico_no_es_un_fosfato(self):
        """El fallo que la expansión aritmética habría cometido.

        `E 338-452` contiene numéricamente al E 400 (ácido algínico), que es un
        espesante y no tiene nada que ver con los fosfatos. Expandir el rango
        como `range(338, 453)` lo habría autorizado en 74 categorías.
        """
        assert not _es_miembro(
            "Ácido algínico", "Ácido fosfórico, fosfatos y polifosfatos")

    def test_el_difosfato_si_es_un_fosfato(self):
        assert _es_miembro("Difosfatos", "Ácido fosfórico, fosfatos y polifosfatos")

    def test_las_palabras_de_relleno_no_hacen_casar_nada(self):
        """Casi todo el Anexo II empieza por «Ácido»; si contara, todo casaría."""
        assert "acido" not in _nucleo("Ácido cítrico")
        assert not _es_miembro("Ácido cítrico", "Ácido fosfórico y fosfatos")

    def test_subcadena_comun(self):
        assert _subcadena_comun("sorbato", "acido sorbico y sorbatos") == 7
        assert _subcadena_comun("alginico", "fosfatos y polifosfatos") < 6


class TestDosis:
    def test_quantum_satis_es_un_limite_no_un_hueco(self):
        """«La cantidad necesaria» es una autorización, como el GRAS del CFR."""
        assert _dosis("quantum satis") == (None, "BPM")

    def test_el_separador_de_millares_espanol_es_un_espacio(self):
        assert _dosis("1 000") == (1000.0, "mg/kg")

    def test_sin_dosis_no_se_inventa_unidad(self):
        assert _dosis("") == (None, None)


class TestNormalizaE:
    @pytest.mark.parametrize("entrada", ["E 200", "e200", "E200", "E 200 (ii)"])
    def test_todas_las_formas_dan_la_misma_clave(self, entrada):
        assert _normaliza_e(entrada) == "E200"


class TestAnalizarRestriccion:
    """La columna que decide el veredicto."""

    def test_sin_restriccion_es_autorizacion_limpia(self):
        assert analizar_restriccion("", set())[0] == "sin_restriccion"

    def test_la_compota_esta_excluida_literalmente(self):
        """Esto no es interpretar: la palabra está en la cláusula de excepto."""
        situacion, motivo = analizar_restriccion(
            RESTRICCION_04_2_4_1, terminos("compota de manzana"))
        assert situacion == "excluido"
        assert "compota" in motivo

    def test_la_pulpa_no_se_da_por_excluida_sola(self):
        """El test que fija la honestidad de este tier.

        La cláusula dice «excepto el puré». La matriz es «pulpa de maracuyá».
        Que una pulpa sea un «producto similar» al puré es un juicio de un
        tecnólogo —probablemente correcto, y es el que hizo `acido1.pptx`— pero
        un juicio. El sistema no lo hace en su nombre: devuelve indeterminado y
        enseña la frase entera.
        """
        situacion, _ = analizar_restriccion(
            RESTRICCION_04_2_4_1, terminos("pulpa de maracuyá"))
        assert situacion == "indeterminado"

    def test_lo_nombrado_en_la_clausula_solo_queda_incluido(self):
        situacion, motivo = analizar_restriccion(
            "solo mermeladas y confituras", terminos("mermelada de fresa"))
        assert situacion == "incluido"
        assert "mermelada" in motivo.lower()

    def test_sin_matriz_no_se_puede_resolver(self):
        """No se buscó nada, así que no se puede afirmar que no estuviera."""
        assert analizar_restriccion(RESTRICCION_04_2_4_1, set())[0] == "indeterminado"

    def test_el_plural_de_la_norma_casa_con_el_singular_de_la_matriz(self):
        situacion, _ = analizar_restriccion(
            "solo purés de fruta", terminos("puré de manzana"))
        assert situacion == "incluido"


class TestTerminos:
    def test_descarta_las_palabras_que_no_distinguen(self):
        assert terminos("preparados de fruta") == {"preparados", "fruta"}

    def test_sin_matriz_no_hay_terminos(self):
        assert terminos(None) == set()


# --- Capa 2: contra el JSON ingerido -------------------------------------

corpus_ingerido = pytest.mark.skipif(
    not RUTA_JSON.exists(),
    reason="Sin el Anexo II; ejecuta `python -m etl.ingerir_anexo_ii`")


@pytest.fixture(scope="module")
def corpus():
    return CorpusAnexoII()


@pytest.fixture(scope="module")
def evaluador(corpus):
    return EvaluadorUE(corpus)


@corpus_ingerido
class TestCorpus:
    def test_las_116_categorias_estan(self, corpus):
        assert len(corpus.categorias) == 116

    def test_el_sorbico_no_es_un_polialcohol(self, corpus):
        """Regresión del fallo del parser de la Parte C.

        El troceado por offsets hacía que la porción del último grupo se
        tragara la sección siguiente («Otros aditivos que pueden regularse»,
        que lista el E 200-203). El Grupo IV pasaba de 7 miembros a 117 y el
        ácido sórbico heredaba la autorización de los polialcoholes.
        """
        datos = __import__("json").loads(RUTA_JSON.read_text(encoding="utf-8"))
        grupo_iv = datos["grupos"]["Grupo IV"]
        assert "E200" not in grupo_iv
        assert "E420" in grupo_iv, "el sorbitol sí es un polialcohol"
        assert len(grupo_iv) < 20, "el Grupo IV son los polialcoholes, no medio anexo"

    def test_el_grupo_i_trae_los_quantum_satis(self, corpus):
        datos = __import__("json").loads(RUTA_JSON.read_text(encoding="utf-8"))
        grupo_i = datos["grupos"]["Grupo I"]
        assert {"E330", "E322", "E300"} <= set(grupo_i)

    def test_el_sorbico_en_la_categoria_del_caso_1(self, corpus):
        """Dos filas, las dos a 1.000 mg/kg, ninguna a quantum satis."""
        usos = corpus.usos("E200", "04.2.4.1")
        assert len(usos) == 2
        assert {u.dosis_valor for u in usos} == {1000.0}
        assert all(u.dosis_unidad == "mg/kg" for u in usos)

    def test_la_restriccion_de_los_pures_esta_entera(self, corpus):
        uso = next(u for u in corpus.usos("E200", "04.2.4.1")
                   if u.entrada == "E 200-203")
        assert "excepto el puré" in uso.restricciones

    def test_el_caramelo_se_encuentra_por_sus_subletras(self, corpus):
        """El snapshot lee «caramel color» y lo llama E150; la norma, E150a-d."""
        assert len(corpus.usos("E150")) > 0

    def test_la_consulta_es_local_y_rapida(self, corpus):
        inicio = time.perf_counter()
        for _ in range(100):
            corpus.usos("E200", "04.2.4.1")
        assert (time.perf_counter() - inicio) / 100 * 1000 < 50


@corpus_ingerido
class TestGateT2:
    """Los dos casos de los PPTX, resueltos sin red y sin modelo."""

    def test_caso_1_el_sorbico_en_pulpa_no_sale_como_si_limpio(self, evaluador):
        """`acido1.pptx` concluye NO*. El sistema no puede decir SÍ a secas."""
        e = evaluador.evaluar("E200", "Ácido sórbico", "04.2.4.1",
                              "pulpa de maracuyá")
        assert e.autorizado != "SI"
        assert e.condicionado
        assert e.limite_valor == 1000.0
        assert "puré" in e.cita_literal

    def test_caso_1_la_compota_si_queda_excluida(self, evaluador):
        e = evaluador.evaluar("E200", "Ácido sórbico", "04.2.4.1",
                              "compota de manzana")
        assert e.autorizado == "NO_CONDICIONADO"

    def test_caso_2_el_edta_no_esta_en_la_categoria_de_encurtidos(self, evaluador):
        """`acido2.pptx`: la UE no autoriza el E 385 en pepinos encurtidos."""
        e = evaluador.evaluar("E385", "EDTA cálcico disódico", "04.2.2.4",
                              "pepinos encurtidos")
        assert e.autorizado == "NO_CONDICIONADO"
        assert "otras categorías" in (e.nota or "")

    def test_un_aditivo_del_grupo_i_sale_autorizado_y_marcado(self, evaluador):
        """Y se dice que la cobertura viene por designación colectiva."""
        e = evaluador.evaluar("E330", "Ácido cítrico", "04.2.4.1", "pulpa")
        assert e.autorizado == "SI"
        assert "colectiva" in (e.nota or "")

    def test_lo_que_no_esta_en_el_anexo_sale_sin_dato_no_prohibido(self, evaluador):
        """El error que no se puede cometer.

        El E 960 (glucósidos de esteviol) no está en el 1129/2011 porque la UE
        lo autorizó meses después, con el 1131/2011. Decir «no autorizado»
        sería convertir una laguna de nuestra copia en una prohibición.
        """
        e = evaluador.evaluar("E960", "Glucósidos de esteviol", "04.2.4.1", "pulpa")
        assert e.autorizado == "SIN_DATO"
        assert e.limite_valor is None

    def test_cobertura_de_los_aditivos_del_snapshot(self, corpus):
        """Gate: ≥ 90 % de los 32 aditivos que aparecen en las 29.054 filas."""
        del_snapshot = [
            "E330", "E300", "E322", "E415", "E440", "E412", "E202", "E960",
            "E296", "E331", "E306", "E955", "E270", "E500", "E170", "E160b",
            "E211", "E410", "E407", "E466", "E950", "E150", "E160a", "E508",
            "E220", "E418", "E282", "E339", "E471", "E171", "E951", "E465",
        ]
        con_uso = [e for e in del_snapshot if corpus.usos(e)]
        cobertura = len(con_uso) / len(del_snapshot)
        assert cobertura >= 0.90, (
            f"solo {cobertura:.1%}; sin cobertura: "
            f"{sorted(set(del_snapshot) - set(con_uso))}")
