"""
S5.2 - Webhook handlers para servicios externos

Actualmente soporta:
- Bright Data Scraper API: webhook_bright_data()

S5.5: Integrada lógica de dedup (EAN + SKU) con procedencia por field.
"""

import logging
import json
import os
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, Header
from pydantic import BaseModel

from adaptadores.bright_data_api import BrightDataClient
from adaptadores.catalogo_dedup import CatalogoDedup
from adaptadores.entorno import ruta_db_sqlite
from dominio.producto_catalogo import ProductoCatalogo, FieldWithSource

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

# Inicializar clientes (singleton)
_bd_client = None
_catalogo = None


def get_bd_client() -> BrightDataClient:
    """Lazy init de cliente BD."""
    global _bd_client
    if _bd_client is None:
        _bd_client = BrightDataClient()
    return _bd_client


def get_catalogo() -> CatalogoDedup:
    """Lazy init de catálogo dedup.

    Por ruta_db_sqlite() y no por el default del constructor: agroscout.db esta
    versionado y AGROSCOUT_DB_PATH existe justo para que los tests escriban en
    otro archivo. Con el default, una pasada de la suite ensuciaba el binario
    del repositorio, y ademas la cascada leia N2 de un archivo distinto del que
    escribia este webhook.
    """
    global _catalogo
    if _catalogo is None:
        _catalogo = CatalogoDedup(ruta_db_sqlite())
    return _catalogo


class BrightDataWebhookPayload(BaseModel):
    """Payload esperado del webhook de Bright Data."""
    snapshot_id: str
    status: str  # 'success' | 'error'
    data: Dict[str, Any]
    error: str = None


def _process_bd_data_to_catalog(
    bd_data: Dict[str, Any],
    tienda_id: str,
    query: str,
) -> list[ProductoCatalogo]:
    """
    Procesar datos de Bright Data webhook a ProductoCatalogo.

    BD retorna algo como:
    {
        "data": [
            {
                "title": "Quinua Organic",
                "price": "12.99",
                "sku": "QUA-001",
                "ean": "5901234123457",
                "url": "https://..."
            },
            ...
        ]
    }

    Convertir a ProductoCatalogo con procedencia N2_BRIGHT_DATA.
    """
    productos = []

    try:
        items = bd_data.get("data", [])
        if not isinstance(items, list):
            logger.warning(f"BD data.data is not a list: {type(items)}")
            return []

        for item in items:
            try:
                ean = item.get("ean") or item.get("code") or "UNKNOWN"
                sku = item.get("sku") or item.get("id") or f"SKU_{len(productos)}"
                nombre = item.get("title") or item.get("name") or "Unknown"
                precio_str = item.get("price")
                stock_str = item.get("availability") or item.get("in_stock")

                producto = ProductoCatalogo(
                    ean=ean,
                    sku=sku,
                    nombre=nombre,
                    marca=FieldWithSource(
                        valor=item.get("brand"),
                        source="N2_BRIGHT_DATA",
                    ) if item.get("brand") else None,
                    categoria=FieldWithSource(
                        valor=item.get("category"),
                        source="N2_BRIGHT_DATA",
                    ) if item.get("category") else None,
                    precio=FieldWithSource(
                        valor=precio_str,
                        source="N2_BRIGHT_DATA",
                    ) if precio_str else None,
                    stock=FieldWithSource(
                        valor=stock_str,
                        source="N2_BRIGHT_DATA",
                    ) if stock_str else None,
                    descripcion=FieldWithSource(
                        valor=item.get("description"),
                        source="N2_BRIGHT_DATA",
                    ) if item.get("description") else None,
                    tienda_id=tienda_id,
                    transporte="N2_BRIGHT_DATA",
                    url=item.get("url", ""),
                    insumo_query=query,
                )
                productos.append(producto)

            except Exception as e:
                logger.error(f"Failed to process BD item: {item}, error: {e}")
                continue

        logger.info(f"Processed {len(productos)} productos from BD data (tienda={tienda_id})")
        return productos

    except Exception as e:
        logger.error(f"Error processing BD data: {e}")
        return []


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

            # S5.5: Procesar datos a catálogo con dedup
            try:
                catalogo = get_catalogo()
                productos_nuevos = _process_bd_data_to_catalog(
                    payload.data,
                    tienda_id=bd_request.tienda_id,
                    query=bd_request.query,
                )

                merged_count = 0
                new_count = 0

                for producto in productos_nuevos:
                    merged_producto, conflicts = catalogo.save_or_merge(producto)
                    if conflicts:
                        merged_count += 1
                    else:
                        new_count += 1

                logger.info(
                    f"BD dedup complete: {len(productos_nuevos)} productos, "
                    f"{new_count} nuevos, {merged_count} merged"
                )

            except Exception as e:
                logger.error(f"BD dedup error: {e}")
                # Continue even if dedup fails; data already saved in BD requests table

            return {
                "status": "ok",
                "request_id": bd_request.request_id,
                "message": "Data received, stored, and deduplicated",
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
