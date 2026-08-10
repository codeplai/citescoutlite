"""
S5.5 - Producto en Catálogo Comercial (con procedencia y dedup)

Extiende ProductoEnMercado con:
- EAN + SKU (llave compuesta para dedup)
- Procedencia por field (source: 'N1_VTEX', 'N2_BrightData', etc)
- Metadata: tienda_id, transporte
"""

from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class FieldWithSource(BaseModel):
    """Un campo con su procedencia."""
    valor: Optional[str] = None
    source: Optional[str] = None  # 'N1_VTEX', 'N1_SCRAPLING', 'N2_BRIGHT_DATA'
    timestamp: Optional[datetime] = None


class ProductoCatalogo(BaseModel):
    """Producto en el catálogo comercial con dedup y procedencia."""

    # --- Llave de dedup ---
    ean: str = Field(description="EAN-13 o equivalente")
    sku: str = Field(description="SKU de la tienda (distingue tallas, colores, etc)")

    # --- Datos básicos ---
    nombre: str
    marca: Optional[FieldWithSource] = None
    descripcion: Optional[FieldWithSource] = None
    categoria: Optional[FieldWithSource] = None

    # --- Comercial (con procedencia) ---
    precio: Optional[FieldWithSource] = None  # Precio de góndola
    stock: Optional[FieldWithSource] = None    # Disponibilidad
    moneda: Optional[FieldWithSource] = None   # Divisa

    # --- Procedencia de este producto ---
    tienda_id: str  # 'amazon', 'costco', 'vitacost', etc
    transporte: str  # 'N1_SNAPSHOT', 'N1_SCRAPLING', 'N2_BRIGHT_DATA'
    url: str        # URL de origen

    # --- Auditoría ---
    insumo_query: str  # Insumo que originó la búsqueda
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    conflict_log: Optional[str] = None  # Log de conflictos durante merge


class DeduplicationConflict(BaseModel):
    """Registro de un conflicto durante dedup."""
    field: str          # 'precio', 'stock', etc
    ean: str
    sku: str
    existing_value: Optional[str]
    existing_source: Optional[str]
    new_value: Optional[str]
    new_source: Optional[str]
    resolution: str     # 'kept_existing', 'merged'
    timestamp: datetime = Field(default_factory=datetime.utcnow)
