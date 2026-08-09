"""
Schemas Pydantic para AgenteInvestigadorComercial (S2.1).

Define la estructura esperada de productos extraídos de la web.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProductoSchema(BaseModel):
    """Schema de un producto extraído del web."""

    nombre: str = Field(..., description="Nombre del producto")
    precio: Optional[float] = Field(None, description="Precio en USD")
    precio_local: Optional[str] = Field(None, description="Precio en moneda local (ej: ARS 1200)")
    marca: Optional[str] = Field(None, description="Marca del productor")
    stock: Optional[int] = Field(None, description="Cantidad disponible")
    descripcion: Optional[str] = Field(None, description="Descripción del producto")
    unidad: Optional[str] = Field(None, description="Unidad (kg, L, unid, etc)")
    categoria: Optional[str] = Field(None, description="Categoría (ej: cereales, verduras)")
    pais_origen: Optional[str] = Field(None, description="País de origen")
    fecha_disponibilidad: Optional[str] = Field(None, description="Fecha de disponibilidad (YYYY-MM-DD)")

    class Config:
        json_schema_extra = {
            "example": {
                "nombre": "Quinua Orgánica Premium",
                "precio": 8.50,
                "precio_local": "ARS 3400",
                "marca": "Cumbres Andinas",
                "stock": 42,
                "descripcion": "Quinua blanca de primera calidad",
                "unidad": "kg",
                "categoria": "cereales",
                "pais_origen": "Perú",
                "fecha_disponibilidad": "2025-08-15"
            }
        }


class BusquedaWebResultado(BaseModel):
    """Resultado de una búsqueda web via Tavily."""

    titulo: str
    url: str
    contenido_preview: str
    fuente: str


class ExtraccionProductoResultado(BaseModel):
    """Resultado de extracción de producto de HTML."""

    producto: ProductoSchema
    fuente_url: str
    html_capturado: Optional[str] = Field(None, description="Fragmento de HTML usado")
    timestamp: datetime
    modelo_usado: str = Field(default="glm-5.2", description="Modelo que hizo la extracción")


class AgenteResultado(BaseModel):
    """Resultado completo de ejecución del agente."""

    insumo: str
    pais: str
    productos_encontrados: list[ExtraccionProductoResultado]
    total_items_buscados: int
    tiempo_total_ms: int
    errores: list[str] = Field(default_factory=list)
    estado: str = Field(default="ok", description="ok, parcial, error")
