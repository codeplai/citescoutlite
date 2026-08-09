"""
Failover para búsqueda: Tavily (primario) → Brave (fallback) (S2.10).

Si Tavily falla 3 veces consecutivas, cambia automáticamente a Brave Search.
Reset cada 1 hora.
"""

import time
import httpx
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import json


@dataclass
class FailoverState:
    """Estado del circuit breaker para Tavily."""
    failures: int = 0
    last_failure_time: Optional[float] = None
    using_brave: bool = False  # True = usando Brave, False = usando Tavily
    switched_at: Optional[float] = None  # Cuándo se switcheó a Brave
    total_failures: int = 0  # Total acumulado (para logging)

    def record_failure(self) -> None:
        """Registra un fallo."""
        self.failures += 1
        self.total_failures += 1
        self.last_failure_time = time.time()
        if self.failures >= 3:
            self.using_brave = True
            self.switched_at = time.time()

    def record_success(self) -> None:
        """Registra un éxito, resetea el contador."""
        self.failures = 0

    def check_reset(self) -> None:
        """Verifica si se debe resetear (1 hora desde switch a Brave)."""
        if self.using_brave and self.switched_at:
            if time.time() - self.switched_at >= 3600:  # 1 hora
                self.using_brave = False
                self.failures = 0
                self.switched_at = None

    def hours_until_reset(self) -> float:
        """Horas faltantes para reset."""
        if not self.using_brave or not self.switched_at:
            return 0
        elapsed = time.time() - self.switched_at
        remaining = 3600 - elapsed
        return max(0, remaining / 3600)


class SearchFailover:
    """Maneja failover entre Tavily y Brave Search."""

    BRAVE_API_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, tavily_client=None, brave_api_key: Optional[str] = None):
        self.tavily_client = tavily_client
        self.brave_api_key = brave_api_key
        self.state = FailoverState()
        self.http_client = httpx.AsyncClient()

    async def search(self, query: str, max_results: int = 5) -> dict:
        """
        Busca con failover automático.
        Retorna: {"results": [...], "source": "tavily"|"brave", "from_failover": bool}
        """
        self.state.check_reset()

        if self.state.using_brave:
            # Usar Brave
            try:
                results = await self._search_brave(query, max_results)
                self.state.record_success()
                return {
                    "results": results,
                    "source": "brave",
                    "from_failover": True,
                }
            except Exception as e:
                raise RuntimeError(f"Brave search failed: {e}")
        else:
            # Usar Tavily (primario)
            try:
                if not self.tavily_client:
                    raise ValueError("Tavily client not initialized")

                results = self.tavily_client.search(
                    query,
                    max_results=max_results,
                    topic="general",
                    include_answer=False,
                )
                self.state.record_success()
                return {
                    "results": results.get("results", []),
                    "source": "tavily",
                    "from_failover": False,
                }
            except Exception as e:
                self.state.record_failure()
                if self.state.using_brave:
                    # Ahora usar Brave
                    try:
                        results = await self._search_brave(query, max_results)
                        self.state.record_success()
                        return {
                            "results": results,
                            "source": "brave",
                            "from_failover": True,
                        }
                    except Exception as e2:
                        raise RuntimeError(f"Failover to Brave failed: {e2}")
                else:
                    raise RuntimeError(f"Tavily search failed: {e}")

    async def _search_brave(self, query: str, max_results: int = 5) -> list:
        """Busca usando Brave Search API."""
        if not self.brave_api_key:
            raise ValueError("BRAVE_SEARCH_API_KEY not configured")

        try:
            resp = await self.http_client.get(
                self.BRAVE_API_ENDPOINT,
                params={
                    "q": query,
                    "count": max_results,
                },
                headers={
                    "User-Agent": "AgroScoutIA/1.0",
                    "X-Subscription-Token": self.brave_api_key,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            # Convertir formato Brave → Tavily
            results = []
            for item in data.get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("description", "")[:500],
                    "source": "brave",
                })
            return results
        except Exception as e:
            raise RuntimeError(f"Brave API error: {e}")

    def get_status(self) -> dict:
        """Retorna estado actual del failover."""
        self.state.check_reset()
        return {
            "using_brave": self.state.using_brave,
            "tavily_failures": self.state.failures,
            "total_failures": self.state.total_failures,
            "hours_until_reset": self.state.hours_until_reset(),
            "switched_at": self.state.switched_at,
        }

    async def close(self) -> None:
        """Cierra conexiones."""
        await self.http_client.aclose()
