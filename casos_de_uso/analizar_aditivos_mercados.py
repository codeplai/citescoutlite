"""
T4.2 — El orquestador: de una fila del mapa comercial a las tres tarjetas.

## Un mecanismo por mercado, y por eso esto no es un bucle

Los tres evaluadores no se parecen (D-1 del plan), y el orquestador existe para
que esa asimetría no se note fuera:

    US     agente en vivo contra el eCFR    ~15-36 s, con coste, cacheable
    UE     Anexo II en local                 < 8 ms, gratis
    CODEX  tabla curada a mano               < 1 ms, hoy casi toda PENDIENTE

## Concurrencia: el número que arregla la latencia de T1

Medido en T1: entre 14,5 y 35,9 s por aditivo, p95 ≈ 36 s. Un producto del
snapshot lleva **una mediana de 2 aditivos y hasta 9**, así que en serie un
producto malo son ~5 minutos. Aquí se evalúan **todos los aditivos a la vez**,
con lo que el producto entero cuesta lo que su aditivo más lento —~36 s— en vez
de la suma.

No es un detalle de rendimiento: a 5 minutos la pestaña no se puede enseñar.

## La caché envuelve solo a EE. UU.

Es lo único caro. La UE y el Codex son diccionarios en memoria: cachearlos
añadiría una capa de invalidación para ahorrar microsegundos. La clave es
`(aditivo, matriz)` y no el producto: dos productos distintos con sorbato de
potasio en pulpa de fruta comparten respuesta, que es justo lo que hace que la
segunda consulta salga instantánea.

## La regla que hereda el asterisco de T4.4

`mapear_categoria` **deduce** la categoría del Anexo II a partir del texto libre
de OFF; no la sabe. Que «Snacks, Sweet snacks» sea 15.1 es una lectura
razonable, no un hecho. Por eso, cuando la categoría viene deducida, **ningún
mercado puede devolver un `SI` limpio**: se degrada a `SI_CONDICIONADO` y la nota
dice de qué segmento salió la deducción.

Es el asterisco de `acido1.pptx` y `acido2.pptx`, y su nota al pie: confirmar la
clasificación exacta del producto antes de cada envío. Un `SI` rotundo apoyado en
una categoría adivinada sería la peor celda que este sistema puede producir.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Protocol

from dominio.analisis_aditivos import (
    MERCADOS,
    AditivoEvaluado,
    AnalisisIngredientes,
    EvaluacionMercado,
)
from etl.analizar_ingredientes import (
    ADITIVOS,
    _plegar,
    aditivos as leer_aditivos,
    codigos_aditivos as leer_codigos,
    separar,
)
from etl.mapear_categoria import Categoria, mapear

logger = logging.getLogger(__name__)

# Cuánto vale una respuesta cacheada del eCFR. El corpus se reingesta cuando uno
# quiere y la FDA modifica el título 21 a menudo, pero no a diario: 90 días es
# el compromiso entre no repagar 30 s y no enseñar una cita de hace un año.
TTL_CACHE = timedelta(days=90)

# Techo de lo que se espera al agente por aditivo.
#
# `AgenteECFR.evaluar` prueba hasta 3 candidatas y cada lectura tiene su propio
# limite de 60 s, asi que el peor caso son **180 s**. Eso no cabe en una
# peticion HTTP: la pasarela corta antes y el usuario se queda sin nada,
# habiendo pagado las tres lecturas.
#
# 45 s da margen holgado sobre los 36 s del p95 medido en T1 y deja la peticion
# acotada. Al agotarse, ESE mercado sale `SIN_DATO` diciendo que se agoto el
# tiempo; los otros dos ya han respondido y el analisis se entrega igual. Es el
# principio del ADR: degradar a "sin dato", nunca a error.
TIEMPO_MAXIMO_US = 45.0

#: Número E -> término con el que se busca en el eCFR.
#:
#: El snapshot es anglosajón y el eCFR también, pero `analizar_ingredientes`
#: devuelve el nombre canónico en castellano. Esta tabla es solo el término de
#: búsqueda: si uno estuviera mal, el agente no encontraría sección y la celda
#: saldría `SIN_DATO`. Es decir, **se equivoca hacia el lado seguro**, que es la
#: razón por la que puede vivir en código y no en una tabla curada.
TERMINO_EN: dict[str, str] = {
    "E330": "citric acid", "E300": "ascorbic acid", "E322": "lecithin",
    "E415": "xanthan gum", "E440": "pectin", "E412": "guar gum",
    "E202": "potassium sorbate", "E960": "steviol glycosides",
    "E296": "malic acid", "E331": "sodium citrate", "E306": "tocopherols",
    "E955": "sucralose", "E270": "lactic acid", "E500": "sodium bicarbonate",
    "E170": "calcium carbonate", "E160b": "annatto", "E211": "sodium benzoate",
    "E410": "locust bean gum", "E407": "carrageenan",
    "E466": "carboxymethyl cellulose", "E950": "acesulfame potassium",
    "E150": "caramel color", "E160a": "beta-carotene",
    "E508": "potassium chloride", "E220": "sulfur dioxide",
    "E418": "gellan gum", "E282": "calcium propionate",
    "E339": "sodium phosphate", "E471": "mono- and diglycerides",
    "E171": "titanium dioxide", "E951": "aspartame", "E200": "sorbic acid",
    "E385": "calcium disodium EDTA", "E203": "calcium sorbate",
    "E386": "disodium EDTA",
}

#: Nombre canónico -> número E, derivado de la tabla que ya usa el mapa comercial.
_NUMERO_E: dict[str, str] = {nombre: numero
                             for nombre, numero in ADITIVOS.values()}


def _clave(codigo: str) -> str:
    """El número E sin subforma, para no evaluar dos veces el mismo aditivo.

    «Lecitina (E322)» leído por nombre y «INS 322(i)» leído por código son el
    mismo aditivo escrito de dos maneras en la misma etiqueta. Sin esta clave
    saldrían dos tarjetas idénticas, y se pagarían dos consultas al agente.
    """
    return re.sub(r"[^A-Za-z0-9]", "", codigo.split("(")[0]).upper()


class Cache(Protocol):
    """La forma de `puertos.cache_llm.CacheLLM`, que es la que ya existe."""

    def obtener(self, clave: str) -> dict | None: ...
    def guardar(self, clave: str, valor: dict, **extra) -> None: ...


class AnalizadorAditivos:
    """Reúne los tres mercados para un producto del mapa comercial."""

    def __init__(self, agente_us=None, evaluador_ue=None, evaluador_codex=None,
                 cache: Cache | None = None,
                 tiempo_maximo_us: float = TIEMPO_MAXIMO_US):
        # Se inyectan los tres para poder probar sin red, sin corpus de 21 MB y
        # sin el CSV del Codex. En producción los construye `dependencias`.
        self._us = agente_us
        self._ue = evaluador_ue
        self._codex = evaluador_codex
        self._cache = cache
        self._tiempo_maximo_us = tiempo_maximo_us
        #: Cuántas veces se llamó al agente de verdad, sin contar los aciertos
        #: de caché. Es **lo único de este objeto que cuesta dinero**, y por eso
        #: se cuenta: el cost-meter de S8 no puede atribuir el gasto a esta
        #: pantalla si solo ve el número de consultas, porque la mayoría no paga.
        self.llamadas_agente = 0

    # -- entrada principal --------------------------------------------------

    async def analizar(self, producto_id: str, nombre: str,
                       ingredientes: str | None,
                       categoria: str | None = None) -> AnalisisIngredientes:
        """El análisis completo de un producto. Nunca lanza por falta de datos.

        Un producto sin aditivos reconocidos devuelve `aditivos=[]`, que es el
        **49,8 % del snapshot** y no es un error: es una etiqueta limpia.
        """
        cat = mapear(categoria)
        aditivos = self._leer_etiqueta(ingredientes)

        evaluados = await asyncio.gather(*(
            self._evaluar_aditivo(nombre, numero_e, cat)
            for nombre, numero_e in aditivos))

        return AnalisisIngredientes(
            producto_id=producto_id,
            producto_nombre=nombre,
            matriz=categoria,
            matriz_ue=cat.codigo_ue,
            aditivos=list(evaluados),
            no_reconocidos=self._no_reconocidos(
                ingredientes, [n for n, _ in aditivos]),
        )

    def _leer_etiqueta(self, ingredientes: str | None) -> list[tuple[str, str | None]]:
        """Los aditivos de la etiqueta como `(nombre, número E)`, sin repetir.

        Se lee de **las dos formas**, porque las etiquetas no escriben igual
        según de dónde vengan:

        - **Por nombre** — «potassium sorbate». Es como escribe el snapshot de
          OpenFoodFacts, que es anglosajón.
        - **Por código** — «Conservante sin 202». Es como escriben las
          etiquetas peruanas, y medido el 2026-08-14 sobre la góndola de las
          cadenas de Perú: **21 de 30 fichas con ingredientes usan códigos INS**
          y ninguna salía con el lector de nombres.

        El nombre de un aditivo que solo viene por código se resuelve contra la
        **Parte B del Anexo II** (321 pares número→nombre), que ya está
        ingerida. No se escribe una tabla nueva a mano: la que hace falta ya
        está, y sale del documento oficial.
        """
        por_nombre: list[tuple[str, str | None]] = []
        vistos: set[str] = set()

        for etiqueta in leer_aditivos(ingredientes):
            nombre = etiqueta.rsplit(" (", 1)[0]
            numero = _NUMERO_E.get(nombre)
            por_nombre.append((nombre, numero))
            if numero:
                vistos.add(_clave(numero))

        for codigo in leer_codigos(ingredientes):
            if _clave(codigo) in vistos:
                # Ya venía por nombre. Se queda esa lectura, que trae el nombre
                # en castellano y la subforma no aporta nada al veredicto.
                continue
            vistos.add(_clave(codigo))
            por_nombre.append((self._nombre_de(codigo), codigo))

        return por_nombre

    def _nombre_de(self, codigo: str) -> str:
        """El nombre oficial del aditivo, o el propio código si no se sabe.

        Devolver el código como nombre no es rendirse: es lo que dice la
        etiqueta. Enseñar «INS 471» es correcto y comprobable; inventarle un
        nombre bonito que la norma no usa, no.
        """
        try:
            from adaptadores.corpus_anexo_ii import corpus as corpus_ue
            nombre = corpus_ue().nombre_de(codigo)
            if nombre:
                return nombre
        except Exception as e:
            logger.debug("Sin nombre para %s: %s", codigo, e)
        return codigo.replace("E", "INS ", 1)

    @staticmethod
    def _no_reconocidos(ingredientes: str | None,
                        etiquetas: list[str]) -> list[str]:
        """Lo que la etiqueta declara y este sistema no sabe clasificar.

        Se enseña para que se vea hasta dónde llega la lectura: una lista de 20
        ingredientes de la que se reconocen 2 aditivos no significa que los
        otros 18 sean inocuos, significa que no se han mirado.

        La comparación va **plegada** —sin tildes y en minúsculas— con la misma
        función que usa el reconocedor. Comparando en crudo, el nombre canónico
        «Ácido cítrico» no casaba con el «acido citrico» de la etiqueta y el
        ingrediente salía en esta lista **después de haberse reconocido**: la
        pestaña decía a la vez que lo conocía y que no.
        """
        if not ingredientes:
            return []
        nombres = {_plegar(e.rsplit(" (", 1)[0]) for e in etiquetas}
        return [i for i in separar(ingredientes)
                if not any(n in _plegar(i) for n in nombres)][:40]

    # -- un aditivo, los tres mercados --------------------------------------

    async def _evaluar_aditivo(self, nombre: str, numero_e: str | None,
                               cat: Categoria) -> AditivoEvaluado:
        # Los tres a la vez. Dos son síncronos e instantáneos, así que el coste
        # real es el del agente; lanzarlos juntos evita encadenar esperas.
        us, ue, codex = await asyncio.gather(
            self._us_con_cache(numero_e, nombre, cat),
            asyncio.to_thread(self._ue_local, numero_e, nombre, cat),
            asyncio.to_thread(self._codex_local, numero_e, nombre, cat),
        )

        evaluaciones = [self._con_asterisco(e, cat) for e in (us, codex, ue)]
        # El contrato exige el orden de MERCADOS (US, CODEX, EU).
        evaluaciones.sort(key=lambda e: MERCADOS.index(e.mercado))

        return AditivoEvaluado(
            nombre=nombre,
            ins=numero_e.lstrip("E") if numero_e else None,
            e_number=numero_e,
            evaluaciones=evaluaciones,
        )

    async def _us_con_cache(self, numero_e: str | None, nombre: str,
                            cat: Categoria) -> EvaluacionMercado:
        if self._us is None:
            return _no_montado("US", "no hay agente del eCFR configurado")

        termino = TERMINO_EN.get(numero_e or "", "")
        if not termino:
            return _no_montado(
                "US", f"no hay término de búsqueda en inglés para {nombre}")

        clave = f"ecfr:{termino}|{cat.termino_en or ''}"
        if (guardado := self._leer_cache(clave)) is not None:
            return guardado

        try:
            # Se cuenta antes de esperar: una llamada que acaba en timeout ya
            # ha gastado tokens, y no contarla escondería justo el gasto que
            # más duele —el que no trajo respuesta—.
            self.llamadas_agente += 1
            evaluacion = await asyncio.wait_for(
                self._us.evaluar(termino, cat.termino_en, nombre),
                timeout=self._tiempo_maximo_us)
        except asyncio.TimeoutError:
            logger.warning("El agente del eCFR agotó %.0f s con %r",
                           self._tiempo_maximo_us, termino)
            return _no_montado(
                "US", f"el agente del eCFR agotó los "
                      f"{self._tiempo_maximo_us:.0f} s para «{termino}»")
        except Exception as e:
            # Un fallo del agente deja SU celda sin dato; los otros dos mercados
            # ya han respondido y el análisis se entrega igual.
            logger.warning("El agente del eCFR falló con %r: %s", termino, e)
            return _no_montado("US", f"el agente del eCFR falló ({type(e).__name__})")

        self._escribir_cache(clave, evaluacion)
        return evaluacion

    def _ue_local(self, numero_e: str | None, nombre: str,
                  cat: Categoria) -> EvaluacionMercado:
        if self._ue is None:
            return _no_montado("EU", "no hay Anexo II ingerido")
        return _sin_reventar("EU", nombre, lambda: self._ue.evaluar(
            numero_e, nombre, cat.codigo_ue, cat.original))

    def _codex_local(self, numero_e: str | None, nombre: str,
                     cat: Categoria) -> EvaluacionMercado:
        if self._codex is None:
            return _no_montado("CODEX", "no hay tabla curada del GSFA")
        return _sin_reventar("CODEX", nombre, lambda: self._codex.evaluar(
            numero_e, nombre, cat.original))

    # -- el asterisco -------------------------------------------------------

    @staticmethod
    def _con_asterisco(evaluacion: EvaluacionMercado,
                       cat: Categoria) -> EvaluacionMercado:
        """Una categoría deducida no puede sostener un `SI` rotundo.

        Solo toca el veredicto limpio. `NO`, `NO_CONDICIONADO` y `SIN_DATO` se
        quedan como están: degradar un «no autorizado» a «quizá» por no estar
        seguros de la categoría sería aflojar justo la respuesta que más
        conviene no aflojar.
        """
        if evaluacion.autorizado != "SI" or not cat.deducida:
            return evaluacion

        aviso = (f"La categoría de alimento se dedujo de «{cat.segmento}» "
                 f"(nivel {cat.nivel}), no consta en el producto. Confirmar la "
                 f"clasificación exacta antes de cada envío.")
        return evaluacion.model_copy(update={
            "autorizado": "SI_CONDICIONADO",
            "nota": f"{evaluacion.nota} {aviso}" if evaluacion.nota else aviso,
        })

    # -- caché --------------------------------------------------------------

    def _leer_cache(self, clave: str) -> EvaluacionMercado | None:
        if self._cache is None:
            return None
        try:
            crudo = self._cache.obtener(clave)
            if not crudo:
                return None
            evaluacion = EvaluacionMercado(**crudo)
        except Exception as e:
            # Una caché corrupta no puede tumbar el análisis: se ignora la
            # entrada y se vuelve a preguntar, que es lo que habría pasado sin
            # caché.
            logger.warning("Entrada de caché ilegible en %s: %s", clave, e)
            return None

        if datetime.now(timezone.utc) - evaluacion.verificado_en > TTL_CACHE:
            logger.info("Caché caducada para %s (%s)", clave,
                        evaluacion.verificado_en.date())
            return None
        return evaluacion

    def _escribir_cache(self, clave: str, evaluacion: EvaluacionMercado) -> None:
        if self._cache is None:
            return
        # `SIN_DATO` no se cachea: suele venir de un fallo de red o de un
        # timeout, y guardarlo 90 días convertiría un tropiezo de un minuto en
        # una celda vacía durante un trimestre.
        if evaluacion.autorizado == "SIN_DATO":
            return
        try:
            self._cache.guardar(clave, json.loads(evaluacion.model_dump_json()),
                                etapa="analisis_aditivos")
        except Exception as e:
            logger.warning("No se pudo cachear %s: %s", clave, e)


def _sin_reventar(mercado: str, nombre: str, llamada) -> EvaluacionMercado:
    """Ejecuta un evaluador local y convierte su fallo en `SIN_DATO`.

    Los dos evaluadores locales cargan su corpus **de forma perezosa**: el
    fichero se abre la primera vez que se consulta, no al construirlos. Así que
    un `data/ue/anexo_ii.json` que falte no revienta en el arranque —donde
    `_analizador` lo recogería— sino aquí dentro, en medio de un
    `asyncio.gather` que no lo esperaba, y se lleva por delante el análisis
    entero con un 500.

    EE. UU. ya estaba protegido porque su llamada es de red y era evidente que
    podía fallar. Estos dos no lo estaban, y son igual de capaces: un JSON
    corrupto, un disco lleno o un CSV a medio editar bastan.

    Que caiga un mercado no puede costar los otros dos. Es el principio del
    ADR: degradar a «sin dato», nunca a error.
    """
    try:
        return llamada()
    except Exception as e:
        logger.warning("El evaluador de %s falló con %r: %s: %s",
                       mercado, nombre, type(e).__name__, e)
        return _no_montado(mercado, f"el evaluador falló ({type(e).__name__})")


def _no_montado(mercado: str, motivo: str) -> EvaluacionMercado:
    """Un mercado sin su mecanismo detrás. No es «no autorizado»."""
    urls = {
        "US": "https://www.ecfr.gov/current/title-21",
        "EU": "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32011R1129",
        "CODEX": "https://www.fao.org/gsfaonline/index.html",
    }
    return EvaluacionMercado(
        mercado=mercado, autorizado="SIN_DATO",
        referencia_texto=f"{mercado} — sin consultar",
        referencia_url=urls[mercado], cita_literal="",
        origen={"US": "AGENTE_ECFR", "EU": "ANEXO_II",
                "CODEX": "CURADO_CODEX"}[mercado],
        nota=f"No se consultó este mercado: {motivo}.",
    )
