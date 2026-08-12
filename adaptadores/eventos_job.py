"""S3.2 Job events tracking and real-time progress streaming.

## Estado (revisado en S8.0)

`eventos_job` estaba a 0 filas y este modulo era la razon: **ninguno de sus
cuatro metodos podia ejecutarse**. Se escribio contra una API que psycopg3 no
tiene, y como el unico llamador —`_emitir` en los jobs— envuelve la llamada en
un try/except para que un fallo de registro no tumbe el trabajo ya hecho, los
cuatro errores se tragaban en silencio:

| Metodo | Lo que hacia | Por que fallaba |
|---|---|---|
| `create_event` | `await cur.scalar(sql, params)` | `AsyncCursor` no tiene `.scalar()` |
| `get_events` | `await cur.fetchall(sql, params)` | `fetchall()` no acepta argumentos: hay que `execute()` antes |
| `stream_events` | `async for x in await cur.stream(...)` | `stream()` ya devuelve un generador asincrono; no se espera |
| los tres | `json.loads(fila[4])` | psycopg3 devuelve `jsonb` como dict, no como texto: `TypeError` |

Todo esto quedaba ademas por detras de un fallo anterior en Windows (el policy
Proactor de asyncio, ver `adaptadores/bucle_asincrono.py`), que era el unico
sintoma visible. Al arreglar aquel, aparecieron estos.

Importa porque `eventos_job` es la unica fuente del dashboard de jobs (S8.1).
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import psycopg
from psycopg import AsyncConnection

logger = logging.getLogger(__name__)


def _a_dict(fila) -> dict:
    """Una fila de eventos_job como dict listo para JSON.

    `data_json` es una columna `jsonb`, y psycopg3 la devuelve ya convertida a
    dict. El `json.loads()` que habia aqui recibia por tanto un dict y moria con
    TypeError. Se admite texto igualmente por si alguna fila vieja se escribio
    como cadena.
    """
    datos = fila[4]
    if isinstance(datos, (str, bytes)):
        datos = json.loads(datos)

    return {
        "event_id": fila[0],
        "run_id": fila[1],
        "job_id": fila[2],
        "evento": fila[3],
        "data": datos or {},
        "created_at": fila[5].isoformat() if fila[5] else None,
    }


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
                await cur.execute(
                    """
                    INSERT INTO eventos_job (run_id, job_id, evento, data_json)
                    VALUES (%s, %s, %s, %s)
                    RETURNING event_id
                    """,
                    (run_id, job_id, evento, data_json),
                )
                fila = await cur.fetchone()
                event_id = fila[0]
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
                await cur.execute(
                    """
                    SELECT event_id, run_id, job_id, evento, data_json, created_at
                    FROM eventos_job
                    WHERE run_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (run_id, limit),
                )
                events = await cur.fetchall()
                return [_a_dict(e) for e in events]

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
                # `stream()` ya devuelve un generador asincrono: se itera con
                # `async for` directamente. El `await` que habia delante
                # intentaba esperar el generador y reventaba antes de la
                # primera fila.
                async for fila in cur.stream(
                    """
                    SELECT event_id, run_id, job_id, evento, data_json, created_at
                    FROM eventos_job
                    WHERE run_id = %s
                    ORDER BY created_at ASC
                    """,
                    (run_id,),
                ):
                    yield _a_dict(fila)


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
