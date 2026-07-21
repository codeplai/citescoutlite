import asyncio
from api.main import dependencias
from casos_de_uso.evaluar_insumo import evaluar_insumo
import json

async def run():
    dependencias.snapshot_version = "2026-07-force-nocache-cacao"
    print("--- EVALUAR INSUMO END-TO-END (Bypass HTTP) ---")
    informe = await evaluar_insumo("cáscara de cacao", dependencias)
    print("REPORTE GENERADO CON ÉXITO")
    print(informe.model_dump_json(indent=2))
    
    if informe.ruta_pdf:
        print("==================================================")
        print("CONTENIDO DEL REPORTE GENERADO (Markdown/PDF)")
        print("==================================================")
        
        if str(informe.ruta_pdf).endswith('.pdf'):
            print(f"El reporte es un archivo PDF binario y ha sido guardado en: {informe.ruta_pdf}")
        else:
            try:
                with open(informe.ruta_pdf, 'r', encoding='utf-8') as f:
                    print(f.read())
            except UnicodeDecodeError:
                print("El archivo generado no se pudo imprimir en texto plano.")

if __name__ == "__main__":
    asyncio.run(run())
