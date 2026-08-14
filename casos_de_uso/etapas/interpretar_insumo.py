"""Etapa 1: qué insumo es y cómo buscarlo."""

import unicodedata

from casos_de_uso.dependencias import Dependencias
from dominio.insumo import InsumoInterpretado


def _sin_tildes(texto: str) -> str:
    plano = unicodedata.normalize("NFD", texto.strip().lower())
    return "".join(c for c in plano if unicodedata.category(c) != "Mn")


def forma_de_producto(texto: str, insumo_normalizado: str) -> str | None:
    """Lo que pidió quien consulta, si pidió algo más que el insumo.

    ## Por qué esto no lo decide el modelo

    Se intentó: un campo en el esquema de la etapa 1 y la regla en el prompt,
    primero en abstracto y luego con seis ejemplos literales. Acertó **1 de 4**
    y luego **4 de 6**, y —lo que lo descarta— **fallando en casos distintos
    cada vez**: 'galletas de quinua' se rellenó en una pasada y quedó a null en
    la siguiente, con el mismo prompt.

    Un tercio de las consultas daría el listado genérico sin que nada avise, y
    quien busca «barras de quinua» y recibe bolsas de grano no tiene forma de
    saber si es que la tienda no las vende o que la búsqueda se redujo.

    La pregunta es mecánica —¿el texto trae algo más que el insumo?— y una
    comparación de cadenas la responde siempre igual. No hace falta un modelo
    para eso, y ponerlo introduce una variable donde no había ninguna.

    ## La regla

    Si el texto tal cual difiere del insumo normalizado, es que trae algo más:
    una forma ('barras de'), una preparación ('harina de') o el nombre local
    del insumo. Los tres casos se buscan mejor con el texto del usuario.

        'quinua'           / 'quinua'             -> None, se pidió el insumo
        'barras de quinua' / 'quinua'             -> 'barras de quinua'
        'cascara de cacao' / 'cáscara de cacao'   -> None, solo cambian tildes
        'aceite de palta'  / 'aceite de aguacate' -> 'aceite de palta'

    El último es el que justifica comparar contra el texto y no contra una
    lista de formas conocidas: 'palta' es como se llama aquí, y es con lo que
    hay que buscar en una tienda peruana aunque el insumo se normalice a
    'aguacate'.
    """
    if not texto or not insumo_normalizado:
        return None
    if _sin_tildes(texto) == _sin_tildes(insumo_normalizado):
        return None
    return texto.strip()


async def interpretar_insumo(d: Dependencias, texto: str) -> InsumoInterpretado:
    interpretado = await d.redactor.interpretar(texto)

    # Se sobrescribe lo que haya dicho el modelo, a propósito: el campo sigue
    # en el esquema —quitarlo obligaría a un modelo aparte solo para esto— pero
    # quien manda es la regla de arriba. Ver su docstring.
    return interpretado.model_copy(update={
        "forma_producto": forma_de_producto(texto, interpretado.insumo_normalizado),
    })
