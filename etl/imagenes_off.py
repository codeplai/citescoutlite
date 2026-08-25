"""
Anade `imagen_url` a los productos de Open Food Facts del snapshot.

## Por que se deriva del codigo de barras y no se pregunta a la API

La ficha de OFF trae `image_front_url` ya curada, pero son 28.642 peticiones a
las 16-37 por minuto que aguanta esa API: entre 13 y 30 horas, y compitiendo
por la misma cuota que las campanas de `cargar_off_terminados`.

La URL de la primera imagen subida, en cambio, sale del propio codigo:

    https://images.openfoodfacts.org/images/products/409/920/016/0948/1.400.jpg

Comprobado contra la API para ese codigo: la ficha declara
`front_en.4.400.jpg`, y `1.400.jpg` responde 200 igual. Va al CDN de imagenes,
que es otro host y no gasta la cuota de la API.

Lo que se pierde: `1` es la PRIMERA foto subida, no necesariamente la frontal
curada ni la del idioma del producto. Para una miniatura en la ficha es
suficiente; si algun dia hace falta la frontal exacta, hay que pagar las
28.642 llamadas a la API.

## Por que se verifica cada una

Medido sobre 25 productos al azar del snapshot: **solo el 60 % tiene imagen**.
Escribir la URL derivada sin comprobarla dejaria a 4 de cada 10 fichas con un
enlace roto, presentado como si fuera un dato. Se hace un HEAD por producto y
`imagen_url` queda en `null` cuando la imagen no existe. `null` es una
respuesta honesta; una URL que da 404 no lo es.

Uso:
    ./venv/Scripts/python.exe -m etl.imagenes_off --muestra 200   # mide y sale
    ./venv/Scripts/python.exe -m etl.imagenes_off
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import requests

DATASET = Path("datasets/2026-07")
MERGED = DATASET / "productos_merged.json"
CACHE = DATASET / "imagenes_off.jsonl"
LOG = DATASET / "etl_imagenes_off.log"

CDN = "https://images.openfoodfacts.org/images/products"
UA = "AgroScout-CITE/0.1 (CITEagroindustrial; codeplaigamessac@gmail.com)"

# Seis hilos y no mas. El CDN no publica limite, y precisamente por eso conviene
# no averiguarlo a golpes: a este ritmo son ~50 min para el snapshot entero, que
# cabe de sobra en una corrida desatendida.
HILOS = 6


def log(msg: str):
    linea = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(linea, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def ruta_cdn(code: str) -> str:
    """Reparto en carpetas que usa OFF: 3/3/3/resto para codigos largos."""
    if len(code) > 9:
        return f"{code[0:3]}/{code[3:6]}/{code[6:9]}/{code[9:]}"
    return code


def url_derivada(code: str) -> str:
    return f"{CDN}/{ruta_cdn(code)}/1.400.jpg"


def comprobar(sesion: requests.Session, code: str) -> tuple[str, str | None]:
    """(code, url) si la imagen existe; (code, None) si no.

    Un fallo de red devuelve None y NO se guarda en el cache, para que la
    siguiente corrida lo vuelva a intentar: "no pude preguntar" y "no tiene
    imagen" son cosas distintas y confundirlas deja huecos permanentes.
    """
    url = url_derivada(code)
    try:
        r = sesion.head(url, timeout=15, allow_redirects=True)
    except requests.RequestException:
        raise
    return code, (url if r.status_code == 200 else None)


def resueltos() -> dict:
    """{code: url|None} de corridas anteriores."""
    if not CACHE.exists():
        return {}
    salida = {}
    for linea in CACHE.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except json.JSONDecodeError:
            continue
        salida[fila["code"]] = fila["imagen_url"]
    return salida


def codigos_off(productos: list[dict]) -> list[str]:
    return [p["id_fuente"].split(":", 1)[1] for p in productos
            if p["id_fuente"].startswith("OFF:")]


def main(muestra: int | None, hilos: int) -> int:
    productos = json.loads(MERGED.read_text(encoding="utf-8"))
    codigos = codigos_off(productos)
    log("=" * 70)
    log(f"Imagenes OFF · {len(productos):,} productos, {len(codigos):,} de OFF")

    ya = resueltos()
    pendientes = [c for c in codigos if c not in ya]
    if muestra:
        pendientes = pendientes[:muestra]
        log(f"--muestra {muestra}: solo se miden {len(pendientes)}")
    log(f"Resueltos: {len(ya):,} · pendientes: {len(pendientes):,} · hilos: {hilos}")

    if pendientes:
        sesion = requests.Session()
        sesion.headers.update({"User-Agent": UA})
        inicio = time.time()
        hechos = fallos = 0
        with open(CACHE, "a", encoding="utf-8") as cache, \
                ThreadPoolExecutor(max_workers=hilos) as pool:
            for resultado in pool.map(lambda c: _seguro(sesion, c), pendientes):
                code, url, error = resultado
                if error:
                    fallos += 1
                    continue
                cache.write(json.dumps({"code": code, "imagen_url": url}) + "\n")
                ya[code] = url
                hechos += 1
                if hechos % 500 == 0:
                    cache.flush()
                    ritmo = hechos / max(time.time() - inicio, 1)
                    restan = (len(pendientes) - hechos) / max(ritmo, 0.01) / 60
                    con = sum(1 for v in ya.values() if v)
                    log(f"    {hechos:,}/{len(pendientes):,} · {ritmo:.1f}/s · "
                        f"con imagen {con:,} · faltan ~{restan:.0f} min")
        log(f"Comprobados {hechos:,} en {(time.time() - inicio) / 60:.1f} min "
            f"· {fallos} fallos de red (se reintentan al relanzar)")

    if muestra:
        con = sum(1 for c in pendientes if ya.get(c))
        log(f"MUESTRA: {con}/{len(pendientes)} con imagen "
            f"({con / max(len(pendientes), 1) * 100:.0f} %). No se escribe el snapshot.")
        return 0

    # Escritura del snapshot. USDA queda en null a proposito: su ficha no
    # publica imagen y derivarla del codigo de OFF seria apuntar a otro producto.
    con = sin = 0
    for p in productos:
        if p["id_fuente"].startswith("OFF:"):
            url = ya.get(p["id_fuente"].split(":", 1)[1])
            p["imagen_url"] = url
            con += bool(url)
            sin += not url
        else:
            p["imagen_url"] = None
    MERGED.write_text(json.dumps(productos, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    log(f"Escrito {MERGED}: {con:,} con imagen, {sin:,} sin ella, "
        f"{len(productos) - con - sin:,} no-OFF en null")
    return 0


def _seguro(sesion, code):
    try:
        c, u = comprobar(sesion, code)
        return c, u, None
    except Exception as e:
        return code, None, e


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--muestra", type=int, default=None,
                    help="Comprueba solo N y reporta el porcentaje; no escribe el snapshot")
    ap.add_argument("--hilos", type=int, default=HILOS)
    args = ap.parse_args()
    sys.exit(main(args.muestra, args.hilos))
