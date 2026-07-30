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

    if len(productos) < 50:
        print(f"\n[FALLBACK] Solo {len(productos)} productos descargados (OFF con problemas).")
        print("[FALLBACK] Agregando datos de demostración para S1/S2...")

        fallback_data = [
            {
                "id_fuente": "DEMO:1",
                "nombre": "Mango Peel Extract Powder",
                "categoria": "Food ingredients, Dietary supplements",
                "ingredientes": "mango peel extract, maltodextrin",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719705600
            },
            {
                "id_fuente": "DEMO:2",
                "nombre": "Organic Mango Bar",
                "categoria": "Organic, Snacks",
                "ingredientes": "organic mango, honey, nuts, mango juice concentrate",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719619200
            },
            {
                "id_fuente": "DEMO:3",
                "nombre": "Freeze Dried Mango Chunks",
                "categoria": "Dried fruit, Snacks",
                "ingredientes": "freeze dried mango",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719532800
            },
            {
                "id_fuente": "DEMO:4",
                "nombre": "Mango Lassi Drink Mix",
                "categoria": "Beverage, Dairy",
                "ingredientes": "mango pulp, yogurt powder, sugar, mango flavoring",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719446400
            },
            {
                "id_fuente": "DEMO:5",
                "nombre": "Blueberry Mango Smoothie",
                "categoria": "Beverage, Frozen",
                "ingredientes": "blueberry concentrate, mango puree, yogurt, honey",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719360000
            },
            {
                "id_fuente": "DEMO:6",
                "nombre": "Asparagus Soup Mix",
                "categoria": "Soup, Dehydrated",
                "ingredientes": "asparagus powder, salt, spices, asparagus extract",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719273600
            },
            {
                "id_fuente": "DEMO:7",
                "nombre": "Quinoa Energy Bar",
                "categoria": "Snacks, Energy bars",
                "ingredientes": "quinoa, dark chocolate, almond butter, quinoa seeds",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719187200
            },
            {
                "id_fuente": "DEMO:8",
                "nombre": "Avocado Oil (Palta)",
                "categoria": "Oils, Cooking",
                "ingredientes": "avocado oil, palta extract",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719100800
            },
            {
                "id_fuente": "DEMO:9",
                "nombre": "Blueberry Powder",
                "categoria": "Food ingredients",
                "ingredientes": "freeze dried blueberry, blueberry extract",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1719014400
            },
            {
                "id_fuente": "DEMO:10",
                "nombre": "Cranberry Mango Juice",
                "categoria": "Beverage, Juice",
                "ingredientes": "mango juice, cranberry concentrate, water, mango flavor",
                "url": "https://example.com",
                "usa_insumo_directo": False,
                "fecha_dato": 1718928000
            }
        ]

        productos.extend(fallback_data)
        print(f"  Agregados {len(fallback_data)} productos de demostración")

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
