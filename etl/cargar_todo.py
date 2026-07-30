#!/usr/bin/env python
"""
Script maestro del ETL:
1. Descarga datos reales de Open Food Facts
2. Genera embeddings bge-m3 e indexa en LanceDB
"""

import sys
from etl.cargar_off import cargar_off_masivo
from etl.indexar_vectores import main as indexar_main

def main():
    print("=" * 80)
    print("ETL AGROSCOUT - PIPELINE COMPLETO")
    print("=" * 80)

    try:
        print("\n[PASO 1] Descargando datos de Open Food Facts...")
        productos = cargar_off_masivo(
            insumos=["arándano", "palta", "espárrago", "mango", "quinua"],
            output_file="data/off_productos.json"
        )

        if not productos:
            print("\n[ERROR] No se descargaron productos. Abortando.")
            return 1

        print(f"\n[OK] {len(productos)} productos descargados")

        print("\n[PASO 2] Generando embeddings e indexando en LanceDB...")
        indexar_main()

        print("\n" + "=" * 80)
        print("ETL COMPLETADO EXITOSAMENTE")
        print("=" * 80)
        return 0

    except Exception as e:
        print(f"\n[ERROR FATAL] {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
