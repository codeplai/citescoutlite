"""
T1.2/T1.3 — Agente regulatorio para EE. UU.: busca en vivo, lee y se deja
comprobar.

## El reparto: el ranking se pregunta, el texto se tiene

`https://www.ecfr.gov/api/search/v1/results` **no** está restringido por el
`robots.txt` del eCFR, y es lo que de verdad aporta inteligencia. Medido el
2026-08-13:

    "calcium disodium EDTA"  -> 29 resultados, el 1.º es §172.120
    "sorbic acid"            -> 90 resultados, el 1.º es §182.3089

Esas dos secciones son exactamente las que citan `acido1.pptx` y `acido2.pptx`,
y **§172.120 no existía en el corpus RAG del proyecto** (734 pasajes, sin la
parte 172). Buscar en vivo no es un capricho: es lo que cierra ese agujero.

El texto de la sección sale del corpus local (`corpus_ecfr.py`), porque el
endpoint que lo sirve sí está vetado a rastreadores y porque el texto no cambia
entre consultas.

## La regla que hace esto defendible: el modelo lee, el código decide

El modelo **no emite el veredicto**. Emite una lectura de lo que la sección dice
—qué cobertura tiene el aditivo, qué alimento aparece nombrado, qué cifra hay— y
`_veredicto()` la traduce a `SI` / `NO_CONDICIONADO` / lo que toque. La política
vive en código revisable, no en un prompt.

Y la cita **no la escribe el modelo**: `referencia_texto` y `referencia_url` se
construyen desde el identificador de sección con el que se pidió el documento.
Una cita a una norma inexistente es imposible por construcción, no por
comprobación.

## Grounding (D-2)

Lo que el modelo sí produce —la cifra y el fragmento— se comprueba contra el
texto de la sección:

1. `cita_literal` tiene que aparecer en la sección, comparando sin espacios de
   más. Un fragmento parafraseado no pasa.
2. Si hay `limite_valor`, ese número tiene que estar en la sección.

Si falla cualquiera de las dos, la celda es `SIN_DATO`. No se degrada a "sin
límite" ni se publica el veredicto sin la cifra: un veredicto que no se puede
señalar con el dedo en la norma no se publica.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import Literal

import httpx
import instructor
from dotenv import load_dotenv
from litellm import acompletion
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from adaptadores.corpus_ecfr import CorpusECFR, SeccionCFR, corpus
from casos_de_uso.integraciones import (
    check_rate_limit,
    record_request_failure,
    record_request_success,
)
from dominio.analisis_aditivos import EvaluacionMercado

load_dotenv()

logger = logging.getLogger(__name__)

URL_BUSQUEDA = "https://www.ecfr.gov/api/search/v1/results"

CABECERAS = {
    "User-Agent": "CiteScout/1.0 (consulta regulatoria; codeplaigamessac@gmail.com)"
}

# Mismo modelo que el agente comercial y que RedactorGLM.
MODELO = "openai/glm-5.2"
HUAWEI_MAAS_BASE_URL = os.getenv(
    "HUAWEI_MAAS_BASE_URL",
    "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
HUAWEI_MAAS_API_KEY = os.getenv("HUAWEI_MAAS_API_KEY", "")

TIEMPO_ESPERA_BUSQUEDA = 30.0
# El agente comercial mide 15-42 s por extraccion con este modelo. Una seccion
# del CFR es texto denso y la respuesta es corta, pero el modelo razona antes de
# contestar, asi que el margen se mantiene.
TIEMPO_ESPERA_EXTRACCION = 60.0

_REINTENTOS = dict(stop=stop_after_attempt(3),
                   wait=wait_exponential(multiplier=1, min=1, max=4),
                   reraise=True)

# Cuanto texto de la seccion se le manda al modelo.
#
# §172.120 son 9.155 bytes de XML, ~5.800 de texto: cabe entero. Las secciones
# largas de la parte 184 pasan de 20.000 y ahi se recorta, pero el recorte es
# por el final y la tabla de alimentos va casi siempre al principio.
MAX_CARACTERES = 12000

# Cuanto vale una parte del titulo 21 para esta pregunta. Multiplica al score
# del buscador; NO lo sustituye.
#
# La primera version agrupaba: todas las partes "de aditivos" antes que todas
# las demas, y dentro de cada grupo por score. Se midio el 2026-08-13 y estaba
# mal. Buscando `sorbic acid`, las candidatas salian asi:
#
#     parte 172  §172.878   score  9.3   White mineral oil     <- 1.a
#     parte 172  §172.878   score  9.0   White mineral oil     <- duplicada
#     parte 182  §182.3089  score 31.5   Sorbic acid           <- la buena, 3.a
#
# Una seccion de 9,3 puntos adelantaba a una de 31,5 solo por estar en la parte
# 172. Se llegaba a la respuesta correcta por los pelos —MAX_CANDIDATAS era 3—
# pagando tres llamadas al modelo en vez de una.
#
# Con peso multiplicativo el score manda y la parte solo inclina:
#
#   172/182/184  aditivos y GRAS. Responden justo la pregunta: que limite tiene
#                este aditivo. La 172 es la que le faltaba al corpus RAG.
#   173          coadyuvantes de proceso, algo mas lejos.
#   145/146/...  normas de identidad. Dicen que admite un alimento concreto, no
#                que limite tiene el aditivo: valen, pero menos.
#   resto        el titulo 21 entero habla de comida; una coincidencia en la
#                parte 1 casi nunca es una autorizacion.
PESO_PARTE: dict[str, float] = {
    "172": 1.0, "182": 1.0, "184": 1.0, "173": 0.9,
    "145": 0.6, "146": 0.6, "150": 0.6, "155": 0.6, "156": 0.6, "169": 0.6,
}
PESO_OTRAS_PARTES = 0.3

# Cuantas candidatas se prueban antes de rendirse. Cada una cuesta una llamada
# al modelo, asi que es un presupuesto, no un limite tecnico. Con la ordenacion
# corregida los dos casos de referencia aciertan a la primera.
MAX_CANDIDATAS = 3

_ESPACIOS = re.compile(r"\s+")
_NUMEROS = re.compile(r"\d[\d,]*\.?\d*")


def _normalizar(texto: str) -> str:
    """Minúsculas y espacios colapsados, para comparar sin falsos negativos."""
    return _ESPACIOS.sub(" ", (texto or "")).strip().lower()


@dataclass(frozen=True)
class Candidata:
    """Una sección que la búsqueda propone como respuesta."""

    seccion: str
    parte: str
    encabezado: str
    url: str
    score: float

    @property
    def cita(self) -> str:
        return f"21 CFR § {self.seccion}"


class LecturaSeccion(BaseModel):
    """Lo que el modelo **lee** en la sección. No es el veredicto.

    La diferencia importa: aquí no hay ningún campo que se llame «autorizado».
    El modelo describe qué dice el texto y el código decide qué significa, que
    es la única forma de que la política sea revisable.
    """

    cobertura: Literal[
        "GENERAL",           # autoriza sin lista de alimentos (GRAS, BPM)
        "ALIMENTO_NOMBRADO", # el alimento consultado aparece en la sección
        "OTROS_ALIMENTOS",   # hay lista de alimentos y el consultado NO está
        "PROHIBIDO",         # la sección prohíbe expresamente este uso
        "NO_TRATA",          # la sección no habla de este aditivo
    ] = Field(description="Qué cobertura da la sección al aditivo consultado")

    alimento_nombrado: str | None = Field(
        default=None,
        description="El alimento de la sección que corresponde al consultado, "
                    "copiado LITERALMENTE del texto (ej: 'Cucumbers pickled'). "
                    "null si no hay lista de alimentos o ninguno corresponde",
    )
    limite_valor: float | None = Field(
        default=None,
        description="Solo la cifra del límite para ese alimento. null si la "
                    "sección no da cifra (p. ej. buenas prácticas)",
    )
    limite_unidad: Literal["mg/kg", "ppm", "BPM", "N/A"] | None = Field(
        default=None,
        description="'ppm' si la sección dice parts per million; 'BPM' si dice "
                    "good manufacturing practice sin cifra",
    )
    cita_literal: str = Field(
        default="",
        description="Fragmento COPIADO PALABRA POR PALABRA de la sección que "
                    "sostiene lo anterior. Sin parafrasear, sin resumir",
    )
    nota: str | None = Field(
        default=None,
        description="Una frase sobre lo que queda por confirmar, si aplica",
    )


class AgenteECFR:
    """Busca la sección aplicable, la lee y devuelve una celda comprobada."""

    def __init__(self, corpus_local: CorpusECFR | None = None,
                 cliente: httpx.AsyncClient | None = None):
        # Se inyectan para poder probar sin red ni corpus de 21 MB.
        self._corpus = corpus_local
        self._cliente = cliente or httpx.AsyncClient(timeout=TIEMPO_ESPERA_BUSQUEDA)
        self._llm = instructor.from_litellm(acompletion)

    @property
    def corpus(self) -> CorpusECFR:
        if self._corpus is None:
            self._corpus = corpus()
        return self._corpus

    # -- 1. Búsqueda en vivo -------------------------------------------------

    async def buscar(self, termino_en: str,
                     max_resultados: int = 20) -> list[Candidata]:
        """Secciones del título 21 que hablan del aditivo, ya ordenadas.

        La consulta va **entrecomillada**: `calcium disodium EDTA` sin comillas
        trae cualquier sección con la palabra `calcium`, que en el título 21 son
        cientos. Con comillas, 29.
        """
        await check_rate_limit(URL_BUSQUEDA)
        try:
            respuesta = await self._cliente.get(
                URL_BUSQUEDA,
                params={"query": f'"{termino_en}"', "per_page": max_resultados},
                headers=CABECERAS,
            )
            respuesta.raise_for_status()
            record_request_success(URL_BUSQUEDA)
        except Exception as e:
            record_request_failure(URL_BUSQUEDA)
            logger.warning("Búsqueda eCFR falló para %r: %s", termino_en, e)
            return []

        candidatas = []
        for item in respuesta.json().get("results", []):
            jerarquia = item.get("hierarchy") or {}
            if str(jerarquia.get("title")) != "21" or not jerarquia.get("section"):
                continue
            candidatas.append(Candidata(
                seccion=str(jerarquia["section"]),
                parte=str(jerarquia.get("part") or ""),
                encabezado=_sin_etiquetas(
                    (item.get("headings") or {}).get("section") or ""),
                url=_url_de(jerarquia),
                score=float(item.get("score") or 0.0),
            ))

        return self._ordenar(candidatas)

    @staticmethod
    def _ordenar(candidatas: list[Candidata]) -> list[Candidata]:
        """Sin repetidas y por relevancia ponderada. Ver PESO_PARTE.

        Deduplica primero. El buscador devuelve una fila por cada versión de la
        sección —§172.878 salía dos veces, con score 9,3 y 9,0—, y cada repetida
        se comía una de las tres llamadas al modelo del presupuesto para releer
        exactamente el mismo texto.
        """
        mejor: dict[str, Candidata] = {}
        for c in candidatas:
            if c.seccion not in mejor or c.score > mejor[c.seccion].score:
                mejor[c.seccion] = c

        return sorted(
            mejor.values(),
            key=lambda c: -c.score * PESO_PARTE.get(c.parte, PESO_OTRAS_PARTES))

    # -- 2. Lectura con modelo ----------------------------------------------

    @retry(**_REINTENTOS)
    async def _leer(self, seccion: SeccionCFR, aditivo_en: str,
                    matriz_en: str | None) -> LecturaSeccion:
        """La llamada al modelo. Con reintentos porque aquí sí hay red.

        La falta de credencial NO se comprueba aquí, sino en `evaluar`: es un
        error de configuración, y reintentarlo tres veces con espera exponencial
        no lo arregla, solo tarda más en fallar. Mismo criterio que
        `AgenteInvestigadorComercial.extraer_producto`.
        """
        alimento = matriz_en or "(no se indicó el alimento)"
        sistema = (
            "Eres un lector de normativa alimentaria de EE. UU. Recibes UNA "
            "seccion del 21 CFR y devuelves lo que esa seccion dice sobre un "
            "aditivo en un alimento concreto.\n\n"
            "REGLA CRITICA: solo puedes afirmar lo que aparezca LITERALMENTE en "
            "el texto. No uses conocimiento general sobre el aditivo, no "
            "deduzcas y no completes. Cada cifra se verifica despues contra "
            "este mismo texto y una cifra que no este aqui invalida la "
            "respuesta entera.\n\n"
            "- 'cobertura': GENERAL si la seccion autoriza sin lista de "
            "alimentos (por ejemplo 'generally recognized as safe ... good "
            "manufacturing practice'). ALIMENTO_NOMBRADO si hay lista o tabla "
            "de alimentos y el alimento consultado esta en ella. "
            "OTROS_ALIMENTOS si hay lista y el consultado NO esta. PROHIBIDO si "
            "la seccion prohibe este uso. NO_TRATA si la seccion no habla de "
            "este aditivo.\n"
            "- EL ALIMENTO CONSULTADO PUEDE VENIR COMO CATEGORIA. Si la seccion "
            "nombra un alimento concreto que pertenece a esa categoria, eso es "
            "ALIMENTO_NOMBRADO: para 'pickled vegetable', la fila 'Cucumbers "
            "pickled' cuenta, porque un pepino encurtido es una hortaliza "
            "encurtida. Usa OTROS_ALIMENTOS solo cuando NINGUN alimento de la "
            "lista pertenezca a la categoria consultada.\n"
            "- 'alimento_nombrado': copia el nombre del alimento tal cual sale "
            "en la seccion, sin traducir. Si la consulta era una categoria, "
            "copia el alimento CONCRETO de la seccion que la cumple.\n"
            "- 'limite_valor': solo la cifra que corresponde a ESE alimento. Si "
            "la seccion no da cifra, null.\n"
            "- 'limite_unidad': 'ppm' si dice parts per million, 'mg/kg' si lo "
            "dice asi, 'BPM' si autoriza por buenas practicas sin cifra.\n"
            "- 'cita_literal': copia entre 10 y 300 caracteres del texto, "
            "PALABRA POR PALABRA, que sostengan lo que has respondido. No "
            "parafrasees: se comprueba por coincidencia exacta.\n"
        )
        usuario = (
            f"ADITIVO CONSULTADO: {aditivo_en}\n"
            f"ALIMENTO CONSULTADO: {alimento}\n\n"
            f"SECCION {seccion.cita}\n{seccion.texto[:MAX_CARACTERES]}"
        )

        return await self._llm.chat.completions.create(
            model=MODELO,
            response_model=LecturaSeccion,
            messages=[{"role": "system", "content": sistema},
                      {"role": "user", "content": usuario}],
            api_key=HUAWEI_MAAS_API_KEY,
            api_base=HUAWEI_MAAS_BASE_URL,
        )

    # -- 3. Grounding --------------------------------------------------------

    @staticmethod
    def grounding(seccion: SeccionCFR, lectura: LecturaSeccion) -> tuple[bool, str]:
        """¿Está en la norma lo que el modelo dice que está? (D-2)

        Devuelve `(pasa, motivo)`. El motivo se registra: un grounding que falla
        en silencio es un agente que miente sin que nadie se entere.
        """
        texto = _normalizar(seccion.texto)

        cita = _normalizar(lectura.cita_literal)
        if not cita:
            return False, "el modelo no devolvió cita literal"
        if cita not in texto:
            return False, f"la cita no está en {seccion.cita}: {cita[:80]!r}"

        if lectura.limite_valor is not None:
            # Se compara por VALOR y no por texto: la seccion escribe `220` y el
            # modelo devuelve 220.0. Buscar la cadena "220.0" daria por
            # inventada una cifra que esta delante.
            if not _numero_en(texto, lectura.limite_valor):
                return False, (f"el límite {lectura.limite_valor} no aparece en "
                               f"{seccion.cita}")

        if lectura.alimento_nombrado:
            if _normalizar(lectura.alimento_nombrado) not in texto:
                return False, (f"el alimento {lectura.alimento_nombrado!r} no "
                               f"aparece en {seccion.cita}")

        return True, "ok"

    # -- 4. Veredicto: esto lo decide el código ------------------------------

    @staticmethod
    def _veredicto(lectura: LecturaSeccion, matriz_en: str | None) -> str:
        """De lo que la sección dice a lo que el informe publica.

        El mapeo, y por qué cada uno:

        - `GENERAL` → **SI**. Es el caso del ácido sórbico: GRAS por buenas
          prácticas, sin lista de alimentos. No hay pregunta de categoría que
          responder, así que no lleva asterisco. Es lo que dice `acido1.pptx`.
        - `ALIMENTO_NOMBRADO` → **SI**. El caso del EDTA: §172.120 nombra los
          pepinos encurtidos con su cifra. Tampoco lleva asterisco, y esa es
          justo la razón por la que `acido2.pptx` lo llama «el mercado con la
          cobertura más directa».
        - `OTROS_ALIMENTOS` → **NO_CONDICIONADO**. El aditivo está autorizado,
          pero no para este alimento. **No es lo mismo que prohibido**, y por
          eso no es `NO` a secas: es el caso de la pulpa en la UE.
        - `PROHIBIDO` → **NO**.
        - Sin matriz y con lista de alimentos → **SI_CONDICIONADO**: se sabe que
          está autorizado, pero cuál de las cifras aplica depende de un dato que
          no tenemos.
        """
        if lectura.cobertura == "PROHIBIDO":
            return "NO"
        if lectura.cobertura == "GENERAL":
            return "SI"
        if lectura.cobertura == "ALIMENTO_NOMBRADO":
            return "SI" if matriz_en else "SI_CONDICIONADO"
        if lectura.cobertura == "OTROS_ALIMENTOS":
            # Sin saber qué alimento es el nuestro no se puede decir que no esté
            # cubierto: no lo hemos podido buscar en la lista.
            return "NO_CONDICIONADO" if matriz_en else "SI_CONDICIONADO"
        return "SIN_DATO"

    # -- 5. El método que se usa desde fuera --------------------------------

    async def evaluar(self, aditivo_en: str, matriz_en: str | None = None,
                      nombre_es: str | None = None) -> EvaluacionMercado:
        """La celda de EE. UU. para un aditivo en una matriz.

        Nunca lanza por no encontrar nada: devuelve `SIN_DATO`, que es el estado
        honesto. Lanzar obligaría a quien llama a decidir si un fallo de red
        significa «no autorizado», y esa confusión es exactamente la que no
        puede llegar a una tabla regulatoria.

        Sí lanza si falta la credencial, y a propósito: eso no es «no se pudo
        comprobar», es que este agente no está montado. Devolver `SIN_DATO`
        dejaría la columna de EE. UU. vacía en toda la aplicación sin que nadie
        se entere de por qué.
        """
        if not HUAWEI_MAAS_API_KEY:
            raise ValueError(
                "HUAWEI_MAAS_API_KEY no configurado: el agente del eCFR no "
                "puede leer secciones.")

        candidatas = await self.buscar(aditivo_en)
        if not candidatas:
            return _sin_dato(aditivo_en, "la búsqueda del eCFR no devolvió nada")

        motivos: list[str] = []
        for candidata in candidatas[:MAX_CANDIDATAS]:
            seccion = self.corpus.seccion(candidata.seccion)
            if seccion is None:
                motivos.append(f"{candidata.cita} no está en el corpus local")
                continue

            try:
                lectura = await asyncio.wait_for(
                    self._leer(seccion, aditivo_en, matriz_en),
                    timeout=TIEMPO_ESPERA_EXTRACCION)
            except Exception as e:
                motivos.append(f"{candidata.cita}: lectura falló ({type(e).__name__})")
                continue

            if lectura.cobertura == "NO_TRATA":
                motivos.append(f"{candidata.cita}: no trata este aditivo")
                continue

            pasa, motivo = self.grounding(seccion, lectura)
            if not pasa:
                # No se degrada a "sin límite" ni se publica a medias: se pasa a
                # la siguiente candidata. Una lectura que no se puede señalar en
                # la norma no vale menos, vale cero.
                logger.warning("Grounding rechazado en %s: %s", candidata.cita, motivo)
                motivos.append(f"{candidata.cita}: {motivo}")
                continue

            veredicto = self._veredicto(lectura, matriz_en)
            if veredicto == "SIN_DATO":
                motivos.append(f"{candidata.cita}: sin veredicto")
                continue

            return EvaluacionMercado(
                mercado="US",
                autorizado=veredicto,
                limite_valor=lectura.limite_valor,
                limite_unidad=lectura.limite_unidad,
                categoria_alimento=lectura.alimento_nombrado,
                # Cita y URL las pone el código desde el id de sección. El
                # modelo no participa: no puede citar una norma que no existe.
                referencia_texto=candidata.cita,
                referencia_url=candidata.url,
                cita_literal=lectura.cita_literal,
                origen="AGENTE_ECFR",
                nota=lectura.nota,
            )

        return _sin_dato(aditivo_en, "; ".join(motivos[:3]))

    async def close(self) -> None:
        await self._cliente.aclose()


# -- utilidades ------------------------------------------------------------

_ETIQUETA = re.compile(r"<[^>]+>")


def _sin_etiquetas(texto: str) -> str:
    """El buscador devuelve los encabezados con <strong> alrededor del término."""
    return _ESPACIOS.sub(" ", _ETIQUETA.sub("", texto or "")).strip()


def _url_de(jerarquia: dict) -> str:
    """La URL larga del eCFR, la misma forma que citan los PPTX de referencia.

    `https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-172/
     subpart-B/section-172.120`

    Se construye con la jerarquía que devuelve el buscador porque es la que el
    eCFR usa en sus enlaces; la forma corta también resuelve, pero esta es la
    que una persona reconoce al pegarla en un correo.
    """
    partes = [f"https://www.ecfr.gov/current/title-{jerarquia['title']}"]
    for campo in ("subtitle", "chapter", "subchapter", "part", "subpart",
                  "subject_group", "appendix", "section"):
        valor = jerarquia.get(campo)
        if valor:
            partes.append(f"{campo.replace('_', '-')}-{valor}")
    return "/".join(partes)


def _numero_en(texto: str, valor: float) -> bool:
    """¿Aparece esta cifra en el texto, escrita como sea?

    `220`, `220.0` y `1,200` son el mismo número escrito de tres formas. La
    comparación textual daba por inventadas cifras que están delante.
    """
    for candidato in _NUMEROS.findall(texto):
        try:
            if abs(float(candidato.replace(",", "")) - valor) < 1e-9:
                return True
        except ValueError:
            continue
    return False


def _sin_dato(aditivo_en: str, motivo: str) -> EvaluacionMercado:
    """La celda honesta cuando no se pudo comprobar nada.

    Apunta al buscador del eCFR y no a una sección concreta: es donde una
    persona seguiría buscando a mano, y prometer una sección que no se ha
    verificado sería justo lo que este módulo evita.
    """
    logger.info("US/%s -> SIN_DATO (%s)", aditivo_en, motivo)
    return EvaluacionMercado(
        mercado="US",
        autorizado="SIN_DATO",
        referencia_texto="21 CFR — sin sección aplicable localizada",
        referencia_url="https://www.ecfr.gov/current/title-21",
        cita_literal="",
        origen="AGENTE_ECFR",
        nota=f"No se pudo verificar contra el eCFR: {motivo}",
    )
