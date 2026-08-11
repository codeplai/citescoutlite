"""
Modelo de alerta de retiro para incluir en dossier.

Parte de Etapa 5 (S6 integration): Vigilancia de Retiros Activos
Incluye alertas de openFDA + RASFF con scoring de severidad.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class AlertaDeRetiro(BaseModel):
    """Una alerta de retiro de producto (FDA enforcement / RASFF alert)."""

    alert_id: str = Field(..., description="Hash único de la alerta para dedup")
    fuente: str = Field(..., description="Fuente: 'openfda' o 'rasff'")

    producto_nombre: str = Field(..., description="Nombre del producto retirado")
    riesgo_categoria: str = Field(..., description="Tipo de riesgo: patógeno, alérgeno, residuo, otro")
    riesgo_texto: str = Field(..., description="Descripción detallada del peligro")

    fecha_emitida: datetime = Field(..., description="Fecha en que se emitió la alerta")
    dias_desde: int = Field(..., description="Días desde que se emitió")

    pais_origen: str = Field(..., description="País donde se originó el producto")
    pais_destino: str = Field(..., description="País o región destino")

    url_oficial: str = Field(..., description="Enlace a documentación oficial (FDA o RASFF)")

    similitud: Optional[float] = Field(None, description="Similitud con ingrediente buscado (0-1)")

    # Scoring
    severity_score: Optional[float] = Field(None, description="Score 1-5 de severidad")
    severity_label: str = Field(..., description="Label de severidad: critical, high, medium, low")

    # Metadata
    empresa: Optional[str] = Field(None, description="Empresa responsable (si aplica)")
    reference_number: Optional[str] = Field(None, description="Número de referencia único")


class AlertasDeRetiro(BaseModel):
    """Sección de alertas activas en el dossier regulatorio."""

    alertas: list[AlertaDeRetiro] = Field(
        default_factory=list,
        description="Lista de alertas relevantes (últimas 90 días)"
    )

    cantidad_criticas: int = Field(
        0,
        description="Cantidad de alertas con severidad 'critical'"
    )

    cantidad_activas: int = Field(
        0,
        description="Cantidad total de alertas activas (< 90 días)"
    )

    sin_alertas: bool = Field(
        True,
        description="True si no hay alertas activas para este ingrediente"
    )

    fecha_ultima_actualizacion: Optional[datetime] = Field(
        None,
        description="Última vez que se actualizaron las alertas"
    )

    def summary(self) -> str:
        """Resumen legible de alertas."""
        if self.sin_alertas:
            return "✅ Sin alertas activas para este ingrediente"

        criticas = f"🔴 {self.cantidad_criticas} críticas" if self.cantidad_criticas > 0 else ""
        total = f"({self.cantidad_activas} totales)"

        return f"⚠️ Alertas de retiro encontradas {criticas} {total}".strip()
