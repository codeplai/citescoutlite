"""
Parser de robots.txt para respetar reglas de crawling (S2.2).

Implementa:
  - Parsea robots.txt de cada dominio
  - Aplica reglas Disallow, Crawl-delay, Request-rate
  - Cachea resultados (TTL 24h)
  - User-Agent: AgroScoutIA/1.0 (+https://agroscout.ai/bot)
"""

import asyncio
import time
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import httpx


USER_AGENT = "AgroScoutIA/1.0 (+https://agroscout.ai/bot)"
CACHE_TTL = 24 * 3600  # 24 horas


class RobotsCache:
    """Cachea reglas de robots.txt por dominio."""

    def __init__(self):
        self.cache = {}  # domain -> (parser: RobotFileParser, timestamp)

    def get(self, domain: str) -> Optional[RobotFileParser]:
        """Retorna parser cacheado si aún es válido."""
        if domain not in self.cache:
            return None
        parser, timestamp = self.cache[domain]
        if time.time() - timestamp > CACHE_TTL:
            del self.cache[domain]
            return None
        return parser

    def set(self, domain: str, parser: RobotFileParser) -> None:
        """Cachea un parser."""
        self.cache[domain] = (parser, time.time())

    def get_status(self, domain: str) -> dict:
        """Estado del cache para un dominio."""
        if domain not in self.cache:
            return {"cached": False}
        parser, timestamp = self.cache[domain]
        age_hours = (time.time() - timestamp) / 3600
        return {
            "cached": True,
            "age_hours": age_hours,
            "ttl_hours": CACHE_TTL / 3600,
        }


class RobotsParser:
    """Parsea y cachea reglas de robots.txt."""

    def __init__(self):
        self.cache = RobotsCache()
        self.http_client = None  # Lazy init

    async def fetch_robots_txt(self, domain: str) -> Optional[str]:
        """Descarga robots.txt de un dominio."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=10.0)

        try:
            url = f"https://{domain}/robots.txt"
            resp = await self.http_client.get(
                url,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            )
            if resp.status_code == 200:
                return resp.text
            else:
                # 404, 403, etc. = no hay robots.txt, permitir todo
                return ""
        except Exception as e:
            # Timeout, connection error, etc. = asumir permitido
            return ""

    async def get_parser(self, domain: str) -> RobotFileParser:
        """Obtiene parser cacheado o descarga robots.txt."""
        parser = self.cache.get(domain)
        if parser is not None:
            return parser

        # Descargar
        robots_txt = await self.fetch_robots_txt(domain)
        parser = RobotFileParser()
        parser.set_url(f"https://{domain}/robots.txt")
        parser.parse(robots_txt.split("\n") if robots_txt else [])
        self.cache.set(domain, parser)
        return parser

    async def can_fetch(self, url: str) -> bool:
        """¿Se puede hacer fetch a esta URL según robots.txt?"""
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"

        parser = await self.get_parser(domain)
        # RobotFileParser.can_fetch(useragent, url)
        # Pero solo funciona si el path está en la URL
        return parser.can_fetch(USER_AGENT, url)

    async def get_crawl_delay(self, domain: str) -> float:
        """Retorna Crawl-delay de robots.txt (segundos)."""
        parser = await self.get_parser(domain)
        delay = parser.crawl_delay(USER_AGENT)
        return delay or 0.0

    async def get_request_rate(self, domain: str) -> Optional[tuple[int, int]]:
        """Retorna Request-rate de robots.txt (requests, seconds)."""
        parser = await self.get_parser(domain)
        rate = parser.request_rate(USER_AGENT)
        if rate:
            return (rate.requests, rate.seconds)
        return None

    def get_cache_status(self, domain: str) -> dict:
        """Estado del cache de robots.txt."""
        return self.cache.get_status(domain)

    async def close(self) -> None:
        """Cierra el cliente HTTP."""
        if self.http_client:
            await self.http_client.aclose()


# Instancia global
_robots_parser = RobotsParser()


async def check_robots_txt(url: str) -> tuple[bool, Optional[str]]:
    """
    ¿Se puede hacer fetch a esta URL según robots.txt?
    Retorna (allowed: bool, reason: str|None)
    """
    try:
        allowed = await _robots_parser.can_fetch(url)
        if not allowed:
            return False, "Disallowed por robots.txt"
        return True, None
    except Exception as e:
        # Si hay error, permitir (fail-open)
        return True, None


async def get_crawl_delay(domain: str) -> float:
    """Retorna Crawl-delay de robots.txt."""
    try:
        return await _robots_parser.get_crawl_delay(domain)
    except Exception:
        return 0.0


async def get_robots_cache_status(domain: str) -> dict:
    """Estado del cache de robots.txt."""
    return _robots_parser.get_cache_status(domain)


async def close_robots_parser() -> None:
    """Cierra recursos."""
    await _robots_parser.close()
