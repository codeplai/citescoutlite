"""
T6.1 - Que puede ejecutar cada plan.

Vive en la **frontera de aplicacion**, no en el dominio. El paywall se resuelve
componiendo casos de uso —etapas 1,2a,3 frente a 1,2a,3,4,5— y no filtrando
campos de un objeto ya generado (ADR-001 §2.4). Esa distincion no es teorica:
si se filtrara al final, el token de la etapa 4 se pagaria igual para quien no
la ha comprado.
"""

import os
from dataclasses import dataclass

from puertos.suscripciones import ContextoSuscripcion

ETAPAS_GRATUITAS = frozenset({"1", "2a", "3"})
ETAPAS_PREMIUM = frozenset({"1", "2a", "3", "4", "5"})


def _tope(variable: str, defecto: float) -> float:
    try:
        return float(os.getenv(variable, defecto))
    except ValueError:
        return defecto


@dataclass(frozen=True)
class Entitlement:
    plan: str
    etapas_permitidas: frozenset[str]
    tope_mes_usd: float

    @property
    def es_premium(self) -> bool:
        return "4" in self.etapas_permitidas


def entitlement_de(contexto: ContextoSuscripcion) -> Entitlement:
    """Traduce un plan a permisos concretos.

    Cualquier plan que no sea exactamente 'premium' cae en gratuito: ante un
    valor inesperado en la columna, lo seguro es conceder de menos.
    """
    if contexto.plan == "premium":
        return Entitlement(
            plan="premium",
            etapas_permitidas=ETAPAS_PREMIUM,
            tope_mes_usd=_tope("PRESUPUESTO_PREMIUM_MES_USD", 10.0),
        )

    return Entitlement(
        plan="gratuito",
        etapas_permitidas=ETAPAS_GRATUITAS,
        tope_mes_usd=_tope("PRESUPUESTO_USUARIO_MES_USD", 2.0),
    )
