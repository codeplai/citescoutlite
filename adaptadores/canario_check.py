"""
S5.4 - Canario Daily Check (Quality Control)

Ejecuta cada noche a las 02:30 UTC.
Verifica que adaptadores no rompieron tras cambios en tiendas.
Si falla: alert PagerDuty + log en audit_log.
"""

import asyncio
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import statistics

from .descubrimiento_snapshot import DescubrimientoSnapshot
from .sweep_attempts import SweepAttemptsRepository, SweepAttempt, SweepAttemptStatus
from .audit_log import AuditLogRepository, AuditLogEntry, AuditLogLevel

logger = logging.getLogger(__name__)


@dataclass
class CanarioTestCase:
    """Un test case para el canario."""
    tienda_id: str
    producto_query: str
    min_ofertas: int = 15
    max_ofertas: int = 60
    min_precio: float = 0.0
    max_precio: float = 1000000.0


class CanarioChecker:
    """
    Canario que detecta roturas en adaptadores.
    Corre cada noche, verifica tiendas conocidas.
    """

    # Test cases: tiendas + productos conocidos con comportamiento estable
    TEST_CASES = [
        CanarioTestCase(
            tienda_id="vitacost",
            producto_query="quinoa",
            min_ofertas=15,
            max_ofertas=60,
        ),
        CanarioTestCase(
            tienda_id="instacart",
            producto_query="oats",
            min_ofertas=10,
            max_ofertas=50,
        ),
        CanarioTestCase(
            tienda_id="amazon",
            producto_query="rice",
            min_ofertas=20,
            max_ofertas=100,
        ),
    ]

    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self.snapshot = DescubrimientoSnapshot(db_path)
        self.sweep_repo = SweepAttemptsRepository(db_path)
        self.audit_repo = AuditLogRepository(db_path)
        self.results = []
        self.failed = False
        self.failure_reasons = []

    async def run(self) -> dict:
        """
        Ejecutar canario check.
        Retorna: {
            "timestamp": "2026-08-10T02:30:00",
            "status": "passed" | "failed",
            "tests_run": 3,
            "tests_passed": 3,
            "failures": [...],
            "alert_severity": "low" | "medium" | "high"
        }
        """
        start_time = datetime.utcnow()
        logger.info("🐤 Canario check started")

        for test_case in self.TEST_CASES:
            try:
                await self._run_test_case(test_case)
            except Exception as e:
                logger.error(f"🐤 Canario test failed for {test_case.tienda_id}: {e}")
                self.failed = True
                self.failure_reasons.append(f"{test_case.tienda_id}: {str(e)}")

        result = {
            "timestamp": start_time.isoformat(),
            "status": "passed" if not self.failed else "failed",
            "tests_run": len(self.TEST_CASES),
            "tests_passed": len(self.TEST_CASES) - len(self.failure_reasons),
            "failures": self.failure_reasons,
            "alert_severity": "high" if self.failed else "none",
            "duration_sec": (datetime.utcnow() - start_time).total_seconds(),
        }

        if self.failed:
            logger.error(f"🐤 Canario FAILED: {result}")
            # Log en audit_log
            self.audit_repo.log(AuditLogEntry(
                level=AuditLogLevel.ALERT,
                component="canario",
                message=f"Canario failed: {'; '.join(self.failure_reasons)}",
                data=result,
            ))
            # TODO: Send PagerDuty alert
            # await self._send_pagerduty_alert(result)
        else:
            logger.info(f"🐤 Canario PASSED: all {len(self.TEST_CASES)} tests OK")
            self.audit_repo.log(AuditLogEntry(
                level=AuditLogLevel.INFO,
                component="canario",
                message="Canario check passed",
                data=result,
            ))

        return result

    async def _run_test_case(self, test: CanarioTestCase) -> None:
        """
        Ejecutar un test case individual.
        Verifica: # ofertas, precio range, categorías presentes.
        """
        logger.info(f"🐤 Testing {test.tienda_id} with query '{test.producto_query}'")

        # Buscar productos
        from puertos.descubrimiento_comercial import NivelDescubrimiento
        productos = self.snapshot.descubrir(
            test.producto_query,
            NivelDescubrimiento.SNAPSHOT
        )

        # Filtrar por tienda
        tienda_productos = [p for p in productos if p.tienda_id == test.tienda_id]

        # Assertion 1: # ofertas en rango
        num_ofertas = len(tienda_productos)
        if not (test.min_ofertas <= num_ofertas <= test.max_ofertas):
            raise AssertionError(
                f"Ofertas fuera de rango: {num_ofertas} no en [{test.min_ofertas}, {test.max_ofertas}]"
            )
        logger.info(f"  ✓ Ofertas: {num_ofertas}")

        # Assertion 2: precio dentro de rango
        if tienda_productos:
            precios = [p.precio for p in tienda_productos if p.precio]
            if precios:
                precio_mediana = statistics.median(precios)
                if not (test.min_precio <= precio_mediana <= test.max_precio):
                    raise AssertionError(
                        f"Precio mediana fuera de rango: ${precio_mediana} no en [${test.min_precio}, ${test.max_precio}]"
                    )
                logger.info(f"  ✓ Precio mediana: ${precio_mediana}")

        # Assertion 3: categorías presentes
        categorias = set(p.categoria for p in tienda_productos if p.categoria)
        if not categorias:
            raise AssertionError(f"No hay categorías en resultados")
        logger.info(f"  ✓ Categorías: {categorias}")

        logger.info(f"🐤 Test passed for {test.tienda_id}")

    async def _send_pagerduty_alert(self, result: dict) -> None:
        """
        Enviar alert a PagerDuty si canario falla.
        Low priority: no despierta a nadie, pero log disponible.
        """
        try:
            # TODO: Implementar integración PagerDuty
            # import httpx
            # async with httpx.AsyncClient() as client:
            #     await client.post(
            #         "https://events.pagerduty.com/v2/enqueue",
            #         json={
            #             "routing_key": os.getenv("PAGERDUTY_KEY"),
            #             "event_action": "trigger",
            #             "dedup_key": "canario_check",
            #             "payload": {
            #                 "summary": f"Canario check failed: {result['failures']}",
            #                 "severity": "info",
            #                 "source": "canario_checker",
            #             }
            #         }
            #     )
            logger.info("PagerDuty alert sent (TODO: implement)")
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")


class CanarioScheduler:
    """
    Scheduler para ejecutar canario diariamente a las 02:30 UTC.
    Usa croniter para calcular próxima ejecución.
    """

    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self.checker = CanarioChecker(db_path)
        self.last_run = None
        self.last_result = None

    async def should_run_now(self) -> bool:
        """
        Chequear si es hora de correr el canario.
        Implementado como llamada manual en tests;
        en prod: usar APScheduler o Celery beat.
        """
        from croniter import croniter
        now = datetime.utcnow()
        cron = croniter("30 2 * * *", now)  # 02:30 UTC cada día
        last_run_time = cron.get_prev(datetime)

        # Correr si no corrió en las últimas 23 horas
        if self.last_run is None or (now - self.last_run).total_seconds() > 23 * 3600:
            return True
        return False

    async def run_if_due(self) -> Optional[dict]:
        """Correr canario si es la hora."""
        if await self.should_run_now():
            self.last_run = datetime.utcnow()
            self.last_result = await self.checker.run()
            return self.last_result
        return None

    def get_last_result(self) -> Optional[dict]:
        """Obtener resultado del último run."""
        return self.last_result
