"""
S5.1 - Scrapling Transport

Adaptador que renderiza JavaScript usando Scrapling SDK.
Pensado para las tiendas dinamicas (SPAs, lazy-load) que no se pueden leer con
una descarga simple.

Docs: https://scrapling.dev/docs

ESTADO: NO IMPLEMENTADO. Falta lo de fuera, no el codigo:

  1. La dependencia `scrapling` no esta declarada ni instalada.
  2. No hay SCRAPLING_API_KEY en el entorno (es un servicio de pago).
  3. TIENDAS_JS_PESADAS nunca se lleno: la auditoria de S5.1.4 no se hizo.

Hasta que eso exista, `buscar()` devuelve NOT_CONFIGURED. Antes devolvia un
HTML de mentira —"<!-- Rendered by Scrapling ... -->"— con status SUCCESS, y
eso es peor que no estar: quien lo conectara al barrido habria contado esas
tiendas como verificadas en sweep_attempts, inflando la cobertura declarada de
P14 con tiendas que nunca se consultaron. La cobertura es justo lo que se le
promete al cliente como medido.
"""

import logging
import asyncio
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class TransportStatus(str, Enum):
    """Estados de un request de transport."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"
    ERROR = "error"
    # El transporte no esta operativo (sin SDK o sin credencial). No es un
    # fallo de la tienda: no debe contar como intento verificado ni como
    # bloqueo de la tienda al calcular cobertura.
    NOT_CONFIGURED = "not_configured"


class ScraplingTransport:
    """
    Transport que usa Scrapling SDK para renderizar JavaScript dinámico.

    Características:
    - Timeout: 30s por página (JS render tarda)
    - Rate-limit: 0.1 req/s por dominio
    - Concurrencia: 5 workers simultáneos
    - Fallback: si falla, retornar HTML vacío (status='timeout')
    """

    # Tiendas dinamicas (JS-heavy). Vacio: la auditoria de S5.1.4 que debia
    # llenarlo no se hizo. Tenia dos entradas de ejemplo, shop.example.com y
    # spa.example.com, que get_tiendas_soportadas() devolvia como si fueran
    # tiendas reales soportadas.
    TIENDAS_JS_PESADAS: dict[str, str] = {}

    def __init__(self, api_key: Optional[str] = None, timeout_sec: int = 30, max_workers: int = 5):
        """
        Inicializar Scrapling transport.

        Args:
            api_key: Scrapling API key (o desde env SCRAPLING_API_KEY)
            timeout_sec: Timeout por request en segundos
            max_workers: Máximo de requests concurrentes
        """
        self.api_key = api_key
        self.timeout_sec = timeout_sec
        self.max_workers = max_workers
        self.rate_limit_delay = 1.0 / 0.1  # 0.1 req/s = 10s entre requests
        self._request_count = 0
        self._last_request_time = 0

        # Cuando la dependencia exista, aqui va:
        #     from scrapling import Client
        #     self.client = Client(api_key=self.api_key)
        # De momento no hay SDK que instanciar, y se dice en voz alta en vez de
        # dejar el atributo a None sin mas.
        self.client = None
        logger.warning(
            "ScraplingTransport sin cliente: falta la dependencia `scrapling` "
            "y SCRAPLING_API_KEY. buscar() devolvera NOT_CONFIGURED."
        )

    async def buscar(self, url: str, query: str, tienda_id: str) -> tuple[str, TransportStatus]:
        """
        Buscar productos en una tienda dinámica usando Scrapling.

        Args:
            url: URL de la tienda
            query: Query de búsqueda (ej: "quinua")
            tienda_id: ID interno de la tienda

        Returns:
            (html_completo, status)
            - html_completo: HTML renderizado con JS ejecutado
            - status: TransportStatus indicando resultado
        """
        if self.client is None:
            # Sin SDK no hay nada que renderizar. Se sale antes del rate-limit
            # porque no hay peticion que espaciar.
            logger.warning(
                f"Scrapling no configurado; no se consulta {tienda_id} ({url})")
            return "", TransportStatus.NOT_CONFIGURED

        try:
            # Aplicar rate-limit (0.1 req/s)
            await self._apply_rate_limit()

            logger.info(f"Scrapling request: tienda={tienda_id}, url={url}, query={query}")

            html = await asyncio.wait_for(
                self.client.render_page(url, headless=True),
                timeout=self.timeout_sec,
            )

            return html, TransportStatus.SUCCESS

        except asyncio.TimeoutError:
            logger.warning(f"Scrapling timeout: tienda={tienda_id}, url={url}")
            return "", TransportStatus.TIMEOUT

        except Exception as e:
            logger.error(f"Scrapling error: tienda={tienda_id}, url={url}, error={e}")
            return "", TransportStatus.ERROR

    async def _apply_rate_limit(self):
        """Aplicar rate-limit: 0.1 req/s = 10s entre requests."""
        import time
        now = time.time()
        if self._last_request_time > 0:
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - elapsed
                logger.debug(f"Rate-limit: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

        self._last_request_time = time.time()
        self._request_count += 1

    async def test_connection(self) -> bool:
        """Test que Scrapling API está disponible.

        Devolvia True incondicionalmente, incluso sin cliente: un chequeo de
        salud que solo sabe decir que si no sirve para nada, y aqui ademas
        habria dado por operativo un transporte inexistente.
        """
        if self.client is None:
            logger.warning("Scrapling sin cliente: conexión no disponible")
            return False

        try:
            logger.info("Testing Scrapling connection...")
            await self.client.test_auth()
            logger.info("Scrapling connection OK")
            return True
        except Exception as e:
            logger.error(f"Scrapling connection failed: {e}")
            return False

    def get_tiendas_soportadas(self) -> list[str]:
        """Tiendas dinámicas soportadas. Vacío mientras no haya auditoría."""
        return list(self.TIENDAS_JS_PESADAS.keys())
