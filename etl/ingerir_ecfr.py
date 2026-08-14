"""
T1.1 — Ingesta del título 21 del CFR. Se ejecuta a mano o desde un cron.

    python -m etl.ingerir_ecfr            # descarga si falta y comprueba
    python -m etl.ingerir_ecfr --forzar   # vuelve a descargar

El GPO republica el título con cada enmienda (el fichero traía `AMDDATE
July 23, 2026` el 2026-08-13). No hay que correrlo por consulta: una vez al mes
sobra, y el agente sigue preguntando el ranking en vivo mientras tanto.

La comprobación del final no es decorativa. Un XML truncado parsea sin lanzar
—se queda en las secciones que alcanzó— y el fallo aparecería mucho después,
como un `SIN_DATO` inexplicable en una celda que antes salía. Por eso el script
verifica que estén las dos secciones de referencia antes de dar por buena la
descarga.
"""

import argparse
import logging
import sys

from adaptadores.corpus_ecfr import RUTA_POR_DEFECTO, CorpusECFR, descargar

# Las dos secciones de `acido1.pptx` y `acido2.pptx`. Si el corpus no las trae,
# no sirve para lo que se descargó.
CANARIOS = {
    "182.3089": "sorbic acid",
    "172.120": "calcium disodium edta",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true",
                        help="Vuelve a descargar aunque el fichero ya esté")
    parser.add_argument("--destino", default=str(RUTA_POR_DEFECTO))
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    ruta = descargar(args.destino, forzar=args.forzar)
    corpus = CorpusECFR(ruta)

    print(f"\nSecciones: {len(corpus)}")
    partes = corpus.partes()
    interesantes = {p: n for p, n in partes.items()
                    if p in ("101", "145", "146", "150", "169", "172", "182", "184")}
    print("Partes que importan para aditivos:")
    for parte, n in interesantes.items():
        print(f"  parte {parte:>4}: {n:>4} secciones")

    fallos = []
    for identificador, esperado in CANARIOS.items():
        seccion = corpus.seccion(identificador)
        if seccion is None:
            fallos.append(f"{identificador}: no está en el corpus")
        elif esperado not in seccion.texto.lower():
            fallos.append(f"{identificador}: no menciona '{esperado}'")
        else:
            print(f"  OK  {seccion.cita} - {seccion.encabezado[:60]}")

    if fallos:
        print("\nDescarga NO válida:")
        for f in fallos:
            print(f"  {f}")
        return 1

    print("\nCorpus listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
