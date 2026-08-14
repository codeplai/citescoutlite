"""
T2.1 — Ingesta del Anexo II de la UE. Se ejecuta a mano o desde un cron.

    python -m etl.ingerir_anexo_ii             # descarga si falta, parsea y audita
    python -m etl.ingerir_anexo_ii --forzar    # vuelve a descargar
    python -m etl.ingerir_anexo_ii --auditar   # solo el informe de derivación

La auditoría del final no es decorativa. La expansión de los rangos se deriva
del propio documento (ver `corpus_anexo_ii`), y una derivación que se degrade
—porque EUR-Lex cambie la maquetación, o porque una modificación posterior
renombre una familia— dejaría aditivos sin cobertura **en silencio**. El informe
imprime cuántos rangos quedan vacíos y cuáles, para que eso se vea el día que
pase y no tres semanas después.
"""

import argparse
import logging
import sys
from pathlib import Path

from adaptadores.corpus_anexo_ii import (
    RUTA_HTML,
    RUTA_JSON,
    CorpusAnexoII,
    descargar,
    parsear,
)

# Los cinco rangos que cubren aditivos del snapshot. Son los que el gate exige
# que se deriven bien; el resto se informa pero no bloquea.
CANARIOS_RANGO = {
    "E202": ("E 200-203", "sorbato de potasio"),
    "E211": ("E 210-213", "benzoato de sodio"),
    "E220": ("E 220-228", "dióxido de azufre / sulfitos"),
    "E282": ("E 280-283", "propionato de calcio"),
    "E339": ("E 338-452", "fosfatos de sodio"),
}

# El caso 1 de `acido1.pptx`: el veredicto está en la restricción, no en la fila.
CANARIO_PURE = ("E200", "04.2.4.1", "puré")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true")
    parser.add_argument("--auditar", action="store_true",
                        help="No vuelve a parsear; solo audita lo ya ingerido")
    parser.add_argument("--destino", default=str(RUTA_JSON))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    destino = Path(args.destino)

    if not args.auditar:
        ruta = descargar(RUTA_HTML, forzar=args.forzar)
        datos = parsear(ruta.read_text(encoding="utf-8"))
        destino.parent.mkdir(parents=True, exist_ok=True)
        import json
        destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        print(f"\nEscrito {destino} ({destino.stat().st_size / 1e6:.1f} MB)")
        for clave, valor in datos["resumen"].items():
            print(f"  {clave:22} {valor}")

    corpus = CorpusAnexoII(destino)
    print(f"\nAnexo II {corpus.celex} · {len(corpus.aditivos())} aditivos · "
          f"{len(corpus.categorias)} categorías · {len(corpus)} usos")

    fallos = []

    print("\nRangos que cubren aditivos del snapshot:")
    for e, (rango, nombre) in CANARIOS_RANGO.items():
        usos = [u for u in corpus.usos(e) if u.entrada == rango]
        if usos:
            print(f"  OK  {e:6} {nombre:30} {rango:12} en {len(usos):3} categorías")
        else:
            fallos.append(f"{e} ({nombre}) no se deriva de {rango}")

    print("\nCanario del caso 1 (la restricción manda sobre la fila):")
    e, categoria, palabra = CANARIO_PURE
    usos = corpus.usos(e, categoria)
    if not usos:
        fallos.append(f"{e} no aparece en la categoría {categoria}")
    elif not any(palabra in u.restricciones.lower() for u in usos):
        fallos.append(f"{e} en {categoria} no menciona '{palabra}' en restricciones")
    else:
        u = next(u for u in usos if palabra in u.restricciones.lower())
        print(f"  OK  {e} en {categoria} ({u.categoria_nombre[:40]})")
        print(f"      dosis: {u.dosis_texto} · vía: {u.via}")
        print(f"      restricción: {u.restricciones[:110]}...")

    if fallos:
        print("\nIngesta NO válida:")
        for f in fallos:
            print(f"  {f}")
        return 1

    print("\nAnexo II listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
