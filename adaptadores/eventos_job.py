"""S3.2 Job events tracking and real-time progress streaming."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import psycopg
from psycopg import AsyncConnection

logger = logging.getLogger(__name__)


class EventosJobStore:
    """Store and retrieve job events from eventos_job table."""

    def __init__(self, db_url: str):
        """Initialize with database URL."""
        self.db_url = db_url

    async def get_connection(self) -> AsyncConnection:
        """Get async database connection."""
        return await psycopg.AsyncConnection.connect(self.db_url)

    async def create_event(
        self,
        run_id: str,
        evento: str,
        job_id: Optional[int] = None,
        data: Optional[dict] = None,
    ) -> int:
        """
        Record a job event in eventos_job.

        Args:
            run_id: Execution identifier
            evento: Event type (created, started, progress, completed, failed)
            job_id: Procrastinate job ID (optional)
            data: Event metadata as dict (progress %, error details, etc.)

        Returns:
            event_id of created record
        """
        if evento not in ("created", "started", "progress", "completed", "failed"):
            raise ValueError(f"Invalid evento: {evento}")

        data_json = json.dumps(data or {})

        # El `async with` cierra la conexion y, a diferencia del try/finally que
        # habia, no se rompe cuando la conexion ni llega a abrirse: alli `conn`
        # no existia y el finally lanzaba UnboundLocalError, que sustituia al
        # error de verdad. Con la base caida se leia "cannot access local
        # variable 'conn'" en vez de por que no se pudo conectar.
        conn = await self.get_connection()
        async with conn:
            async with conn.cursor() as cur:
                event_id = await cur.scalar(
                    """
                    INSERT INTO eventos_job (run_id, job_id, evento, data_json)
                    VALUES (%s, %s, %s, %s)
                    RETURNING event_id
                    """,
                    (run_id, job_id, evento, data_json),
                )
                logger.info(f"📌 [{evento}] run_id={run_id}, event_id={event_id}")
                return event_id

    async def get_events(self, run_id: str, limit: int = 100) -> list[dict]:
        """
        Retrieve all events for a run, ordered by timestamp.

        Args:
            run_id: Execution identifier
            limit: Max events to return

        Returns:
            List of event dicts: {event_id, run_id, job_id, evento, data_json, created_at}
        """
        conn = await self.get_connection()
        async with conn:
            async with conn.cursor() as cur:
                events = await cur.fetchall(
                    """
                    SELECT event_id, run_id, job_id, evento, data_json, created_at
                    FROM eventos_job
                    WHERE run_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (run_id, limit),
                )
                return [
                    {
                        "event_id": e[0],
                        "run_id": e[1],
                        "job_id": e[2],
                        "evento": e[3],
                        "data": json.loads(e[4]),
                        "created_at": e[5].isoformat() if e[5] else None,
                    }
                    for e in events
                ]

    async def get_latest_event(self, run_id: str) -> Optional[dict]:
        """Get the most recent event for a run."""
        events = await self.get_events(run_id, limit=1)
        return events[0] if events else None

    async def stream_events(self, run_id: str):
        """
        Stream events for a run (for WebSocket).

        Yields events in chronological order as they are created.
        This is a polling generator; for true streaming use PostgreSQL LISTEN.

        Args:
            run_id: Execution identifier

        Yields:
            Event dicts as they become available
        """
        # TODO S3.2: Implement real PostgreSQL LISTEN/NOTIFY for true streaming
        # For now, return existing events in chronological order

        conn = await self.get_connection()
        async with conn:
            async with conn.cursor() as cur:
                # Get all events in chronological order
                async for event_row in await cur.stream(
                    """
                    SELECT event_id, run_id, job_id, evento, data_json, created_at
                    FROM eventos_job
                    WHERE run_id = %s
                    ORDER BY created_at ASC
                    """,
                    (run_id,),
                ):
                    yield {
                        "event_id": event_row[0],
                        "run_id": event_row[1],
                        "job_id": event_row[2],
                        "evento": event_row[3],
                        "data": json.loads(event_row[4]),
                        "created_at": event_row[5].isoformat() if event_row[5] else None,
                    }


# Singleton instance
_eventos_store: Optional[EventosJobStore] = None


def get_eventos_store(db_url: str) -> EventosJobStore:
    """Get or create EventosJobStore singleton."""
    global _eventos_store
    if _eventos_store is None:
        _eventos_store = EventosJobStore(db_url)
    return _eventos_store


async def emit_event(
    run_id: str,
    evento: str,
    job_id: Optional[int] = None,
    data: Optional[dict] = None,
) -> int:
    """
    Emit a job event (convenience function).

    Usage:
        await emit_event("run_123", "started", job_id=456, data={"percent": 10})
    """
    import os

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not configured")
        raise ValueError("DATABASE_URL not configured")

    store = get_eventos_store(db_url)
    return await store.create_event(run_id, evento, job_id, data)
