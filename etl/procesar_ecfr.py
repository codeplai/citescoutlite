"""
TIER 6 · T6.1: Corpus regulatorio eCFR (FDA, Title 21).

Descarga y normaliza del Title 21:
  - Part 182: Substances Generally Recognized As Safe
  - Part 184: Direct Food Substances Affirmed As GRAS
  - Part 145: Canned Fruits
  - Part 146: Canned Fruit Juices
  - Part 150: Fruit Butters, Jellies, Preserves and Related Products

Las partes 145/146/150 se incluyen porque 182/184 son catálogos de aditivos
químicos: no contienen nada sobre frutas concretas, y consultarlas por los
insumos piloto (arándano, mango, palta) daba similitud negativa. Las normas de
producto procesado sí son el marco regulatorio que aplica a esos insumos.

NOTA SOBRE EL ENDPOINT: el plan (PLAN-TIERS-S2.md §T6.1) propone
`https://www.ecfr.gov/api/renderer/versions/title-21/part-182/full.json`,
que devuelve **404**. El API real es el `versioner`, que entrega XML:
  https://www.ecfr.gov/api/versioner/v1/full/{fecha}/title-21.xml?part={parte}

La fecha se resuelve contra /api/versioner/v1/titles.json (latest_issue_date),
de modo que el corpus queda fechado con la vigencia oficial, no con la fecha
de descarga.

Salida: datasets/2026-07/ecfr_aditivos.json
"""
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from etl.troceo import trocear

API = "https://www.ecfr.gov/api/versioner/v1"
UA = {"User-Agent": "AgroScout-MVP/0.1 (CITE agroindustrial; ETL S2 TIER6)"}
PARTES = ["182", "184", "145", "146", "150"]
SALIDA = "datasets/2026-07/ecfr_aditivos.json"


def _get(url: str, timeout: int = 90) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout
    ).read()


def fecha_vigencia(titulo: int = 21) -> str:
    """Última fecha de emisión oficial del título (no la fecha de descarga)."""
    datos = json.loads(_get(f"{API}/titles.json", timeout=30))
    for t in datos["titles"]:
        if t["number"] == titulo:
            return t["latest_issue_date"]
    raise RuntimeError(f"Title {titulo} no encontrado en titles.json")


def _texto_seccion(div8: ET.Element) -> str:
    """
    Aplana una sección: párrafos + filas de tabla.

    Las tablas de la Part 182 son la parte sustantiva (pares nombre común /
    nombre botánico de cada sustancia GRAS); ignorarlas dejaría secciones con
    solo la frase introductoria.
    """
    partes = []
    for p in div8.iter("P"):
        txt = " ".join(p.itertext()).strip()
        if txt:
            partes.append(re.sub(r"\s+", " ", txt))

    for fila in div8.iter("TR"):
        celdas = [" ".join(td.itertext()).strip() for td in fila.iter("TD")]
        celdas = [re.sub(r"\s+", " ", c) for c in celdas if c.strip()]
        if celdas:
            partes.append(" — ".join(celdas))

    return "\n".join(partes)


def procesar_parte(parte: str, fecha: str) -> list[dict]:
    url = f"{API}/full/{fecha}/title-21.xml?part={parte}"
    print(f"[eCFR] Descargando Part {parte} ({fecha})...")
    raw = _get(url)
    print(f"[eCFR]   {len(raw):,} bytes")

    raiz = ET.fromstring(raw)
    documentos = []
    secciones = 0

    for div8 in raiz.iter("DIV8"):
        num = div8.attrib.get("N", "")
        cabecera = div8.find("HEAD")
        titulo = " ".join(cabecera.itertext()).strip() if cabecera is not None else ""
        # El HEAD trae el símbolo de sección y el número; sobra en el título.
        titulo = re.sub(r"^[§§\s]*[\d.]+\s*", "", titulo).strip()

        texto = _texto_seccion(div8)
        if len(texto.split()) < 10:
            continue  # secciones reservadas o vacías

        # Una sección puede pasar de 1000 palabras; se trocea para que la
        # similitud no se diluya frente a consultas de pocas palabras.
        pasajes = trocear(texto)
        for i, pasaje in enumerate(pasajes):
            documentos.append({
                "id": f"eCFR:{num}#{i}" if len(pasajes) > 1 else f"eCFR:{num}",
                "titulo": titulo,
                "texto": pasaje,
                "cita": f"21 CFR {num}",
                "fuente": "eCFR (FDA, EE.UU.)",
                "fuente_url": f"https://www.ecfr.gov/current/title-21/section-{num}",
                "fecha_publicacion": fecha,
                "tipo": "eCFR",
            })
        secciones += 1

    print(f"[eCFR]   Part {parte}: {secciones} secciones -> {len(documentos)} pasajes")
    return documentos


def main(salida: str = SALIDA) -> int:
    fecha = fecha_vigencia()
    print(f"[eCFR] Vigencia oficial Title 21: {fecha}")

    documentos = []
    for parte in PARTES:
        try:
            documentos.extend(procesar_parte(parte, fecha))
        except Exception as e:
            # Una parte caída no debe tumbar el corpus completo.
            print(f"[eCFR] ERROR en Part {parte}: {type(e).__name__}: {e}")

    if not documentos:
        print("[eCFR] FALLO: no se obtuvo ningún documento.")
        return 1

    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(documentos, f, ensure_ascii=False, indent=2)

    palabras = sum(len(d["texto"].split()) for d in documentos)
    print(f"[eCFR] OK: {len(documentos)} documentos, {palabras:,} palabras -> {salida}")
    print(f"[eCFR] Gate T6.1 (>=5 documentos): "
          f"{'PASA' if len(documentos) >= 5 else 'FALLA'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
