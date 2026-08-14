"""
T2 — El Anexo II del Reglamento (CE) 1333/2008 en local: qué aditivo se puede
usar en qué categoría de alimento en la UE, y con qué límite.

## Por qué esto NO va por agente

Fue la decisión D-1 del plan y la sonda la confirma. El Anexo II no está
repartido por la web: es **un solo documento**, el Reglamento (UE) 1129/2011
(`CELEX:32011R1129`), de 3,4 MB y 602 tablas. Buscarlo con un agente en cada
consulta sería pagar esa descarga y una extracción por modelo para releer lo
mismo. Se ingiere una vez y se consulta en local: determinista, instantáneo y
completo. Aquí el agente rinde *peor*, no es que dé miedo.

## Lo que enseña la estructura, y que cambia el diseño

    PARTE B  lista de TODOS los aditivos autorizados: 321 pares E -> nombre
    PARTE C  los grupos (I a IV) y sus miembros
    PARTE D  el árbol de categorías de alimento
    PARTE E  la matriz: 116 categorías × 2.177 filas de uso

Cada fila de la Parte E tiene seis columnas, y la sexta es la que manda:

    Nº categoría | Nº E | Denominación | Dosis máxima | Notas | **Restricciones**

**El veredicto vive en la columna de restricciones, no en la existencia de la
fila.** El caso de referencia lo demuestra: `acido1.pptx` dice que la UE no
autoriza el ácido sórbico en pulpa de maracuyá, y a primera vista el Anexo II
parece contradecirlo —E 200-203 aparece en la categoría 04.2.4.1 con 1.000
mg/kg—. Pero la restricción completa dice:

    "solo preparados de fruta y verdura, incluidos los preparados a base de
     algas, las salsas a base de frutas y el áspic, EXCEPTO EL PURÉ, la mousse,
     la compota, las ensaladas y los productos similares en conserva"

Un parser que se quedara en «E 200 está en 04.2.4.1 → autorizado» daría la
respuesta contraria a la correcta para una pulpa. Por eso `restricciones` se
guarda entera y viaja hasta la pantalla.

## Los rangos: por qué no se expanden con aritmética

444 de las 2.177 filas no traen un número E sino un rango: `E 200-203`,
`E 338-452`. Y **no son intervalos aritméticos**, son designaciones colectivas.
Expandir `E 338-452` como `range(338, 453)` inventaría 114 aditivos falsos e
incluiría el E 400 (ácido algínico) dentro de «fosfatos».

Tampoco se cablean de memoria: se **derivan del propio documento**. Miembro de
un rango es el aditivo de la Parte B cuyo número cae dentro y **cuyo nombre es
consistente con la denominación del rango** (subcadena común ≥ 6 caracteres,
quitando antes las palabras de relleno: «ácido», «sódico», «potásico»…).

    E 200-203  "Ácido sórbico y sorbatos"       -> E200 E202 E203   (E201 derogado)
    E 400-404  "Ácido algínico y alginatos"     -> E400 E401 ... E404
    E 338-452  "Ácido fosfórico, fosfatos..."   -> E338 E339 E340 E343 E450 ...
                                                   y NO el E400

## Auditoría de la derivación, con sus fallos declarados

Se revisaron los 25 rangos el 2026-08-14. La derivación es correcta para **los
cinco rangos que afectan a los 32 aditivos del snapshot** (E 200-203, E 210-213,
E 220-228, E 280-283, E 338-452), que es lo que fija el test del gate. Fuera de
ese alcance tiene tres fallos conocidos, y los tres se dejan a la vista:

- **Erratas del Diario Oficial.** `E 341` figura como «Fost*atos de calcio» y
  `E 355-228` tiene el inicio mayor que el fin. La derivación falla porque la
  fuente está mal, no el código. No se corrigen aquí: corregir en silencio el
  texto oficial es peor que no cubrirlo.
- **Siglas.** `E 310-320 "Galatos, TBHQ y BHA"` no recoge el E 319 ni el E 320
  porque en la Parte B se llaman «Terbutilhidroquinona (TBHQ)» y
  «Butilhidroxianisol (BHA)», y las siglas no llegan al umbral de 6 caracteres.
- **Familias sin raíz común.** `E 626-635 "Ribonucleótidos"` no recoge el
  «Ácido guanílico»; `E 551-559` no recoge el «Talco».

Los tres fallan **por defecto**, no por exceso: el aditivo sale `SIN_DATO` en vez
de salir autorizado sin serlo. Es el sentido correcto en el que equivocarse.
La única sobre-inclusión detectada es el `E 442` («Fosfátidos de amonio») dentro
de `E 338-452`, y por eso toda fila derivada de un rango viaja marcada con
`via="rango"`: quien la lea sabe que la cobertura es por designación colectiva.

## La limitación que hay que declarar: esto es la foto de 2011

`CELEX:32011R1129` es el reglamento que **rellenó** el Anexo II, no su versión
consolidada de hoy. Las modificaciones posteriores no están. Se nota, y está
medido: de los 32 aditivos del snapshot, 30 tienen uso aquí (93,8 %), y de los
dos que faltan uno es exactamente ese problema —los **glucósidos de esteviol
(E 960)**, que la UE autorizó con el Reglamento (UE) 1131/2011, meses después—.
El propio `acido1.pptx` cita el Reglamento (UE) 2018/98, que tampoco está.

No se disimula: un aditivo que no aparece sale `SIN_DATO`, nunca «no
autorizado». Distinguir «la UE lo prohíbe» de «nuestra copia es de 2011» es la
diferencia entre un dato y un error, y el segundo caso no puede disfrazarse del
primero. La vía de arreglo es ingerir la versión consolidada
(`CELEX:02008R1333-<fecha>`), que en la sonda del 2026-08-13 devolvía 404 en la
forma probada y hay que investigar aparte.
"""

from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import httpx
import lxml.html

logger = logging.getLogger(__name__)

CELEX = "32011R1129"
URL_FUENTE = (f"https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:{CELEX}")
URL_CITA = f"https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:{CELEX}"

RUTA_HTML = Path("data/ue/anexo_ii.html")
RUTA_JSON = Path("data/ue/anexo_ii.json")

CABECERAS = {
    "User-Agent": "CiteScout/1.0 (consulta regulatoria; codeplaigamessac@gmail.com)"
}
TIEMPO_ESPERA = 240.0

# Umbral de subcadena comun para dar por miembro de un rango a un aditivo.
#
# 6 y no menos: con 4 entrarian las siglas (TBHQ) pero tambien coincidencias
# tontas entre nombres quimicos que comparten sufijo ('-ato', '-ico'). Se
# prefiere quedarse corto —el aditivo sale SIN_DATO— a colar uno de mas.
UMBRAL_SUBCADENA = 6

# Palabras que no distinguen un aditivo de otro: casi todos los nombres del
# Anexo II las llevan, asi que dejarlas haria casar cualquier cosa con
# cualquier cosa ('acido citrico' con 'acido fosforico').
PALABRAS_VACIAS = {
    "acido", "acidos", "sodico", "sodicos", "sodio", "potasico", "potasicos",
    "potasio", "calcico", "calcicos", "calcio", "amonico", "amonio",
    "magnesico", "magnesio", "sal", "sales", "del", "las", "los", "que",
}

_ESPACIOS = re.compile(r"\s+")
_E_SIMPLE = re.compile(r"^E\s*(\d+[a-z]?)\s*(?:\([ivx]+\))?$", re.I)
_E_RANGO = re.compile(r"^E\s*(\d+)\s*-\s*(\d+)$", re.I)
_E_EN_TEXTO = re.compile(r"E\s*(\d+[a-z]?)", re.I)
_GRUPO = re.compile(r"^Grupo\s+([IVX]+)", re.I)


def _limpiar(elemento) -> str:
    return _ESPACIOS.sub(" ", (elemento.text_content() or "")).strip()


def _plegar(texto: str) -> str:
    """Minúsculas, sin tildes y sin puntuación. Para comparar nombres."""
    texto = texto.lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", " ", texto)


def _nucleo(nombre: str) -> list[str]:
    """Las palabras del nombre que de verdad lo distinguen."""
    return [p for p in _plegar(nombre).split()
            if len(p) >= 4 and p not in PALABRAS_VACIAS]


def _subcadena_comun(a: str, b: str) -> int:
    """Longitud de la subcadena común más larga. `a` corta, `b` larga."""
    mejor = 0
    for i in range(len(a)):
        for j in range(i + mejor + 1, len(a) + 1):
            if a[i:j] in b:
                mejor = j - i
            else:
                break
    return mejor


def _es_miembro(nombre_aditivo: str, denominacion_rango: str) -> bool:
    """¿El aditivo pertenece a la familia que nombra el rango?

    Se decide con el texto del propio documento, no con una tabla escrita de
    memoria. Ver la auditoría del docstring del módulo para lo que esto acierta
    y lo que no.
    """
    plegada = _plegar(denominacion_rango)
    return any(_subcadena_comun(p, plegada) >= UMBRAL_SUBCADENA
               for p in _nucleo(nombre_aditivo))


def _dosis(texto: str) -> tuple[float | None, str | None]:
    """El texto de la dosis a (valor, unidad).

    `quantum satis` es un límite real —«la cantidad necesaria, sin exceder»— y
    no un hueco: se devuelve como unidad 'BPM' con valor None, igual que el GRAS
    del CFR. Confundirlo con «sin dato» perdería una autorización.
    """
    limpio = texto.replace("\xa0", " ").strip()
    if not limpio:
        return None, None
    if "quantum satis" in limpio.lower():
        return None, "BPM"
    numero = re.match(r"^([\d][\d\s.,]*)$", limpio)
    if numero:
        try:
            return float(numero.group(1).replace(" ", "").replace(",", ".")), "mg/kg"
        except ValueError:
            return None, None
    return None, None


@dataclass(frozen=True)
class UsoUE:
    """Una fila de la Parte E: este aditivo, en esta categoría, así."""

    categoria: str            # "04.2.4.1"
    categoria_nombre: str
    entrada: str              # "E 200-203" | "E 330" | "Grupo I"
    denominacion: str
    dosis_texto: str
    dosis_valor: float | None
    dosis_unidad: str | None  # "mg/kg" | "BPM" | None
    notas: str
    restricciones: str        # la columna que decide. Ver docstring del módulo
    via: Literal["directo", "rango", "grupo"]

    #: La fila entera tal como se lee en el documento, con sus seis celdas
    #: separadas por espacios.
    #:
    #: Existe porque **una cita tiene que ser literal**, y sin esto no lo era.
    #: `EvaluadorUE` componía la cita como `f"{entrada} — {denominacion}:
    #: {dosis}"`, que produce `«E 440 — Pectinas: quantum satis»`: una cadena
    #: montada con puntuación propia que no aparece en ninguna parte del Anexo
    #: II. Lo detectó P-ADI-2 (T7.2) sobre una mermelada, y tenía razón: era un
    #: resumen con aspecto de cita. Aquí se guarda lo que el documento dice.
    texto_fila: str = ""

    @property
    def cita(self) -> str:
        return (f"Reglamento (CE) 1333/2008, Anexo II, categoría "
                f"{self.categoria.rstrip('.')}")


class CorpusAnexoII:
    """El Anexo II indexado por número E. Todo en memoria: consultar es O(1)."""

    def __init__(self, ruta: Path | str = RUTA_JSON):
        self.ruta = Path(ruta)
        if not self.ruta.exists():
            raise FileNotFoundError(
                f"No está el Anexo II en {self.ruta}. "
                f"Ejecuta `python -m etl.ingerir_anexo_ii`.")
        datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.celex: str = datos["celex"]
        self.ingerido_en: str = datos["ingerido_en"]
        self.categorias: dict[str, str] = datos["categorias"]
        self.nombres: dict[str, str] = datos.get("nombres", {})
        self._por_e: dict[str, list[UsoUE]] = {
            e: [UsoUE(**u) for u in usos] for e, usos in datos["usos"].items()}
        logger.info("Anexo II (%s): %d aditivos, %d categorías",
                    self.celex, len(self._por_e), len(self.categorias))

    def usos(self, e_number: str, categoria: str | None = None) -> list[UsoUE]:
        """Dónde se puede usar este aditivo. Filtrado por categoría si se da.

        La categoría casa por prefijo a propósito: quien pregunta por `04.2.4`
        quiere ver también lo de `04.2.4.1`, porque el árbol del Anexo II
        hereda hacia abajo y una autorización de la rama aplica a sus hojas.
        """
        clave = _normaliza_e(e_number)
        todos = self._por_e.get(clave, [])

        if not todos:
            # Aditivos con subletra: el snapshot lee «caramel color» y lo llama
            # E150, pero el Anexo II lo desglosa en E150a, E150b, E150c y E150d
            # —los cuatro caramelos, que se obtienen por procesos distintos—.
            # Buscar solo la forma sin letra dejaba fuera un aditivo que sí está
            # regulado. Lo mismo con E551/E553a-b.
            #
            # Se unen todas las variantes: la restricción y la dosis de cada una
            # viajan en su fila, así que quien lea la celda ve de cuál se trata.
            variantes = sorted(
                e for e in self._por_e
                if re.fullmatch(rf"{re.escape(clave)}[a-z]", e))
            todos = [u for e in variantes for u in self._por_e[e]]

        if categoria is None:
            return todos
        clave = categoria.rstrip(".")
        return [u for u in todos if u.categoria.rstrip(".").startswith(clave)]

    def nombre_de(self, e_number: str) -> str | None:
        """El nombre oficial del aditivo según la Parte B, o `None`.

        Sirve para titular la tarjeta de un aditivo que la etiqueta solo
        declara por código. `None` cuando el código no está en el Anexo II —lo
        que pasa con los que la UE no ha autorizado nunca—, y entonces quien
        llama enseña el código, que es lo que dice la etiqueta.
        """
        clave = _normaliza_e(e_number)
        if clave in self.nombres:
            return self.nombres[clave]
        # Variantes por letra: la etiqueta pone «E150» y el Anexo II desglosa
        # E150a-d. Se devuelve la primera, que da el nombre de familia.
        for variante in sorted(self.nombres):
            if re.fullmatch(rf"{re.escape(clave)}[a-z]", variante):
                return self.nombres[variante]
        return None

    def aditivos(self) -> list[str]:
        return sorted(self._por_e)

    def __len__(self) -> int:
        return sum(len(v) for v in self._por_e.values())


def _normaliza_e(e: str) -> str:
    """'E 200', 'e200', 'E200 (ii)' -> 'E200'."""
    m = _E_EN_TEXTO.search(e or "")
    return f"E{m.group(1).lower()}" if m else (e or "").strip().upper()


# -- Ingesta ---------------------------------------------------------------

# Tamaño mínimo creíble del documento. El real son 3,4 MB; cualquier cosa por
# debajo de esto es una página de error o de espera, no el Anexo II.
TAMANO_MINIMO = 1_000_000

# Cuántas veces se reintenta ante un 202, y cuánto se espera.
INTENTOS = 4
ESPERA_ENTRE_INTENTOS = 15.0


def descargar(destino: Path | str = RUTA_HTML, forzar: bool = False) -> Path:
    """Trae el Reglamento 1129/2011 de EUR-Lex (3,4 MB).

    ## Por qué esto valida el cuerpo antes de tocar el fichero de destino

    **EUR-Lex responde 202 cuando aún está generando el documento**, y el cuerpo
    llega vacío. `raise_for_status()` no salta —202 es 2xx— así que la primera
    versión escribía cero bytes y hacía `replace()` sobre el corpus bueno.
    Medido en carne propia el 2026-08-14: un `--forzar` dejó
    `anexo_ii.html` en 0 bytes y el parseo murió con «Document is empty».

    Un descargador que puede destruir el corpus que ya funcionaba es peor que no
    tener descargador: el fallo aparece cuando alguien quiere *actualizar*, que
    es justo cuando menos se espera perder lo que había.

    Ahora se reintenta ante el 202 y **no se reemplaza el destino hasta haber
    comprobado que lo descargado tiene tamaño creíble y contiene la Parte E**.
    """
    destino = Path(destino)
    if destino.exists() and destino.stat().st_size > TAMANO_MINIMO and not forzar:
        logger.info("Anexo II ya descargado en %s (%.1f MB)",
                    destino, destino.stat().st_size / 1e6)
        return destino

    destino.parent.mkdir(parents=True, exist_ok=True)
    parcial = destino.with_suffix(".parcial")

    for intento in range(1, INTENTOS + 1):
        logger.info("Descargando %s (intento %d/%d)...",
                    URL_FUENTE, intento, INTENTOS)
        with httpx.stream("GET", URL_FUENTE, headers=CABECERAS,
                          timeout=TIEMPO_ESPERA, follow_redirects=True) as r:
            r.raise_for_status()
            codigo = r.status_code
            with parcial.open("wb") as f:
                for trozo in r.iter_bytes(1 << 20):
                    f.write(trozo)

        tamano = parcial.stat().st_size
        if codigo == 202 or tamano < TAMANO_MINIMO:
            logger.warning(
                "EUR-Lex devolvió HTTP %d con %d bytes: aún está generando el "
                "documento. Se reintenta en %.0f s.", codigo, tamano,
                ESPERA_ENTRE_INTENTOS)
            parcial.unlink(missing_ok=True)
            if intento < INTENTOS:
                time.sleep(ESPERA_ENTRE_INTENTOS)
            continue

        # Última comprobación antes de pisar lo que había: que sea el documento
        # y no una página de error de 2 MB.
        cabeza = parcial.read_text(encoding="utf-8", errors="replace")[:400_000]
        if "PARTE E" not in cabeza and "PART E" not in cabeza:
            parcial.unlink(missing_ok=True)
            raise RuntimeError(
                f"Lo descargado ({tamano} bytes) no contiene la Parte E del "
                f"Anexo II. No se reemplaza {destino}.")

        parcial.replace(destino)
        logger.info("Anexo II descargado: %.1f MB", tamano / 1e6)
        return destino

    raise RuntimeError(
        f"EUR-Lex no entregó el documento tras {INTENTOS} intentos. "
        f"{destino} se ha dejado como estaba.")


def _partes(html: str) -> dict[str, str]:
    """El documento troceado por sus partes. Las de interés son B, C y E."""
    marcas = {}
    for letra in "ABCDE":
        i = html.find(f"PARTE {letra}")
        if i >= 0:
            marcas[letra] = i
    orden = sorted(marcas.items(), key=lambda kv: kv[1])
    trozos = {}
    for n, (letra, inicio) in enumerate(orden):
        fin = orden[n + 1][1] if n + 1 < len(orden) else len(html)
        trozos[letra] = html[inicio:fin]
    return trozos


def _parsear_parte_b(fragmento: str) -> dict[str, str]:
    """Nº E -> nombre oficial. 321 pares, y es la base de todo lo demás."""
    doc = lxml.html.fromstring(fragmento)
    pares: dict[str, str] = {}
    for fila in doc.xpath("//tr"):
        celdas = [_limpiar(c) for c in fila.xpath("./td")]
        if len(celdas) >= 2 and _E_SIMPLE.match(celdas[0]):
            pares.setdefault(_normaliza_e(celdas[0]), celdas[1])
    return pares


def _parsear_parte_c(fragmento: str) -> dict[str, list[str]]:
    """Grupo -> números E que lo componen.

    Los grupos importan para la cobertura: una categoría que admite «Grupo I»
    admite con ella un centenar de aditivos a *quantum satis*, y varios de los
    32 del snapshot (E 330, E 322, E 300, E 296…) solo aparecen por esta vía.
    """
    # Se recorre el DOM en orden, no se trocea el HTML por offsets.
    #
    # El troceado por offsets tenía un fallo silencioso y caro: la porción del
    # último grupo llegaba hasta el final del fragmento y se tragaba la sección
    # siguiente, «Otros aditivos que pueden regularse combinados», que lista
    # entre otros el E 200-203. Resultado: **el ácido sórbico salía como
    # miembro del Grupo IV (Polialcoholes)**, y con él heredaba la autorización
    # de los polialcoholes en 117 sitios. Un aditivo que no es un polialcohol
    # autorizado en todas las categorías que admiten polialcoholes.
    #
    # Se ignoran los <p> que viven dentro de una tabla: los encabezados de
    # grupo son párrafos de nivel superior, y un «Grupo I» dentro de una celda
    # es un dato, no una cabecera.
    doc = lxml.html.fromstring(fragmento)
    grupos: dict[str, list[str]] = {}
    actual: str | None = None

    for elemento in doc.xpath(
            "//p[not(ancestor::table)] | //table[not(ancestor::table)]"):
        if elemento.tag == "p":
            texto = _limpiar(elemento)
            # Las cabeceras van numeradas como lista: «1) Grupo I»,
            # «4) Grupo IV: Polialcoholes», «5) Otros aditivos que pueden
            # regularse». Anclar el patrón en «Grupo» no encuentra ninguna.
            cabecera = re.match(r"^(?:\d+\)\s*)?Grupo\s+([IVX]+)\b", texto, re.I)
            if cabecera:
                # `.title()` convertiría «Grupo II» en «Grupo Ii».
                actual = f"Grupo {cabecera.group(1).upper()}"
            elif re.match(r"^(?:\d+\)\s*)?otros aditivos", texto, re.I):
                # Fin de los grupos. Lo que viene después son designaciones
                # colectivas, que se resuelven por rango en la Parte E.
                actual = None
            continue

        if actual is None:
            continue
        for fila in elemento.xpath(".//tr"):
            celdas = [_limpiar(c) for c in fila.xpath("./td")]
            if celdas and _E_SIMPLE.match(celdas[0]):
                miembros = grupos.setdefault(actual, [])
                e = _normaliza_e(celdas[0])
                if e not in miembros:
                    miembros.append(e)

    return grupos


def _expandir(entrada: str, denominacion: str, parte_b: dict[str, str],
              grupos: dict[str, list[str]]) -> tuple[list[str], str]:
    """La celda «Nº E» a la lista de aditivos que cubre, y por qué vía."""
    entrada = entrada.strip()

    if _E_SIMPLE.match(entrada):
        return [_normaliza_e(entrada)], "directo"

    if _GRUPO.match(entrada):
        clave = next((g for g in grupos if _plegar(g) == _plegar(entrada[:8])), None)
        if clave is None:
            clave = next((g for g in grupos
                          if _plegar(entrada).startswith(_plegar(g))), None)
        return (grupos.get(clave, []), "grupo")

    rango = _E_RANGO.match(entrada)
    if rango:
        desde, hasta = int(rango.group(1)), int(rango.group(2))
        if desde > hasta:
            # Errata del Diario Oficial (E 355-228). No se adivina el fin.
            return [], "rango"
        miembros = [
            e for e, nombre in parte_b.items()
            if (num := re.match(r"E(\d+)", e))
            and desde <= int(num.group(1)) <= hasta
            and _es_miembro(nombre, denominacion)
        ]
        return miembros, "rango"

    # 'E 200-203, 214 - 219' y demás listas: se recogen los números sueltos que
    # aparezcan y los rangos internos se pierden. Son 2 filas de 2.177.
    sueltos = [_normaliza_e(m.group(0)) for m in _E_EN_TEXTO.finditer(entrada)]
    return (sueltos, "rango") if sueltos else ([], "directo")


def parsear(html: str) -> dict:
    """El Anexo II entero a la estructura que se guarda en JSON."""
    partes = _partes(html)
    parte_b = _parsear_parte_b(partes.get("B", ""))
    grupos = _parsear_parte_c(partes.get("C", ""))
    logger.info("Parte B: %d aditivos · Parte C: %s",
                len(parte_b),
                ", ".join(f"{g} ({len(m)})" for g, m in grupos.items()) or "sin grupos")

    doc = lxml.html.fromstring(partes.get("E", ""))
    categorias: dict[str, str] = {}
    usos: dict[str, list[dict]] = {}
    categoria = nombre_categoria = None
    filas_uso = sin_expandir = 0

    for fila in doc.xpath("//tr"):
        celdas = fila.xpath("./td")
        textos = [_limpiar(c) for c in celdas]

        # Cabecera de categoría: nº con rowspan + nombre con colspan.
        if len(celdas) == 2 and celdas[0].get("rowspan"):
            categoria, nombre_categoria = textos[0], textos[1]
            categorias[categoria.rstrip(".")] = nombre_categoria
            continue

        if len(celdas) != 5 or categoria is None:
            continue

        entrada, denominacion, dosis_txt, notas, restricciones = textos
        if not entrada:
            continue
        filas_uso += 1

        miembros, via = _expandir(entrada, denominacion, parte_b, grupos)
        if not miembros:
            sin_expandir += 1
            continue

        valor, unidad = _dosis(dosis_txt)
        for e in miembros:
            usos.setdefault(e, []).append(asdict(UsoUE(
                categoria=categoria, categoria_nombre=nombre_categoria,
                entrada=entrada, denominacion=denominacion,
                dosis_texto=dosis_txt, dosis_valor=valor, dosis_unidad=unidad,
                notas=notas, restricciones=restricciones, via=via,
                texto_fila=_limpiar(fila))))

    return {
        "celex": CELEX,
        "url": URL_CITA,
        "ingerido_en": __import__("datetime").date.today().isoformat(),
        "categorias": categorias,
        "grupos": grupos,
        # La Parte B entera, 321 pares número→nombre oficial.
        #
        # Se parseaba ya —hace falta para derivar los rangos— y se tiraba al
        # terminar. Se guarda porque es lo único que permite ponerle nombre a un
        # aditivo que la etiqueta declara **solo por código**: una galleta
        # peruana pone «Leudante sin 500(ii)» y sin esto la tarjeta se titularía
        # «E500». El nombre sale del documento oficial, no de una tabla escrita
        # a mano.
        "nombres": parte_b,
        "usos": usos,
        "resumen": {
            "filas_parte_e": filas_uso,
            "filas_sin_expandir": sin_expandir,
            "aditivos_parte_b": len(parte_b),
            "aditivos_con_uso": len(usos),
            "categorias": len(categorias),
        },
    }


_corpus: CorpusAnexoII | None = None


def corpus(ruta: Path | str = RUTA_JSON) -> CorpusAnexoII:
    global _corpus
    if _corpus is None:
        _corpus = CorpusAnexoII(ruta)
    return _corpus


def _reset_corpus() -> None:
    global _corpus
    _corpus = None
