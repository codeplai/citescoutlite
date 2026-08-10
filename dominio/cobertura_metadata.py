"""
S5.6 - Cobertura Metadata

Estadísticas de cobertura por sweep.
Calcula porcentaje de tiendas consultadas exitosamente.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CoberturaMetadata:
    """Estadísticas de cobertura para un barrido."""
    sweep_id: str
    insumo: str

    # Conteos por status
    in_scope: int              # Total de tiendas en scope
    verified: int              # status='ok'
    blocked_policy: int        # ToS violation
    blocked_server: int        # Rate limit / IP block
    blocked_robots: int        # robots.txt
    skipped_budget: int        # Presupuesto agotado
    circuit_open: int          # Circuit breaker
    deferred: int              # Async pending
    failed: int                # Error genérico
    out_of_scope: int          # No aplica

    # Cálculos
    coverage_pct: float        # verified / in_scope * 100
    publishable: bool          # coverage_pct > 60%
    note: Optional[str] = None

    # Auditoría
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()

        # Calcular cobertura
        if self.in_scope > 0:
            self.coverage_pct = round((self.verified / self.in_scope) * 100, 1)
        else:
            self.coverage_pct = 0.0

        # Publicable si > 60%
        self.publishable = self.coverage_pct > 60.0

    def to_dict(self) -> dict:
        """Serializar a diccionario."""
        return {
            "sweep_id": self.sweep_id,
            "insumo": self.insumo,
            "in_scope": self.in_scope,
            "verified": self.verified,
            "blocked_policy": self.blocked_policy,
            "blocked_server": self.blocked_server,
            "blocked_robots": self.blocked_robots,
            "skipped_budget": self.skipped_budget,
            "circuit_open": self.circuit_open,
            "deferred": self.deferred,
            "failed": self.failed,
            "out_of_scope": self.out_of_scope,
            "coverage_pct": self.coverage_pct,
            "publishable": self.publishable,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
