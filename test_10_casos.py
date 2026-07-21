import asyncio
import os
import glob
from api.main import dependencias
from casos_de_uso.evaluar_insumo import evaluar_insumo

casos = [
    "cáscara de cacao",
    "semilla de palta",
    "bagazo de caña",
    "pulpa de café",
    "hojas de guanábana",
    "cáscara de maracuyá",
    "coronta de maíz morado",
    "pepa de uva",
    "piel de limón",
    "residuos de espárrago"
]

async def run_single(i, insumo):
    print(f"[{i}/{len(casos)}] Iniciando evaluación: {insumo}")
    try:
        informe = await evaluar_insumo(insumo, dependencias)
        print(f"  -> ÉXITO [{insumo}]: {informe.ruta_pdf}")
    except Exception as e:
        print(f"  -> ERROR evaluando '{insumo}': {e}")

async def run_tests():
    dependencias.snapshot_version = "2026-07-lote-10-casos-parallel"
    print(f"=== INICIANDO PRUEBA PARALELA DE {len(casos)} CASOS ===")
    
    tasks = [run_single(i, insumo) for i, insumo in enumerate(casos, 1)]
    await asyncio.gather(*tasks)
            
    print("\n=== PRUEBA DE LOTE PARALELO COMPLETADA ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
