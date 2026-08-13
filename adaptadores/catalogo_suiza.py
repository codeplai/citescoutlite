"""
S8 - Gondola suiza. Como Alemania, **por agente**, y por decision explicita.

## Lo que dio la sonda, y por que no se usa el atajo

Se sondearon cinco tiendas el 2026-08-13 (ver `TIERSV3/S8_GONDOLA_SUIZA.md` §3):

| Tienda | Resultado | Veredicto |
|---|---|---|
| migros.ch | 403 en todo, incluidas sus rutas de API | anti-bot |
| coop.ch | 403 hasta en robots.txt | anti-bot duro |
| farmy.ch | el DNS no resuelve | caida o fuera de servicio |
| rappn.ch | 404 en las rutas de busqueda; la raiz no trae el termino | SPA |
| piccantino.ch | 200 con JSON-LD `Product`, precio en CHF y `gtin13` | **gratis** |

O sea: **si habia una via gratis**, Piccantino, y `extraer_productos` ya la lee
sin tocar nada. No se ha tomado, y conviene que quede escrito por que.

Piccantino da **una oferta por pagina de categoria** —el destacado; el resto
del listado no esta en JSON-LD— y solo si se acierta la URL de la categoria
(`/quinoa` trae `Product`, `/heidelbeeren` no). Es una tienda gourmet online,
no una muestra del mercado suizo, y Migros y Coop —que son ~70 % del comercio
minorista de alimentacion del pais— estan las dos cerradas al acceso directo.
Una tabla rotulada «Suiza» construida solo con Piccantino diria «el precio en
Suiza» donde el dato es «el precio en una tienda de nicho».

Se eligio el agente para todo: cubre Migros y Coop cuando la busqueda las
alcanza, y cuando cae en Piccantino el propio agente pasa **primero** por
`extraer_productos`, asi que el camino gratis sigue usandose donde existe. Lo
que se paga es la busqueda y las fichas sin JSON-LD.

## Lo que este modulo tiene y el aleman no: la guarda de mercado

`CatalogoAlemania` deja pasar cualquier tienda que encuentre el agente. Aqui
**no se puede**, y no es simetria mal entendida: se busca en aleman, y una
consulta en aleman devuelve sobre todo tiendas alemanas. Sin filtrar, la tabla
rotulada «Suiza» se llenaria de rewe.de y amazon.de con precios en euros —el
error exacto que la tabla existe para no cometer—.

`es_tienda_suiza` acota a `.ch` y a los hosts suizos conocidos que no lo usan.
Cuando la busqueda no alcanza ninguna tienda suiza, la tabla sale vacia y se
anota: es «sin dato» declarado, que es una respuesta legitima (ADR-001).

## El idioma

Se busca con `InsumoInterpretado.terminos_aleman`, el mismo termino que
Alemania. Piccantino es germanofona y el aleman es la region linguistica mas
grande de Suiza, asi que es la eleccion de mayor cobertura con el campo que ya
existe.

**No es gratis y conviene saberlo:** Migros y Coop sirven tambien en frances e
italiano, con URL por idioma (`/de/`, `/fr/`, `/it/`), y esas fichas quedan
fuera. Cubrirlas pedira un `terminos_frances`/`terminos_italiano` en la etapa 1
—un campo mas que el modelo rellena— y eso es una decision aparte, no un
detalle de este conector.

## La interfaz es la de CatalogoVTEX y CatalogoAlemania a proposito

`buscar()` / `buscar_sync()` devolviendo objetos con `.producto`,
`.fuente_url`, `.evidencia` y `.tienda`, para que `OfertasGondola` trate a las
tres gondolas igual.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlparse

from casos_de_uso.agente.schemas import ProductoSchema

logger = logging.getLogger(__name__)

PAIS = "Schweiz"

# Moneda del mercado, no de la pagina. Misma decision que en VTEX y en
# Alemania: que una tienda suiza cobre en francos es una propiedad del mercado,
# no una deduccion sobre el documento, y por eso se declara aqui y a la vista.
MONEDA = "CHF"

# host -> nombre legible. No es una lista de bloqueo (eso es SUFIJOS_SUIZOS):
# es cosmetica de la tabla, para que una fila diga 'Migros' y no 'migros.ch'.
TIENDAS_CONOCIDAS: dict[str, str] = {
    "zwicky.swiss": "Zwicky",
    "migros.ch": "Migros",
    "leshop.ch": "LeShop (Migros)",
    "coop.ch": "Coop",
    "denner.ch": "Denner",
    "volg.ch": "Volg",
    "aldi-suisse.ch": "Aldi Suisse",
    "lidl.ch": "Lidl Schweiz",
    "piccantino.ch": "Piccantino",
    "farmy.ch": "Farmy",
    "rappn.ch": "Rappn",
    "galaxus.ch": "Galaxus",
    "brack.ch": "Brack",
}

# Que cuenta como tienda suiza.
#
# `.ch` hace casi todo el trabajo. La lista de conocidas se consulta ademas por
# si alguna sirve desde otro dominio, y esta escrita al lado de los nombres
# legibles para que no haya que mantener dos listas que digan lo mismo.
#
# **`.swiss` no es opcional.** Estaba fuera y costo una oferta buena: en la
# pasada del 2026-08-13 la unica tienda de la que se saco nombre y precio
# limpios fue `zwicky.swiss`, y esta guarda la tiro por no acabar en `.ch`.
# `.swiss` es un dominio restringido que administra la Confederacion y solo se
# concede a entidades con vinculo suizo demostrado, asi que como senal de pais
# es mas fuerte que `.ch`, no mas debil.
SUFIJOS_SUIZOS = (".ch", ".swiss")


@dataclass(frozen=True)
class OfertaSuiza:
    """Lo mismo que `OfertaVTEX` y `OfertaAlemana`, para que `OfertasGondola`
    no note la diferencia."""
    producto: ProductoSchema
    fuente_url: str
    evidencia: str
    tienda: str


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def es_tienda_suiza(url: str) -> bool:
    """Si la URL es de una tienda que vende en Suiza.

    Existe porque la busqueda va en aleman y el mercado aleman domina esos
    resultados: sin esta guarda, la tabla rotulada «Suiza» traeria rewe.de y
    amazon.de con precios en euros. Una fila con la etiqueta de un pais que no
    es el suyo es peor que una tabla vacia, porque la tabla vacia se declara y
    la fila equivocada se lee como dato.

    Se equivoca hacia descartar: una tienda suiza que sirva desde un `.com` y
    no este en `TIENDAS_CONOCIDAS` se queda fuera. Es el lado correcto —lo que
    se pierde es una fila; lo que se colaria es una afirmacion falsa— y se
    arregla anadiendo su host arriba.
    """
    host = _host(url)
    if not host:
        return False
    if host.endswith(SUFIJOS_SUIZOS):
        return True
    return any(host == conocido or host.endswith("." + conocido)
               for conocido in TIENDAS_CONOCIDAS)


def nombre_de_tienda(url: str) -> str:
    """El nombre legible de la tienda a partir de su URL.

    Cae al dominio sin `www.` cuando no se conoce. Se prefiere eso a poner
    "tienda suiza": el dominio es informacion real y quien lee el informe puede
    ir a comprobarlo, que es justo lo que se le pide a la procedencia.
    """
    host = _host(url)
    if host in TIENDAS_CONOCIDAS:
        return TIENDAS_CONOCIDAS[host]

    # Un subdominio de una conocida sigue siendo esa cadena.
    for conocido, nombre in TIENDAS_CONOCIDAS.items():
        if host.endswith("." + conocido):
            return nombre

    return host or "tienda desconocida"


class CatalogoSuiza:
    """Ofertas suizas, via agente investigador."""

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
                     insumo: str | None = None) -> list[OfertaSuiza]:
        """Ofertas del insumo en tiendas suizas.

        `termino` va en aleman (`InsumoInterpretado.terminos_aleman`); `insumo`
        es la etiqueta original, solo para la traza. Sin termino no se busca:
        con el insumo en castellano, Tavily devolveria articulos sobre
        exportacion y el filtro por nombre descartaria despues cualquier ficha
        alemana que llegara. Gastar una busqueda y varias extracciones para
        garantizar cero ofertas es peor que no llamar.
        """
        if not termino:
            return []

        from casos_de_uso.agente.agente import PLANTILLA_BUSQUEDA_CH

        resultado = await self._instancia().ejecutar(
            insumo=insumo or termino,
            pais=self._pais,
            termino=termino,
            plantilla=PLANTILLA_BUSQUEDA_CH,
            # Una ficha sin precio sigue entrando en la tabla. Es lo contrario
            # de lo que pide la cuarentena, y aqui es lo correcto: «este
            # producto se vende en esta tienda suiza» ya es informacion, y la
            # columna de precio tiene su estado «sin dato» para decir el resto.
            # Sin esto la tabla salia vacia teniendo tres fichas con el nombre
            # bien extraido (medido el 2026-08-13).
            exigir_precio=False,
        )

        ofertas = []
        descartadas = []
        for extraccion in resultado.productos_encontrados:
            if not es_tienda_suiza(extraccion.fuente_url):
                descartadas.append(_host(extraccion.fuente_url) or extraccion.fuente_url)
                continue
            if len(ofertas) >= limite:
                break

            producto = extraccion.producto
            # La moneda es del mercado. Si la pagina la declaro, manda la
            # pagina: una tienda suiza que publique en euros existe —varias
            # sirven a la UE— y sobrescribirlo a CHF convertiria mal la cifra.
            if not producto.moneda:
                producto = producto.model_copy(update={"moneda": MONEDA})

            ofertas.append(OfertaSuiza(
                producto=producto,
                fuente_url=extraccion.fuente_url,
                evidencia=extraccion.html_capturado or "",
                tienda=nombre_de_tienda(extraccion.fuente_url),
            ))

        # Los descartes por pais se anotan aparte de los errores del agente.
        # Son la diferencia entre "no se encontro nada" y "se encontro, pero no
        # era suizo", y sin distinguirlas una tabla vacia no dice si hay que
        # afinar la busqueda o si el producto no se vende alli.
        if descartadas:
            logger.info(f"Gondola CH '{termino}': {len(descartadas)} ficha(s) "
                        f"descartada(s) por no ser de una tienda suiza: "
                        f"{sorted(set(descartadas))}")

        if resultado.errores:
            logger.info(f"Gondola CH '{termino}': {len(ofertas)} oferta(s), "
                        f"{len(resultado.errores)} descarte(s): {resultado.errores[:3]}")
        else:
            logger.info(f"Gondola CH '{termino}': {len(ofertas)} oferta(s) "
                        f"en {resultado.tiempo_total_ms} ms")
        return ofertas

    def buscar_sync(self, termino: str, limite: int = 5,
                    insumo: str | None = None) -> list[OfertaSuiza]:
        """Lo mismo, desde codigo sincrono.

        Mismo motivo y misma solucion que en `CatalogoVTEX.buscar_sync`: la
        etapa 2b es sincrona pero corre dentro del bucle de eventos de la
        peticion, y un `asyncio.run` ahi lanza 'cannot be called from a running
        event loop'. Se corre la corrutina en un hilo aparte, con su bucle.

        Aqui pesa lo mismo que en Alemania: el agente tarda minutos, no
        segundos, y el hilo que llama se queda esperando todo ese rato. Y ahora
        son **dos** agentes por consulta, uno detras de otro. Es la consecuencia
        aceptada al elegir el agente para Suiza; el freno de mano es
        `AGROSCOUT_GONDOLA_CH=0` (ver `api/main.py`).
        """
        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            futuro = ejecutor.submit(
                lambda: asyncio.run(self.buscar(termino, limite, insumo)))
            return futuro.result()
