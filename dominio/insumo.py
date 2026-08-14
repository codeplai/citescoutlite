from typing import Optional

from pydantic import BaseModel, Field

class InsumoInterpretado(BaseModel):
    insumo_normalizado: str
    reconocible: bool
    #: La forma de PRODUCTO TERMINADO que pidió quien consulta, si pidió una.
    #:
    #: `insumo_normalizado` reduce a la materia prima, y eso es correcto para
    #: casi todo el informe: el snapshot, la taxonomía de CITE y el precio
    #: mayorista de MIDAGRI se indexan por el insumo, no por el producto.
    #:
    #: Pero la góndola pregunta otra cosa. Quien escribe «barras de quinua»
    #: quiere barras, y buscando «quinua» en un supermercado sale el grano a
    #: granel. Medido: `'barras de quinua'` → `insumo_normalizado='quinua'`, y
    #: la tabla salía llena de quinua suelta.
    #:
    #: No se resuelve con `sinonimos_busqueda`. En una consulta real —`'barra
    #: quinua'`— la lista fue `['quinua', 'quinoa', 'quinoa grano',
    #: 'chenopodium quinoa']`: la forma de producto se había perdido y el
    #: término más largo era el nombre botánico, que en un supermercado no
    #: encuentra nada.
    #:
    #: None es el estado normal y correcto: significa que se preguntó por el
    #: insumo a secas y la góndola busca por él.
    forma_producto: Optional[str] = Field(
        None,
        description="Si la consulta pide una FORMA DE PRODUCTO TERMINADO y no "
                    "el insumo a secas, el término tal como se buscaría en un "
                    "supermercado: 'barras de quinua', 'galletas de quinua', "
                    "'harina de maca', 'aceite de palta'. Deja None si se "
                    "preguntó por el insumo sin forma ('quinua', 'cacao')",
    )
    sinonimos_busqueda: list[str] = Field(min_length=1, max_length=8)
    terminos_ingles: list[str] = Field(default_factory=list, description="Traducciones exactas al inglés del insumo (ej. 'mango peel')")
    #: Cómo se llama el insumo en una tienda alemana.
    #:
    #: Va aparte de `terminos_ingles` porque el inglés no sirve de puente: el
    #: buscador de una tienda alemana devuelve fichas en alemán, y el filtro
    #: `corresponde_al_insumo` compara el término buscado contra el nombre del
    #: producto. Con 'blueberry' contra 'Heidelbeeren 200g' no casa nada, y el
    #: resultado —cero ofertas— se lee igual que «la tienda no lo vende».
    #:
    #: Lista y no cadena porque hay insumos con dos nombres corrientes
    #: ('Heidelbeere' y 'Blaubeere' son la misma fruta). Se busca con el
    #: primero; el resto queda para cuando el conector pruebe varios.
    #:
    #: Vacía es un estado válido: significa que el modelo no supo traducirlo, y
    #: entonces la góndola alemana devuelve [] en vez de buscar un término
    #: inventado. Degradar a «sin dato», nunca a error (ADR-001).
    terminos_aleman: list[str] = Field(
        default_factory=list,
        description="Cómo se llama el insumo en un supermercado alemán, en "
                    "singular o plural según se etiquete allí (ej. 'Heidelbeeren' "
                    "para arándano, 'Quinoa' para quinua). Vacío si no lo sabes "
                    "con certeza: es preferible a inventar un término",
    )
