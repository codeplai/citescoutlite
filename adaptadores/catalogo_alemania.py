"""
S8 - Gondola alemana. A diferencia de Peru, aqui **no hay API**: va por agente.

## Por que no hay conector directo, y esto esta medido

Se sondearon las cinco cadenas el 2026-08-13, con el mismo metodo que dio el
conector peruano (ver `TIERSV3/S8_GONDOLA_ALEMANIA.md` §5.2):

| Tienda | HTML de busqueda | API JSON | Veredicto |
|---|---|---|---|
| rewe.de | 403 | 200, catalogo | precio NO |
| edeka.de | 403 | 403 | anti-bot |
| alnatura.de | 200, sin producto | 404 | SPA pura |
| kaufland.de | 403 | 403 | anti-bot |
| lidl.de | 200, sin JSON | 404 | render por JS |

Ninguna corre sobre VTEX. El caso que engaña es REWE:

    GET https://shop.rewe.de/api/products?search=Quinoa
    -> 200, content-type: application/vnd.rewe.fallback+json
       67 resultados con nombre, marca, categoryPath y URL
       _embedded.products[]._embedded.articles == []   <- el precio va aqui

`fallback` significa "sin mercado seleccionado". El precio en Alemania es por
tienda fisica, asi que vive detras de esa seleccion, que es justo lo que el API
abierto no deja hacer; probado con `market=`, `marketCode=`, `wwIdent=` y
`serviceTypes=PICKUP`. La ficha del producto, que si lo tiene, da 403.

Es estructural del mercado aleman, no un detalle de la API de REWE. Por eso
esto cuesta dinero y tarda, y por eso lo dice la interfaz.

## La interfaz es la de CatalogoVTEX a proposito

`buscar()` / `buscar_sync()` devolviendo objetos con `.producto`,
`.fuente_url`, `.evidencia` y `.tienda`. Asi `OfertasGondola` trata a las dos
gondolas igual y no hay dos rutas que mantener sincronizadas. Lo que cambia
—que detras haya un agente y no un GET— se queda dentro de este modulo.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlparse

from casos_de_uso.agente.schemas import ProductoSchema

logger = logging.getLogger(__name__)

PAIS = "Deutschland"

# Moneda del mercado, no de la pagina.
#
# Es la misma decision que en VTEX y por el mismo motivo: el JSON-LD de una
# ficha alemana suele traer `priceCurrency`, pero cuando lo extrae el modelo de
# texto plano no siempre hay un simbolo que leer. Que sea EUR es una propiedad
# del mercado —son tiendas alemanas vendiendo en Alemania—, no una deduccion
# sobre el documento, y por eso se declara aqui arriba y a la vista.
MONEDA = "EUR"

# host -> nombre legible. No es una lista de bloqueo: es cosmetica de la tabla.
#
# Cualquier tienda alemana que encuentre el agente entra igual; estas son las
# que se sabe que aparecen y que merecen salir con su nombre propio en vez de
# con el dominio pelado. Las tres primeras son las que promete la interfaz.
TIENDAS_CONOCIDAS: dict[str, str] = {
    "rewe.de": "REWE",
    "shop.rewe.de": "REWE",
    "edeka.de": "Edeka",
    "alnatura.de": "Alnatura",
    "kaufland.de": "Kaufland",
    "lidl.de": "Lidl",
    "amazon.de": "Amazon.de",
    "denns-biomarkt.de": "denn's Biomarkt",
}


@dataclass(frozen=True)
class OfertaAlemana:
    """Lo mismo que `OfertaVTEX`, para que `OfertasGondola` no note la diferencia."""
    producto: ProductoSchema
    fuente_url: str
    evidencia: str
    tienda: str


def nombre_de_tienda(url: str) -> str:
    """El nombre legible de la tienda a partir de su URL.

    Cae al dominio sin `www.` cuando no se conoce. Se prefiere eso a poner
    "Tienda alemana" o dejarlo vacio: el dominio es informacion real y quien
    lee el informe puede ir a mirarlo, que es justo lo que se le pide a la
    columna de procedencia.
    """
    host = (urlparse(url).hostname or "").lower()
    if host in TIENDAS_CONOCIDAS:
        return TIENDAS_CONOCIDAS[host]

    limpio = host[4:] if host.startswith("www.") else host
    if limpio in TIENDAS_CONOCIDAS:
        return TIENDAS_CONOCIDAS[limpio]

    # Un subdominio de una conocida ('shop.rewe.de' ya esta arriba, pero puede
    # haber otros) sigue siendo esa cadena.
    for conocido, nombre in TIENDAS_CONOCIDAS.items():
        if limpio.endswith("." + conocido):
            return nombre

    return limpio or "tienda desconocida"


class CatalogoAlemania:
    """Ofertas alemanas, via agente investigador."""

    def __init__(self, agente=None, pais: str = PAIS):
        # Se inyecta para poder probar sin red ni modelo. Por defecto, el real.
        self._agente = agente
        self._pais = pais

    def _instancia(self):
        if self._agente is None:
            from casos_de_uso.agente.agente import AgenteInvestigadorComercial
            self._agente = AgenteInvestigadorComercial()
        return self._agente

    async def buscar(self, termino: str, limite: int = 5,
                     insumo: str | None = None) -> list[OfertaAlemana]:
        """Ofertas del insumo en tiendas alemanas.

        `termino` va en aleman (`InsumoInterpretado.terminos_aleman`); `insumo`
        es la etiqueta original, solo para la traza. Sin termino no se busca:
        ver la nota de `OfertasGondola.de_alemania`.
        """
        if not termino:
            return []

        from casos_de_uso.agente.agente import PLANTILLA_BUSQUEDA_DE

        resultado = await self._instancia().ejecutar(
            insumo=insumo or termino,
            pais=self._pais,
            termino=termino,
            plantilla=PLANTILLA_BUSQUEDA_DE,
            # Igual que la suiza: una ficha sin precio sigue entrando en la
            # tabla, porque «este producto se vende en esta tienda alemana» ya
            # es informacion y la columna de precio tiene su «sin dato». La
            # cuarentena, que es quien no puede permitirselo, usa el valor por
            # defecto.
            exigir_precio=False,
        )

        ofertas = []
        for extraccion in resultado.productos_encontrados[:limite]:
            producto = extraccion.producto
            # La moneda es del mercado. Si la pagina la declaro, manda la
            # pagina: un producto en libras en una tienda alemana existe, y
            # sobrescribirlo a EUR convertiria mal la cifra.
            if not producto.moneda:
                producto = producto.model_copy(update={"moneda": MONEDA})

            ofertas.append(OfertaAlemana(
                producto=producto,
                fuente_url=extraccion.fuente_url,
                evidencia=extraccion.html_capturado or "",
                tienda=nombre_de_tienda(extraccion.fuente_url),
            ))

        if resultado.errores:
            logger.info(f"Gondola DE '{termino}': {len(ofertas)} oferta(s), "
                        f"{len(resultado.errores)} descarte(s): {resultado.errores[:3]}")
        else:
            logger.info(f"Gondola DE '{termino}': {len(ofertas)} oferta(s) "
                        f"en {resultado.tiempo_total_ms} ms")
        return ofertas

    def buscar_sync(self, termino: str, limite: int = 5,
                    insumo: str | None = None) -> list[OfertaAlemana]:
        """Lo mismo, desde codigo sincrono.

        Mismo motivo y misma solucion que en `CatalogoVTEX.buscar_sync`: la
        etapa 2b es sincrona pero corre dentro del bucle de eventos de la
        peticion, y un `asyncio.run` ahi lanza 'cannot be called from a running
        event loop'. Se corre la corrutina en un hilo aparte, con su bucle.

        Aqui pesa mas que en Peru: el agente tarda minutos, no segundos, y el
        hilo que llama se queda esperando todo ese rato. Es una consecuencia
        aceptada al elegir meter Alemania en el camino sincrono de /consultas.
        """
        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            futuro = ejecutor.submit(
                lambda: asyncio.run(self.buscar(termino, limite, insumo)))
            return futuro.result()
