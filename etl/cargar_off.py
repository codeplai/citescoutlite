import requests
import json
import os

def cargar_off(query="mango peel"):
    print(f"Descargando datos de Open Food Facts para '{query}'...")
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=50"
    
    try:
        response = requests.get(url, headers={"User-Agent": "AgroScout-CITE/0.1"})
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error accediendo a OFF: {e}. Usando datos de respaldo.")
        data = {
            "products": [
                {
                    "id": "OFF:999",
                    "product_name": "Mango Peel Powder",
                    "categories": "Dietary supplements, Food ingredients",
                    "ingredients_text": "100% dried mango peel",
                    "url": "https://world.openfoodfacts.org"
                },
                {
                    "id": "OFF:888",
                    "product_name": "Mango & Fiber Bar",
                    "categories": "Snacks, Sweet snacks",
                    "ingredients_text": "Oats, honey, dried mango, mango peel extract, citric acid",
                    "url": "https://world.openfoodfacts.org"
                }
            ]
        }
    
    productos = []
    for item in data.get("products", []):
        if not item.get("ingredients_text"):
            continue
            
        productos.append({
            "id_fuente": f"OFF:{item.get('id', 'N/A')}",
            "nombre": item.get("product_name", "Desconocido"),
            "categoria": item.get("categories", "Desconocido"),
            "ingredientes": item.get("ingredients_text", ""),
            "url": item.get("url", ""),
            "usa_insumo_directo": True
        })
        
    # Guardar a un archivo local
    os.makedirs("data", exist_ok=True)
    with open("data/off_productos.json", "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)
        
    print(f"Guardados {len(productos)} productos de Open Food Facts.")

if __name__ == "__main__":
    cargar_off()
