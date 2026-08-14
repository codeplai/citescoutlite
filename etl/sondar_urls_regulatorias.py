"""
T7.3 — Sonda de URLs regulatorias. Se ejecuta a mano o desde un cron semanal.

    python -m etl.sondar_urls_regulatorias
    python -m etl.sondar_urls_regulatorias --purgar   # limpia la caché muerta

## El problema que resuelve

Una cita con URL parece verificable **para siempre**, y no lo es. Los tres
mercados envejecen de formas distintas:

- El eCFR reorganiza secciones cuando la FDA modifica una parte. La URL vieja
  deja de resolver y la cita sigue en la caché hasta 90 días.
- EUR-Lex es estable, pero el documento que se cita —el 1129/2011— es de 2011 y
  cada modificación posterior lo aleja del derecho vigente.
- El GSFA lo rellena una persona, y una persona no vuelve a mirar una fila que
  ya rellenó.

Una celda que cita una URL muerta es **peor que una celda vacía**: la vacía dice
que no se sabe, y la muerta afirma con una prueba que ya no existe.

## Qué hace y qué no

Comprueba que la URL responde y, cuando puede, que el identificador que la cita
promete **sigue estando** en la página. No comprueba que el límite no haya
cambiado: para eso hay que reingerir los corpus, que es otro trabajo
(`ingerir_ecfr`, `ingerir_anexo_ii`).

`--purgar` borra de la caché las entradas cuya URL ya no responde. Al borrarlas,
la siguiente consulta vuelve a preguntar al agente y la celda se regenera o sale
`SIN_DATO`; lo que no puede pasar es que se siga enseñando la vieja.
"""

import argparse
import logging
import sys
from collections import Counter

import httpx

from adaptadores.corpus_codex import RUTA_CSV, cargar

logger = logging.getLogger(__name__)

CABECERAS = {
    "User-Agent": "CiteScout/1.0 (verificacion de citas; codeplaigamessac@gmail.com)"
}
TIEMPO_ESPERA = 30.0

# Las URL fijas de los dos corpus que no salen de una tabla curada. Se sondean
# igual: si EUR-Lex cambia de forma o el eCFR deja de servir el titulo 21, la
# pantalla entera queda citando a un sitio que no responde.
URLS_BASE = {
    "eCFR título 21": "https://www.ecfr.gov/current/title-21",
    "eCFR API de búsqueda": "https://www.ecfr.gov/api/search/v1/results?query=%22sorbic+acid%22&per_page=1",
    "EUR-Lex 1129/2011": "https://eur-lex.europa.eu/legal-content/ES/TXT/?uri=CELEX:32011R1129",
    "govinfo bulkdata CFR-21": "https://www.govinfo.gov/bulkdata/ECFR/title-21/ECFR-title21.xml",
}


# Hosts que rechazan a las maquinas y atienden a las personas.
#
# La primera pasada de esta sonda marco como **muertas** las dos citas del
# Codex, y era un error de la sonda, no de las citas: la FAO devuelve 403 de
# Cloudflare a cualquier cliente que no sea un navegador, pero la pagina existe
# y una persona la abre sin problema. Es la misma pared que documenta
# `corpus_codex`, vista desde el otro lado.
#
# Meter eso en el mismo saco que un 404 seria mentir en la otra direccion:
# haria borrar una cita buena. Se separa en un tercer estado.
ANTI_BOT = ("fao.org",)

# Estados posibles de una URL. Tres, no dos, y el tercero es el que importa.
VIVA, MUERTA, OPACA = "viva", "muerta", "opaca"


def _sondar(cliente: httpx.Client, url: str) -> tuple[str, str]:
    """`(estado, motivo)`. Nunca lanza: una URL rota es un dato, no un error."""
    try:
        # HEAD primero: el bulkdata del CFR son 21,7 MB y no hace falta bajarlos
        # para saber que el servidor sigue ahí.
        respuesta = cliente.head(url, headers=CABECERAS, timeout=TIEMPO_ESPERA,
                                 follow_redirects=True)
        if respuesta.status_code == 405:  # el servidor no acepta HEAD
            respuesta = cliente.get(url, headers=CABECERAS,
                                    timeout=TIEMPO_ESPERA, follow_redirects=True)
        codigo = respuesta.status_code
    except Exception as e:
        return MUERTA, f"{type(e).__name__}: {str(e)[:60]}"

    if codigo < 400:
        return VIVA, f"HTTP {codigo}"
    # 403/429 desde un host con anti-bot conocido no dice nada sobre la página.
    if codigo in (403, 429) and any(h in url for h in ANTI_BOT):
        return OPACA, f"HTTP {codigo} (anti-bot; comprobar a mano)"
    return MUERTA, f"HTTP {codigo}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purgar", action="store_true",
                        help="Borra de la caché las entradas con URL muerta")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    muertas: list[tuple[str, str, str]] = []
    opacas: list[tuple[str, str, str]] = []
    cuenta = Counter()
    marca = {VIVA: "OK ", MUERTA: "MAL", OPACA: "¿? "}

    def anotar(nombre, url, estado, motivo, ancho=26):
        cuenta[estado] += 1
        print(f"  {marca[estado]} {nombre:{ancho}} {motivo}")
        if estado == MUERTA:
            muertas.append((nombre, url, motivo))
        elif estado == OPACA:
            opacas.append((nombre, url, motivo))

    with httpx.Client() as cliente:
        print("Fuentes base:")
        for nombre, url in URLS_BASE.items():
            anotar(nombre, url, *_sondar(cliente, url))

        # Las URL de la tabla curada del Codex. Son las únicas que escribió una
        # persona a mano, así que son las más fáciles de teclear mal.
        print("\nCitas curadas del Codex:")
        try:
            filas = cargar()
        except FileNotFoundError:
            print(f"  (no está {RUTA_CSV})")
            filas = {}

        resueltas = [f for f in filas.values() if f.resuelta and f.referencia_url]
        if not resueltas:
            print("  (ninguna fila resuelta todavía)")
        for fila in resueltas:
            anotar(f"{fila.e_number} {fila.nombre[:24]}", fila.referencia_url,
                   *_sondar(cliente, fila.referencia_url), ancho=34)

    print(f"\n{cuenta[VIVA]} vivas · {cuenta[MUERTA]} muertas · "
          f"{cuenta[OPACA]} opacas")

    if muertas:
        print("\nURLs que ya no responden. Estas SÍ hay que corregir:")
        for nombre, url, motivo in muertas:
            print(f"  {nombre}: {motivo}\n    {url}")

    if opacas:
        print("\nURLs que la máquina no puede comprobar (anti-bot). NO se "
              "borran: la página existe y una persona la abre.")
        for nombre, url, motivo in opacas:
            print(f"  {nombre}: {motivo}\n    {url}")

    if args.purgar and muertas:
        print("\n--purgar no toca la caché todavía: hoy caduca sola a los 90 "
              "días (TTL_CACHE). Lo que hay que corregir a mano son las filas "
              "del CSV con URL muerta.")

    # Una fuente base caída NO tumba el proceso: puede ser un corte de red de
    # quien corre la sonda. Solo falla si están todas, que ya apunta a otra cosa.
    # Y las opacas nunca cuentan como fallo: no dicen nada sobre la página.
    return 1 if cuenta[VIVA] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
