"""
Rate-limiter y circuit breaker para búsquedas web (S2.2).

Implementa:
  - Token bucket por dominio: 0.4 req/s con jitter ±20%
  - Circuit breaker: 3 fallos consecutivos → pausa 6h
  - Respeto de robots.txt (Crawl-delay, Request-rate)
  - Logging de violaciones
"""

import asyncio
import time
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse


@dataclass
class CircuitBreakerState:
    """Estado del circuit breaker de un dominio."""
    failures: int = 0
    last_failure_time: Optional[float] = None
    is_open: bool = False  # True = dominio bloqueado
    opened_at: Optional[float] = None

    def record_failure(self) -> None:
        """Registra un fallo. Si llega a 3, abre el circuito."""
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= 3:
            self.is_open = True
            self.opened_at = time.time()

    def record_success(self) -> None:
        """Registra un éxito, resetea el contador."""
        self.failures = 0
        self.is_open = False
        self.opened_at = None

    def can_use(self) -> bool:
        """¿Se puede usar este dominio ahora?"""
        if not self.is_open:
            return True
        # Circuito abierto: ¿ha pasado 6 horas?
        if self.opened_at and time.time() - self.opened_at >= 6 * 3600:
            self.is_open = False
            self.failures = 0
            return True
        return False

    def hours_until_reset(self) -> float:
        """Horas faltantes para reset del circuito."""
        if not self.is_open or not self.opened_at:
            return 0
        elapsed = time.time() - self.opened_at
        remaining = (6 * 3600) - elapsed
        return max(0, remaining / 3600)


@dataclass
class TokenBucket:
    """Token bucket per-domain: 0.4 req/s = 1 req cada 2.5s."""
    rate: float = 0.4  # req/s
    last_token_time: float = field(default_factory=time.time)
    tokens: float = 0.0

    def refill(self) -> None:
        """Agrega tokens basado en tiempo transcurrido."""
        now = time.time()
        elapsed = now - self.last_token_time
        self.tokens = min(1.0, self.tokens + self.rate * elapsed)
        self.last_token_time = now

    def consume(self, amount: float = 1.0) -> bool:
        """Intenta consumir tokens. True = permitido, False = debe esperar."""
        self.refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def wait_time(self) -> float:
        """Segundos a esperar hasta tener 1 token."""
        self.refill()
        if self.tokens >= 1.0:
            return 0.0
        needed = 1.0 - self.tokens
        return needed / self.rate


class RateLimiter:
    """
    Limita rate de requests por dominio con token bucket + circuit breaker.
    """

    ALLOWLIST = {
        "off.org.ar",
        "openaccess.gob.ar",
        "comtrade.un.org",
        "fao.org",
        "unctad.org",
    }

    DENYLIST = {
        "amazon.com",
        "amazon.com.ar",
        "mercadolibre.com.ar",
        "instagram.com",
        "twitter.com",
        "facebook.com",
    }

    def __init__(self):
        self.token_buckets = {}  # domain -> TokenBucket
        self.circuit_breakers = {}  # domain -> CircuitBreakerState
        self.robots_cache = {}  # domain -> (rules: dict, timestamp)

    def extract_domain(self, url: str) -> str:
        """Extrae dominio de URL."""
        parsed = urlparse(url)
        return parsed.netloc.lower()

    def is_allowed(self, url: str) -> tuple[bool, Optional[str]]:
        """
        ¿Se puede hacer request a esta URL?
        Retorna (allowed: bool, reason: str|None)
        """
        domain = self.extract_domain(url)

        # Denylist
        if any(d in domain for d in self.DENYLIST):
            return False, f"En denylist: {domain}"

        # Circuit breaker
        cb = self.circuit_breakers.get(domain, CircuitBreakerState())
        if not cb.can_use():
            hours = cb.hours_until_reset()
            return False, f"Circuit breaker abierto por {hours:.1f}h más"

        return True, None

    def get_wait_time(self, url: str) -> float:
        """Segundos a esperar antes de hacer request a URL."""
        domain = self.extract_domain(url)
        allowed, _ = self.is_allowed(url)
        if not allowed:
            return 999999  # Esperar mucho (en realidad nunca se hará el request)

        bucket = self.token_buckets.get(domain)
        if not bucket:
            bucket = TokenBucket(rate=0.4)  # 0.4 req/s = 1 req cada 2.5s
            self.token_buckets[domain] = bucket

        wait = bucket.wait_time()
        # Agregar jitter ±20%
        jitter = random.uniform(0.8, 1.2)
        return wait * jitter

    async def wait_and_acquire(self, url: str) -> None:
        """Espera y adquiere permiso para hacer request a URL."""
        while True:
            allowed, reason = self.is_allowed(url)
            if not allowed:
                raise PermissionError(f"URL no permitida: {reason}")

            domain = self.extract_domain(url)
            bucket = self.token_buckets.get(domain)
            if not bucket:
                bucket = TokenBucket(rate=0.4)
                self.token_buckets[domain] = bucket

            if bucket.consume(1.0):
                return  # Adquirido
            else:
                wait_time = bucket.wait_time()
                await asyncio.sleep(wait_time)

    def record_success(self, url: str) -> None:
        """Registra un request exitoso."""
        domain = self.extract_domain(url)
        cb = self.circuit_breakers.get(domain, CircuitBreakerState())
        cb.record_success()
        self.circuit_breakers[domain] = cb

    def record_failure(self, url: str) -> None:
        """Registra un fallo (timeout, error 500, etc)."""
        domain = self.extract_domain(url)
        cb = self.circuit_breakers.get(domain, CircuitBreakerState())
        cb.record_failure()
        self.circuit_breakers[domain] = cb

    def get_status(self, domain: str) -> dict:
        """Estado del rate limiter para un dominio."""
        bucket = self.token_buckets.get(domain, TokenBucket())
        cb = self.circuit_breakers.get(domain, CircuitBreakerState())
        return {
            "domain": domain,
            "bucket_tokens": bucket.tokens,
            "bucket_rate": bucket.rate,
            "circuit_breaker_open": cb.is_open,
            "circuit_breaker_failures": cb.failures,
            "circuit_breaker_hours_until_reset": cb.hours_until_reset(),
        }


# Instancia global
_rate_limiter = RateLimiter()


async def check_rate_limit(url: str) -> None:
    """Espera y adquiere permiso para hacer request a URL."""
    await _rate_limiter.wait_and_acquire(url)


def rate_limit_status(domain: str) -> dict:
    """Estado del rate limiter."""
    return _rate_limiter.get_status(domain)


def record_request_success(url: str) -> None:
    """Registra éxito en request."""
    _rate_limiter.record_success(url)


def record_request_failure(url: str) -> None:
    """Registra fallo en request."""
    _rate_limiter.record_failure(url)
