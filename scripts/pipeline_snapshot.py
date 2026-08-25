"""
Pipeline completo de actualizacion del snapshot, desatendido, con parte horario.

Lo lanza `pipeline.bat`. Corre las etapas en orden y, en paralelo, manda un
correo cada hora con el avance. Las etapas van como subprocesos y no como
importaciones porque cada una tiene su propio interprete: los ETL de embeddings
y busqueda viven en `venv/`, que es el unico entorno con lancedb y torch.

    1. canasta      cosecha de 400 formas de producto en Peru (reanudable)
    2. imagenes     imagen_url verificada de los 28.642 productos de OFF
    3. merge        OFF + USDA + las dos campanas de terminados
    4. indexar      embeddings bge-m3 de lo nuevo, incremental
    5. manifest     SHA256 y estadisticas recalculadas

Si una etapa falla, el pipeline **para** y lo dice en el correo. No sigue
adelante: indexar sobre un merge a medias dejaria el snapshot describiendo algo
que no es.

Las etapas 1 y 2 se reanudan solas, asi que relanzar el pipeline tras un corte
continua donde se quedo en vez de repetir horas de descarga.

Uso:
    pipeline.bat
    uv run python -m scripts.pipeline_snapshot --solo imagenes,merge
    uv run python -m scripts.pipeline_snapshot --sin-correo
"""
import argparse
import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATASET = RAIZ / "datasets" / "2026-07"
PY_VENV = RAIZ / "venv" / "Scripts" / "python.exe"
LOG = RAIZ / "logs" / "pipeline_snapshot.log"

INTERVALO_PARTE_S = 3600

# El orden importa y no es intercambiable. `merge` REGENERA
# productos_merged.json desde sus fuentes, e `imagenes` escribe `imagen_url`
# sobre ese mismo archivo. Con imagenes antes que merge, el merge se lleva por
# delante las URLs recien escritas: paso de verdad el 2026-08-24, imagenes
# termino a las 12:02:55 con 20.139 URLs y merge las borro a las 12:02:57.
# Nadie se entera, porque el pipeline reporta las cinco etapas en OK.
#
# `manifest` va al final porque calcula el SHA256 de productos_merged.json, y
# tiene que ser el del archivo ya terminado.
ETAPAS = [
    ("canasta", [str(PY_VENV), "-m", "etl.cargar_off_terminados",
                 "--campana", "canasta", "--mercados", "peru", "--page-size", "20"]),
    ("merge", [str(PY_VENV), "-m", "etl.merge_datasets"]),
    ("imagenes", [str(PY_VENV), "-m", "etl.imagenes_off"]),
    ("indexar", [str(PY_VENV), "-m", "etl.indexar_incremental"]),
    ("manifest", [str(PY_VENV), "-m", "etl.finalizar_manifest"]),
]

_estado = {"etapa": "arrancando", "desde": time.time(), "inicio": time.time(),
           "hechas": [], "fallo": None}
_fin = threading.Event()


def log(msg: str):
    linea = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(linea, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


def _lineas(ruta: Path) -> int:
    if not ruta.exists():
        return 0
    with open(ruta, encoding="utf-8") as f:
        return sum(1 for l in f if l.strip())


def _cuenta_json(ruta: Path) -> int | None:
    if not ruta.exists():
        return None
    try:
        d = json.loads(ruta.read_text(encoding="utf-8"))
        return len(d)
    except Exception:
        return None


def avance() -> str:
    """Cifras reales leidas de los archivos de estado, no estimaciones."""
    lineas = []

    codigos = _cuenta_json(DATASET / "off_canasta_codigos.json")
    fichas = _lineas(DATASET / "off_canasta_fichas.jsonl")
    if codigos is None:
        lineas.append("canasta   : buscando codigos (fase 1 de 2)")
    else:
        pct = fichas / codigos * 100 if codigos else 0
        utiles = _cuenta_json(DATASET / "off_canasta.json")
        cola = f" · {utiles} aceptados" if utiles is not None else ""
        lineas.append(f"canasta   : {fichas:,}/{codigos:,} fichas ({pct:.0f} %){cola}")

    img = _lineas(DATASET / "imagenes_off.jsonl")
    lineas.append(f"imagenes  : {img:,}/28.642 comprobadas ({img / 28642 * 100:.0f} %)")

    merged = _cuenta_json(DATASET / "productos_merged.json")
    if merged:
        lineas.append(f"snapshot  : {merged:,} productos en productos_merged.json")
    return "\n".join(lineas)


def cuerpo_parte() -> str:
    ahora = datetime.now()
    total = timedelta(seconds=int(time.time() - _estado["inicio"]))
    en_etapa = timedelta(seconds=int(time.time() - _estado["desde"]))
    partes = [
        f"AgroScout · actualizacion del snapshot 2026-07",
        f"Hora           : {ahora:%Y-%m-%d %H:%M:%S}",
        f"Etapa en curso : {_estado['etapa']} (desde hace {en_etapa})",
        f"Etapas hechas  : {', '.join(_estado['hechas']) or 'ninguna todavia'}",
        f"Tiempo total   : {total}",
        "",
        avance(),
    ]
    if _estado["fallo"]:
        partes += ["", f"FALLO: {_estado['fallo']}", "El pipeline se detuvo aqui."]
    return "\n".join(partes)


def _parte(asunto: str, silencioso: bool):
    if silencioso:
        log(f"(--sin-correo) parte omitido: {asunto}")
        return
    from adaptadores.correo_smtp import enviar
    ok, detalle = enviar(asunto, cuerpo_parte())
    log(f"parte por correo: {'OK' if ok else 'NO ENVIADO'} · {detalle}")


def hilo_partes(silencioso: bool):
    """Un correo por hora hasta que el pipeline termine."""
    while not _fin.wait(INTERVALO_PARTE_S):
        _parte(f"AgroScout · snapshot en curso · etapa {_estado['etapa']}", silencioso)


def corre_etapa(nombre: str, comando: list[str]) -> bool:
    _estado["etapa"] = nombre
    _estado["desde"] = time.time()
    log("=" * 70)
    log(f"ETAPA {nombre}: {' '.join(comando)}")
    inicio = time.time()
    proceso = subprocess.run(comando, cwd=str(RAIZ))
    minutos = (time.time() - inicio) / 60
    if proceso.returncode != 0:
        _estado["fallo"] = f"la etapa '{nombre}' salio con codigo {proceso.returncode}"
        log(f"ETAPA {nombre}: FALLO ({proceso.returncode}) tras {minutos:.1f} min")
        return False
    _estado["hechas"].append(nombre)
    log(f"ETAPA {nombre}: OK en {minutos:.1f} min")
    return True


def _cargar_env():
    """Mete `.env` en el entorno. Sin esto `os.getenv` no ve nada de SMTP."""
    try:
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
    except ImportError:
        log("AVISO: python-dotenv no esta instalado; solo se leeran las "
            "variables ya presentes en el entorno.")


def main(solo: list[str] | None, silencioso: bool) -> int:
    _cargar_env()
    etapas = [(n, c) for n, c in ETAPAS if not solo or n in solo]
    if not etapas:
        raise SystemExit(f"Ninguna etapa coincide con {solo}. Hay: {[n for n, _ in ETAPAS]}")

    if not silencioso:
        from adaptadores.correo_smtp import configuracion
        _, faltan = configuracion()
        if faltan:
            log(f"AVISO: no se enviaran correos, faltan en .env: {', '.join(faltan)}. "
                f"El pipeline sigue igual y el avance queda en {LOG}.")
            silencioso = True

    log(f"Pipeline: {[n for n, _ in etapas]}")
    _parte("AgroScout · snapshot: pipeline arrancado", silencioso)

    hilo = threading.Thread(target=hilo_partes, args=(silencioso,), daemon=True)
    hilo.start()

    correcto = True
    for nombre, comando in etapas:
        if not corre_etapa(nombre, comando):
            correcto = False
            break

    _fin.set()
    _estado["etapa"] = "terminado" if correcto else "detenido por fallo"
    _parte(f"AgroScout · snapshot {'TERMINADO' if correcto else 'DETENIDO'}", silencioso)
    log(f"Pipeline {'completo' if correcto else 'detenido'}. Detalle en {LOG}")
    return 0 if correcto else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solo", default=None,
                    help="Etapas a correr, separadas por comas: "
                         "canasta,imagenes,merge,indexar,manifest")
    ap.add_argument("--sin-correo", action="store_true",
                    help="No manda partes; el avance queda solo en el log")
    args = ap.parse_args()
    seleccion = [s.strip() for s in args.solo.split(",")] if args.solo else None
    sys.exit(main(seleccion, args.sin_correo))
