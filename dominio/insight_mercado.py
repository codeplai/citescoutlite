from typing import Literal

from pydantic import BaseModel, Field


class InsightDeMercado(BaseModel):
    """Etapa 3. Es lo que recibe el plan gratuito.

    Hasta S2 este objeto llevaba tambien `hipotesis_formulacion` y
    `verificacion_regulatoria`, que salian de la misma llamada al modelo. Con
    esa forma el paywall no se podia implementar honestamente: el token de la
    formulacion se pagaba siempre y "ocultarla" habria sido recortar un string
    ya generado. Ahora son las etapas 4 y 5, cada una con su cache, su
    auditoria y su costo.
    """

    cobertura: Literal["baja", "media", "alta"] = Field(..., description="Nivel de cobertura de datos en bases abiertas")
    resumen: str = Field(..., description="Resumen orientativo sobre el uso actual en la industria")
    formatos_comunes: list[str] = Field(..., description="Formatos comerciales (ej. Polvo, extracto, mermelada)")
    citas: list[str] = Field(..., description="IDs de productos usados como referencia")
    # D4: el plan gratuito conserva un parrafo regulatorio, porque quitarlo del
    # todo debilitaria la demo. Pero es orientativo y sin corpus: lo que premium
    # anade en la etapa 5 son citas verificables con fuente, URL y fecha. Si lo
    # gratuito ya trajera fuentes, el dossier no anadiria nada.
    nota_regulatoria: str | None = Field(
        None, description="Parrafo regulatorio orientativo, sin fuentes verificadas")
