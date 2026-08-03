"""
Precio mayorista de un insumo como materia prima.

**No es el precio del producto terminado.** `ProductoEnMercado.precio_rango`
—cuánto cuesta en góndola el guacamole de una marca— sigue vacío y sigue siendo
el hueco declarado del §R2 del plan. Esto es otra cosa: a cuánto está el kilo de
palta en el mercado mayorista de Lima, que es el número con el que una mipyme
costea una fórmula.

Mezclar los dos sería el peor malentendido que puede tener este informe, porque
haría parecer que el precio de góndola está detrás de un plan de pago cuando en
realidad no lo tenemos. Por eso viven en modelos distintos y se pintan en
bloques distintos.
"""

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class PrecioMateriaPrima(BaseModel):
    """Una observación de precio mayorista, con su fuente y su fecha."""

    insumo: str = Field(description="Insumo piloto: 'palta', 'espárrago'…")
    producto: str = Field(
        description="La variedad tal como la nombra el boletín: "
                    "'PALTA FUERTE COSTA'. No se traduce ni se agrupa")
    mercado: str = Field(description="GMML | MMF2")
    mercado_nombre: str

    precio_soles_kg: float = Field(gt=0, description="S/ por kilogramo")
    precio_semana_anterior: float | None = Field(
        default=None, description="Para poder leer la variación sin recalcularla")
    variacion_pct: float | None = Field(
        default=None,
        description="Respecto a la semana anterior. None si el boletín no la da")

    fecha: date = Field(description="Fecha del boletín, no de la descarga")
    fuente: str = "MIDAGRI · SISAP"
    url_boletin: HttpUrl = Field(description="El PDF exacto del que salió")
