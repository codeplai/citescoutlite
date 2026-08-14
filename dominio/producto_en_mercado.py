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

    categoria: str | None = Field(
        default=None,
        description="La categoría tal cual la publica OFF, sin normalizar: "
                    "82,7 % de cobertura y 8.322 valores distintos. Es texto "
                    "libre, no un código",
    )
    # Se añade en T5 y es lo que hace posible el análisis regulatorio.
    #
    # El adaptador del snapshot ya la leía —está en `_COLUMNAS` y se usa para
    # filtrar por insumo— pero no la pasaba al contrato, así que se perdía al
    # salir de la consulta. Sin ella, `etl.mapear_categoria` no tiene entrada y
    # **las tres tarjetas de la pestaña saldrían condicionadas o sin dato**: el
    # veredicto depende del par (aditivo × categoría), y de la categoría no
    # llegaba nada.

    # --- Formulación. Todo sale del texto de ingredientes del snapshot. ---
    ingredientes: str | None = Field(
        default=None,
        description="Texto de la etiqueta tal cual. 100 % del snapshot lo trae",
    )
    lista_ingredientes: list[str] = Field(
        default_factory=list,
        description="El mismo texto partido por comas fuera de paréntesis, para "
                    "enseñarlo como lista sin romper los subcompuestos",
    )
    n_ingredientes: int | None = Field(
        default=None,
        description="len(lista_ingredientes). Un solo número para una sola lista",
    )
    aditivos: list[str] = Field(
        default_factory=list,
        description="Los que aparecen escritos, con número E: 'Pectina (E440)'",
    )
    alergenos: list[str] = Field(
        default_factory=list,
        description="Solo los que la etiqueta DECLARA. [] = sin declaración, "
                    "nunca 'no tiene'",
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

    # BRIGHT_DATA entra con el merge de N2 (S5.5): son productos de tienda
    # traidos por la API licenciada, no del snapshot. Siguen siendo una sola
    # fuente por fila, que es lo que este campo promete.
    fuente: Literal["OFF", "USDA", "BRIGHT_DATA"] = Field(
        description="Una sola fuente por fila")
    url: HttpUrl
    fecha_dato: date
