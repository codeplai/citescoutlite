from pydantic import BaseModel, Field


class HipotesisFormulacion(BaseModel):
    """Etapa 4. Premium.

    Ingenieria inversa de la formulacion a partir de los productos encontrados
    en el snapshot. Hasta S2 era el campo `hipotesis_formulacion` dentro del
    insight, sin etapa propia: sin auditoria, sin costo y sin posibilidad de
    ponerle un paywall delante.
    """

    hipotesis: str = Field(..., description="Ingenieria inversa de la formulacion probable")
    ingredientes_probables: list[str] = Field(..., description="Ingredientes deducidos de los productos comparables")
    procesos_sugeridos: list[str] = Field(..., description="Procesos industriales plausibles (secado, extraccion, molienda...)")
    citas: list[str] = Field(..., description="IDs de productos que sostienen la hipotesis")
