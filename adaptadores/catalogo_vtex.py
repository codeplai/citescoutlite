"""
S8 - Conector directo al catalogo de las cadenas peruanas (VTEX).

## Por que

El agente N3 sale a buscar a ciegas por la web. Funciona, pero justo con las
cadenas que mas le importan a CITE —Wong, Metro, Plaza Vea, Makro— fallaba: son
aplicaciones de una sola pagina y el precio lo inyecta JavaScript, asi que no
esta en el HTML que se descarga. Ni JSON-LD ni microdatos ni OpenGraph; medido
en las cuatro.

La salida evidente era pagar un servicio que renderice JavaScript. No hace
falta: **VTEX, la plataforma sobre la que estan montadas, expone un API publico
de catalogo**. Sin anti-bot, sin credencial y sin coste:

    GET https://{tienda}/api/catalog_system/pub/products/search?ft={insumo}

Y devuelve mas de lo que se podia sacar raspando una ficha:

| Dato | De donde sale |
|---|---|
| precio vigente | `commertialOffer.Price` |
| precio sin descuento | `commertialOffer.ListPrice` |
| **stock en unidades** | `commertialOffer.AvailableQuantity` |
| **EAN** | `items[].ean` |
| marca, categoria, unidad | `brand`, `categories`, `measurementUnit` |
| URL de la ficha | `link` |

El stock es el dato que le falta a la regla `stock_minimo` de
`promotion_rules`, apagada desde S7 precisamente porque ninguna fuente lo daba.
Y el EAN es la clave con la que comparar el mismo producto entre cadenas: en la
prueba, la misma bolsa de quinua tricolor de 454 g sale a 15,70 en Wong y a
15,00 en Metro. Eso es exactamente lo que un mapa comercial debe enseñar.

## Que tiendas y por que estas

Se comprobo una por una. Responden con el API: Wong, Metro, Plaza Vea, Makro,
Oechsle y Promart. Solo entran las cuatro de alimentacion; Oechsle es tienda
por departamentos y Promart ferreteria, y para un insumo agroalimentario solo
aportarian ruido. Tottus devuelve 503 y Vivanda y Tambo no exponen el API.

## Sobre la moneda

El API no declara la moneda. Se marca PEN porque **es una propiedad de la
tienda**, no una deduccion sobre la pagina: las cuatro son cadenas peruanas que
venden en soles. Va en la tabla de tiendas de abajo, a la vista, y no escondido
en el codigo que mapea los campos.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from casos_de_uso.agente.agente import _sin_tildes, corresponde_al_insumo
from casos_de_uso.agente.schemas import ProductoSchema

logger = logging.getLogger(__name__)

# host -> (nombre legible, moneda en la que vende)
TIENDAS_VTEX: dict[str, tuple[str, str]] = {
    "www.wong.pe": ("Wong", "PEN"),
    "www.metro.pe": ("Metro", "PEN"),
    "www.plazavea.com.pe": ("Plaza Vea", "PEN"),
    "www.makro.plazavea.com.pe": ("Makro", "PEN"),
}

_RUTA = "/api/catalog_system/pub/products/search"

# VTEX usa cifras centinela para "hay de sobra" en vez de un stock real. Por
# encima de esto no se guarda como unidades: decir que hay 99.999 bolsas de
# quinua seria inventar una cifra, y `stock_minimo` la daria por buena siempre.
STOCK_CENTINELA = 10000

TIEMPO_ESPERA = 25.0

# Departamentos que no pueden contener un insumo agroalimentario.
#
# Hace falta porque el nombre por si solo no basta: Plaza Vea vende un
# "Smartphone MOTOROLA G17 6.8\" 4GB 128GB 50MP+5MP **Arandano**" —arandano es
# el color del telefono—, y por nombre casa perfectamente. Lo que lo delata es
# su categoria: /Tecnologia/Telefonia/.
#
# La lista es corta a proposito y se equivoca hacia dejar pasar. Un champu de
# maca o una galleta de arandano SI son mercado del insumo, y descartarlos
# empobreceria el mapa; esto solo saca lo que no es consumible de ninguna
# forma. Lo dudoso lo resuelve la persona que revisa la cuarentena.
DEPARTAMENTOS_EXCLUIDOS = ("tecnologia", "telefonia", "electrohogar",
                           "muebles", "ferreteria", "jugueteria",
                           "vestuario", "calzado")


@dataclass(frozen=True)
class OfertaVTEX:
    producto: ProductoSchema
    fuente_url: str
    evidencia: str
    tienda: str


def _evidencia_de(nodo: dict, item: dict, oferta: dict) -> str:
    """Los campos que respaldan cada valor extraido, y solo esos.

    Primero se guardaba el nodo entero recortado a 8.000 caracteres, y el
    precio **quedaba fuera del recorte**: vive en
    `items[].sellers[].commertialOffer`, detras de las especificaciones y las
    imagenes, que en estas fichas ocupan de sobra ese presupuesto. El grounding
    daba entonces por inventado un precio que la tienda si publica, y la regla
    `grounding_ok` de S7 habria rechazado la oferta.

    Es el mismo error que ya se corrigio con el JSON-LD, y la misma leccion: la
    evidencia se construye con lo que respalda la afirmacion, no recortando un
    volcado por donde caiga.
    """
    return json.dumps({
        "productName": nodo.get("productName"),
        "brand": nodo.get("brand"),
        "categories": nodo.get("categories"),
        "link": nodo.get("link"),
        "productReference": nodo.get("productReference"),
        "ean": item.get("ean"),
        "measurementUnit": item.get("measurementUnit"),
        "unitMultiplier": item.get("unitMultiplier"),
        "Price": oferta.get("Price"),
        "ListPrice": oferta.get("ListPrice"),
        "PriceWithoutDiscount": oferta.get("PriceWithoutDiscount"),
        "AvailableQuantity": oferta.get("AvailableQuantity"),
        "IsAvailable": oferta.get("IsAvailable"),
        "consultado_en": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False)


def _categoria_de(categorias: list[str] | None) -> str | None:
    """La mas especifica: VTEX las da de la mas profunda a la mas general."""
    if not categorias:
        return None
    return categorias[0].strip("/").split("/")[-1] or None


def _es_departamento_excluido(categorias: list[str] | None) -> bool:
    """Si el producto vive en un departamento que no vende comida."""
    if not categorias:
        return False
    texto = _sin_tildes(" ".join(categorias))
    return any(d in texto for d in DEPARTAMENTOS_EXCLUIDOS)


def _a_producto(nodo: dict, moneda: str) -> ProductoSchema | None:
    items = nodo.get("items") or []
    if not items:
        return None
    item = items[0]

    vendedores = item.get("sellers") or []
    if not vendedores:
        return None
    oferta = vendedores[0].get("commertialOffer") or {}

    precio = oferta.get("Price")
    nombre = nodo.get("productName") or item.get("nameComplete")
    if precio in (None, 0) or not nombre:
        return None

    stock = oferta.get("AvailableQuantity")
    if not isinstance(stock, int) or stock <= 0 or stock >= STOCK_CENTINELA:
        stock = None

    return ProductoSchema(
        nombre=nombre,
        precio=float(precio),
        precio_local=f"{moneda} {precio}",
        moneda=moneda,
        marca=nodo.get("brand") or None,
        stock=stock,
        ean=item.get("ean") or None,
        descripcion=(nodo.get("description") or "").strip() or None,
        unidad=item.get("measurementUnit") or None,
        categoria=_categoria_de(nodo.get("categories")),
        pais_origen=None,
        fecha_disponibilidad=None,
    )


class CatalogoVTEX:
    """Consulta el catalogo de las cadenas conocidas."""

    def __init__(self, tiendas: dict[str, tuple[str, str]] | None = None,
                 timeout: float = TIEMPO_ESPERA):
        self._tiendas = tiendas if tiendas is not None else TIENDAS_VTEX
        self._timeout = timeout

    async def buscar(self, insumo: str,
                     limite_por_tienda: int = 5) -> list[OfertaVTEX]:
        """Ofertas del insumo en todas las tiendas, consultadas en paralelo.

        Una tienda que falle no cancela a las demas: son fuentes
        independientes, y quedarse sin Metro porque Wong dio un 500 seria
        perder datos por nada.
        """
        if not insumo:
            return []

        async with httpx.AsyncClient(
                timeout=self._timeout, follow_redirects=True,
                headers={"User-Agent": "AgroScoutIA/1.0 (+https://agroscout.ai/bot)"}
        ) as cliente:
            tareas = [self._de_una_tienda(cliente, host, insumo, limite_por_tienda)
                      for host in self._tiendas]
            tandas = await asyncio.gather(*tareas, return_exceptions=True)

        ofertas: list[OfertaVTEX] = []
        for host, tanda in zip(self._tiendas, tandas):
            if isinstance(tanda, Exception):
                logger.warning(f"VTEX {host}: {type(tanda).__name__}: {tanda}")
                continue
            ofertas.extend(tanda)
        return ofertas

    async def _de_una_tienda(self, cliente: httpx.AsyncClient, host: str,
                             insumo: str, limite: int) -> list[OfertaVTEX]:
        nombre_tienda, moneda = self._tiendas[host]
        url = f"https://{host}{_RUTA}"

        respuesta = await cliente.get(
            url, params={"ft": insumo, "_from": 0, "_to": max(limite - 1, 0)})

        # 206 es lo normal: VTEX pagina y devuelve Partial Content.
        if respuesta.status_code not in (200, 206):
            logger.warning(f"VTEX {host}: HTTP {respuesta.status_code}")
            return []
        if "json" not in respuesta.headers.get("content-type", ""):
            logger.warning(f"VTEX {host}: no devolvio JSON")
            return []

        ofertas = []
        descartadas = 0
        for nodo in respuesta.json():
            producto = _a_producto(nodo, moneda)
            if producto is None:
                continue

            # El buscador de VTEX es generoso: para 'arandano' devolvio un
            # smartphone Motorola, y para 'maca' una hamaca de bañera. Se
            # aplica el mismo criterio que a las fichas de la web abierta.
            if not corresponde_al_insumo(producto.nombre, insumo):
                descartadas += 1
                continue

            if _es_departamento_excluido(nodo.get("categories")):
                logger.info(f"  descartado por departamento: "
                            f"{producto.nombre[:50]!r} en {nodo.get('categories')}")
                descartadas += 1
                continue

            item = (nodo.get("items") or [{}])[0]
            oferta = ((item.get("sellers") or [{}])[0]
                      .get("commertialOffer") or {})

            ofertas.append(OfertaVTEX(
                producto=producto,
                fuente_url=nodo.get("link") or f"https://{host}",
                evidencia=_evidencia_de(nodo, item, oferta),
                tienda=nombre_tienda,
            ))

        logger.info(f"VTEX {nombre_tienda}: {len(ofertas)} oferta(s) de '{insumo}'"
                    + (f" ({descartadas} descartada(s) por no serlo)" if descartadas else ""))
        return ofertas
