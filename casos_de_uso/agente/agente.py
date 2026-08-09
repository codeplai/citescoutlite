"""
AgenteInvestigadorComercial: busca productos en web con Tavily, extrae datos (S2.1).

Toolset:
  1. buscar_web(query, país) → lista de URLs via Tavily
  2. abrir_url(url) → HTML via trafilatura + rate-limiting + robots.txt
  3. extraer_producto(html, schema) → JSONB via glm-5.2 (Huawei)

Timeouts: 60s búsqueda, 30s extracción, 10s validación.
"""

import asyncio
import os
import time
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from pydantic_ai import Agent
import httpx
import trafilatura
from tavily import TavilyClient

from .schemas import ProductoSchema, ExtraccionProductoResultado, AgenteResultado, BusquedaWebResultado
from ..integraciones import check_rate_limit, record_request_success, record_request_failure

load_dotenv()

# Configuración
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
HUAWEI_MAAS_BASE_URL = os.getenv("HUAWEI_MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
HUAWEI_MAAS_API_KEY = os.getenv("HUAWEI_MAAS_API_KEY", "")

# Timeouts
TIMEOUT_BUSQUEDA = 60  # segundos
TIMEOUT_EXTRACCION = 30
TIMEOUT_VALIDACION = 10


class AgenteInvestigadorComercial:
    """Agente que busca productos en web y los extrae."""

    def __init__(self):
        self.tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.products_extracted = 0
        self.start_time = None

    async def buscar_web(self, query: str, pais: str) -> list[BusquedaWebResultado]:
        """
        Busca en web usando Tavily API.
        Retorna lista de resultados (URL + preview).
        """
        if not self.tavily_client:
            raise ValueError("TAVILY_API_KEY no configurado")

        try:
            query_con_pais = f"{query} {pais}" if pais not in query else query
            results = self.tavily_client.search(
                query_con_pais,
                max_results=5,
                topic="general",
                include_answer=False,
            )

            resultados = []
            for item in results.get("results", []):
                resultados.append(
                    BusquedaWebResultado(
                        titulo=item.get("title", ""),
                        url=item.get("url", ""),
                        contenido_preview=item.get("content", "")[:500],
                        fuente=item.get("source", ""),
                    )
                )
            return resultados
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tavily search timeout después de {TIMEOUT_BUSQUEDA}s")
        except Exception as e:
            raise RuntimeError(f"Tavily search error: {e}")

    async def abrir_url(self, url: str) -> str:
        """
        Descarga HTML de URL respetando rate-limiting y robots.txt.
        Usa trafilatura para extraer contenido principal.
        """
        try:
            # Rate limiting + robots.txt check
            await check_rate_limit(url)

            # Descargar
            resp = await self.http_client.get(
                url,
                headers={"User-Agent": "AgroScoutIA/1.0 (+https://agroscout.ai/bot)"},
                follow_redirects=True,
                timeout=30.0,
            )
            resp.raise_for_status()
            record_request_success(url)

            # Extraer HTML limpio
            html = trafilatura.extract(resp.text, include_comments=False)
            return html or resp.text
        except asyncio.TimeoutError:
            raise TimeoutError(f"URL fetch timeout: {url}")
        except Exception as e:
            record_request_failure(url)
            raise RuntimeError(f"URL fetch error ({url}): {e}")

    async def extraer_producto(self, html: str, schema: ProductoSchema) -> ProductoSchema:
        """
        Extrae datos estructurados de HTML usando glm-5.2 (Huawei ModelArts).
        Usa Pydantic AI para tool-use.
        """
        if not HUAWEI_MAAS_API_KEY:
            raise ValueError("HUAWEI_MAAS_API_KEY no configurado")

        try:
            # Crear agente extractor con glm-5.2
            agent = Agent(
                model_type="openai",
                model_name="glm-5.2",
                api_key=HUAWEI_MAAS_API_KEY,
                base_url=HUAWEI_MAAS_BASE_URL,
            )

            prompt = f"""Extrae datos de producto de este HTML.
Retorna un JSON con estos campos:
- nombre (str, requerido)
- precio (float|null)
- precio_local (str|null, ej: "ARS 1200")
- marca (str|null)
- stock (int|null)
- descripcion (str|null)
- unidad (str|null, ej: "kg")
- categoria (str|null)
- pais_origen (str|null)
- fecha_disponibilidad (str|null, YYYY-MM-DD)

HTML:
{html[:2000]}  # Limitar a 2000 chars para no sobrecargar

Retorna SOLO el JSON, sin explicaciones."""

            # TODO(s2): Implementar llamada real a glm-5.2 con manejo de timeout
            # Por ahora, retornar schema dummy para que compile
            return schema
        except asyncio.TimeoutError:
            raise TimeoutError(f"Extracción timeout después de {TIMEOUT_EXTRACCION}s")
        except Exception as e:
            raise RuntimeError(f"Extracción error: {e}")

    async def ejecutar(self, insumo: str, pais: str) -> AgenteResultado:
        """
        Ejecuta el agente: busca productos y extrae datos.
        Retorna resultado agregado.
        """
        self.start_time = time.time()
        self.products_extracted = 0
        productos = []
        errores = []

        try:
            # 1. Buscar en web
            print(f"🔍 Buscando '{insumo}' en {pais}...")
            resultados_busqueda = await asyncio.wait_for(
                self.buscar_web(insumo, pais),
                timeout=TIMEOUT_BUSQUEDA,
            )
            print(f"   ✅ Encontrados {len(resultados_busqueda)} resultados")

            # 2. Procesar cada URL
            for idx, resultado in enumerate(resultados_busqueda[:3]):  # Max 3 URLs
                try:
                    print(f"   📄 Abriendo URL {idx+1}: {resultado.url[:50]}...")
                    html = await asyncio.wait_for(
                        self.abrir_url(resultado.url),
                        timeout=30,
                    )

                    # 3. Extraer producto de HTML
                    print(f"   📊 Extrayendo datos...")
                    producto = await asyncio.wait_for(
                        self.extraer_producto(html, ProductoSchema),
                        timeout=TIMEOUT_EXTRACCION,
                    )

                    # Empaquetar resultado
                    extraccion = ExtraccionProductoResultado(
                        producto=producto,
                        fuente_url=resultado.url,
                        html_capturado=html[:500] if html else None,
                        timestamp=datetime.now(),
                        modelo_usado="glm-5.2",
                    )
                    productos.append(extraccion)
                    self.products_extracted += 1
                    print(f"   ✅ Producto extraído: {producto.nombre}")

                except TimeoutError as e:
                    errores.append(f"Timeout en {resultado.url}: {e}")
                    print(f"   ⏱️  {errores[-1]}")
                except Exception as e:
                    errores.append(f"Error en {resultado.url}: {e}")
                    print(f"   ❌ {errores[-1]}")

            # 4. Retornar resultado
            tiempo_ms = int((time.time() - self.start_time) * 1000)
            return AgenteResultado(
                insumo=insumo,
                pais=pais,
                productos_encontrados=productos,
                total_items_buscados=len(resultados_busqueda),
                tiempo_total_ms=tiempo_ms,
                errores=errores,
                estado="ok" if productos else "parcial" if errores else "error",
            )

        except Exception as e:
            tiempo_ms = int((time.time() - self.start_time) * 1000)
            return AgenteResultado(
                insumo=insumo,
                pais=pais,
                productos_encontrados=productos,
                total_items_buscados=0,
                tiempo_total_ms=tiempo_ms,
                errores=errores + [str(e)],
                estado="error",
            )

    async def close(self) -> None:
        """Cierra conexiones."""
        await self.http_client.aclose()
