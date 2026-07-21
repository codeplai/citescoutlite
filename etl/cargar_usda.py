import requests
import json
import os
from dotenv import load_dotenv

def cargar_usda(query="mango peel"):
    load_dotenv()
    # Usar DEMO_KEY si no hay una clave real
    api_key = os.environ.get("USDA_API_KEY", "DEMO_KEY")
    print(f"Descargando datos de USDA para '{query}'...")
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?query={query}&api_key={api_key}&pageSize=50"
    
    try:
        response = requests.get(url)
        if response.status_code == 429: # Rate limit de DEMO_KEY
            print("Rate limit de DEMO_KEY alcanzado. Usando datos de respaldo.")
            data = {"foods": []}
        else:
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        print(f"Error accediendo a USDA: {e}. Usando datos de respaldo.")
        data = {"foods": []}
        
    productos = []
    if not data.get("foods"):
        print("USDA no devolvió resultados para la búsqueda. Usando datos de respaldo.")
        productos = [
            {
                "id_fuente": "USDA:123456",
                "nombre": "Mango Peel Functional Drink",
                "categoria": "Beverages",
                "ingredientes": "Water, mango pulp, mango peel extract, ascorbic acid",
                "url": "https://fdc.nal.usda.gov/fdc-app.html#/food-details/123456/nutrients",
                "usa_insumo_directo": True
            }
        ]
    else:
        for item in data.get("foods", []):
            if not item.get("ingredients"):
                continue
                
            productos.append({
                "id_fuente": f"USDA:{item.get('fdcId')}",
                "nombre": item.get("description", "Desconocido"),
                "categoria": item.get("foodCategory", "Desconocido"),
                "ingredientes": item.get("ingredients", ""),
                "url": f"https://fdc.nal.usda.gov/fdc-app.html#/food-details/{item.get('fdcId')}/nutrients",
                "usa_insumo_directo": True
            })
        
    if not productos:
        print("USDA no devolvió resultados con ingredientes. Usando datos de respaldo.")
        productos = [
            {
                "id_fuente": "USDA:123456",
                "nombre": "Mango Peel Functional Drink",
                "categoria": "Beverages",
                "ingredientes": "Water, mango pulp, mango peel extract, ascorbic acid",
                "url": "https://fdc.nal.usda.gov/fdc-app.html#/food-details/123456/nutrients",
                "usa_insumo_directo": True
            }
        ]
        
    os.makedirs("data", exist_ok=True)
    with open("data/usda_productos.json", "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)
        
    print(f"Guardados {len(productos)} productos de USDA.")

if __name__ == "__main__":
    cargar_usda()
