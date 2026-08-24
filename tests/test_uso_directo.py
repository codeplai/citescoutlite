"""
Etapa 2a - `n_directos` cuando la consulta pide una forma de producto.

De esta cuenta sale un cartel: por debajo de 3, `evaluar_insumo` marca el
informe como parcial con motivo 'pocos_productos' y la pantalla escribe
«cobertura limitada en el snapshot».

Lo que se arregla aqui esta medido sobre la ejecucion fa76f0ca ('galletas de
quinua', 200 productos del snapshot, todos con texto de ingredientes):

    frases enteras de `sinonimos_busqueda` ...... 0 de 200
    token 'quinoa' ............................ 194 de 200
    token 'galletas' / 'cookies' / 'biscuits' ... 0 de 200

Es decir: las frases no fallaban por poco, no podian acertar. Una lista de
ingredientes dice 'harina de quinoa'; jamas dice 'galletas de quinua', porque
el producto no se lleva a si mismo dentro.
"""

import pytest

from casos_de_uso.etapas.buscar_productos import _detectar_uso_directo, _es_variante

# Salida literal de la etapa 1 para 'galletas de quinua' en la ejecucion
# fa76f0ca. No es un ejemplo inventado: es lo que el modelo devolvio.
SINONIMOS_GALLETAS = [
    "galletas de quinua", "galletas de quinoa", "quinoa cookies",
    "quinoa biscuits", "cookies de quinua", "biscuits de quinua",
    "quinua horneada en galletas", "galletas con quinua",
]

# Ingredientes reales de dos de esos 200 productos.
INGREDIENTES_EN = ("flour blend (gluten-free oat, garbanzo/chickpea, potato "
                   "starch, quinoa), cane sugar, palm oil")
INGREDIENTES_ES = "Harina de quinoa, Azúcar rubia, Manteca vegetal, Maicena, Huevo"


class TestFormaDeProducto:
    def test_la_frase_entera_no_acierta_ninguna_ficha(self):
        """El fallo original, fijado para que no vuelva disfrazado de mejora."""
        assert _detectar_uso_directo(INGREDIENTES_EN, SINONIMOS_GALLETAS) is False
        assert _detectar_uso_directo(INGREDIENTES_ES, SINONIMOS_GALLETAS) is False

    def test_con_el_insumo_normalizado_si_lo_reconoce(self):
        assert _detectar_uso_directo(INGREDIENTES_EN, SINONIMOS_GALLETAS, "quinua")
        assert _detectar_uso_directo(INGREDIENTES_ES, SINONIMOS_GALLETAS, "quinua")

    def test_cruza_el_idioma_por_las_variantes_de_los_sinonimos(self):
        """'quinua' encuentra 'quinoa' porque 'quinoa' esta en los sinonimos.

        El snapshot es OpenFoodFacts y sus ingredientes estan casi todos en
        ingles: sin este puente, el insumo en castellano no acierta nada.
        """
        assert _detectar_uso_directo("quinoa flour, sugar", ["quinoa"], "quinua")
        # Sin ningun sinonimo del que sacar la variante, no se inventa.
        assert not _detectar_uso_directo("quinoa flour, sugar", ["mango"], "quinua")

    def test_las_palabras_de_la_forma_no_cuentan(self):
        """'galletas' esta en los sinonimos, pero no es la materia prima."""
        assert not _detectar_uso_directo(
            "galletas de trigo, azúcar, mantequilla", SINONIMOS_GALLETAS, "quinua")


class TestInsumoDeVariasPalabras:
    """Un insumo compuesto exige TODAS sus partes, y esto no es un detalle.

    'cascara de cacao' contra un chocolate: trae 'cacao' pero no 'cascara'. Dar
    eso por uso directo seria cambiar un cartel equivocado ('no hay cobertura'
    con 200 productos) por otro peor: decir que 36 chocolates usan cascarilla
    de cacao.
    """

    SINONIMOS_CACAO = ["cáscara de cacao", "cascarilla de cacao", "cocoa shell"]

    def test_el_chocolate_no_usa_cascara_de_cacao(self):
        assert not _detectar_uso_directo(
            "azúcar, pasta de cacao, manteca de cacao, lecitina",
            self.SINONIMOS_CACAO, "cáscara de cacao")

    def test_el_que_si_la_lleva_entra(self):
        assert _detectar_uso_directo(
            "harina de trigo, cascara de cacao molida, sal",
            self.SINONIMOS_CACAO, "cáscara de cacao")


class TestCompatibilidad:
    """Sin `insumo_normalizado` la funcion se comporta como siempre.

    Es la firma con la que la llaman `evals/runner_s2.py` y
    `test/test_e2e_s2.py`: el golden set fija sus propios sinonimos y no tiene
    de donde sacar el insumo normalizado. Que esa via no se mueva es lo que
    garantiza que el 5/5 de T7.1 siga midiendo lo mismo.
    """

    @pytest.mark.parametrize("sinonimos,ingredientes", [
        (["arándano", "arandano", "blueberry", "blueberries"], "sugar, blueberries, pectin"),
        (["mango", "mangoes"], "mango puree, water"),
        (["quinua", "quinoa"], "quinoa, sea salt"),
    ])
    def test_los_sinonimos_de_una_palabra_siguen_acertando(self, sinonimos, ingredientes):
        assert _detectar_uso_directo(ingredientes, sinonimos)
        # Y dan lo mismo con y sin insumo: la via 2 solo suma.
        assert _detectar_uso_directo(ingredientes, sinonimos, sinonimos[0])

    def test_sin_ingredientes_no_hay_uso_directo(self):
        assert not _detectar_uso_directo("", ["quinua"], "quinua")
        assert not _detectar_uso_directo(None, ["quinua"], "quinua")

    def test_las_tildes_no_separan_la_misma_palabra(self):
        assert _detectar_uso_directo("pulpa de arandano", ["arándano"])


class TestEsVariante:
    @pytest.mark.parametrize("a,b", [
        ("quinoa", "quinua"),     # el mismo grano en dos idiomas
        ("mangoes", "mango"),     # plural ingles
        ("cascaras", "cascara"),  # plural castellano
    ])
    def test_reconoce_la_misma_palabra(self, a, b):
        assert _es_variante(a, b)

    @pytest.mark.parametrize("a,b", [
        ("galletas", "quinua"),     # forma de producto, no materia prima
        ("cookies", "quinua"),
        ("harina", "quinua"),
        ("macarrones", "maca"),     # comparte prefijo pero no es lo mismo
        ("cocoa", "cacao"),         # no comparten prefijo: se prefiere no acertar
    ])
    def test_no_junta_lo_que_no_es(self, a, b):
        assert not _es_variante(a, b)
