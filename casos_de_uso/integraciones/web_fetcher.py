"""
Web fetcher que respeta rate-limiting, robots.txt y circuito abierto.
Usado por AgenteInvestigadorComercial en S2.1.
"""

import httpx
from typing import Optional
from .rate_limiter import (
    check_rate_limit,
    record_request_success,
    record_request_failure,
)
from .robots_parser import check_robots_txt


class WebFetcher:
    """
    Realiza requests HTTP respetando:
      - Rate limiting por dominio (token bucket 0.4 req/s)
      - Robots.txt (Disallow, Crawl-delay, Request-rate)
      - Circuit breaker (3 fallos = pausa 6h)
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def fetch(self, url: str) -> Optional[str]:
        """
        Descarga HTML de URL respetando todas las restricciones.
        Retorna el contenido HTML, o None si hay error.
        """
        # 1. Verificar robots.txt
        allowed, reason = await check_robots_txt(url)
        if not allowed:
            raise PermissionError(f"robots.txt: {reason}")

        # 2. Esperar según rate limit
        await check_rate_limit(url)

        # 3. Hacer request
        try:
            resp = await self.client.get(
                url,
                headers={"User-Agent": "AgroScoutIA/1.0 (+https://agroscout.ai/bot)"},
                follow_redirects=True,
            )
            resp.raise_for_status()
            record_request_success(url)
            return resp.text
        except httpx.HTTPError as e:
            record_request_failure(url)
            raise

    async def close(self) -> None:
        """Cierra el cliente HTTP."""
        await self.client.aclose()
