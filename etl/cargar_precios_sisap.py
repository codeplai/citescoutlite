"""
Precios mayoristas de materia prima (MIDAGRI · SISAP).

Descarga los boletines diarios de abastecimiento y precios que MIDAGRI publica
en gob.pe y extrae los precios de los insumos piloto a un snapshot fechado, con
el mismo trato que el resto de datos del proyecto: se descarga una vez, se
versiona y se lee sin red.

**Por qué el boletín y no el sistema SISAP.** La consulta interactiva de SISAP
(`sistemas.midagri.gob.pe/sisap/portal2/`) es JavaScript de arriba abajo: la
consulta va por AJAX con un `postID` de sesión y la exportación a Excel manda un
`datos_a_enviar` que construye el navegador. No hay ningún GET ni POST que
devuelva datos sin replicar ese JS. El boletín publicado trae **los mismos
precios**, en PDF, en URL directa del CDN del Estado y sin sesión.

**Lo que este módulo NO es.** El precio de aquí es el de la **materia prima** en
el mercado mayorista de Lima —palta a S/ 3,85 el kilo—, no el del producto
terminado de la competencia en góndola. Son dos preguntas distintas y mezclarlas
sería el peor malentendido posible: `ProductoEnMercado.precio_rango` sigue vacío
y sigue siendo el hueco declarado del §R2 del plan.

Uso:
    uv run python -m etl.cargar_precios_sisap            # los meses configurados
    uv run python -m etl.cargar_precios_sisap --todos    # todos los días del mes
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

import pdfplumber
import requests

SALIDA = Path("datasets/precios-sisap")

# gob.pe rechaza a los clientes que no parecen navegador (HTTP 418).
NAVEGADOR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "es-PE,es;q=0.9",
}

# La extraccion normal de pdfplumber devuelve basura en las paginas de tabla
# ('CN PA', '011', '01122'...). Con estrategia por texto sale limpia.
CFG_TABLA = {"vertical_strategy": "text", "horizontal_strategy": "text"}

# Los identificadores de publicacion de gob.pe no son predecibles: cada mes
# recibe uno nuevo. Se listan a mano, que es lo honesto para un snapshot; anadir
# un mes es anadir una linea.
BOLETINES: dict[str, str] = {
    "2026-07": "https://www.gob.pe/institucion/midagri/informes-publicaciones/8319966-boletin-de-abastecimiento-y-precios-mayoristas-en-el-mercado-mayorista-de-lima-gmml-y-mercado-de-frutas-n-2-mm-n-2-julio-2026",
    "2026-05": "https://www.gob.pe/institucion/midagri/informes-publicaciones/8083199-boletin-de-abastecimiento-y-precios-mayoristas-en-el-mercado-mayorista-de-lima-gmml-y-mercado-de-frutas-n-2-mm-n-2-mayo-2026",
    "2026-04": "https://www.gob.pe/institucion/midagri/informes-publicaciones/7958973-boletin-de-abastecimiento-y-precios-mayoristas-en-el-mercado-mayorista-de-lima-gmml-y-mercado-de-frutas-n-2-mm-n-2-abril-2026",
}

# Insumos piloto y como aparecen escritos en el boletin.
INSUMOS: dict[str, tuple[str, ...]] = {
    "palta": ("palta",),
    "espárrago": ("esparrago",),
    "mango": ("mango",),
    "quinua": ("quinua",),
    "arándano": ("arandano",),
}

MERCADOS = {
    "GMML": "Gran Mercado Mayorista de Lima",
    "MMF2": "Mercado Mayorista de Frutas Nº 2",
}

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12}

_FECHA = re.compile(r"Lima,\s*(\d{1,2})\s+de\s+(\w+)\s+del?\s+(\d{4})", re.I)
_PRECIO = re.compile(r"^\d+([.,]\d{1,2})?$")
_CNPA = re.compile(r"^\d{3,5}$")


def _plegar(texto: str) -> str:
    texto = re.sub(r"\s+", " ", texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def _numero(celda: str) -> float | None:
    """`'3.85'` -> 3.85. Nunca inventa: lo que no es número es None."""
    celda = (celda or "").strip().replace(",", ".")
    if not _PRECIO.fullmatch(celda):
        return None
    try:
        valor = float(celda)
    except ValueError:
        return None
    # Un 0 en un precio es "no se registró", no "vale cero soles".
    return valor if valor > 0 else None


def fecha_del_boletin(pdf) -> date | None:
    """La fecha va en la cabecera: 'Lima, 24 de julio del 2026'."""
    texto = pdf.pages[0].extract_text() or ""
    m = _FECHA.search(texto)
    if not m:
        return None
    dia, mes, anio = m.group(1), _plegar(m.group(2)), m.group(3)
    if mes not in MESES:
        return None
    try:
        return date(int(anio), MESES[mes], int(dia))
    except ValueError:
        return None


def filas_de_precio(pdf) -> list[list[str]]:
    filas = []
    for pagina in pdf.pages:
        for tabla in pagina.extract_tables(CFG_TABLA):
            for fila in tabla:
                filas.append([re.sub(r"\s+", " ", str(c or "")).strip()
                              for c in fila])
    return filas


def interpretar(fila: list[str]) -> dict | None:
    """Una fila de la tabla -> registro de precio, o None si no lo es.

    La forma es: CNPA · nombre · mercado · promedio semana anterior ·
    promedio semana · variación % · serie diaria. El nombre puede venir partido
    en varias celdas porque la extracción por texto corta por columnas visuales.
    """
    utiles = [c for c in fila if c]
    if len(utiles) < 5 or not _CNPA.fullmatch(utiles[0]):
        return None

    mercado = next((c for c in utiles if c.replace(" ", "").upper() in MERCADOS), None)
    if mercado is None:
        return None
    mercado = mercado.replace(" ", "").upper()

    # El nombre es lo que hay entre el código y el mercado.
    corte = utiles.index(next(c for c in utiles
                              if c.replace(" ", "").upper() == mercado))
    nombre = " ".join(utiles[1:corte]).strip()
    if not nombre:
        return None

    numeros = [_numero(c) for c in utiles[corte + 1:]]
    numeros = [n for n in numeros if n is not None]
    if len(numeros) < 2:
        return None

    variacion = next((c for c in utiles[corte + 1:] if c.endswith("%")), None)
    if variacion:
        try:
            variacion = float(variacion.rstrip("%").replace(",", "."))
        except ValueError:
            variacion = None

    return {
        "codigo_cnpa": utiles[0],
        "producto": nombre,
        "mercado": mercado,
        "mercado_nombre": MERCADOS[mercado],
        # El boletín ordena: promedio de la semana anterior, luego el de esta.
        "precio_semana_anterior": numeros[0],
        "precio_soles_kg": numeros[1],
        "variacion_pct": variacion,
    }


def _posiciones_de_espacio(nombre: str) -> set[int]:
    """Dónde caen los espacios, contando sobre el nombre ya sin espacios."""
    posiciones, i = set(), 0
    for caracter in nombre:
        if caracter == " ":
            posiciones.add(i)
        else:
            i += 1
    return posiciones


def unificar_nombres(registros: list[dict]) -> None:
    """Arregla los espacios que mete la extracción por columnas del PDF.

    El mismo producto sale como `PALTA LINDA (COSTA/SE LVA)` un día y
    `PALTA LINDA (CO STA/SELVA)` otro: el corte por columnas parte palabras, y
    parte por sitios distintos según dónde caiga la maquetación de ese boletín.
    Sin arreglarlo, un producto tiene tantos nombres como días y no se agrupa.

    La reconstrucción se apoya en dos hechos del artefacto y no en adivinar:

    1. **Solo añade espacios, nunca los quita.** Así que quitándolos todos se
       obtiene la identidad del producto, y todas las grafías de un mismo
       producto colapsan a la misma clave.
    2. **Parte por sitios distintos en boletines distintos.** Así que un espacio
       que aparece en *todas* las muestras es de verdad, y uno que falta en
       alguna es del corte.

    Se conservan los espacios en los que **todas** las variantes coinciden. Con
    una sola muestra la intersección es ella misma y el nombre queda como venía:
    degrada a no tocar nada, nunca a inventar una palabra.
    """
    variantes: dict[str, list[str]] = {}
    for r in registros:
        variantes.setdefault(r["producto"].replace(" ", "").upper(), []).append(
            r["producto"])

    canonico: dict[str, str] = {}
    for clave, nombres in variantes.items():
        comunes = set.intersection(*(_posiciones_de_espacio(n) for n in nombres))
        sin_espacios = nombres[0].replace(" ", "")
        reconstruido = "".join(
            (" " if i in comunes else "") + caracter
            for i, caracter in enumerate(sin_espacios))
        canonico[clave] = reconstruido.strip()

    for r in registros:
        r["producto"] = canonico[r["producto"].replace(" ", "").upper()]


def insumo_de(nombre: str) -> str | None:
    plegado = _plegar(nombre)
    for insumo, patrones in INSUMOS.items():
        if any(p in plegado for p in patrones):
            return insumo
    return None


def descargar_mes(sesion: requests.Session, mes: str, url: str,
                  todos: bool) -> list[dict]:
    r = sesion.get(url, headers=NAVEGADOR, timeout=90)
    if r.status_code != 200:
        print(f"[{mes}] la página del boletín devolvió HTTP {r.status_code}")
        return []

    pdfs = sorted(set(re.findall(r'href="(https://cdn\.www\.gob\.pe/[^"]+)"', r.text)))
    if not pdfs:
        print(f"[{mes}] sin PDFs en la página")
        return []

    # Tres boletines por mes —principio, medio y fin—, no uno.
    #
    # No es por la serie de precios, que con uno bastaría: es porque el corte por
    # columnas del PDF parte los nombres por sitios distintos según el día
    # ("PALTA LINDA (COSTA/SE LVA)"). Con varias muestras aparece la grafía
    # entera y `unificar_nombres` la elige. Arreglarlo con más datos es más
    # honesto que adivinar dónde iba el espacio.
    #
    # Tres y no los 19 del mes: bajar sesenta PDF de un servidor público para
    # ganar decimales es maltratarlo sin necesidad.
    elegidos = pdfs if todos else sorted({pdfs[0], pdfs[len(pdfs) // 2], pdfs[-1]})
    print(f"[{mes}] {len(pdfs)} boletines diarios · se leen {len(elegidos)}")

    SALIDA.mkdir(parents=True, exist_ok=True)
    registros = []
    for enlace in elegidos:
        d = sesion.get(enlace, headers=NAVEGADOR, timeout=180)
        if d.status_code != 200 or d.content[:4] != b"%PDF":
            print(f"[{mes}] descarga fallida: HTTP {d.status_code}")
            continue

        ruta = SALIDA / f"boletin-{mes}-{hashlib.sha256(enlace.encode()).hexdigest()[:8]}.pdf"
        ruta.write_bytes(d.content)

        with pdfplumber.open(ruta) as pdf:
            fecha = fecha_del_boletin(pdf)
            for fila in filas_de_precio(pdf):
                registro = interpretar(fila)
                if registro is None:
                    continue
                insumo = insumo_de(registro["producto"])
                if insumo is None:
                    continue
                registro |= {
                    "insumo": insumo,
                    "fecha": fecha.isoformat() if fecha else None,
                    "fuente": "MIDAGRI · SISAP",
                    "url_boletin": enlace,
                    "sha256_pdf": hashlib.sha256(d.content).hexdigest(),
                }
                registros.append(registro)
        print(f"[{mes}] {ruta.name}: {fecha} · "
              f"{sum(1 for x in registros if x['url_boletin'] == enlace)} precios")
    return registros


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--todos", action="store_true",
                    help="Leer todos los boletines del mes, no solo el último")
    args = ap.parse_args()

    sesion = requests.Session()
    registros: list[dict] = []
    for mes, url in sorted(BOLETINES.items()):
        registros += descargar_mes(sesion, mes, url, args.todos)

    unificar_nombres(registros)
    encontrados = sorted({r["insumo"] for r in registros})
    sin_dato = [i for i in INSUMOS if i not in encontrados]

    manifiesto = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "fuente": "MIDAGRI · Boletín de Abastecimiento y Precios Mayoristas "
                  "(GMML y MM Nº2), publicado en gob.pe",
        "unidad": "S/ por kilogramo",
        "alcance": "precio de MATERIA PRIMA en mercado mayorista de Lima; no es "
                   "el precio de góndola del producto terminado",
        "meses": sorted(BOLETINES),
        "insumos_con_precio": encontrados,
        "insumos_sin_precio": sin_dato,
        "registros": registros,
    }

    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / "precios.json"
    destino.write_text(json.dumps(manifiesto, indent=2, ensure_ascii=False),
                       encoding="utf-8")

    print(f"\n[PRECIOS] {len(registros)} registros · con precio: {encontrados}")
    print(f"[PRECIOS] sin precio: {sin_dato}")
    print(f"[PRECIOS] -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
