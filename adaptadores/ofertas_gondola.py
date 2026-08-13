"""
Las ofertas de gondola que se enseñan en el informe (etapa 2b).

## Que hace y que NO hace

Lee el catalogo de las tiendas y devuelve `OfertaComercial` listas para pintar,
ya convertidas a soles. **No escribe en `staging_agente`.**

Esa distincion es el nucleo de este modulo. Son dos caminos con dos propositos
distintos sobre la misma fuente:

| | Informe (esto) | Cuarentena (`repositorio_staging`) |
|---|---|---|
| Pregunta | "a cuanto esta HOY" | "que metemos en el catalogo" |
| Vida | la del informe | 24 h, hasta que alguien la revise |
| Revision | ninguna, y se dice en la tabla | una persona promueve o rechaza |

Si este modulo escribiera en cuarentena, cada consulta de cada usuario meteria
decenas de filas que nadie pidio revisar, y la cola de Promociones —que hoy
tiene 5 y es manejable— se volveria inservible en una tarde. La cuarentena se
llena desde el job y desde `scripts/poblar_staging_real.py`, a ritmo
controlado.

## Fallar aqui no rompe la consulta

Ante cualquier error se devuelve lista vacia y se anota en el log. Es el
principio del ADR-001: degradar a "sin dato", nunca a error. Que una tienda no
responda no puede tumbar un informe cuyo resto —composicion, regulacion,
insight— no depende de ella.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from dominio.oferta_comercial import (ConversionMoneda, EspecificacionNutricional,
                                      OfertaComercial)

logger = logging.getLogger(__name__)

# Tope de lo que se enseña por tienda en el informe. El conector puede traer
# mas; una tabla de gondola con cincuenta filas por cadena deja de leerse.
POR_TIENDA = 5

# El tope aleman es por busqueda entera, no por tienda: el agente no consulta
# una lista de cadenas conocidas, sale a la web y trae lo que encuentra, asi
# que "por tienda" no significa nada ahi. Cinco es lo que cabe leido junto a la
# tabla peruana sin que la comparacion se pierda de vista.
POR_BUSQUEDA_DE = 5

# Y el suizo, por lo mismo. Va aparte de POR_BUSQUEDA_DE aunque hoy valga igual
# porque las dos gondolas no rinden igual: en Suiza el conector descarta ademas
# las fichas que no son de una tienda suiza (`es_tienda_suiza`), asi que este
# tope y el aleman se afinan mirando cosas distintas.
POR_BUSQUEDA_CH = 5


def _conversion_de(precio: Optional[float], moneda: Optional[str],
                   cambio) -> tuple[Optional[float], Optional[ConversionMoneda]]:
    """El precio en soles y con que se convirtio.

    Para una tienda peruana la conversion es la identidad, pero se rellena
    igual: asi la columna en soles no tiene huecos y se puede ordenar sin casos
    especiales.
    """
    if precio is None:
        return None, None

    if (moneda or "PEN").upper() == "PEN":
        return round(float(precio), 2), ConversionMoneda(
            tasa=1.0, moneda_origen="PEN",
            fuente="Precio publicado en soles por la tienda")

    resultado = cambio.a_soles(precio, moneda) if cambio else None
    if resultado is None:
        # Sin tasa no se inventa una: la columna en soles queda vacia y el
        # precio original sigue ahi. Es preferible a una cifra sin respaldo.
        logger.warning(f"Sin tipo de cambio para {moneda}; la oferta se "
                       f"enseña solo en su moneda original")
        return None, None

    return resultado.precio_pen, ConversionMoneda(
        tasa=resultado.tasa, moneda_origen=resultado.moneda_origen,
        fecha_tasa=resultado.fecha_tasa, fuente=resultado.fuente)


def _ordenadas(ofertas: list[OfertaComercial]) -> list[OfertaComercial]:
    """Por EAN y luego por precio.

    Asi el mismo producto en dos tiendas cae en filas contiguas y la diferencia
    se ve sin buscarla; es lo que convierte la lista en una comparacion. Las
    que no tienen EAN van al final, ordenadas por precio, porque no se pueden
    emparejar con nada.

    Vive fuera de `de_peru` porque las dos gondolas tienen que ordenar igual.
    Copiada en cada metodo, la primera vez que alguien afinase una de las dos
    tablas quedarian discrepando, y la comparacion entre ambas —que es el
    entregable— se leeria mal sin que nada fallara.
    """
    return sorted(ofertas, key=lambda o: (
        o.ean is None,
        o.ean or "",
        o.precio_pen if o.precio_pen is not None else 1e9,
    ))


class OfertasGondola:
    """Ofertas de las tiendas conocidas, para el informe."""

    def __init__(self, catalogo=None, cambio=None, catalogo_de=None,
                 catalogo_ch=None):
        # Se inyectan para poder probar sin red. Por defecto, los de verdad.
        #
        # Son TRES ranuras de catalogo y no una compartida: si `de_alemania`
        # reutilizara `self._catalogo`, la primera llamada que se hiciera
        # decidiria el conector de las gondolas —la peruana acabaria
        # preguntandole al agente, o la alemana a VTEX— segun el orden en que
        # cayeran las consultas. Alemania y Suiza tampoco pueden compartir la
        # suya: van las dos por agente, pero con plantilla, pais y guarda de
        # mercado distintos, y una sola ranura haria que la primera consulta
        # decidiera en que pais busca la otra.
        #
        # Cada parametro nuevo va **al final** de la firma: los tests de S8
        # inyectan por nombre (`catalogo=`, `cambio=`, `catalogo_de=`) y de eso
        # cuelgan las suites peruana y alemana.
        self._catalogo = catalogo
        self._cambio = cambio
        self._catalogo_de = catalogo_de
        self._catalogo_ch = catalogo_ch

    def _catalogo_vtex(self):
        if self._catalogo is None:
            from adaptadores.catalogo_vtex import CatalogoVTEX
            self._catalogo = CatalogoVTEX()
        return self._catalogo

    def _catalogo_alemania(self):
        if self._catalogo_de is None:
            from adaptadores.catalogo_alemania import CatalogoAlemania
            self._catalogo_de = CatalogoAlemania()
        return self._catalogo_de

    def _catalogo_suiza(self):
        if self._catalogo_ch is None:
            from adaptadores.catalogo_suiza import CatalogoSuiza
            self._catalogo_ch = CatalogoSuiza()
        return self._catalogo_ch

    def _tipo_cambio(self):
        if self._cambio is None:
            from adaptadores.tipo_cambio import tipo_cambio
            self._cambio = tipo_cambio()
        return self._cambio

    def de_peru(self, insumo: str) -> list[OfertaComercial]:
        """Wong, Metro, Plaza Vea y Makro, por su API publico de catalogo.

        Sin anti-bot, sin credencial y sin coste: son segundos y no pasa por
        ningun modelo, que es lo que permite ponerlo en el camino de una
        consulta sincrona sin cambiar su latencia de forma apreciable.
        """
        if not insumo:
            return []

        try:
            crudas = self._catalogo_vtex().buscar_sync(insumo, POR_TIENDA)
        except Exception as e:
            logger.error(f"No se pudieron leer las tiendas peruanas para "
                         f"{insumo!r}: {type(e).__name__}: {e}")
            return []

        cambio = self._tipo_cambio()
        ahora = datetime.now(timezone.utc).isoformat()

        ofertas = [self._a_dominio(o, cambio, ahora, "vtex") for o in crudas]
        return _ordenadas(ofertas)

    def de_alemania(self, insumo: str, termino: str) -> list[OfertaComercial]:
        """REWE, Edeka, Alnatura y quien mas aparezca, **por agente**.

        No hay conector directo y no es por no haberlo buscado: se sondearon las
        cinco cadenas y ninguna publica precio sin credencial. El detalle esta
        en el docstring de `adaptadores/catalogo_alemania.py`.

        La consecuencia es que esto **tarda minutos y cuesta dinero**, al
        contrario que `de_peru`. Va igualmente dentro de /consultas, que es
        sincrono, por decision explicita.

        `termino` es la palabra alemana (`InsumoInterpretado.terminos_aleman`).
        **Sin termino no se busca**: con el insumo en castellano, Tavily
        devolveria articulos sobre exportacion y el filtro por nombre
        descartaria despues cualquier ficha alemana que llegara. Gastar una
        busqueda y varias extracciones para garantizar cero ofertas es peor que
        no llamar.
        """
        if not insumo or not termino:
            if insumo and not termino:
                logger.info(f"Sin termino aleman para {insumo!r}; no se consulta "
                            f"la gondola alemana")
            return []

        try:
            crudas = self._catalogo_alemania().buscar_sync(
                termino, POR_BUSQUEDA_DE, insumo)
        except Exception as e:
            logger.error(f"No se pudieron leer las tiendas alemanas para "
                         f"{termino!r}: {type(e).__name__}: {e}")
            return []

        cambio = self._tipo_cambio()
        ahora = datetime.now(timezone.utc).isoformat()

        ofertas = [self._a_dominio(o, cambio, ahora, "agente") for o in crudas]
        return _ordenadas(ofertas)

    def de_suiza(self, insumo: str, termino: str) -> list[OfertaComercial]:
        """Las tiendas suizas que el agente alcance, **por agente**.

        Ojo con lo que NO promete: Migros y Coop devuelven 403, y el 403 es del
        servidor, no del metodo, asi que el agente tampoco entra. Lo que llena
        esta tabla son tiendas suizas menores y Piccantino.

        La sonda del 2026-08-13 encontro una via gratis —Piccantino publica
        JSON-LD con precio en CHF— y se decidio no construir la gondola sobre
        ella sola: es una tienda gourmet de nicho, y Migros y Coop, que son la
        mayor parte del mercado, devuelven 403. El detalle esta en el docstring
        de `adaptadores/catalogo_suiza.py`.

        El camino gratis no se pierde: el agente pasa primero por
        `extraer_productos`, asi que cuando cae en una ficha con JSON-LD la lee
        sin gastar modelo.

        Cuesta lo mismo que Alemania —minutos y dinero— y va detras de ella en
        la misma peticion sincrona. Ese es el precio de la decision, y lleva su
        propio freno de mano: `AGROSCOUT_GONDOLA_CH=0`.

        `termino` es la palabra alemana (`InsumoInterpretado.terminos_aleman`),
        la misma que usa Alemania: las tiendas suizas que importan publican en
        aleman. **Sin termino no se busca**, por lo mismo que en `de_alemania`.
        """
        if not insumo or not termino:
            if insumo and not termino:
                logger.info(f"Sin termino aleman para {insumo!r}; no se consulta "
                            f"la gondola suiza")
            return []

        try:
            crudas = self._catalogo_suiza().buscar_sync(
                termino, POR_BUSQUEDA_CH, insumo)
        except Exception as e:
            logger.error(f"No se pudieron leer las tiendas suizas para "
                         f"{termino!r}: {type(e).__name__}: {e}")
            return []

        cambio = self._tipo_cambio()
        ahora = datetime.now(timezone.utc).isoformat()

        ofertas = [self._a_dominio(o, cambio, ahora, "agente") for o in crudas]
        return _ordenadas(ofertas)

    @staticmethod
    def _a_dominio(cruda: Any, cambio, capturado_en: str,
                   procedencia: str) -> OfertaComercial:
        p = cruda.producto
        precio_pen, conversion = _conversion_de(p.precio, p.moneda, cambio)

        return OfertaComercial(
            nombre=p.nombre,
            tienda=cruda.tienda,
            fuente_url=cruda.fuente_url,
            precio=p.precio,
            moneda=p.moneda,
            precio_pen=precio_pen,
            conversion=conversion,
            marca=p.marca,
            ean=p.ean,
            unidad=p.unidad,
            categoria=p.categoria,
            stock=p.stock,
            # Tal como lo publica la ficha. Si la tienda no la trae, va None y
            # la columna dira "sin dato": no se busca en otra fuente ni se
            # deduce de productos parecidos.
            nutricion=(EspecificacionNutricional(**getattr(cruda, "nutricion", None))
                       if getattr(cruda, "nutricion", None) else None),
            capturado_en=capturado_en,
            # El prefijo lo pone quien llama, no este metodo. Estaba fijado a
            # 'vtex:' y con eso una oferta de REWE —que llega por agente,
            # tras una busqueda web y una extraccion con modelo— se habria
            # etiquetado 'vtex:REWE'. Es el unico campo que dice de donde salio
            # la fila, y las dos rutas no cuestan lo mismo ni valen lo mismo:
            # una es un GET a un API publico y la otra pasa por un LLM.
            procedencia=f"{procedencia}:{cruda.tienda}",
        )
