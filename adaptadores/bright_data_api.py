"""
S5.2 - Bright Data Scraper API

Cliente para Bright Data Scraper API con handling async via webhooks.
Docs: https://www.brightdata.com/products/scraper-api
"""

import os
import json
import httpx
import logging
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .bright_data_requests import (
    BrightDataRequest,
    BrightDataRequestStatus,
    BrightDataRequestRepository,
)

logger = logging.getLogger(__name__)


class BrightDataClient:
    """
    Cliente para Bright Data Scraper API.

    Flujo:
    1. Enqueue job: POST /request con URL
    2. BD responde con snapshot_id
    3. Configurar webhook en BD dashboard (ej: https://prod.com/api/webhooks/bright-data)
    4. BD llama webhook cuando data listo
    5. Webhook handler actualiza DB con datos
    """

    # Tiendas anti-bot soportadas por N2
    TIENDAS_N2 = {
        "amazon": "https://www.amazon.com",
        "costco": "https://www.costco.com",
        "instacart": "https://www.instacart.com",
        "kroger": "https://www.kroger.com",
        "meituan": "https://www.meituan.com",
    }

    def __init__(self, api_key: Optional[str] = None, db_path: str = "agroscout.db"):
        self.api_key = api_key or os.getenv("BRIGHT_DATA_KEY")
        if not self.api_key:
            raise ValueError("BRIGHT_DATA_KEY not set in environment")

        self.base_url = "https://api.brightdata.com"
        self.db_repo = BrightDataRequestRepository(db_path)
        self.session = httpx.Client(timeout=10.0)

    def _headers(self) -> dict:
        """Headers con autenticación."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def enqueue_scrape(
        self,
        url: str,
        query: str,
        tienda_id: str,
        run_id: str,
        webhook_url: str = "https://api.agroscout.ai/api/webhooks/bright-data",
    ) -> BrightDataRequest:
        """
        Enqueue un job de scraping en Bright Data.

        Args:
            url: URL de la tienda a scrapear
            query: Query de búsqueda (ej: "quinua")
            tienda_id: ID interno de la tienda
            run_id: ID del discovery run (para agrupar requests)
            webhook_url: URL donde BD llamará con los datos

        Returns:
            BrightDataRequest con snapshot_id asignado

        Raises:
            ValueError: Si la tienda no es soportada
            httpx.HTTPError: Si BD API falla
        """
        # Validar tienda
        if tienda_id.lower() not in self.TIENDAS_N2:
            raise ValueError(f"Tienda {tienda_id} no soportada en N2. Soportadas: {list(self.TIENDAS_N2.keys())}")

        request_id = str(uuid4())

        # Payload para BD API
        payload = {
            "url": url,
            "query": query,
            "webhook_url": webhook_url,
            "formats": ["json"],
            "method": "GET",
            "timeout": 30,  # segundos
        }

        try:
            logger.info(f"Enqueuing BD request: tienda={tienda_id}, query={query}, run_id={run_id}")
            response = self.session.post(
                f"{self.base_url}/request",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()

            data = response.json()
            snapshot_id = data.get("snapshot_id")

            if not snapshot_id:
                raise ValueError(f"BD API didn't return snapshot_id: {data}")

            # Guardar en DB
            bd_request = BrightDataRequest(
                request_id=request_id,
                tienda_id=tienda_id,
                query=query,
                run_id=run_id,
                snapshot_id=snapshot_id,
                status=BrightDataRequestStatus.PENDING,
            )
            self.db_repo.save(bd_request)
            logger.info(f"BD request enqueued: snapshot_id={snapshot_id}, request_id={request_id}")

            return bd_request

        except httpx.HTTPError as e:
            error_msg = f"BD API error: {e}"
            logger.error(error_msg)

            # Guardar error en DB
            bd_request = BrightDataRequest(
                request_id=request_id,
                tienda_id=tienda_id,
                query=query,
                run_id=run_id,
                status=BrightDataRequestStatus.FAILED,
                error_reason=str(e),
            )
            self.db_repo.save(bd_request)
            raise

    def mark_completed(
        self,
        snapshot_id: str,
        data_json: str,
    ) -> BrightDataRequest:
        """
        Marcar request como completado (llamado por webhook handler).

        Args:
            snapshot_id: ID del snapshot retornado por BD
            data_json: Datos en JSON retornados por BD

        Returns:
            BrightDataRequest actualizado
        """
        bd_request = self.db_repo.get_by_snapshot_id(snapshot_id)
        if not bd_request:
            raise ValueError(f"snapshot_id {snapshot_id} not found in DB")

        bd_request.status = BrightDataRequestStatus.COMPLETED
        bd_request.webhook_received_at = datetime.utcnow()
        bd_request.data_json = data_json
        bd_request.completed_at = datetime.utcnow()

        self.db_repo.save(bd_request)
        logger.info(f"BD request marked completed: snapshot_id={snapshot_id}, request_id={bd_request.request_id}")

        return bd_request

    def mark_failed(
        self,
        snapshot_id: str,
        error_reason: str,
    ) -> BrightDataRequest:
        """Marcar request como fallido."""
        bd_request = self.db_repo.get_by_snapshot_id(snapshot_id)
        if not bd_request:
            raise ValueError(f"snapshot_id {snapshot_id} not found in DB")

        bd_request.status = BrightDataRequestStatus.FAILED
        bd_request.webhook_received_at = datetime.utcnow()
        bd_request.error_reason = error_reason
        bd_request.completed_at = datetime.utcnow()

        self.db_repo.save(bd_request)
        logger.warning(f"BD request marked failed: snapshot_id={snapshot_id}, reason={error_reason}")

        return bd_request

    def get_pending_by_run(self, run_id: str) -> list[BrightDataRequest]:
        """Obtener requests pendientes de un run."""
        all_requests = self.db_repo.get_by_run_id(run_id)
        return [r for r in all_requests if r.status in (
            BrightDataRequestStatus.PENDING,
            BrightDataRequestStatus.RETRYING,
        )]

    def close(self):
        """Cerrar sesión HTTP."""
        self.session.close()
