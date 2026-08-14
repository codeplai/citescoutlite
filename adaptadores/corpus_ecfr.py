"""
T1.1 — El título 21 del CFR en local, desde la distribución oficial del GPO.

## Por qué no se descarga sección a sección de la API del eCFR

Era el diseño del plan, y la sonda lo tumbó. El `robots.txt` de `ecfr.gov` dice:

    # Don't index developer tool links
    Disallow: /api/renderer/v1/content/
    Disallow: /api/versioner/v1/full/

`/api/versioner/v1/full/` es justo el endpoint que devuelve el texto de una
sección. La decisión D-6 del plan —no se rastrea lo que el sitio pide que no se
rastree— se tomó para la FAO y vale igual aquí, aunque aquí el dato sea público
y federal.

Tampoco sirve la página que ve una persona: `ecfr.gov/current/title-21/...` está
permitida, pero es una SPA. Las dos secciones de prueba devuelven **el mismo
shell de 10.595 bytes** y cero texto de la norma.

## Lo que sí sirve: bulkdata de govinfo

El GPO publica el título entero en `govinfo.gov/bulkdata/ECFR/title-21/`, que su
`robots.txt` **no restringe**. Un fichero, 21,6 MB, 8.406 secciones, con las
tablas dentro. Medido el 2026-08-13:

    §172.120  → 9.155 b, con la fila "Cucumbers pickled 220" de la tabla
    §182.3089 → 226 b, "generally recognized as safe ... good manufacturing"

Que son exactamente las dos citas de `acido1.pptx` y `acido2.pptx`.

## Y entonces, ¿dónde está el agente?

En la otra mitad (`agente_ecfr.py`). `/api/search/v1/results` **no** está
restringido, y es lo que de verdad aporta inteligencia: para
`"calcium disodium EDTA"` devuelve §172.120 como primer resultado de 29. Esa
búsqueda va en vivo. Lo que viene aquí en local es el texto, que no cambia entre
consultas y no tiene sentido volver a pedir cada vez.

Reparto, entonces: **el ranking se pregunta; el texto se tiene.**

## Ojo con la consola

El fichero es UTF-8 y se decodifica como UTF-8. Si al imprimirlo aparecen
rombos, es la consola cp1252 de Windows, no el dato: `Title 21—Food` sale como
`Title 21?Food` en pantalla y entero en memoria.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

URL_BULK = "https://www.govinfo.gov/bulkdata/ECFR/title-21/ECFR-title21.xml"

RUTA_POR_DEFECTO = Path("data/ecfr/ECFR-title21.xml")

# Se identifica de verdad. No es cortesía: es lo que permite al GPO distinguir
# este tráfico y bloquearlo si molesta, en vez de bloquear a todo httpx.
CABECERAS = {
    "User-Agent": "CiteScout/1.0 (consulta regulatoria; codeplaigamessac@gmail.com)"
}

# 21,6 MB por una conexión lenta tarda. Solo corre en la ingesta, no por consulta.
TIEMPO_ESPERA_DESCARGA = 300.0

# `<DIV8 N="§ 172.120" NODE="..." TYPE="SECTION"> ... </DIV8>`
#
# El N trae el símbolo de sección delante y a veces un rango ("§§ 1.1-1.5"), así
# que el número se saca aparte con _NUMERO en vez de meterlo en este patrón:
# un patrón que intente las dos cosas deja fuera las secciones raras en silencio.
_SECCION = re.compile(
    r'<DIV8\s+N="([^"]+)"[^>]*TYPE="SECTION"\s*>(.*?)</DIV8>', re.S)

_NUMERO = re.compile(r"(\d+[A-Za-z]?\.\d+[A-Za-z0-9\-]*)")

# El encabezado de la sección: `<HEAD>§ 172.120 Calcium disodium EDTA.</HEAD>`
_ENCABEZADO = re.compile(r"<HEAD>(.*?)</HEAD>", re.S)

_ETIQUETA = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"\s+")


def _a_texto(xml: str) -> str:
    """XML de una sección a texto plano legible.

    Las etiquetas se sustituyen por **un espacio** y no por nada. Suena a
    detalle y no lo es: las tablas del CFR son `<CELL>Cucumbers pickled</CELL>
    <CELL>220</CELL>`, y concatenar sin separador produce `pickled220`, que
    rompe tanto la lectura del modelo como el grounding del número.
    """
    texto = _ETIQUETA.sub(" ", xml)
    texto = (texto.replace("&amp;", "&").replace("&lt;", "<")
                  .replace("&gt;", ">").replace("&quot;", '"')
                  .replace("&#xA7;", "§").replace("&nbsp;", " "))
    return _ESPACIOS.sub(" ", texto).strip()


@dataclass(frozen=True)
class SeccionCFR:
    """Una sección del título 21, tal como la publica el GPO."""

    seccion: str          # "172.120"
    parte: str            # "172"
    encabezado: str       # "§ 172.120 Calcium disodium EDTA."
    texto: str            # texto plano, tablas incluidas

    @property
    def cita(self) -> str:
        """Como se escribe en el informe. La construye el código, no el modelo."""
        return f"21 CFR § {self.seccion}"

    @property
    def url(self) -> str:
        """La página que abre una persona. Es la forma que citan los PPTX.

        Sin la jerarquía completa (chapter/subchapter/subpart) porque el eCFR
        resuelve la forma corta. Cuando la búsqueda en vivo devuelve jerarquía,
        `agente_ecfr` construye la URL larga, que es la que sale en los PPTX.
        """
        return f"https://www.ecfr.gov/current/title-21/section-{self.seccion}"


def descargar(destino: Path | str = RUTA_POR_DEFECTO,
              forzar: bool = False) -> Path:
    """Trae el título 21 del bulkdata del GPO. Idempotente salvo `forzar`."""
    destino = Path(destino)
    if destino.exists() and not forzar:
        logger.info("eCFR ya descargado en %s (%.1f MB)",
                    destino, destino.stat().st_size / 1e6)
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    # A un fichero temporal y luego renombrar: si la descarga se corta a medias,
    # lo que queda en `destino` es el corpus anterior entero y no un XML
    # truncado que parsearia sin error y con la mitad de las secciones.
    parcial = destino.with_suffix(".parcial")

    logger.info("Descargando %s ...", URL_BULK)
    with httpx.stream("GET", URL_BULK, headers=CABECERAS,
                      timeout=TIEMPO_ESPERA_DESCARGA,
                      follow_redirects=True) as respuesta:
        respuesta.raise_for_status()
        with parcial.open("wb") as f:
            for trozo in respuesta.iter_bytes(1 << 20):
                f.write(trozo)

    parcial.replace(destino)
    logger.info("eCFR descargado: %.1f MB", destino.stat().st_size / 1e6)
    return destino


class CorpusECFR:
    """El título 21 indexado por número de sección.

    Parsea al construirse (0,34 s para las 8.406 secciones) y se queda en
    memoria. Es un diccionario, así que consultar es O(1) y gratis: el coste de
    esta clase es el arranque, no la consulta.
    """

    def __init__(self, ruta: Path | str = RUTA_POR_DEFECTO):
        self.ruta = Path(ruta)
        if not self.ruta.exists():
            raise FileNotFoundError(
                f"No está el corpus del eCFR en {self.ruta}. "
                f"Ejecuta `python -m etl.ingerir_ecfr` para descargarlo."
            )
        self._secciones: dict[str, SeccionCFR] = self._parsear()
        logger.info("Corpus eCFR: %d secciones de %d partes",
                    len(self._secciones), len(self.partes()))

    def _parsear(self) -> dict[str, SeccionCFR]:
        xml = self.ruta.read_text(encoding="utf-8", errors="replace")
        secciones: dict[str, SeccionCFR] = {}

        for atributo_n, cuerpo in _SECCION.findall(xml):
            numero = _NUMERO.search(atributo_n)
            if not numero:
                # Secciones reservadas o con N raro. No se cuentan como error:
                # simplemente no son consultables por número.
                continue
            identificador = numero.group(1)

            encabezado = _ENCABEZADO.search(cuerpo)
            secciones[identificador] = SeccionCFR(
                seccion=identificador,
                parte=identificador.split(".")[0],
                encabezado=_a_texto(encabezado.group(1)) if encabezado else "",
                texto=_a_texto(cuerpo),
            )

        return secciones

    def seccion(self, identificador: str) -> SeccionCFR | None:
        """La sección por su número ('172.120'), o None si no está.

        Acepta también '§ 172.120' y '21 CFR 172.120': quien llama viene de una
        cita, no de un identificador limpio, y obligarle a normalizar es
        repartir el mismo `strip` por tres módulos.
        """
        numero = _NUMERO.search(identificador or "")
        return self._secciones.get(numero.group(1)) if numero else None

    def partes(self) -> dict[str, int]:
        """Parte del título 21 -> nº de secciones. Para comprobar cobertura."""
        cuenta: dict[str, int] = {}
        for s in self._secciones.values():
            cuenta[s.parte] = cuenta.get(s.parte, 0) + 1
        return dict(sorted(cuenta.items(), key=lambda kv: int(kv[0])))

    def __len__(self) -> int:
        return len(self._secciones)

    def __contains__(self, identificador: str) -> bool:
        return self.seccion(identificador) is not None


# Singleton de proceso, como `busqueda_lancedb._get_tabla`: parsear 21,6 MB en
# cada consulta convertiría 0,34 s en el coste dominante de la pestaña.
_corpus: CorpusECFR | None = None


def corpus(ruta: Path | str = RUTA_POR_DEFECTO) -> CorpusECFR:
    global _corpus
    if _corpus is None:
        _corpus = CorpusECFR(ruta)
    return _corpus


def _reset_corpus() -> None:
    """Invalida el singleton. Solo para tests que cargan otro fichero."""
    global _corpus
    _corpus = None
