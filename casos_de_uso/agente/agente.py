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
from .precio_en_html import texto_para_el_modelo
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

# La misma idea para Alemania, y en alemán por el mismo motivo por el que la de
# arriba está en castellano: Tavily devuelve lo que se le pide en el idioma en
# que se le pide. Una consulta en castellano sobre tiendas alemanas trae blogs
# de exportación y artículos de prensa, no fichas con precio.
#
# `kaufen` (comprar) y `Preis` (precio) son las dos palabras que separan una
# ficha de tienda de un artículo, igual que 'comprar'/'precio' en la peruana.
PLANTILLA_BUSQUEDA_DE = "{insumo} kaufen Preis Online Shop {pais}"

# Suiza. Palabra por palabra la misma que la alemana, y a propósito: las
# tiendas que importan allí —Migros, Coop, Piccantino— publican en alemán, y lo
# que separa un resultado suizo de uno alemán es el `{pais}` («Schweiz»), no el
# idioma de la consulta.
#
# Va con nombre propio en vez de reutilizar la constante alemana porque las dos
# tienen motivos para divergir: si Suiza acaba necesitando 'CHF' en la consulta
# para desplazar a las tiendas alemanas —que dominan los resultados en
# alemán—, ese ajuste no puede arrastrar a Alemania, donde no haría más que
# estrechar la búsqueda sin motivo.
#
# Lo que la plantilla no puede hacer sola es garantizar que el resultado sea
# suizo. De eso se encarga `catalogo_suiza.es_tienda_suiza`.
PLANTILLA_BUSQUEDA_CH = "{insumo} kaufen Preis Online Shop {pais}"

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


# Codigos que significan "no me dejan entrar", no "no existe".
#
# 403 es el caso normal del anti-bot. 429 y 503 son el mismo muro con otra
# cara: limitacion por volumen y "servicio no disponible" que muchas capas
# devuelven ante trafico que no reconocen. Un 404 NO entra: la pagina no esta,
# y pasar por un proxy no la va a crear.
_CODIGOS_DE_BLOQUEO = ("403", "429", "503")


def _es_bloqueo(error: Exception) -> bool:
    """Si el fallo de descarga fue un muro anti-bot y no una ausencia.

    El camino normal es el `isinstance`: `raise_for_status()` lanza
    `HTTPStatusError` y ahi el codigo esta estructurado. El respaldo por texto
    cubre el caso en que el fallo llegue ya envuelto por otra capa, y usa
    limites de palabra para no confundir un 403 de verdad con los tres digitos
    finales de un identificador dentro de la URL.
    """
    if isinstance(error, httpx.HTTPStatusError):
        return str(error.response.status_code) in _CODIGOS_DE_BLOQUEO
    return any(re.search(rf"\b{c}\b", str(error)) for c in _CODIGOS_DE_BLOQUEO)


def corresponde_al_insumo(nombre: str, insumo: str) -> bool:
    """Si el nombre del producto es del insumo que se buscaba.

    Hace falta porque una pagina de categoria publica en su JSON-LD **todos**
    sus productos, no solo el que motivo la busqueda. Buscando 'maca' en una
    tienda colombiana entraron HARINA DE ARROZ, HARINA DE LENTEJA y HARINA DE
    SOYA junto a la maca: la pagina las listaba todas.

    El criterio es que el termino aparezca **al principio o al final de una
    palabra**, sin tildes. Asi 'arandano' casa con 'Arandanos rojos
    deshidratado' —el plural es el caso normal— y no con 'Harina de arroz'.

    Lo del final no estaba y hacia falta desde que se busca en aleman: **el
    aleman compone palabras**. El 2026-08-13, buscando 'Quinoa' en Suiza, el
    modelo extrajo 'Bio-Weissquinoa - 500 g - Rapunzel' con su precio y esta
    funcion la tiro, porque 'quinoa' iba pegado detras de 'Weiss' y no habia
    limite de palabra delante. Perdiamos justo las fichas mejor extraidas, y el
    log decia 'no es Quinoa' de un producto que era exactamente eso.

    Deja pasar algun falso positivo por prefijo (un 'macarron' contando como
    'maca'), y es el lado por el que conviene equivocarse: descartar de mas se
    nota mucho menos que colar un producto que no es, y aguas abajo hay o una
    persona que revisa la cuarentena o una tabla que dice de que tienda salio
    cada fila.
    """
    if not nombre or not insumo:
        return False
    termino = re.escape(_sin_tildes(insumo))
    return re.search(rf"\b{termino}|{termino}\b",
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

    def __init__(self, desbloqueo=None):
        self.tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
        self.http_client = httpx.AsyncClient(timeout=30.0)
        # Reserva para las paginas que devuelven 403. Se inyecta para poder
        # probar sin red; por defecto, la de verdad. Si no hay clave o no hay
        # zona, se apaga sola y el agente se comporta como antes.
        if desbloqueo is None:
            from adaptadores.desbloqueo_brightdata import DesbloqueoBrightData
            desbloqueo = DesbloqueoBrightData()
        self.desbloqueo = desbloqueo
        self.llm = instructor.from_litellm(acompletion)
        self.products_extracted = 0
        self.start_time = None

    async def buscar_web(self, query: str, pais: str,
                         plantilla: str | None = None) -> list[BusquedaWebResultado]:
        """
        Busca en web usando Tavily API.
        Retorna lista de resultados (URL + preview).

        `plantilla` permite buscar en el idioma del mercado; por defecto, la
        peruana. Ver PLANTILLA_BUSQUEDA_DE.
        """
        if not self.tavily_client:
            raise ValueError("TAVILY_API_KEY no configurado")

        try:
            consulta = (plantilla or PLANTILLA_BUSQUEDA).format(insumo=query, pais=pais)
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
            # Un 403 no es "la pagina no esta": es "no me dejan entrar", y eso
            # tiene remedio. Medido sobre 'Quinoa', el agente perdio DOS de las
            # tres URL asi —idealo.de y rewe.de— y la gondola alemana salio
            # vacia para un insumo que Alemania vende en todos los
            # supermercados.
            #
            # Solo se reintenta el bloqueo, no cualquier fallo: un 404 o un DNS
            # roto no mejoran por pasar por un proxy, y cada peticion cuesta.
            if _es_bloqueo(e):
                html = await self._desbloquear(url)
                if html:
                    record_request_success(url)
                    texto = trafilatura.extract(html, include_comments=False)
                    return html, (texto or html)

            record_request_failure(url)
            raise RuntimeError(f"URL fetch error ({url}): {e}")

    async def _desbloquear(self, url: str) -> str | None:
        """Segundo intento por Web Unlocker. None si no hay o no pudo."""
        if self.desbloqueo is None:
            return None
        logger.info(f"  {url[:60]} bloqueada; reintento por Bright Data")
        return await self.desbloqueo.descargar(url)

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

    async def ejecutar(self, insumo: str, pais: str,
                       termino: str | None = None,
                       plantilla: str | None = None,
                       exigir_precio: bool = True) -> AgenteResultado:
        """
        Ejecuta el agente: busca productos y extrae datos.
        Retorna resultado agregado.

        `termino` es la palabra con la que se busca y con la que se filtra
        después; `insumo` es la etiqueta del run, la que va a la auditoría. En
        Perú coinciden. En Alemania no: se busca 'Heidelbeeren' y el run sigue
        siendo de 'arandano', porque es lo que preguntó el usuario y lo que hay
        que poder rastrear en `etapas_ejecucion`.

        Que el filtro use el término y no el insumo es lo que hace utilizable
        este método fuera de Perú: `corresponde_al_insumo('Heidelbeeren 200g',
        'arandano')` es False, y descartaría el catálogo entero.

        `exigir_precio` separa los dos destinos de este método, que hasta ahora
        compartían criterio sin quererlo:

        - **La cuarentena** (`descubrimiento_cascada.descubrir_n3`) lo deja en
          True. Una fila sin precio ocupa un hueco de revisión manual sin traer
          el dato que motiva revisarla, y `staging_agente` la revisa una
          persona.
        - **Las góndolas del informe** lo ponen en False. Ahí una fila con «sin
          dato» en el precio sigue diciendo que ese producto se vende en esa
          tienda, y eso es más que no enseñar nada. Medido el 2026-08-13: de
          tres tiendas suizas reales, las tres traían nombre correcto y las
          tres se descartaban por no traer precio, dejando la tabla vacía.

        Lo que **no** cambia con False es el filtro por nombre: cuando la
        página no tiene ficha, el modelo devuelve cosas como 'dm-drogerie markt
        - dauerhaft günstig online kaufen', y `corresponde_al_insumo` sigue
        tirándolas. Ese, y no el precio, es el que frena la basura.
        """
        self.start_time = time.time()
        self.products_extracted = 0
        productos = []
        errores = []
        termino = termino or insumo

        try:
            # 1. Buscar en web
            logger.info(f"Buscando '{termino}' en {pais}"
                        + (f" (insumo: '{insumo}')" if termino != insumo else "") + "...")
            resultados_busqueda = await asyncio.wait_for(
                self.buscar_web(termino, pais, plantilla),
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
                    estructurados = extraer_productos(crudo, exigir_precio)

                    # Una pagina de categoria publica todas sus fichas; solo
                    # interesan las del insumo que se buscaba.
                    if estructurados:
                        antes = len(estructurados)
                        estructurados = [
                            o for o in estructurados
                            if corresponde_al_insumo(o.producto.nombre, termino)]
                        if antes != len(estructurados):
                            logger.info(f"  {antes - len(estructurados)} ficha(s) "
                                        f"de la pagina no son '{termino}'")

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
                    #
                    # Antes de pagarla, se comprueba que la pregunta tenga
                    # respuesta posible. `trafilatura` devuelve el contenido
                    # principal y en una ficha de tienda **el precio no suele
                    # estar ahi**: en zwicky.swiss reducia 74.200 caracteres a
                    # 688 y el precio (8,05 CHF) se quedaba fuera. El modelo
                    # devolvia precio=None con razon —nunca lo tuvo delante— y
                    # se habia pagado la extraccion igual. Ver
                    # `precio_en_html.py` para las cifras de las tres tiendas.
                    lectura, rescatado = texto_para_el_modelo(
                        texto, crudo, MAX_CARACTERES_HTML)
                    if rescatado:
                        logger.info("  El precio no estaba en el texto principal; "
                                    "se añaden los fragmentos del HTML que lo traen")

                    logger.info("  Sin JSON-LD; extrayendo con el modelo...")
                    producto = await asyncio.wait_for(
                        self.extraer_producto(lectura, ProductoSchema),
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
                    #
                    # El precio solo se exige cuando el destino es la
                    # cuarentena. Para las gondolas del informe basta el nombre:
                    # ver la nota de `exigir_precio` en el docstring. El colador
                    # de basura en los dos casos es `corresponde_al_insumo`, que
                    # va justo debajo y no depende del precio.
                    if not producto.nombre or (exigir_precio and producto.precio is None):
                        errores.append(
                            f"Sin oferta utilizable en {resultado.url} "
                            f"(nombre={producto.nombre!r}, precio={producto.precio!r})")
                        logger.info(f"  Descartada: {errores[-1]}")
                        continue

                    # El mismo criterio que para las fichas estructuradas. Sin
                    # esto, buscando 'cafe' entraba un 'Pack Premium CATA- Caja
                    # Negra': el modelo extrae lo que encuentra en la pagina,
                    # aunque la pagina no sea del insumo que se buscaba.
                    if not corresponde_al_insumo(producto.nombre, termino):
                        errores.append(f"{producto.nombre!r} no es '{termino}' "
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
                        #
                        # `lectura` y no `texto`: cuando el precio se rescata
                        # del HTML, solo esta en la version compuesta. Guardar
                        # `texto` aqui rechazaria por inventado justo el precio
                        # que el rescate acaba de recuperar, y la tienda volveria
                        # a salir sin dato despues de haber pagado la extraccion.
                        html_capturado=lectura or None,
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
