"""
S5.2 - Webhook handlers para servicios externos

Actualmente soporta:
- Bright Data Scraper API: webhook_bright_data()
"""

import logging
import json
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel

from adaptadores.bright_data_api import BrightDataClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Inicializar cliente BD (singleton)
_bd_client = None


def get_bd_client() -> BrightDataClient:
    """Lazy init de cliente BD."""
    global _bd_client
    if _bd_client is None:
        _bd_client = BrightDataClient()
    return _bd_client


class BrightDataWebhookPayload(BaseModel):
    """Payload esperado del webhook de Bright Data."""
    snapshot_id: str
    status: str  # 'success' | 'error'
    data: Dict[str, Any]
    error: str = None


@router.post("/bright-data")
async def webhook_bright_data(
    request: Request,
    x_bd_auth: str = Header(None),  # Auth token de BD
):
    """
    Webhook handler para Bright Data Scraper API.

    BD llamará este endpoint cuando el scraping termine (éxito o error).
    Espera autenticación via header X-BD-Auth.

    Request body: {
        "snapshot_id": "uuid",
        "status": "success" | "error",
        "data": {...},      # JSON con datos scrapados
        "error": "mensaje"  # Si error
    }
    """
    # Verificar auth token
    expected_token = os.getenv("BRIGHT_DATA_WEBHOOK_TOKEN", "")
    if not expected_token:
        logger.warning("BRIGHT_DATA_WEBHOOK_TOKEN not set; skipping auth check")
    elif x_bd_auth != expected_token:
        logger.warning(f"BD webhook auth failed: token mismatch")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Parsear payload
        body = await request.json()
        payload = BrightDataWebhookPayload(**body)

        logger.info(f"BD webhook received: snapshot_id={payload.snapshot_id}, status={payload.status}")

        bd_client = get_bd_client()

        if payload.status == "success":
            # Guardar datos en DB
            data_json = json.dumps(payload.data)
            bd_request = bd_client.mark_completed(payload.snapshot_id, data_json)
            logger.info(f"BD webhook processed: request_id={bd_request.request_id}")

            # TODO: Trigger merge job (S5.5)
            # enqueue_merge_to_catalog(bd_request.run_id)

            return {
                "status": "ok",
                "request_id": bd_request.request_id,
                "message": "Data received and stored",
            }

        elif payload.status == "error":
            # Marcar como fallido
            bd_request = bd_client.mark_failed(payload.snapshot_id, payload.error or "Unknown error")
            logger.error(f"BD webhook error: request_id={bd_request.request_id}, reason={payload.error}")

            return {
                "status": "error_processed",
                "request_id": bd_request.request_id,
                "message": "Error recorded",
            }

        else:
            logger.warning(f"BD webhook unknown status: {payload.status}")
            raise HTTPException(status_code=400, detail=f"Unknown status: {payload.status}")

    except json.JSONDecodeError as e:
        logger.error(f"BD webhook JSON parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    except Exception as e:
        logger.error(f"BD webhook unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
