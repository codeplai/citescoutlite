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
    # Va como campo propio y no enterrado dentro de `precio_local` porque hay
    # que poder convertir a soles sin adivinar: 'From $7.64' no dice si son
    # dolares de EE. UU. o de otro sitio, y un mapa que mezcla monedas no se
    # puede leer. El JSON-LD lo da exacto en `priceCurrency`.
    moneda: Optional[str] = Field(None, description="Codigo ISO de la moneda del precio: PEN, USD, EUR... Solo si figura en la pagina")
    marca: Optional[str] = Field(None, description="Marca del productor")
    # El codigo de barras es lo unico que identifica el MISMO producto en dos
    # tiendas distintas: el nombre cambia de una a otra. Es lo que permite
    # decir "esta bolsa cuesta 15,70 en Wong y 15,00 en Metro" en vez de
    # listar dos ofertas sueltas. El API de VTEX lo da; en una ficha web suele
    # estar solo si la tienda lo publica.
    ean: Optional[str] = Field(None, description="Codigo de barras EAN/GTIN, solo si figura literalmente")
    stock: Optional[int] = Field(None, description="Cantidad disponible")
    descripcion: Optional[str] = Field(None, description="Descripción del producto")
    unidad: Optional[str] = Field(None, description="Unidad (kg, L, unid, etc)")
    categoria: Optional[str] = Field(None, description="Categoría (ej: cereales, verduras)")
    pais_origen: Optional[str] = Field(None, description="País de origen")
    fecha_disponibilidad: Optional[str] = Field(None, description="Fecha de disponibilidad (YYYY-MM-DD)")

    # Sin `json_schema_extra` con un ejemplo.
    #
    # Llevaba uno completo —"Quinua Orgánica Premium", 8.50, "Cumbres
    # Andinas", stock 42— y instructor lo manda dentro de la definición de la
    # herramienta que ve el modelo. Cuando la página no tiene ficha que leer,
    # el modelo lo copia: en una pasada real apareció "Quinua Orgánica
    # Premium" como oferta encontrada **buscando arándano**. Un valor
    # inventado que además parece plausible es lo peor que puede entrar en una
    # tabla de cuarentena que luego una persona aprueba.
    #
    # Las descripciones de cada campo y el prompt de `_pedir_extraccion` ya
    # dicen qué va en cada uno, que es lo que el ejemplo aportaba.


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
