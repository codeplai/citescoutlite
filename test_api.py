import requests
import json
import time

url = "http://127.0.0.1:8000/consultas"
payload = {
    "texto": "polvo de arándano deshidratado"
}

print(f"Probando la API con el insumo: '{payload['texto']}'")
print("Enviando petición a la API...")
start = time.time()
try:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
    
    data = response.json()
    end = time.time()
    
    print(f"\n¡Respuesta recibida en {end - start:.2f} segundos!")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    if "ruta_pdf" in data:
        with open(data["ruta_pdf"], "r", encoding="utf-8") as f:
            contenido = f.read()
            print("\n" + "="*50)
            print("CONTENIDO DEL REPORTE GENERADO (Markdown/PDF)")
            print("="*50)
            print(contenido)
            
except requests.exceptions.RequestException as e:
    print(f"Error al conectar con la API: {e}")
