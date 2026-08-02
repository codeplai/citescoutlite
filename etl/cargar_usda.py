"""
TIER 2 (completado en TIER 7): descarga de USDA FoodData Central — Branded.

Se ejecutó originalmente sin `USDA_API_KEY` y el dataset quedó como un marcador
"SALTADO"; este módulo lo sustituye ahora que la clave está en `.env`.

Diferencias con la versión anterior, que no era apta para cerrar S2:

- **No fabrica datos de respaldo.** La versión previa, ante cualquier fallo de
  la API, escribía un producto inventado ("USDA:123456 — Mango Peel Functional
  Drink") con una URL que no resuelve. Eso es exactamente el dato inventado que
  el MVP prohíbe. Aquí un fallo devuelve lista vacía y queda registrado.
- **Filtra a `Branded`**, que es lo que pide el plan; antes admitía cualquier
  dataType.
- **Trae `fecha_dato` real** (Unix, desde `modifiedDate`/`publicationDate`) en
  vez de omitirla. La búsqueda de TIER 5 exige fecha real o `None`.
- **Cubre los 5 insumos piloto**, no solo "mango peel".
- Escribe en `datasets/2026-07/`, no en `data/`.

Salida: datasets/2026-07/usda_productos.json
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

API = "https://api.nal.usda.gov/fdc/v1/foods/search"
SALIDA = "datasets/2026-07/usda_productos.json"

# Términos en inglés de los 5 insumos piloto (USDA FDC es un catálogo de EE.UU.).
INSUMOS = ["blueberry", "avocado", "asparagus", "mango", "quinoa"]

POR_INSUMO = 200  # pageSize máximo de la API


def _a_timestamp(food: dict) -> int | None:
    """
    Fecha real del registro USDA como Unix timestamp.

    Se prefiere `modifiedDate` (última actualización del producto) y se cae a
    `publicationDate`. Si no viene ninguna se devuelve None: nunca se sustituye
    por la fecha de hoy.
    """
    for campo in ("modifiedDate", "publicationDate"):
        valor = food.get(campo)
        if not valor:
            continue
        for formato in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(valor, formato).replace(tzinfo=timezone.utc)
                return int(dt.timestamp())
            except ValueError:
                continue
    return None


def descargar_insumo(insumo: str, api_key: str) -> list[dict]:
    parametros = {
        "query": insumo,
        "pageSize": POR_INSUMO,
        "dataType": ["Branded"],
        "api_key": api_key,
    }
    respuesta = requests.get(API, params=parametros, timeout=45)
    respuesta.raise_for_status()
    datos = respuesta.json()

    productos = []
    for food in datos.get("foods", []):
        if food.get("dataType") != "Branded":
            continue
        ingredientes = (food.get("ingredients") or "").strip()
        if not ingredientes:
            # Sin ingredientes el producto no aporta al embedding ni permite
            # derivar el uso directo del insumo.
            continue

        fdc_id = food.get("fdcId")
        productos.append({
            "id_fuente": f"USDA:{fdc_id}",
            "nombre": food.get("description", "").strip() or "Desconocido",
            "categoria": (food.get("foodCategory") or "").strip(),
            "ingredientes": ingredientes,
            "url": f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
            # El snapshot no deriva este campo (igual que OFF); lo recalcula
            # casos_de_uso/etapas/buscar_productos.py contra los sinónimos.
            "usa_insumo_directo": False,
            "fecha_dato": _a_timestamp(food),
            "marca": (food.get("brandName") or food.get("brandOwner") or "").strip(),
            "pais": food.get("marketCountry", "United States"),
        })

    print(f"[USDA] {insumo}: {datos.get('totalHits', 0):,} hits, "
          f"{len(productos)} productos con ingredientes")
    return productos


def main(salida: str = SALIDA) -> int:
    load_dotenv()
    api_key = os.environ.get("USDA_API_KEY", "").strip()

    if not api_key or api_key == "DEMO_KEY":
        print("[USDA] USDA_API_KEY ausente o DEMO_KEY. No se descarga nada.")
        print("[USDA] No se generan datos de respaldo: se prefiere un dataset "
              "vacío a uno inventado.")
        return 1

    productos, vistos = [], set()
    for insumo in INSUMOS:
        try:
            for p in descargar_insumo(insumo, api_key):
                # Un mismo producto puede aparecer bajo varios términos.
                if p["id_fuente"] not in vistos:
                    vistos.add(p["id_fuente"])
                    productos.append(p)
        except Exception as e:
            print(f"[USDA] {insumo}: ERROR {type(e).__name__}: {str(e)[:100]}")
        time.sleep(0.5)  # cortesía con el rate limit de la API

    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)

    con_fecha = sum(1 for p in productos if p["fecha_dato"])
    print(f"\n[USDA] {len(productos)} productos únicos -> {salida}")
    print(f"[USDA] Con fecha_dato real: {con_fecha}/{len(productos)}")
    print(f"[USDA] Gate T2.2 (>=10 productos): "
          f"{'PASA' if len(productos) >= 10 else 'FALLA'}")
    return 0 if len(productos) >= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
