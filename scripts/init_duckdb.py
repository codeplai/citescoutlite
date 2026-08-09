#!/usr/bin/env python3
"""Initialize DuckDB file with basic schema for shelf_facts analytics."""

import duckdb
import os

def init_duckdb():
    db_path = "data/shelf_facts.duckdb"

    # Crear directorio si no existe
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Conectar o crear base de datos
    db = duckdb.connect(db_path)

    # Crear tabla inicial
    db.execute('''
        CREATE TABLE IF NOT EXISTS shelf_facts_quarterly (
            year_quarter VARCHAR,           -- ej: "2026-Q3"
            insumo VARCHAR,                 -- ej: "arándano"
            tienda_id VARCHAR,              -- ej: "walmart-pe"
            producto_ean VARCHAR,           -- código de barras
            precio_promedio FLOAT,          -- precio promedio en USD
            fecha_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    db.execute('''
        CREATE TABLE IF NOT EXISTS shelf_facts_daily (
            fecha DATE,
            insumo VARCHAR,
            tienda_id VARCHAR,
            producto_ean VARCHAR,
            precio FLOAT,
            cantidad_disponible INT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    print(f"✅ DuckDB initialized: {db_path}")
    print("   Tables created:")
    print("   - shelf_facts_quarterly")
    print("   - shelf_facts_daily")

    db.close()

if __name__ == "__main__":
    init_duckdb()
