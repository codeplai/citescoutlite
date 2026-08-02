"""
TIER 7 · T7.2: cierre del manifest del snapshot.

Hace dos cosas:

1. **SHA256 + tamaño de cada fuente**, para que el snapshot sea verificable.

2. **Regenera `fuentes` y `estadisticas` a partir de los archivos reales.**
   Hasta TIER 6 el manifest seguía describiendo el snapshot original de 89
   productos (con `espárrago: 0`) mientras el índice tenía 29.054: cualquier
   auditoría que leyera el manifest se contradecía con los datos. Las cifras se
   recalculan aquí en vez de mantenerse a mano.

Uso:
    python -m etl.finalizar_manifest
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATASET = Path("datasets/2026-07")
MANIFEST = DATASET / "manifest.json"

# Sinónimos usados para medir cobertura. Deben coincidir con evals/set_dorado.yaml.
INSUMOS = {
    "arándano": ["arándano", "arandano", "blueberry", "blueberries"],
    "palta": ["palta", "aguacate", "avocado", "avocados"],
    "espárrago": ["espárrago", "esparrago", "asparagus"],
    "mango": ["mango", "mangoes"],
    "quinua": ["quinua", "quinoa"],
}

FUENTES = [
    ("off_productos.json", "Open Food Facts — export offline filtrado", "API/export world.openfoodfacts.org"),
    ("usda_productos.json", "USDA FoodData Central — dataType Branded", "api.nal.usda.gov/fdc/v1"),
    ("productos_merged.json", "OFF + USDA deduplicado por marca+nombre", "TIER 3 (etl.merge_datasets)"),
    ("ecfr_aditivos.json", "eCFR Title 21 partes 182/184/145/146/150", "API versioner ecfr.gov"),
    ("digesa_normas.json", "PDFs normativos DIGESA con capa de texto", "digesa.minsa.gob.pe"),
    ("normativas_codex.json", "Normas Codex (demo S1, sustituido por el corpus TIER 6)", "Demo"),
]


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def contar_filas(ruta: Path) -> int | None:
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(datos, list):
        return len(datos)
    if isinstance(datos, dict):
        return len(datos.get("productos", []))
    return None


def estadisticas_productos() -> dict:
    """Cobertura real por insumo sobre el dataset mergeado."""
    ruta = DATASET / "productos_merged.json"
    if not ruta.exists():
        return {}

    productos = json.loads(ruta.read_text(encoding="utf-8"))
    por_fuente, cobertura = {}, {k: 0 for k in INSUMOS}
    sin_fecha = sin_url = 0

    for p in productos:
        fuente = p["id_fuente"].split(":")[0]
        por_fuente[fuente] = por_fuente.get(fuente, 0) + 1

        if not p.get("fecha_dato"):
            sin_fecha += 1
        if not p.get("url"):
            sin_url += 1

        texto = (f"{p.get('nombre', '')} {p.get('ingredientes', '')} "
                 f"{p.get('categoria', '')}").lower()
        for insumo, sinonimos in INSUMOS.items():
            if any(s in texto for s in sinonimos):
                cobertura[insumo] += 1

    return {
        "total_productos": len(productos),
        "por_fuente": por_fuente,
        "coverage_por_insumo": cobertura,
        "productos_sin_fecha_dato": sin_fecha,
        "productos_sin_url": sin_url,
    }


def estadisticas_regulatorio() -> dict:
    salida = {}
    for archivo, clave in [("ecfr_aditivos.json", "ecfr"),
                           ("digesa_normas.json", "digesa")]:
        ruta = DATASET / archivo
        if not ruta.exists():
            continue
        docs = json.loads(ruta.read_text(encoding="utf-8"))
        salida[clave] = {
            "documentos": len(docs),
            "palabras": sum(len(d["texto"].split()) for d in docs),
        }
    return salida


def main() -> int:
    if not MANIFEST.exists():
        print(f"[MANIFEST] No existe {MANIFEST}")
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["fecha_descarga"] = datetime.now(timezone.utc).isoformat()
    manifest["snapshot_version"] = "2026-07"

    # 1. SHA256 por fuente
    fuentes = {}
    for archivo, descripcion, origen in FUENTES:
        ruta = DATASET / archivo
        if not ruta.exists():
            print(f"[MANIFEST] {archivo}: ausente, se omite")
            continue
        fuentes[archivo] = {
            "descripcion": descripcion,
            "origen": origen,
            "filas": contar_filas(ruta),
            "tamaño_bytes": ruta.stat().st_size,
            "sha256": sha256(ruta),
        }
        print(f"[MANIFEST] {archivo}: {fuentes[archivo]['filas']} filas, "
              f"{fuentes[archivo]['tamaño_bytes']:,} bytes, "
              f"sha256 {fuentes[archivo]['sha256'][:16]}...")

    manifest["fuentes"] = fuentes
    manifest["estadisticas"] = estadisticas_productos()
    manifest["estadisticas"]["regulatorio"] = estadisticas_regulatorio()

    manifest["reproducibilidad"] = {
        "verificar": "sha256sum de cada archivo debe coincidir con fuentes[].sha256",
        "pipeline": [
            "python -m etl.cargar_off_bulk",
            "python -m etl.cargar_usda",
            "python -m etl.merge_datasets",
            "python -m etl.tier4_gpu",
            "python -m etl.indexar_incremental",
            "python -m etl.procesar_ecfr",
            "python -m etl.procesar_digesa",
            "python -m etl.procesar_regulatorio",
            "python -m etl.finalizar_manifest",
        ],
        "validar": [
            "python -m evals.runner_s2",
            "python -m pytest test/ -v",
        ],
    }

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    est = manifest["estadisticas"]
    print(f"\n[MANIFEST] Total productos: {est['total_productos']:,} "
          f"{est['por_fuente']}")
    print(f"[MANIFEST] Cobertura: {est['coverage_por_insumo']}")
    print(f"[MANIFEST] Sin fecha_dato: {est['productos_sin_fecha_dato']} | "
          f"sin url: {est['productos_sin_url']}")
    print(f"[MANIFEST] Regulatorio: {est['regulatorio']}")
    print(f"[MANIFEST] OK -> {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
