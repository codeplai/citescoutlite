from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ContextoSuscripcion:
    """Todo lo que hace falta saber de un usuario antes de empezar un run.

    Va junto a proposito. El plan decide que etapas se ejecutan (T6.1) y los dos
    gastos deciden si se ejecuta alguna (T6.3); pedirlos por separado serian tres
    viajes a Sao Paulo antes de la primera etapa, ~330 ms que se comerian el
    margen del gate de sobrecoste de T3.4.
    """

    plan: str
    gasto_usuario_mes_usd: float
    gasto_global_mes_usd: float


class Suscripciones(Protocol):
    def contexto_de(self, usuario_id: str | None) -> ContextoSuscripcion:
        """Plan del usuario y gasto acumulado del mes en curso.

        Un usuario sin fila en `perfiles` se trata como 'gratuito': el plan se
        concede, nunca se presupone.
        """
        ...
