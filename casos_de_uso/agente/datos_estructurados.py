"""
S8 - Extraccion de ofertas desde los datos estructurados de la pagina.

## Por que existe

El agente N3 descargaba la pagina, la pasaba por `trafilatura.extract()` y le
daba el texto resultante al modelo para que sacara nombre y precio. Medido
contra tiendas peruanas reales, eso no funciona: de Falabella salian 828
caracteres de texto util y el modelo extraia `nombre='; '`; de
frutossecosdeperu, 365 caracteres y `precio=None`. El precio lo pinta
JavaScript, asi que no esta en el texto que ve `trafilatura`.

Pero **si esta en el HTML**. Casi todas las plataformas de comercio
—VTEX, WooCommerce, Shopify, Magento— publican la ficha en un bloque
`<script type="application/ld+json">` con el vocabulario `schema.org/Product`,
en la respuesta inicial y sin necesidad de renderizar nada.

Medido sobre ocho fichas peruanas: **cinco dan nombre, precio y moneda
exactos** por esta via (Falabella/Tottus 15,20; frutossecosdeperu 4,50; Vega
tres ofertas; Metro 14,99; Comfrutti 7,50). Las tres restantes —Wong, Ecoandino,
Plaza Vea— no traen JSON-LD y siguen necesitando el camino del modelo o un
renderizador.

## Por que va ANTES que el modelo, y no despues

1. **Es exacto.** El precio es el que la tienda publica para maquinas, no el que
   un modelo cree leer. No hay alucinacion posible que corregir despues.
2. **Es gratis y es instantaneo.** Una extraccion con glm-5.2 cuesta entre 15 y
   42 segundos medidos; esto son milisegundos y cero tokens.
3. **Cubre las paginas de categoria.** Vega devuelve tres productos en una sola
   URL. El camino del modelo daba como mucho uno.

El modelo se queda como respaldo para las fichas sin datos estructurados, que
es donde de verdad aporta.

## Lo que NO se rellena

Solo se traduce lo que schema.org define. `stock` se queda a null aunque haya
`availability`: 'InStock' no es una cifra de unidades, y el contrato de
ProductoSchema dice unidades. Inventarlo aqui seria exactamente lo que el
prompt del extractor prohibe.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Iterator

from .schemas import ProductoSchema

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OfertaEstructurada:
    """Una oferta y el trozo de pagina del que salio.

    La evidencia es el nodo JSON-LD, no un recorte del principio del HTML.
    Medido: en Vega el primer bloque JSON-LD empieza en el caracter 202.210 y
    en frutossecosdeperu en el 134.407, muy por detras de los 6.000 que el
    agente guardaba. Con un prefijo ciego, el grounding check no encontraria el
    valor y la regla `grounding_ok` de S7 rechazaria ofertas perfectamente
    buenas.
    """
    producto: ProductoSchema
    evidencia: str

# Tope de la evidencia que se guarda por oferta. Un nodo Product con
# descripcion larga y variantes puede ocupar bastante, y esto acaba en
# staging_agente.html_capturado, una fila por oferta.
MAX_EVIDENCIA = 8000

_BLOQUES_JSONLD = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL)

# Claves cuyo valor puede contener mas nodos. `@graph` es lo que usan Yoast y
# WooCommerce para meter Product, Organization y BreadcrumbList en el mismo
# bloque; sin recorrerlo, media web queda como "sin Product".
_CLAVES_ANIDADAS = ("@graph", "offers", "hasVariant", "itemListElement", "item",
                    "mainEntity", "priceSpecification")


def _nodos(dato: Any) -> Iterator[dict]:
    """Todos los diccionarios del arbol, entrando por las claves anidadas."""
    if isinstance(dato, list):
        for elemento in dato:
            yield from _nodos(elemento)
    elif isinstance(dato, dict):
        yield dato
        for clave in _CLAVES_ANIDADAS:
            if clave in dato:
                yield from _nodos(dato[clave])


def _es_producto(nodo: dict) -> bool:
    tipos = nodo.get("@type")
    tipos = tipos if isinstance(tipos, list) else [tipos]
    return "Product" in tipos


def a_decimal(valor: Any) -> float | None:
    """El precio llega como numero o como cadena ('15.2', '1.234,50', 'S/ 4.50')."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return None

    # Deja solo digitos y separadores, luego normaliza el decimal.
    texto = re.sub(r"[^\d.,]", "", texto)
    if not texto:
        return None
    if "," in texto and "." in texto:
        # El ultimo separador que aparece es el decimal.
        decimal = "," if texto.rfind(",") > texto.rfind(".") else "."
        miles = "." if decimal == "," else ","
        texto = texto.replace(miles, "").replace(decimal, ".")
    elif "," in texto:
        # Coma sola: decimal si deja dos cifras detras, si no es de miles.
        entero, _, resto = texto.rpartition(",")
        texto = f"{entero}.{resto}" if len(resto) == 2 else texto.replace(",", "")

    try:
        return float(texto)
    except ValueError:
        return None


def _precio_de(oferta: dict) -> float | None:
    """El precio de una oferta, mirando donde cada plataforma lo pone.

    `price` es lo normal; `lowPrice`/`highPrice` aparecen en AggregateOffer
    (una ficha con variantes); `priceSpecification` es lo que usa VTEX.
    """
    for clave in ("price", "lowPrice", "highPrice"):
        precio = a_decimal(oferta.get(clave))
        if precio is not None:
            return precio

    especificacion = oferta.get("priceSpecification")
    if especificacion:
        for nodo in _nodos(especificacion):
            precio = a_decimal(nodo.get("price"))
            if precio is not None:
                return precio
    return None


def _texto(valor: Any) -> str | None:
    """schema.org admite un objeto donde se espera texto: brand puede ser
    `"Tottus"` o `{"@type": "Brand", "name": "Tottus"}`."""
    if valor is None:
        return None
    if isinstance(valor, dict):
        valor = valor.get("name")
    if isinstance(valor, list):
        valor = valor[0] if valor else None
        if isinstance(valor, dict):
            valor = valor.get("name")
    texto = str(valor).strip() if valor is not None else ""
    return texto or None


def _a_producto(nodo: dict) -> ProductoSchema | None:
    """Traduce un nodo Product de schema.org a ProductoSchema.

    Devuelve None si falta el nombre o el precio: sin uno de los dos no es una
    oferta, y el validador de S7 la rechazaria igualmente.
    """
    nombre = _texto(nodo.get("name"))
    if not nombre:
        return None

    ofertas = [n for n in _nodos(nodo.get("offers", {})) if isinstance(n, dict)]
    precio = next((p for p in (_precio_de(o) for o in ofertas) if p is not None), None)
    if precio is None:
        return None

    moneda = next((_texto(o.get("priceCurrency")) for o in ofertas
                   if o.get("priceCurrency")), None)

    return ProductoSchema(
        nombre=nombre,
        precio=precio,
        # Con la moneda tal cual la declara la pagina. No se traduce a simbolo:
        # 'PEN' es lo que dice la fuente y 'S/' seria cosecha nuestra.
        precio_local=f"{moneda} {precio}" if moneda else None,
        moneda=moneda,
        marca=_texto(nodo.get("brand")),
        # stock se queda a null aposta: availability es 'InStock', no unidades.
        stock=None,
        descripcion=_texto(nodo.get("description")),
        unidad=None,
        categoria=_texto(nodo.get("category")),
        pais_origen=None,
        fecha_disponibilidad=None,
    )


def extraer_productos(html: str) -> list[OfertaEstructurada]:
    """Ofertas publicadas como datos estructurados en el HTML crudo.

    Lista vacia si la pagina no trae JSON-LD utilizable: quien llama debe
    entonces recurrir al modelo. Nunca lanza — una pagina con JSON roto es
    normal y no es motivo para tumbar el barrido.
    """
    if not html:
        return []

    ofertas: list[OfertaEstructurada] = []
    vistos: set[tuple[str, float]] = set()

    for bloque in _BLOQUES_JSONLD.findall(html):
        try:
            dato = json.loads(bloque.strip())
        except (json.JSONDecodeError, ValueError):
            continue

        for nodo in _nodos(dato):
            if not _es_producto(nodo):
                continue
            producto = _a_producto(nodo)
            if producto is None:
                continue
            # Una misma ficha suele aparecer en dos bloques (uno del tema y
            # otro del plugin de SEO).
            clave = (producto.nombre, producto.precio)
            if clave in vistos:
                continue
            vistos.add(clave)
            ofertas.append(OfertaEstructurada(
                producto=producto,
                evidencia=json.dumps(nodo, ensure_ascii=False)[:MAX_EVIDENCIA],
            ))

    return ofertas
