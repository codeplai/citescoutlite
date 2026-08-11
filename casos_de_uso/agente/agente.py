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
import instructor
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential
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

# Mismo modelo que las etapas 3-5 en RedactorGLM. El prefijo 'openai/' es lo
# que hace que litellm hable el dialecto OpenAI contra ModelArts.
MODELO_EXTRACCION = "openai/glm-5.2"

# Cuanto HTML se le manda al modelo. trafilatura ya devuelve solo el contenido
# principal, pero 2000 caracteres —lo que habia— no llegan ni al precio en una
# ficha de producto normal: se corta antes de la parte util.
MAX_CARACTERES_HTML = 6000

# Reintentos cortos a proposito: quien llama envuelve esto en un
# asyncio.wait_for(TIMEOUT_EXTRACCION), asi que un backoff largo solo sirve
# para agotar el timeout sin llegar a reintentar de verdad.
# reraise: sin el, al agotar los intentos tenacity lanza un RetryError que
# esconde la causa, y arriba solo se ve "RetryError[Future...]".
_REINTENTOS = dict(stop=stop_after_attempt(3),
                   wait=wait_exponential(multiplier=1, min=1, max=4),
                   reraise=True)


class AgenteInvestigadorComercial:
    """Agente que busca productos en web y los extrae."""

    def __init__(self):
        self.tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.llm = instructor.from_litellm(acompletion)
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

    async def extraer_producto(self, html: str,
                               schema: type[ProductoSchema] = ProductoSchema) -> ProductoSchema:
        """
        Extrae datos estructurados de HTML usando glm-5.2 (Huawei ModelArts).

        Se apoya en instructor, igual que RedactorGLM: el modelo devuelve el
        schema ya validado por pydantic, no una cadena que haya que parsear.

        Lo que habia aqui no llegaba a llamar al modelo. Construia un
        `pydantic_ai.Agent(model_type=..., model_name=..., api_key=...)` con
        parametros que ese constructor no acepta, asi que reventaba con
        TypeError, el except lo convertia en RuntimeError y N3 devolvia siempre
        cero productos. El `return schema` que venia despues —la clase, no una
        instancia— era inalcanzable.

        La falta de credencial se comprueba aqui, fuera del reintento: es un
        error de configuracion y reintentarlo tres veces con espera no lo
        arregla, solo retrasa el fallo.
        """
        if not HUAWEI_MAAS_API_KEY:
            raise ValueError("HUAWEI_MAAS_API_KEY no configurado")

        return await self._pedir_extraccion(html, schema)

    @retry(**_REINTENTOS)
    async def _pedir_extraccion(self, html: str,
                                schema: type[ProductoSchema]) -> ProductoSchema:
        """La llamada al modelo. Con reintentos porque aqui si hay red."""
        sistema = (
            "Eres un extractor de fichas de producto. Recibes el texto principal "
            "de una pagina de una tienda y devuelves sus datos estructurados.\n\n"
            "REGLA CRITICA: extrae SOLO lo que aparezca literalmente en el texto. "
            "Si un dato no esta, ponlo a null. No lo deduzcas, no lo estimes y no "
            "lo completes con conocimiento general: cada valor se verifica despues "
            "contra el HTML de origen (grounding check) y un valor que no este ahi "
            "se rechaza y tumba el producto entero.\n\n"
            "- 'nombre': el del producto, tal cual aparece.\n"
            "- 'precio': solo el numero, sin simbolo de moneda. Si hay varios "
            "(oferta y tachado), el que se cobra hoy.\n"
            "- 'precio_local': el precio con su moneda tal cual figura, ej 'S/ 24.90'.\n"
            "- 'stock': unidades disponibles SOLO si la pagina da una cifra. Que "
            "diga 'disponible' no es una cifra: en ese caso va null.\n"
            "- 'unidad': la de venta, ej 'kg', 'L', '500 g'.\n"
            "- 'fecha_disponibilidad': en formato YYYY-MM-DD.\n"
        )
        usuario = f"CONTENIDO DE LA PAGINA:\n{html[:MAX_CARACTERES_HTML]}"

        try:
            return await self.llm.chat.completions.create(
                model=MODELO_EXTRACCION,
                response_model=schema,
                messages=[
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": usuario},
                ],
                api_key=HUAWEI_MAAS_API_KEY,
                api_base=HUAWEI_MAAS_BASE_URL,
            )
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
                        # Se guarda el MISMO trozo que vio el modelo. Estaba a
                        # 500 caracteres: el grounding check verifica cada valor
                        # extraido contra este texto, asi que un recorte mas
                        # corto que la ventana de extraccion daria por inventado
                        # todo lo que el modelo leyo mas alla del corte.
                        html_capturado=html[:MAX_CARACTERES_HTML] if html else None,
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
