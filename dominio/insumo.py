from pydantic import BaseModel, Field

class InsumoInterpretado(BaseModel):
    insumo_normalizado: str
    reconocible: bool
    sinonimos_busqueda: list[str] = Field(min_length=1, max_length=8)
    terminos_ingles: list[str] = Field(default_factory=list, description="Traducciones exactas al inglés del insumo (ej. 'mango peel')")
