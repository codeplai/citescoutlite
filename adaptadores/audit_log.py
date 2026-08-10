"""
Audit Log - Registro de eventos y alertas del sistema

Usado por: canario_check, BD webhook errors, sweep status changes.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import sqlite3
from contextlib import closing
from typing import Optional, Any
import json


class AuditLogLevel(str, Enum):
    """Niveles de evento."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    ALERT = "alert"  # Crítico, requiere atención


@dataclass
class AuditLogEntry:
    """Evento de auditoría."""
    level: AuditLogLevel
    component: str  # 'canario', 'bright_data', 'sweep', etc.
    message: str
    data: dict = None  # Datos adicionales como JSON
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.data is None:
            self.data = {}


class AuditLogRepository:
    """Persistir eventos de auditoría."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        level TEXT NOT NULL,
        component TEXT NOT NULL,
        message TEXT NOT NULL,
        data TEXT,
        timestamp TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_audit_component ON audit_log(component);
    CREATE INDEX IF NOT EXISTS idx_audit_level ON audit_log(level);
    CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
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

    def log(self, entry: AuditLogEntry) -> None:
        """Registrar evento."""
        data_json = json.dumps(entry.data) if entry.data else None

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                INSERT INTO audit_log (level, component, message, data, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (
                entry.level.value,
                entry.component,
                entry.message,
                data_json,
                entry.timestamp.isoformat(),
            ))

    def get_by_component(self, component: str, limit: int = 100) -> list[AuditLogEntry]:
        """Obtener eventos de un componente."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM audit_log WHERE component = ?
                ORDER BY timestamp DESC LIMIT ?
            """, (component, limit)).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def get_errors(self, limit: int = 50) -> list[AuditLogEntry]:
        """Obtener solo eventos ERROR y ALERT."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM audit_log WHERE level IN ('error', 'alert')
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,)).fetchall()
            return [self._row_to_entry(row) for row in rows]

    def _row_to_entry(self, row: sqlite3.Row) -> AuditLogEntry:
        """Convertir row a AuditLogEntry."""
        data = json.loads(row["data"]) if row["data"] else {}
        return AuditLogEntry(
            level=AuditLogLevel(row["level"]),
            component=row["component"],
            message=row["message"],
            data=data,
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
