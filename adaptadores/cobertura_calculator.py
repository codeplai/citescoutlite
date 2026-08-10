"""
S5.6 - Coverage Calculator

Calcula cobertura a partir de sweep_attempts.
Guarda en mapa_comercial_metadata.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Optional

from dominio.cobertura_metadata import CoberturaMetadata
from .sweep_attempts import SweepAttemptsRepository, SweepAttemptStatus
from .audit_log import AuditLogRepository, AuditLogEntry, AuditLogLevel

logger = logging.getLogger(__name__)


class CoberturaCalculator:
    """Calcula y persiste cobertura de un sweep."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS mapa_comercial_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sweep_id TEXT UNIQUE NOT NULL,
        insumo TEXT NOT NULL,
        in_scope INTEGER NOT NULL,
        verified INTEGER NOT NULL,
        blocked_policy INTEGER DEFAULT 0,
        blocked_server INTEGER DEFAULT 0,
        blocked_robots INTEGER DEFAULT 0,
        skipped_budget INTEGER DEFAULT 0,
        circuit_open INTEGER DEFAULT 0,
        deferred INTEGER DEFAULT 0,
        failed INTEGER DEFAULT 0,
        out_of_scope INTEGER DEFAULT 0,
        coverage_pct REAL NOT NULL,
        publishable INTEGER NOT NULL,
        note TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_metadata_sweep ON mapa_comercial_metadata(sweep_id);
    CREATE INDEX IF NOT EXISTS idx_metadata_insumo ON mapa_comercial_metadata(insumo);
    """

    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self.sweep_repo = SweepAttemptsRepository(db_path)
        self.audit_repo = AuditLogRepository(db_path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Crear tabla si no existe."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            for stmt in self.SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(stmt)

    def calculate_coverage(self, sweep_id: str, insumo: str = "unknown") -> CoberturaMetadata:
        """
        Calcular cobertura para un sweep.

        Args:
            sweep_id: ID del sweep
            insumo: Producto buscado (para contexto)

        Returns:
            CoberturaMetadata con estadísticas calculadas
        """
        # Obtener todos los attempts
        attempts = self.sweep_repo.get_by_sweep_id(sweep_id)

        if not attempts:
            logger.warning(f"No attempts found for sweep {sweep_id}")
            return None

        # Contar por status
        counts = {status.value: 0 for status in SweepAttemptStatus}
        for attempt in attempts:
            counts[attempt.status.value] += 1

        # Calcular totales
        in_scope = len(attempts)
        verified = counts.get("ok", 0)
        blocked_policy = counts.get("blocked_policy", 0)
        blocked_server = counts.get("blocked_server", 0)
        blocked_robots = counts.get("blocked_robots", 0)
        skipped_budget = counts.get("skipped_budget", 0)
        circuit_open = counts.get("circuit_open", 0)
        deferred = counts.get("deferred", 0)
        failed = counts.get("failed", 0)
        out_of_scope = counts.get("out_of_scope", 0)

        # Generar nota explicativa
        blocked_reasons = []
        if blocked_policy > 0:
            blocked_reasons.append(f"{blocked_policy} tiendas bloqueadas por policy")
        if blocked_server > 0:
            blocked_reasons.append(f"{blocked_server} tiendas rate-limited")
        if blocked_robots > 0:
            blocked_reasons.append(f"{blocked_robots} tiendas robots.txt")

        note = None
        if blocked_reasons:
            note = "; ".join(blocked_reasons)

        # Crear metadata
        metadata = CoberturaMetadata(
            sweep_id=sweep_id,
            insumo=insumo,
            in_scope=in_scope,
            verified=verified,
            blocked_policy=blocked_policy,
            blocked_server=blocked_server,
            blocked_robots=blocked_robots,
            skipped_budget=skipped_budget,
            circuit_open=circuit_open,
            deferred=deferred,
            failed=failed,
            out_of_scope=out_of_scope,
            note=note,
        )

        logger.info(
            f"Coverage calculated: sweep={sweep_id}, "
            f"verified={verified}/{in_scope} ({metadata.coverage_pct}%), "
            f"publishable={metadata.publishable}"
        )

        return metadata

    def save_coverage(self, metadata: CoberturaMetadata) -> None:
        """Guardar cobertura en DB."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                INSERT OR REPLACE INTO mapa_comercial_metadata
                (sweep_id, insumo, in_scope, verified, blocked_policy,
                 blocked_server, blocked_robots, skipped_budget, circuit_open,
                 deferred, failed, out_of_scope, coverage_pct, publishable, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.sweep_id,
                metadata.insumo,
                metadata.in_scope,
                metadata.verified,
                metadata.blocked_policy,
                metadata.blocked_server,
                metadata.blocked_robots,
                metadata.skipped_budget,
                metadata.circuit_open,
                metadata.deferred,
                metadata.failed,
                metadata.out_of_scope,
                metadata.coverage_pct,
                int(metadata.publishable),
                metadata.note,
                metadata.created_at.isoformat(),
            ))

        # Log en audit
        self.audit_repo.log(AuditLogEntry(
            level=AuditLogLevel.INFO if metadata.publishable else AuditLogLevel.WARNING,
            component="coverage",
            message=f"Coverage saved: {metadata.insumo} {metadata.coverage_pct}% ({'publishable' if metadata.publishable else 'draft'})",
            data=metadata.to_dict(),
        ))

    def get_coverage(self, sweep_id: str) -> Optional[CoberturaMetadata]:
        """Obtener cobertura guardada."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM mapa_comercial_metadata WHERE sweep_id = ?
            """, (sweep_id,)).fetchone()

            if row is None:
                return None

            return CoberturaMetadata(
                sweep_id=row["sweep_id"],
                insumo=row["insumo"],
                in_scope=row["in_scope"],
                verified=row["verified"],
                blocked_policy=row["blocked_policy"],
                blocked_server=row["blocked_server"],
                blocked_robots=row["blocked_robots"],
                skipped_budget=row["skipped_budget"],
                circuit_open=row["circuit_open"],
                deferred=row["deferred"],
                failed=row["failed"],
                out_of_scope=row["out_of_scope"],
                coverage_pct=row["coverage_pct"],
                publishable=bool(row["publishable"]),
                note=row["note"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )

    def calculate_and_save(self, sweep_id: str, insumo: str = "unknown") -> CoberturaMetadata:
        """Calcular y guardar cobertura en una operación."""
        metadata = self.calculate_coverage(sweep_id, insumo)
        if metadata:
            self.save_coverage(metadata)
        return metadata
