"""
TIER 3 · T3.1 (S4): puerto de descubrimiento comercial.

El objetivo **no es traer más datos**: es que la cascada del ADR-001 esté en la
interfaz aunque el agente no exista todavía. Contra este contrato se escribirá
el adaptador de nivel 3 en F4, sin reescribir la etapa 2b ni el informe.

La regla que sostiene el diseño: **pedir un nivel que no existe no es un error.**
`descubrir(insumo, nivel_maximo=AGENTE_WEB)` devuelve lo que sí se puede dar —el
nivel 1— y declara por separado lo que no. Si lanzara una excepción, cada
llamante tendría que saber qué niveles hay implementados, que es exactamente el
acoplamiento que el puerto viene a evitar.
"""

from enum import IntEnum
from typing import Protocol

from dominio.producto_en_mercado import ProductoEnMercado


class NivelDescubrimiento(IntEnum):
    """Cascada del ADR-001. El orden es el de coste y el de confianza.

    Es `IntEnum` a propósito: `nivel <= nivel_maximo` tiene que poder escribirse
    sin ceremonia, y el valor se serializa como número en `salida_json`.
    """

    SNAPSHOT = 1        # índice LanceDB local. Real en el MVP.
    API_LICENCIADA = 2  # no disponible en el MVP
    AGENTE_WEB = 3      # no disponible en el MVP


class DescubrimientoComercial(Protocol):
    """Descubre productos reales en el mercado para un insumo."""

    def descubrir(
        self,
        insumo: str,
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> list[ProductoEnMercado]:
        """Productos hasta `nivel_maximo`, sin lanzar si un nivel no existe."""
        ...

    def niveles_no_disponibles(
        self,
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> list[int]:
        """Niveles pedidos que este adaptador no puede servir.

        Va aparte de `descubrir()` para que la firma de esta devuelva una lista
        de productos y nada más. La etapa 2b escribe el resultado en su
        `salida_json` y el informe lo imprime como una línea: es la versión
        barata y honesta de "esto es lo que no miramos".
        """
        ...
