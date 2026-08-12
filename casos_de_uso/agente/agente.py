"""
AgenteInvestigadorComercial: busca productos en web con Tavily, extrae datos (S2.1).

Toolset:
  1. buscar_web(query, país) → lista de URLs via Tavily
  2. abrir_url(url) → HTML via trafilatura + rate-limiting + robots.txt
  3. extraer_producto(html, schema) → JSONB via glm-5.2 (Huawei)

Timeouts: 60s búsqueda, 30s extracción, 10s validación.
"""

import asyncio
import logging
import os
import re
import time
import unicodedata
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
import instructor
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx
import trafilatura
from tavily import TavilyClient

from .datos_estructurados import extraer_productos
from .schemas import ProductoSchema, ExtraccionProductoResultado, AgenteResultado, BusquedaWebResultado
from ..integraciones import check_rate_limit, record_request_success, record_request_failure

load_dotenv()

# El progreso va por logging y no por print(). No es cosmetico: `ejecutar()`
# imprimia el avance con emojis dentro de su try, y en una consola cp1252
# —la de Windows por defecto— `print` lanza UnicodeEncodeError. El except lo
# recogia y devolvia el run entero como estado='error' con cero productos,
# despues de haber pagado la busqueda y las extracciones. Un mensaje de
# progreso no puede tumbar el trabajo que describe.
logger = logging.getLogger(__name__)

# Como se le pide a Tavily una ficha de tienda y no un articulo.
#
# La consulta era `f"{insumo} {pais}"` — literalmente "quinua Peru" — con
# topic="general". Eso es una consulta enciclopedica, y devolvia lo que
# corresponde a una consulta enciclopedica: para "quinua Peru", las cinco
# primeras eran Wikipedia (del **pueblo** de Quinua, en Ayacucho), un blog de
# turismo, un video de YouTube, un reel de Instagram y una receta. Cero
# ofertas. El agente extraia de ahi productos como 'Acerca de' con todos los
# campos a null, que el grounding check rechazaba despues, con lo que N3
# gastaba busqueda y extracciones para no aportar una sola oferta.
#
# Medido sobre quinua, arandano y cacao: la plantilla de abajo devuelve 14 de
# 15 fichas de tienda reales (Plaza Vea, Metro, Wong, Tottus, Vega y varios
# productores). La de antes, 0 de 5.
PLANTILLA_BUSQUEDA = "comprar {insumo} precio tienda online {pais}"

# Dominios que nunca son una ficha de producto. No es una lista de bloqueo por
# calidad: es que en estos sitios no hay precio ni stock que extraer, y cada
# uno cuesta una descarga y una llamada al modelo.
DOMINIOS_NO_COMERCIALES = [
    "wikipedia.org", "youtube.com", "instagram.com", "facebook.com",
    "tiktok.com", "x.com", "twitter.com", "reddit.com", "pinterest.com",
]

# Configuración
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
HUAWEI_MAAS_BASE_URL = os.getenv("HUAWEI_MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
HUAWEI_MAAS_API_KEY = os.getenv("HUAWEI_MAAS_API_KEY", "")

# Timeouts
TIMEOUT_BUSQUEDA = 60  # segundos

# Medido contra fichas reales con glm-5.2 (2026-08-12): 15,4 s para 828
# caracteres de texto util y 41,8 s para 365. No escala con el tamano de la
# entrada porque el modelo razona antes de responder, asi que el limite de
# antes —30 s— se quedaba corto incluso con paginas pequenas: en una pasada
# sobre tres tiendas peruanas reales, **las tres agotaron el timeout** y el
# agente devolvio cero ofertas habiendo pagado las tres extracciones.
#
# OJO al presupuesto de arriba: descubrimiento_cascada.descubrir_n3 envuelve
# ejecutar() en un asyncio.wait_for de 120 s, y ejecutar() procesa hasta 3 URL
# en serie. Con 60 s por extraccion, dos URL ya rozan ese techo. Subir el
# limite exterior es una decision de latencia de /consultas, no del agente, y
# por eso no se toca aqui.
TIMEOUT_EXTRACCION = 60
TIMEOUT_VALIDACION = 10

# Mismo modelo que las etapas 3-5 en RedactorGLM. El prefijo 'openai/' es lo
# que hace que litellm hable el dialecto OpenAI contra ModelArts.
MODELO_EXTRACCION = "openai/glm-5.2"

# Cuanto HTML se le manda al modelo. trafilatura ya devuelve solo el contenido
# principal, pero 2000 caracteres —lo que habia— no llegan ni al precio en una
# ficha de producto normal: se corta antes de la parte util.
MAX_CARACTERES_HTML = 6000

# Tope de ofertas por pagina. Una ficha de producto da una; una pagina de
# categoria puede dar decenas (Vega devuelve tres quinuas distintas en una
# sola URL). El limite esta para que una categoria enorme no llene la
# cuarentena de una tienda sola: staging_agente tiene TTL de 24 h y quien la
# revisa es una persona.
MAX_OFERTAS_POR_PAGINA = 5


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto or "")
                   if unicodedata.category(c) != "Mn").lower()


def corresponde_al_insumo(nombre: str, insumo: str) -> bool:
    """Si el nombre del producto es del insumo que se buscaba.

    Hace falta porque una pagina de categoria publica en su JSON-LD **todos**
    sus productos, no solo el que motivo la busqueda. Buscando 'maca' en una
    tienda colombiana entraron HARINA DE ARROZ, HARINA DE LENTEJA y HARINA DE
    SOYA junto a la maca: la pagina las listaba todas.

    El criterio es que el nombre contenga el insumo al principio de alguna
    palabra, sin tildes. Asi 'arandano' casa con 'Arandanos rojos
    deshidratado' —el plural es el caso normal— y no con 'Harina de arroz'.
    Deja pasar algun falso positivo por prefijo (un 'macarron' contando como
    'maca'), y es el lado por el que conviene equivocarse: esto alimenta una
    cola que revisa una persona, y descartar de mas se nota mucho menos que
    colar un producto que no es.
    """
    if not nombre or not insumo:
        return False
    return re.search(rf"\b{re.escape(_sin_tildes(insumo))}",
                     _sin_tildes(nombre)) is not None

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
            consulta = PLANTILLA_BUSQUEDA.format(insumo=query, pais=pais)
            results = self.tavily_client.search(
                consulta,
                max_results=5,
                topic="general",
                include_answer=False,
                exclude_domains=DOMINIOS_NO_COMERCIALES,
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

    async def descargar(self, url: str) -> tuple[str, str]:
        """Descarga una pagina y devuelve `(html_crudo, texto_principal)`.

        Hacen falta los dos. El texto es lo que se le da al modelo. El HTML
        crudo es donde vive el JSON-LD con el precio exacto, que `trafilatura`
        descarta junto con el resto de los `<script>`: hasta ahora se tiraba
        ahi mismo la unica copia fiable del dato que se venia a buscar.
        """
        try:
            # Rate limiting + robots.txt check
            await check_rate_limit(url)

            resp = await self.http_client.get(
                url,
                headers={"User-Agent": "AgroScoutIA/1.0 (+https://agroscout.ai/bot)"},
                follow_redirects=True,
                timeout=30.0,
            )
            resp.raise_for_status()
            record_request_success(url)

            texto = trafilatura.extract(resp.text, include_comments=False)
            return resp.text, (texto or resp.text)
        except asyncio.TimeoutError:
            raise TimeoutError(f"URL fetch timeout: {url}")
        except Exception as e:
            record_request_failure(url)
            raise RuntimeError(f"URL fetch error ({url}): {e}")

    async def abrir_url(self, url: str) -> str:
        """Solo el contenido principal. Parte del toolset documentado arriba."""
        _, texto = await self.descargar(url)
        return texto

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
            "- 'moneda': el codigo ISO de esa moneda: PEN si pone 'S/' o 'soles', "
            "USD si pone '$' o 'US$', EUR si pone '€'. Si el simbolo es ambiguo y "
            "la pagina no aclara el pais, ponlo a null antes que suponerlo.\n"
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
            logger.info(f"Buscando '{insumo}' en {pais}...")
            resultados_busqueda = await asyncio.wait_for(
                self.buscar_web(insumo, pais),
                timeout=TIMEOUT_BUSQUEDA,
            )
            logger.info(f"  Encontrados {len(resultados_busqueda)} resultados")

            # 2. Procesar cada URL
            for idx, resultado in enumerate(resultados_busqueda[:3]):  # Max 3 URLs
                try:
                    logger.info(f"  Abriendo URL {idx+1}: {resultado.url[:50]}...")
                    crudo, texto = await asyncio.wait_for(
                        self.descargar(resultado.url),
                        timeout=30,
                    )

                    # 3a. Datos estructurados primero. Si la tienda publica su
                    # ficha en JSON-LD, el precio es exacto, sale en
                    # milisegundos y no cuesta un token. Ver el modulo
                    # datos_estructurados para las cifras medidas.
                    estructurados = extraer_productos(crudo)

                    # Una pagina de categoria publica todas sus fichas; solo
                    # interesan las del insumo que se buscaba.
                    if estructurados:
                        antes = len(estructurados)
                        estructurados = [
                            o for o in estructurados
                            if corresponde_al_insumo(o.producto.nombre, insumo)]
                        if antes != len(estructurados):
                            logger.info(f"  {antes - len(estructurados)} ficha(s) "
                                        f"de la pagina no son '{insumo}'")

                    if estructurados:
                        logger.info(f"  {len(estructurados)} oferta(s) en JSON-LD "
                                    f"(sin llamar al modelo)")
                        for oferta in estructurados[:MAX_OFERTAS_POR_PAGINA]:
                            productos.append(ExtraccionProductoResultado(
                                producto=oferta.producto,
                                fuente_url=resultado.url,
                                # El nodo JSON-LD del que salio la oferta, no un
                                # recorte del principio del HTML: en Vega y en
                                # frutossecosdeperu el bloque esta pasado el
                                # caracter 130.000, muy lejos de los primeros
                                # 6.000, y el grounding check no encontraria
                                # nada contra lo que verificar.
                                html_capturado=oferta.evidencia,
                                timestamp=datetime.now(),
                                modelo_usado="json-ld",
                            ))
                            self.products_extracted += 1
                            logger.info(
                                f"    {oferta.producto.nombre} = "
                                f"{oferta.producto.precio_local or oferta.producto.precio}")
                        continue

                    # 3b. Sin datos estructurados: que lo lea el modelo. Es
                    # donde de verdad aporta, y donde se paga.
                    logger.info("  Sin JSON-LD; extrayendo con el modelo...")
                    producto = await asyncio.wait_for(
                        self.extraer_producto(texto, ProductoSchema),
                        timeout=TIMEOUT_EXTRACCION,
                    )

                    # Sin nombre o sin precio no es una oferta, y no entra en
                    # cuarentena. Cuando la pagina no tiene ficha, el modelo
                    # devuelve cosas como 'N/A', 'No se encontro producto en
                    # esta pagina.' o —lo mas engañoso— 'Quinua Organica
                    # Premium', que es el ejemplo del json_schema_extra de
                    # ProductoSchema: instructor lo manda dentro de la
                    # definicion de la herramienta y el modelo lo copia cuando
                    # no tiene nada que leer. Salio bajo el insumo 'arandano'.
                    #
                    # Todas fallaban el grounding despues, asi que el validador
                    # de S7 las rechazaba igual; pero antes ocupaban una fila de
                    # staging y un hueco de la revision manual.
                    if not producto.nombre or producto.precio is None:
                        errores.append(
                            f"Sin oferta utilizable en {resultado.url} "
                            f"(nombre={producto.nombre!r}, precio={producto.precio!r})")
                        logger.info(f"  Descartada: {errores[-1]}")
                        continue

                    # El mismo criterio que para las fichas estructuradas. Sin
                    # esto, buscando 'cafe' entraba un 'Pack Premium CATA- Caja
                    # Negra': el modelo extrae lo que encuentra en la pagina,
                    # aunque la pagina no sea del insumo que se buscaba.
                    if not corresponde_al_insumo(producto.nombre, insumo):
                        errores.append(f"{producto.nombre!r} no es '{insumo}' "
                                       f"({resultado.url})")
                        logger.info(f"  Descartada: {errores[-1]}")
                        continue

                    # Empaquetar resultado
                    extraccion = ExtraccionProductoResultado(
                        producto=producto,
                        fuente_url=resultado.url,
                        # Se guarda el MISMO trozo que vio el modelo. Estaba a
                        # 500 caracteres: el grounding check verifica cada valor
                        # extraido contra este texto, asi que un recorte mas
                        # corto que la ventana de extraccion daria por inventado
                        # todo lo que el modelo leyo mas alla del corte.
                        html_capturado=texto[:MAX_CARACTERES_HTML] if texto else None,
                        timestamp=datetime.now(),
                        modelo_usado="glm-5.2",
                    )
                    productos.append(extraccion)
                    self.products_extracted += 1
                    logger.info(f"  Producto extraido: {producto.nombre}")

                except TimeoutError as e:
                    errores.append(f"Timeout en {resultado.url}: {e}")
                    logger.warning(f"  {errores[-1]}")
                except Exception as e:
                    errores.append(f"Error en {resultado.url}: {e}")
                    logger.warning(f"  {errores[-1]}")

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
