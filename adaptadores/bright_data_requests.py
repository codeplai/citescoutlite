"""
S5.2 - Bright Data Request Tracker

Tabla y helpers para manejar requests async a Bright Data Scraper API.
Modelo: trigger request → get snapshot_id → wait webhook → update DB
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import sqlite3
from contextlib import closing


class BrightDataRequestStatus(str, Enum):
    """Estados del request a Bright Data."""
    PENDING = "pending"          # Enqueued, esperando respuesta
    COMPLETED = "completed"      # Webhook llegó, datos disponibles
    FAILED = "failed"            # Error permanente
    RETRYING = "retrying"        # Retry en progreso
    DEFERRED = "deferred"        # Timeout esperando webhook
    TIMEOUT = "timeout"          # Timeout excedido


@dataclass
class BrightDataRequest:
    """Record de un request a Bright Data."""
    request_id: str
    tienda_id: str
    query: str
    run_id: str
    snapshot_id: Optional[str] = None
    webhook_received_at: Optional[datetime] = None
    data_json: Optional[str] = None
    status: BrightDataRequestStatus = BrightDataRequestStatus.PENDING
    error_reason: Optional[str] = None
    created_at: datetime = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class BrightDataRequestRepository:
    """Repositorio para persistir requests a Bright Data."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS bright_data_requests (
        request_id TEXT PRIMARY KEY,
        tienda_id TEXT NOT NULL,
        query TEXT NOT NULL,
        run_id TEXT NOT NULL,
        snapshot_id TEXT,
        webhook_received_at TEXT,
        data_json TEXT,
        status TEXT DEFAULT 'pending',
        error_reason TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        retry_count INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_bright_data_run ON bright_data_requests(run_id);
    CREATE INDEX IF NOT EXISTS idx_bright_data_status ON bright_data_requests(status);
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

    def save(self, request: BrightDataRequest) -> None:
        """Guardar o actualizar request."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                INSERT OR REPLACE INTO bright_data_requests
                (request_id, tienda_id, query, run_id, snapshot_id,
                 webhook_received_at, data_json, status, error_reason,
                 created_at, completed_at, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request.request_id,
                request.tienda_id,
                request.query,
                request.run_id,
                request.snapshot_id,
                request.webhook_received_at.isoformat() if request.webhook_received_at else None,
                request.data_json,
                request.status.value,
                request.error_reason,
                request.created_at.isoformat(),
                request.completed_at.isoformat() if request.completed_at else None,
                request.retry_count,
            ))

    def get_by_run_id(self, run_id: str) -> list[BrightDataRequest]:
        """Obtener todos los requests para un run."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM bright_data_requests WHERE run_id = ? ORDER BY created_at DESC
            """, (run_id,)).fetchall()
            return [self._row_to_request(row) for row in rows]

    def get_completed_by_run_id(self, run_id: str) -> list[BrightDataRequest]:
        """Obtener requests completados para un run."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM bright_data_requests
                WHERE run_id = ? AND status = ?
                ORDER BY created_at DESC
            """, (run_id, BrightDataRequestStatus.COMPLETED.value)).fetchall()
            return [self._row_to_request(row) for row in rows]

    def get_by_snapshot_id(self, snapshot_id: str) -> Optional[BrightDataRequest]:
        """Buscar request por snapshot_id (para webhook handler)."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM bright_data_requests WHERE snapshot_id = ?
            """, (snapshot_id,)).fetchone()
            return self._row_to_request(row) if row else None

    def _row_to_request(self, row: sqlite3.Row) -> BrightDataRequest:
        """Convertir row a BrightDataRequest."""
        return BrightDataRequest(
            request_id=row["request_id"],
            tienda_id=row["tienda_id"],
            query=row["query"],
            run_id=row["run_id"],
            snapshot_id=row["snapshot_id"],
            webhook_received_at=datetime.fromisoformat(row["webhook_received_at"]) if row["webhook_received_at"] else None,
            data_json=row["data_json"],
            status=BrightDataRequestStatus(row["status"]),
            error_reason=row["error_reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            retry_count=row["retry_count"],
        )
