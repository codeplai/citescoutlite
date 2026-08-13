from pydantic import BaseModel, Field

class InsumoInterpretado(BaseModel):
    insumo_normalizado: str
    reconocible: bool
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
