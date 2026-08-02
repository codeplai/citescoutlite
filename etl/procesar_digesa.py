"""
TIER 6 · T6.2: Corpus regulatorio DIGESA (Perú).

Descarga PDFs normativos publicados por DIGESA y extrae su texto.

Tres problemas reales de esta fuente, y cómo se tratan aquí:

1. **Muchos PDFs son escaneos sin capa de texto.** No se hace OCR y no se
   inventa contenido: si un documento extrae 0 palabras se descarta y queda
   registrado en el log y en el reporte de salida.

2. **Los separados de El Peruano vienen a dos columnas.** Extraer la página
   entera intercala ambas columnas línea por línea y produce texto incoherente
   (embeddings basura). Se detecta el canal central vacío y se recorta cada
   columna por separado.

3. **Una página de El Peruano mezcla normas de varios sectores.** Se filtran
   los pasajes por vocabulario sanitario/alimentario para no indexar, por
   ejemplo, designaciones de funcionarios de PRODUCE.

Salida: datasets/2026-07/digesa_normas.json
"""
import io
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

from etl.troceo import trocear

BASE = "http://www.digesa.minsa.gob.pe/"
UA = {"User-Agent": "Mozilla/5.0 (AgroScout-MVP)"}
SALIDA = "datasets/2026-07/digesa_normas.json"

# Documentos normativos/orientativos de alcance alimentario publicados por
# DIGESA. La lista es curada a propósito: el sitio tiene ~80 PDFs, la mayoría
# comunicados administrativos sin contenido normativo aprovechable.
DOCUMENTOS = [
    ("RM_865-2020-MINSA", "Resolución Ministerial N° 865-2020-MINSA",
     "noticias/Octubre2020/RM_865-2020-MINSA.pdf"),
    ("RM_854-2020-MINSA", "Resolución Ministerial N° 854-2020-MINSA",
     "noticias/Octubre2020/RM-854-2020-MINSA.pdf"),
    ("RD_043-2017-DIGESA", "Resolución Directoral N° 043-2017-DIGESA-SA",
     "NormasLegales/Normas/RD_N_043-2017-DIGESA-SA.pdf"),
    ("DS_010-2014-SA", "Decreto Supremo N° 010-2014-SA",
     "NormasLegales/Normas/DS_010-2014-SA.PDF"),
    ("RD_192-2017-DIGESA", "Resolución Directoral N° 192-2017-DIGESA-SA",
     "Orientacion/RESOLUCION_DIRECTORAL_192-2017-DIGESA-SA.pdf"),
    ("DIRECTIVA_87-2020", "Directiva Sanitaria N° 87-2020-DIGESA-MINSA",
     "Orientacion/CARTILLA_DIRECTIVA_SANITARIA_87-2020-DIGESA-MINSA.pdf"),
    ("GUIA_ALIMENTOS", "Guía didáctica de inocuidad de alimentos",
     "Orientacion/GUIA-DIDACTICA-ALIMENTOS.pdf"),
    ("CRITERIOS_TECNICOS", "Informe de criterios técnicos sanitarios",
     "orientacion/Informe_criterios_tecnicos_C.pdf"),
    ("ART_SIN_AUTORIZACION", "Artículos que no requieren autorización sanitaria",
     "DEPA/juguetes_utiles/pdf/Articulos_que_no_requieren_autorizacion_sanitaria.pdf"),
    ("DECALOGO_ALIMENTOS", "Decálogo de inocuidad alimentaria",
     "orientacion/decalogo_alimentos.pdf"),
]

# Vocabulario sanitario/alimentario. Un pasaje debe tocar al menos uno.
TERMINOS = (
    "aliment", "sanitari", "inocuidad", "digesa", "aditiv", "higien", "higién",
    "registro sanitario", "haccp", "microbiolog", "plaguicid", "rotulad",
    "etiquetad", "insumo", "contaminan", "salud", "bebida", "fabricaci",
    "almacenamiento", "manipulaci", "vigilancia", "codex", "límite máximo",
    "limite maximo", "residuo", "envasad", "producto",
)

MIN_PALABRAS_PASAJE = 40


def _descargar(url: str, timeout: int = 60) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout
    ).read()


def _detectar_canal(pagina) -> float | None:
    """
    Localiza el canal vertical vacío del maquetado a dos columnas.

    Devuelve la coordenada x del canal, o None si la página es de una columna.

    Se analiza solo el cuerpo: la cabecera de El Peruano ("NORMAS LEGALES") y el
    pie cruzan la página entera, así que llenan la banda central y esconden el
    canal. Tampoco se asume que el canal esté en width/2: en estos PDFs aparece
    entre x=235 y x=244 según la página.
    """
    cuerpo = [c for c in pagina.chars
              if pagina.height * 0.10 < c["top"] < pagina.height * 0.93]
    if len(cuerpo) < 50:
        return None

    N_BANDAS = 50
    ocupadas = {int(c["x0"] / pagina.width * N_BANDAS) for c in cuerpo}
    # Banda vacía dentro del 30% central de la página.
    centrales = [b for b in range(int(N_BANDAS * 0.36), int(N_BANDAS * 0.65) + 1)
                 if b not in ocupadas]
    if not centrales:
        return None

    return (sum(centrales) / len(centrales) + 0.5) / N_BANDAS * pagina.width


def extraer_texto(raw: bytes) -> tuple[str, int]:
    """Extrae texto respetando columnas. Devuelve (texto, n_paginas)."""
    import pdfplumber

    partes = []
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        n_paginas = len(pdf.pages)
        for pagina in pdf.pages:
            canal = _detectar_canal(pagina)
            if canal is not None:
                cajas = [(0, 0, canal, pagina.height),
                         (canal, 0, pagina.width, pagina.height)]
            else:
                cajas = [(0, 0, pagina.width, pagina.height)]

            for caja in cajas:
                txt = pagina.crop(caja).extract_text() or ""
                if txt.strip():
                    partes.append(txt)

    return "\n".join(partes), n_paginas


def _es_relevante(pasaje: str) -> bool:
    if len(pasaje.split()) < MIN_PALABRAS_PASAJE:
        return False
    bajo = pasaje.lower()
    return any(t in bajo for t in TERMINOS)


def main(salida: str = SALIDA) -> int:
    documentos = []
    reporte = []

    for doc_id, titulo, ruta in DOCUMENTOS:
        url = BASE + ruta.replace(" ", "%20")
        try:
            raw = _descargar(url)
            texto, n_paginas = extraer_texto(raw)
            n_palabras = len(texto.split())

            if n_palabras == 0:
                print(f"[DIGESA] {doc_id}: ESCANEADO sin capa de texto "
                      f"({n_paginas} pág.) -> descartado (no se hace OCR)")
                reporte.append({"id": doc_id, "estado": "escaneado_sin_texto",
                                "paginas": n_paginas, "url": url})
                continue

            pasajes = [p for p in trocear(texto) if _es_relevante(p)]
            for i, pasaje in enumerate(pasajes):
                documentos.append({
                    "id": f"DIGESA:{doc_id}#{i}",
                    "titulo": titulo,
                    "texto": pasaje,
                    "cita": titulo,
                    "fuente": "DIGESA (Perú)",
                    "fuente_url": url,
                    "fecha_publicacion": None,  # el PDF no la expone de forma fiable
                    "tipo": "DIGESA",
                })

            palabras_utiles = sum(len(p.split()) for p in pasajes)
            print(f"[DIGESA] {doc_id}: {n_paginas} pág., {n_palabras} palabras "
                  f"-> {len(pasajes)} pasajes relevantes ({palabras_utiles} palabras)")
            reporte.append({"id": doc_id, "estado": "ok", "paginas": n_paginas,
                            "palabras_extraidas": n_palabras,
                            "pasajes": len(pasajes),
                            "palabras_utiles": palabras_utiles, "url": url})

        except Exception as e:
            print(f"[DIGESA] {doc_id}: ERROR {type(e).__name__}: {str(e)[:90]}")
            reporte.append({"id": doc_id, "estado": f"error_{type(e).__name__}",
                            "url": url})

        time.sleep(1)  # el servidor devuelve 403 si se le pide muy seguido

    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(documentos, f, ensure_ascii=False, indent=2)
    with open(salida.replace(".json", "_reporte.json"), "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)

    total = sum(len(d["texto"].split()) for d in documentos)
    print(f"\n[DIGESA] {len(documentos)} pasajes, {total:,} palabras -> {salida}")
    print(f"[DIGESA] Gate T6.2 (>=2000 palabras): "
          f"{'PASA' if total >= 2000 else f'FALLA ({total})'}")
    return 0 if total >= 2000 else 1


if __name__ == "__main__":
    sys.exit(main())
