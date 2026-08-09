"""
Agente Investigador Comercial: busca productos en web y extrae datos (S2).
"""

from .schemas import (
    ProductoSchema,
    BusquedaWebResultado,
    ExtraccionProductoResultado,
    AgenteResultado,
)
from .agente import AgenteInvestigadorComercial
from .grounding_check import (
    grounding_check,
    grounding_check_json,
    GroundingCheckResult,
    GroundingChecker,
)
from .search_failover import (
    SearchFailover,
    FailoverState,
)

__all__ = [
    "ProductoSchema",
    "BusquedaWebResultado",
    "ExtraccionProductoResultado",
    "AgenteResultado",
    "AgenteInvestigadorComercial",
    "grounding_check",
    "grounding_check_json",
    "GroundingCheckResult",
    "GroundingChecker",
    "SearchFailover",
    "FailoverState",
]
