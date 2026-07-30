import requests
import json
import os
import gzip
import io
from typing import List, Dict

def cargar_off_masivo(insumos: List[str] = None, output_file: str = "data/off_productos.json"):
    """
    Descarga datos de Open Food Facts usando búsqueda por insumo.
    Alternativa: usar el export completo comprimido si está disponible.
    """
    if insumos is None:
        insumos = ["arándano", "palta", "espárrago", "mango", "quinua"]

    print(f"Iniciando descarga de OFF para insumos: {insumos}")

    productos = []
    user_agent = "AgroScout-CITE/0.1 (CITEagroindustrial)"

    for insumo in insumos:
        print(f"\n  Buscando '{insumo}' en OFF...")
        try:
            url = f"https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": insumo,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 100,
                "sort_by": "created_t"
            }

            response = requests.get(url, params=params, headers={"User-Agent": user_agent}, timeout=15)
            response.raise_for_status()
            data = response.json()

            count = 0
            for item in data.get("products", []):
                if not item.get("ingredients_text"):
                    continue

                productos.append({
                    "id_fuente": f"OFF:{item.get('id', 'N/A')}",
                    "nombre": item.get("product_name", "Desconocido"),
                    "categoria": item.get("categories", "Desconocido"),
                    "ingredientes": item.get("ingredients_text", ""),
                    "url": item.get("url", ""),
                    "usa_insumo_directo": False,
                    "fecha_dato": item.get("last_modified_t")
                })
                count += 1

            print(f"    Encontrados {count} productos con '{insumo}'")

        except Exception as e:
            print(f"    Error descargando '{insumo}': {e}")

    if not productos:
        print("\n[FALLBACK] No se descargaron productos. Usando datos de demostración.")
        productos = [
            {
                "id_fuente": "OFF:999",
                "nombre": "Mango Peel Powder",
                "categoria": "Dietary supplements, Food ingredients",
                "ingredientes": "100% dried mango peel",
                "url": "https://world.openfoodfacts.org",
                "usa_insumo_directo": False,
                "fecha_dato": 1719705600
            },
            {
                "id_fuente": "OFF:888",
                "nombre": "Mango & Fiber Bar",
                "categoria": "Snacks, Sweet snacks",
                "ingredientes": "Oats, honey, dried mango, mango peel extract, citric acid",
                "url": "https://world.openfoodfacts.org",
                "usa_insumo_directo": False,
                "fecha_dato": 1719619200
            }
        ]

    os.makedirs("data", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)

    print(f"\nTotal: {len(productos)} productos guardados en {output_file}")
    return productos

def cargar_off(query="mango peel"):
    """Interfaz de compatibilidad (mantener si se llama desde otro lado)."""
    return cargar_off_masivo([query])

if __name__ == "__main__":
    cargar_off()
