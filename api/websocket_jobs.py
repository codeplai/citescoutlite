"""S3.2 WebSocket endpoint for real-time job progress streaming."""

import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from adaptadores.eventos_job import get_eventos_store
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket", "jobs"])

# Track active WebSocket connections per run_id
# Key: run_id, Value: Set of WebSocket connections
_active_connections: dict[str, Set[WebSocket]] = {}


@router.websocket("/run/{run_id}")
async def websocket_run_progress(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for streaming job progress events.

    A client connects to /ws/run/{run_id} and receives real-time events:
    - 'created': Job enqueued
    - 'started': Execution began
    - 'progress': Intermediate status (with % or custom data)
    - 'completed': Job finished successfully
    - 'failed': Job failed (with error details)

    Message format (JSON):
    {
        "event_id": 123,
        "run_id": "run_abc",
        "job_id": 456,
        "evento": "progress",
        "data": {"percent": 50, "message": "Processing..."},
        "created_at": "2026-08-09T12:34:56Z"
    }

    Usage from frontend (Vue 3):
    ```javascript
    const ws = new WebSocket(`ws://localhost:8000/ws/run/run_123`);
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        console.log(`Progress: ${msg.data.percent}%`);
    };
    ```
    """
    await websocket.accept()
    logger.info(f"✅ WebSocket client connected: {run_id}")

    # Track connection
    if run_id not in _active_connections:
        _active_connections[run_id] = set()
    _active_connections[run_id].add(websocket)

    try:
        # Get database
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            await websocket.send_json(
                {"error": "DATABASE_URL not configured"}
            )
            await websocket.close(code=1008, reason="Server error")
            return

        store = get_eventos_store(db_url)

        # Send existing events first (historical)
        logger.info(f"📨 Sending historical events for {run_id}...")
        existing_events = await store.get_events(run_id, limit=100)
        for event in reversed(existing_events):  # Chronological order
            await websocket.send_json({
                "event_id": event["event_id"],
                "run_id": event["run_id"],
                "job_id": event["job_id"],
                "evento": event["evento"],
                "data": event["data"],
                "created_at": event["created_at"],
            })

        # Keep connection open for new events
        # In production, use PostgreSQL LISTEN/NOTIFY for true streaming
        # For now, just keep connection open and client can poll or use other transport
        logger.info(f"👂 Streaming new events for {run_id}...")

        while True:
            # Wait for client messages (heartbeat/ping)
            data = await websocket.receive_text()
            if data.lower() == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"❌ WebSocket client disconnected: {run_id}")
        _active_connections[run_id].discard(websocket)
        if not _active_connections[run_id]:
            del _active_connections[run_id]

    except Exception as e:
        logger.error(f"❌ WebSocket error [{run_id}]: {e}")
        try:
            await websocket.close(code=1011, reason="Server error")
        except Exception:
            pass
        if run_id in _active_connections:
            _active_connections[run_id].discard(websocket)
            if not _active_connections[run_id]:
                del _active_connections[run_id]


async def broadcast_event(run_id: str, event: dict):
    """
    Broadcast an event to all connected WebSocket clients for a run.

    Called by Procrastinate event callbacks to push updates to all
    connected frontends.

    Args:
        run_id: Execution identifier
        event: Event dict from eventos_job
    """
    if run_id not in _active_connections:
        return

    disconnected = set()
    for websocket in _active_connections[run_id]:
        try:
            await websocket.send_json(event)
        except Exception as e:
            logger.error(f"❌ Failed to send event to client: {e}")
            disconnected.add(websocket)

    # Remove disconnected clients
    for ws in disconnected:
        _active_connections[run_id].discard(ws)

    if not _active_connections[run_id]:
        del _active_connections[run_id]
