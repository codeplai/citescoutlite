from pydantic import BaseModel, Field


class CitaRegulatoria(BaseModel):
    """Una cita que se puede ir a comprobar.

    Es la diferencia entre el parrafo gratuito y el dossier premium: aqui la
    fuente y la URL no son adorno, son lo que se compra.
    """

    texto: str = Field(..., description="Fragmento de la norma que aplica")
    fuente: str = Field(..., description="Norma y organismo (ej. 21 CFR 145.110, FDA)")
    url: str | None = Field(None, description="Enlace navegable a la fuente oficial, si el corpus lo trae")
    fecha: str | None = Field(None, description="Fecha o version de la norma, si consta")


class DossierRegulatorio(BaseModel):
    """Etapa 5. Premium.

    `sin_dato` no es un detalle: el principio del ADR es degradar a "sin dato",
    nunca a error. Si el corpus no tiene normas aplicables al insumo, o si el
    presupuesto corta la etapa (T6.3), el dossier vuelve marcado y el run cierra
    en 'parcial' con HTTP 200.
    """

    restricciones: list[str] = Field(..., description="Restricciones o requisitos que aplican al insumo")
    citas: list[CitaRegulatoria] = Field(..., description="Citas verificables que sostienen cada restriccion")
    sin_dato: bool = Field(False, description="True si no hubo corpus aplicable o la etapa se degrado")
