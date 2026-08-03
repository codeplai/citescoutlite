#!/usr/bin/env python
"""
Catálogo de productos con precio mayorista disponible (MIDAGRI · SISAP).

Lee los boletines ya descargados en `datasets/precios-sisap/` y escribe
`COBERTURA-PRECIOS-MIDAGRI.md` con **todos** los productos que aparecen, no solo
los cinco insumos piloto. Responde a una pregunta concreta: si mañana el CITE
quiere trabajar otro insumo, ¿tendría precio de materia prima o no?

No descarga nada: opera sobre el snapshot. Para actualizarlo primero:
    uv run python -m etl.cargar_precios_sisap

Uso:
    uv run python scripts/cobertura_precios.py
"""

import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pdfplumber

from etl.cargar_precios_sisap import (CFG_TABLA, MERCADOS, SALIDA,
                                      fecha_del_boletin, filas_de_precio,
                                      insumo_de, interpretar, unificar_nombres)

DESTINO = Path("COBERTURA-PRECIOS-MIDAGRI.md")

# Familias por el prefijo del código CNPA, para que la lista se lea por grupos y
# no como 152 nombres seguidos.
#
# Los prefijos están comprobados contra los productos que trae el boletín, no
# supuestos: una primera versión puso 015 en "legumbres" y mandó toda la papa
# —el producto de mayor volumen del mercado, 2.467 t diarias— a la familia
# equivocada.
GRUPOS = {
    "011": "Cereales",
    "012": "Hortalizas",
    "013": "Frutas",
    "014": "Frutos oleaginosos",
    "015": "Raíces y tubérculos",
    "016": "Especias y aromáticas",
    "019": "Otros cultivos",
}


def grupo_de(codigo: str) -> str:
    for prefijo, nombre in GRUPOS.items():
        if codigo.startswith(prefijo):
            return nombre
    return "Otros"


def recolectar() -> list[dict]:
    registros = []
    for pdf_path in sorted(SALIDA.glob("boletin-*.pdf")):
        with pdfplumber.open(pdf_path) as pdf:
            fecha = fecha_del_boletin(pdf)
            for fila in filas_de_precio(pdf):
                r = interpretar(fila)
                if r is None:
                    continue
                r["fecha"] = fecha
                r["archivo"] = pdf_path.name
                registros.append(r)
    unificar_nombres(registros)
    return registros


def main() -> int:
    if not SALIDA.exists():
        print(f"[COBERTURA] No existe {SALIDA}. Correr primero "
              f"`uv run python -m etl.cargar_precios_sisap`")
        return 1

    registros = recolectar()
    if not registros:
        print("[COBERTURA] Ningún boletín legible en el snapshot")
        return 1

    # La observación más reciente de cada producto y mercado.
    ultimo: dict[tuple[str, str], dict] = {}
    for r in registros:
        clave = (r["producto"], r["mercado"])
        if clave not in ultimo or (r["fecha"] and ultimo[clave]["fecha"]
                                   and r["fecha"] > ultimo[clave]["fecha"]):
            ultimo[clave] = r

    por_grupo: dict[str, list[dict]] = defaultdict(list)
    for r in ultimo.values():
        por_grupo[grupo_de(r["codigo_cnpa"])].append(r)

    fechas = sorted({r["fecha"] for r in registros if r["fecha"]})
    piloto = {i for r in ultimo.values() if (i := insumo_de(r["producto"]))}

    lineas = [
        "# Cobertura de precio de materia prima · MIDAGRI (SISAP)",
        "",
        f"**Generado:** {datetime.now().date().isoformat()} · "
        f"por `scripts/cobertura_precios.py`",
        "",
        "Productos para los que **hoy podríamos dar precio de materia prima** en "
        "el informe, leídos de los boletines diarios de abastecimiento y precios "
        "que MIDAGRI publica en gob.pe.",
        "",
        "> **Qué es este precio.** El del insumo a granel en el mercado mayorista "
        "de Lima, en soles por kilogramo. Es con lo que se costea una "
        "formulación. **No** es el precio en góndola de un producto terminado de "
        "marca, que no tenemos para ningún producto.",
        "",
        "## Resumen",
        "",
        f"| | |",
        f"|---|---|",
        f"| Productos con precio | **{len(ultimo)}** |",
        f"| Familias | {len(por_grupo)} |",
        f"| Boletines leídos | {len({r['archivo'] for r in registros})} |",
        (f"| Rango de fechas | {fechas[0]} – {fechas[-1]} |" if fechas
         else "| Rango de fechas | sin dato |"),
        f"| Mercados | " + " · ".join(f"{k} ({v})" for k, v in MERCADOS.items()) + " |",
        "",
        "### Insumos piloto",
        "",
        "| Insumo | ¿Hay precio? | Nota |",
        "|---|---|---|",
    ]
    NOTAS = {
        "palta": "Varias variedades, todo el año",
        "espárrago": "Una entrada, todo el año",
        "mango": "Estacional: presente de noviembre a mayo, ausente en invierno",
        "quinua": "El boletín diario de Lima no la cubre; es grano, no hortaliza",
        "arándano": "No se sigue: casi toda la producción peruana va a exportación",
    }
    for insumo, nota in NOTAS.items():
        lineas.append(f"| {insumo} | {'✅' if insumo in piloto else '❌'} | {nota} |")

    lineas += ["", "## Catálogo completo", ""]
    for grupo in sorted(por_grupo):
        filas = sorted(por_grupo[grupo], key=lambda r: r["producto"])
        lineas += [f"### {grupo} ({len(filas)})", "",
                   "| Producto | CNPA | Mercado | S/ por kg | Var. semanal | Fecha |",
                   "|---|---|---|---:|---:|---|"]
        for r in filas:
            variacion = (f"{r['variacion_pct']:+.1f} %"
                         if r["variacion_pct"] is not None else "—")
            lineas.append(
                f"| {r['producto'].title()} | `{r['codigo_cnpa']}` | {r['mercado']} "
                f"| {r['precio_soles_kg']:.2f} | {variacion} | {r['fecha']} |")
        lineas.append("")

    lineas += [
        "## Cómo se actualiza",
        "",
        "```bash",
        "uv run python -m etl.cargar_precios_sisap   # descarga y parsea",
        "uv run python scripts/cobertura_precios.py  # regenera este documento",
        "```",
        "",
        "Añadir un mes es añadir una línea al diccionario `BOLETINES` de "
        "`etl/cargar_precios_sisap.py`: gob.pe da un identificador nuevo a cada "
        "publicación mensual y no es predecible.",
        "",
        "## Límites conocidos",
        "",
        "- **Solo Lima.** Los dos mercados son el Gran Mercado Mayorista y el "
        "Mercado de Frutas Nº 2. No hay precio de mercados regionales.",
        "- **Producto fresco a granel.** No hay procesados, ni congelados, ni "
        "deshidratados, que suele ser la forma en que una agroindustria compra.",
        "- **Estacionalidad.** Un producto ausente de un boletín no es un fallo "
        "de lectura: es que ese día no entró al mercado.",
        "- **Nombres partidos.** La extracción por columnas del PDF parte alguna "
        "palabra (`MANGO EDWARD PLANT A`). Se reconstruye comparando boletines de "
        "días distintos; cuando todas las muestras se parten igual, se deja como "
        "vino en vez de inventar dónde iba el espacio.",
        "",
        "**Fuente:** MIDAGRI · Boletín de Abastecimiento y Precios Mayoristas "
        "(GMML y MM Nº 2), publicado en gob.pe.",
        "",
    ]

    DESTINO.write_text("\n".join(lineas), encoding="utf-8")
    print(f"[COBERTURA] {len(ultimo)} productos en {len(por_grupo)} familias")
    print(f"[COBERTURA] insumos piloto con precio: {sorted(piloto)}")
    print(f"[COBERTURA] -> {DESTINO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
