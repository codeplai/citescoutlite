"""
TIER 1 · T1.3 (S4): contrato de una fila del mapa comercial.

Modelo **plano**, sin `CampoConFuente[T]` genérico. La procedencia por campo
servía para distinguir "la marca viene de OFF, el precio de Open Prices, la
presentación de la API v2"; cortados el precio y la presentación del MVP
(PLAN-TIERS-S4-MVP.md §0), **cada fila tiene una sola fuente**: su producto de
OFF o de USDA, con una URL y una fecha. El genérico ya no compra nada.

Los tres campos que hoy son siempre `None` se quedan en el modelo **a
propósito**: son lo que la tabla del informe enseña como "sin dato" y el gancho
por donde entra el agente del nivel 3 en F4. Borrarlos escondería el hueco, que
es justo lo contrario de lo que la demo quiere enseñar.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProductoEnMercado(BaseModel):
    """Un producto real, con su procedencia, tal como lo ve el mapa comercial."""

    insumo: str = Field(description="Insumo piloto que originó la consulta")
    producto_id: str = Field(description="Id con prefijo de fuente: 'OFF:00000036'")
    nombre: str
    marca: str | None = Field(
        default=None,
        description="18 % del snapshot no lo trae; null, nunca cadena vacía",
    )
    paises_iso: list[str] = Field(
        default_factory=list,
        description="ISO-3166 alpha-2 normalizado (T2.1); [] si no se pudo mapear",
    )

    # --- El hueco, declarado. Ver §0 y §R2 del plan. ---
    presentacion: str | None = Field(
        default=None,
        description="Siempre None en el MVP: el ETL de S2 descartó `quantity`",
    )
    precio_rango: str | None = Field(
        default=None,
        description="Siempre None en el MVP: Open Prices cubre el 3 % (T1.2)",
    )
    canal: str | None = Field(
        default=None,
        description="Siempre None en el MVP: el ETL de S2 descartó `stores`",
    )

    fuente: Literal["OFF", "USDA"] = Field(description="Una sola fuente por fila")
    url: HttpUrl
    fecha_dato: date
