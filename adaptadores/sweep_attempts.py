"""
S5.3 - Sweep Attempts Tracker

Tabla que registra 1 fila por tienda por cada barrido (sweep).
Captura estado: 'ok', 'failed', 'blocked_policy', 'blocked_robots', etc.
Permite calcular cobertura: 72 'ok' de 97 tiendas = 74.2% coverage.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import sqlite3
from contextlib import closing
from typing import Optional


class SweepAttemptStatus(str, Enum):
    """Estados posibles de un sweep attempt."""
    OK = "ok"                      # Éxito: encontró ofertas
    FAILED = "failed"              # Error genérico
    BLOCKED_POLICY = "blocked_policy"      # ToS violation (no consultamos)
    BLOCKED_SERVER = "blocked_server"      # Rate limit / IP block
    BLOCKED_ROBOTS = "blocked_robots"      # robots.txt denies access
    SKIPPED_BUDGET = "skipped_budget"      # Presupuesto agotado
    CIRCUIT_OPEN = "circuit_open"          # Circuit breaker activo
    DEFERRED = "deferred"          # Asyncwaiting (N2 webhook pending)
    OUT_OF_SCOPE = "out_of_scope"  # Tienda no aplica para esta búsqueda


@dataclass
class SweepAttempt:
    """Un intento de barrido de una tienda."""
    sweep_id: str           # ID del sweep global
    store_id: str           # ID de la tienda
    status: SweepAttemptStatus
    transport: str          # "N1_SNAPSHOT" | "N1_SCRAPLING" | "N2_BRIGHT_DATA"
    offers_found: int = 0   # Cantidad de ofertas encontradas
    cost_usd: float = 0.0   # Costo en USD (Bright Data)
    error_reason: Optional[str] = None
    started_at: datetime = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()


class SweepAttemptsRepository:
    """Persistir sweep attempts en SQLite."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS sweep_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sweep_id TEXT NOT NULL,
        store_id TEXT NOT NULL,
        status TEXT NOT NULL,
        transport TEXT NOT NULL,
        offers_found INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        error_reason TEXT,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE(sweep_id, store_id)
    );
    CREATE INDEX IF NOT EXISTS idx_sweep_attempts_sweep_id ON sweep_attempts(sweep_id);
    CREATE INDEX IF NOT EXISTS idx_sweep_attempts_status ON sweep_attempts(status);
    CREATE INDEX IF NOT EXISTS idx_sweep_attempts_store ON sweep_attempts(store_id);
    """

    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self):
        """Crear tabla si no existe."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            for stmt in self.SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(stmt)

    def save(self, attempt: SweepAttempt) -> None:
        """Guardar o actualizar sweep attempt."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                INSERT OR REPLACE INTO sweep_attempts
                (sweep_id, store_id, status, transport, offers_found, cost_usd,
                 error_reason, started_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt.sweep_id,
                attempt.store_id,
                attempt.status.value,
                attempt.transport,
                attempt.offers_found,
                attempt.cost_usd,
                attempt.error_reason,
                attempt.started_at.isoformat(),
                attempt.completed_at.isoformat() if attempt.completed_at else None,
            ))

    def save_batch(self, attempts: list[SweepAttempt]) -> None:
        """Guardar múltiples attempts en una transacción."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            for attempt in attempts:
                conn.execute("""
                    INSERT OR REPLACE INTO sweep_attempts
                    (sweep_id, store_id, status, transport, offers_found, cost_usd,
                     error_reason, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt.sweep_id,
                    attempt.store_id,
                    attempt.status.value,
                    attempt.transport,
                    attempt.offers_found,
                    attempt.cost_usd,
                    attempt.error_reason,
                    attempt.started_at.isoformat(),
                    attempt.completed_at.isoformat() if attempt.completed_at else None,
                ))

    def get_by_sweep_id(self, sweep_id: str) -> list[SweepAttempt]:
        """Obtener todos los attempts de un sweep."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM sweep_attempts WHERE sweep_id = ? ORDER BY started_at
            """, (sweep_id,)).fetchall()
            return [self._row_to_attempt(row) for row in rows]

    def count_by_status(self, sweep_id: str, status: SweepAttemptStatus) -> int:
        """Contar attempts con un status específico."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            count = conn.execute("""
                SELECT COUNT(*) FROM sweep_attempts WHERE sweep_id = ? AND status = ?
            """, (sweep_id, status.value)).fetchone()[0]
            return count

    def _row_to_attempt(self, row: sqlite3.Row) -> SweepAttempt:
        """Convertir row a SweepAttempt."""
        return SweepAttempt(
            sweep_id=row["sweep_id"],
            store_id=row["store_id"],
            status=SweepAttemptStatus(row["status"]),
            transport=row["transport"],
            offers_found=row["offers_found"],
            cost_usd=row["cost_usd"],
            error_reason=row["error_reason"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
        )
