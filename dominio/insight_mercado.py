from typing import Literal
from pydantic import BaseModel, Field

class InsightDeMercado(BaseModel):
    cobertura: Literal["baja", "media", "alta"] = Field(..., description="Nivel de cobertura de datos en bases abiertas")
    resumen: str = Field(..., description="Resumen orientativo sobre el uso actual en la industria")
    hipotesis_formulacion: str = Field(..., description="Ingeniería inversa de ingredientes y posible formulación")
    verificacion_regulatoria: str = Field(..., description="Restricciones o consideraciones regulatorias sanitarias")
    formatos_comunes: list[str] = Field(..., description="Formatos comerciales (ej. Polvo, extracto, mermelada)")
    citas: list[str] = Field(..., description="IDs de productos usados como referencia")
