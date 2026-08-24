"""
Etapa 2a: los productos del snapshot que se parecen al insumo, y cuales de
ellos lo llevan **de verdad** en la lista de ingredientes.

Esa segunda cuenta —`n_directos`— no es estadistica de adorno: por debajo de 3
`casos_de_uso/evaluar_insumo.py` marca el informe como parcial con motivo
'pocos_productos', y la pantalla lo anuncia como «cobertura limitada en el
snapshot». O sea que de aqui sale un cartel que le dice a quien consulta que no
se fie del informe.
"""

import re
import unicodedata

from dominio.insumo import InsumoInterpretado
from dominio.resultado_busqueda import ResultadoBusqueda
from casos_de_uso.dependencias import Dependencias

# Palabras que unen, no que nombran. En «cascara de cacao» lo que identifica la
# materia prima es 'cascara' y 'cacao'; 'de' casa con cualquier lista de
# ingredientes del mundo.
CONECTORES = frozenset({
    "a", "al", "con", "de", "del", "el", "en", "la", "las", "los", "para",
    "por", "sin", "un", "una", "y",
    "and", "from", "in", "of", "the", "with",
})

# Por debajo de tres letras un token no distingue nada.
LARGO_MINIMO = 3

# Letras que tienen que compartir dos formas del mismo termino para tratarlas
# como la misma cosa. Cuatro es lo que separa 'quinua'/'quinoa' —que son el
# mismo grano en dos idiomas— de 'quinua'/'galletas', que no.
PREFIJO_VARIANTE = 4


def _sin_tildes(texto: str) -> str:
    """Minusculas y sin diacriticos: 'Cáscara' y 'cascara' son la misma palabra.

    El snapshot mezcla fichas escritas con tilde y sin ella, asi que comparar
    en crudo hacia que 'arándano' no encontrase 'arandano'.
    """
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def _tokens(texto: str) -> list[str]:
    """Las palabras que nombran algo, ya normalizadas."""
    return [t for t in re.findall(r"[a-z]+", _sin_tildes(texto))
            if len(t) >= LARGO_MINIMO and t not in CONECTORES]


def _es_variante(candidato: str, termino: str) -> bool:
    """Si dos palabras son la misma cosa escrita de otra manera.

    Prefijo comun y longitud parecida, las dos condiciones a la vez. Solo el
    prefijo daria 'maca' == 'macarrones'; solo la longitud, 'quinua' == 'quinoa'
    pero tambien 'quinua' == 'harina'.
    """
    if candidato == termino:
        return True
    if len(candidato) < PREFIJO_VARIANTE or len(termino) < PREFIJO_VARIANTE:
        return False
    return (abs(len(candidato) - len(termino)) <= 2
            and candidato[:PREFIJO_VARIANTE] == termino[:PREFIJO_VARIANTE])


def _detectar_uso_directo(ingredientes_texto: str,
                          terminos_busqueda: list[str],
                          insumo_normalizado: str | None = None) -> bool:
    """Si la lista de ingredientes de un producto nombra el insumo.

    ## Por que no basta con buscar los terminos de busqueda tal cual

    Era lo unico que se hacia, y se cae en cuanto la consulta pide una FORMA DE
    PRODUCTO. Medido sobre 'galletas de quinua' (ejecucion fa76f0ca, 200
    productos, todos con texto de ingredientes): la etapa 1 devolvio
    `sinonimos_busqueda = ['galletas de quinua', 'galletas de quinoa',
    'quinoa cookies', 'quinoa biscuits', ...]` y **las ocho frases acertaron
    cero fichas**. Es que no pueden acertar ninguna: una lista de ingredientes
    dice 'harina de quinoa', nunca 'galletas de quinua', porque el producto no
    se lleva a si mismo dentro. El token 'quinoa' suelto, en cambio, sale en
    194 de las 200.

    Resultado: `n_directos = 0`, informe marcado parcial y un cartel de
    «cobertura limitada» encima de una cabecera que decia 200 productos.

    ## La regla

    Dos vias, y basta con una:

    1. **La frase entera**, como siempre. Se conserva intacta porque para un
       insumo de una palabra —que es lo que produce la etapa 1 cuando se
       pregunta por la materia prima a secas, y lo que fija el golden set— es
       exactamente la comparacion correcta.

    2. **Cada parte del insumo, en cualquiera de sus formas.** El insumo
       normalizado es la materia prima; se exige que **todas** sus partes esten
       presentes, cada una en cualquier variante que aparezca en los terminos
       de busqueda. Para 'quinua' hay una sola parte y sus variantes son
       {quinua, quinoa}: entra. Para 'cascara de cacao' hay dos, y un chocolate
       cualquiera trae 'cacao' pero no 'cascara', asi que **no** entra: la
       cascara no es el cacao, y contarla como uso directo seria peor que la
       cuenta que se quiere arreglar.

    La segunda via solo suma. Sin `insumo_normalizado` la funcion se comporta
    exactamente como antes, que es como la llaman `evals/runner_s2.py` y
    `test/test_e2e_s2.py`: el golden set fija sus propios sinonimos y no tiene
    de donde sacar el insumo normalizado.
    """
    if not ingredientes_texto:
        return False

    texto = _sin_tildes(ingredientes_texto)

    for termino in terminos_busqueda:
        if _sin_tildes(termino) in texto:
            return True

    if not insumo_normalizado:
        return False

    partes = _tokens(insumo_normalizado)
    if not partes:
        return False

    # El vocabulario sale de lo que dijo la etapa 1 y de nada mas: son los
    # nombres del insumo, no palabras sueltas de ningun corpus. Eso acota lo
    # que puede colarse como variante.
    vocabulario = {t for termino in (insumo_normalizado, *terminos_busqueda)
                   for t in _tokens(termino)}

    return all(
        any(variante in texto
            for variante in {parte} | {v for v in vocabulario
                                       if _es_variante(v, parte)})
        for parte in partes
    )


def buscar_productos(d: Dependencias, interpretado: InsumoInterpretado) -> ResultadoBusqueda:
    resultado = d.catalogo.buscar(interpretado.sinonimos_busqueda)

    # Los terminos en ingles entran tambien en la deteccion, aunque la busqueda
    # vectorial no los use: el snapshot es OpenFoodFacts y sus listas de
    # ingredientes estan en su mayoria en ingles. Son de donde salen variantes
    # como 'quinoa' para 'quinua'.
    terminos = [*interpretado.sinonimos_busqueda, *interpretado.terminos_ingles]

    n_directos = 0
    for producto in resultado.productos:
        es_directo = _detectar_uso_directo(producto.ingredientes, terminos,
                                           interpretado.insumo_normalizado)
        producto.usa_insumo_directo = es_directo
        if es_directo:
            n_directos += 1

    resultado.n_directos = n_directos
    return resultado
