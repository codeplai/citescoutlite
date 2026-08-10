"""
S5.7 - Puerto Descubrimiento con N2 Async

Wrapper sobre DescubrimientoCascada que:
- N1: Retorna inmediatamente (sync)
- N2: Enqueue async, no espera
- UX: Usuario ve N1 rápido, N2 llega después via webhook

Responde al protocolo DescubrimientoComercial pero añade async.
"""

import asyncio
import logging
from typing import Optional
from uuid import uuid4
from datetime import datetime

from dominio.producto_en_mercado import ProductoEnMercado
from puertos.descubrimiento_comercial import NivelDescubrimiento
from .descubrimiento_cascada import DescubrimientoCascada, DescubrimientoCascadaMetadata
from .bright_data_api import BrightDataClient
from .bright_data_requests import BrightDataRequestStatus

logger = logging.getLogger(__name__)


class N2Status(str):
    """Status del descubrimiento N2 para respuesta HTTP."""
    COMPLETED = "completed"      # Webhook llegó, datos disponibles
    PENDING = "pending"          # Enqueue exitoso, waiting webhook
    SKIPPED = "skipped"          # Level no pedido
    FAILED = "failed"            # Error en enqueue
    TIMEOUT = "timeout"          # Timeout esperando


class DescubrimientoComercialAsync:
    """
    Versión async de DescubrimientoCascada para Puerto.

    Diferencia con descubrir_sync():
    - N1: Ejecuta sync (rápido, ~50-100ms)
    - N2: Enqueue async, retorna inmediatamente
         No espera webhook (timeout 30s en versión sync se ignora)
    - Usuario obtiene N1 al toque + N2 llega después

    Usado por: API endpoint `GET /discovery?nivel=2&insumo=quinua`
    """

    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self.cascada = DescubrimientoCascada(db_path)
        self.bd_client = None

    def _get_bd_client(self) -> BrightDataClient:
        """Lazy init BD client."""
        if self.bd_client is None:
            self.bd_client = BrightDataClient(db_path=self.db_path)
        return self.bd_client

    async def descubrir_async(
        self,
        insumo: str,
        pais: str = "Perú",
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
        timeout_n2_sec: int = 5,  # Timeout CORTO: no bloquear al usuario
    ) -> dict:
        """
        Descubrimiento con N2 async (no-blocking).

        Retorna:
        {
            "productos": [...N1 results...],
            "metadata": {...},
            "n2_status": "pending" | "completed" | "failed" | "skipped",
            "run_id": "uuid para tracking",
            "note": "N2 en proceso, recarga en 1-5 min para ver datos"
        }
        """
        run_id = str(uuid4())
        start_time = datetime.utcnow()

        logger.info(
            f"Descubrimiento async start: insumo={insumo}, nivel={nivel_maximo}, run_id={run_id}"
        )

        # N1: Always sync (rápido)
        try:
            n1_productos = self.cascada.descubrir_n1(insumo)
            logger.info(f"N1 complete: {len(n1_productos)} productos")
        except Exception as e:
            logger.error(f"N1 error: {e}")
            n1_productos = []

        # N2: Async (no-blocking)
        n2_status = N2Status.SKIPPED
        n2_productos = []

        if nivel_maximo >= NivelDescubrimiento.API_LICENCIADA:
            try:
                # Enqueue N2 async
                await self._enqueue_n2_async(insumo, pais, run_id)
                n2_status = N2Status.PENDING
                logger.info(f"N2 enqueued: run_id={run_id} (waiting webhook...)")

            except Exception as e:
                logger.error(f"N2 enqueue error: {e}")
                n2_status = N2Status.FAILED

        # N3: Check for gaps (like descubrir_sync)
        has_gaps = self.cascada._has_gaps(n1_productos, insumo)
        n3_staging = 0

        if nivel_maximo >= NivelDescubrimiento.AGENTE_WEB and has_gaps:
            try:
                agente_resultado, staging_items = await self.cascada.descubrir_n3(insumo, pais)
                n3_staging = len(staging_items)
            except Exception as e:
                logger.error(f"N3 error: {e}")

        # Metadata
        niveles_ejecutados = [1]  # N1 siempre
        if n2_status == N2Status.PENDING or n2_status == N2Status.COMPLETED:
            niveles_ejecutados.append(2)
        if n3_staging > 0:
            niveles_ejecutados.append(3)

        metadata = DescubrimientoCascadaMetadata(
            nivel_solicitado=int(nivel_maximo),
            niveles_ejecutados=niveles_ejecutados,
            niveles_no_disponibles=[n for n in [1, 2, 3] if n <= nivel_maximo and n not in niveles_ejecutados],
            productos_n1=len(n1_productos),
            productos_n2=len(n2_productos),
            productos_n3_staging=n3_staging,
            has_gaps=has_gaps,
            gap_reason="Cobertura insuficiente" if has_gaps else None,
        )

        # Nota para usuario
        note = None
        if n2_status == N2Status.PENDING:
            note = f"N2 en proceso (recarga en 1-5 minutos para ver datos). run_id={run_id}"
        elif n2_status == N2Status.FAILED:
            note = "Error enqueuing N2; mostrando solo N1"

        elapsed_sec = (datetime.utcnow() - start_time).total_seconds()
        logger.info(
            f"Descubrimiento complete: {len(n1_productos)} N1, "
            f"N2={n2_status}, elapsed={elapsed_sec:.2f}s"
        )

        return {
            "productos": n1_productos,
            "metadata": metadata,
            "n2_status": n2_status,
            "run_id": run_id,
            "note": note,
            "elapsed_sec": elapsed_sec,
        }

    async def _enqueue_n2_async(self, insumo: str, pais: str, run_id: str) -> None:
        """
        Enqueue N2 (Bright Data) sin esperar.

        Envia requests a BD para las 5 tiendas, retorna inmediatamente.
        BD llamará webhook cuando esté listo.
        """
        bd_client = self._get_bd_client()

        # Las 5 tiendas N2
        tiendas = list(bd_client.TIENDAS_N2.keys())
        logger.info(f"Enqueuing N2 for {len(tiendas)} tiendas: {tiendas}")

        for tienda_id in tiendas:
            try:
                url = bd_client.TIENDAS_N2.get(tienda_id)
                if not url:
                    logger.warning(f"N2: No URL for {tienda_id}")
                    continue

                bd_client.enqueue_scrape(
                    url=url,
                    query=insumo,
                    tienda_id=tienda_id,
                    run_id=run_id,
                )
                logger.debug(f"N2 enqueued: {tienda_id}")

            except Exception as e:
                logger.error(f"N2 enqueue error for {tienda_id}: {e}")
                # Continue on error, don't block

    def descubrir_sync(
        self,
        insumo: str,
        pais: str = "Perú",
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> tuple[list[ProductoEnMercado], DescubrimientoCascadaMetadata]:
        """
        Versión sync para etapa_sync (mapear_comercio).

        Usa asyncio.run() para ejecutar versión async.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                self.descubrir_async(insumo, pais, nivel_maximo, timeout_n2_sec=5)
            )
            return result["productos"], result["metadata"]
        finally:
            loop.close()

    def descubrir(
        self,
        insumo: str,
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> list[ProductoEnMercado]:
        """
        Implementa protocolo DescubrimientoComercial (sync).

        Retorna solo N1 (N2 es async, no disponible en sync).
        """
        return self.cascada.descubrir_n1(insumo)

    def niveles_no_disponibles(
        self,
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> list[int]:
        """Niveles no implementados."""
        # Ahora N2 sí está disponible (async)
        no_disponibles = []
        # N1 siempre disponible
        # N2 disponible (async)
        # N3 disponible si adaptador de agente existe
        return no_disponibles
