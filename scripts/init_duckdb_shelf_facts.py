#!/usr/bin/env python3
"""
S3.4 Initialize DuckDB with shelf_facts_quarterly table.

Creates local shelf_facts.duckdb with quarterly price history for pilot crops.

Schema:
  shelf_facts_quarterly:
    - year_quarter: CHAR(4) like '2026Q2'
    - insumo: crop name (quinua, palto, espárrago, mango, arándano)
    - tienda_id: store ID
    - producto_ean: product barcode
    - precio_promedio: average price
    - precio_min: min price
    - precio_max: max price
    - stock_promedio: average stock
    - promociones_count: number of promotions
    - last_update: timestamp

Usage:
    python scripts/init_duckdb_shelf_facts.py
"""

import duckdb
import json
from datetime import datetime, timezone
from pathlib import Path

# DuckDB database file
DB_PATH = Path("shelf_facts.duckdb")

# Pilot crops for CITE
INSUMOS_PILOTO = ["quinua", "palto", "espárrago", "mango", "arándano"]

# Sample stores (from tiendas.xlsx)
TIENDAS_MUESTRA = [
    {"id": 1, "nombre": "Plaza Vea", "país": "PE"},
    {"id": 2, "nombre": "Tottus", "país": "PE"},
    {"id": 3, "nombre": "Wong", "país": "PE"},
]


def create_schema():
    """Create shelf_facts_quarterly table."""
    print("\n🗄️  Creating shelf_facts_quarterly schema...")

    conn = duckdb.connect(str(DB_PATH))

    # Drop existing table (fresh start for testing)
    conn.execute("DROP TABLE IF EXISTS shelf_facts_quarterly")

    # Create main table
    conn.execute("""
        CREATE TABLE shelf_facts_quarterly (
            year_quarter VARCHAR NOT NULL,
            insumo VARCHAR NOT NULL,
            tienda_id INTEGER NOT NULL,
            producto_ean VARCHAR NOT NULL,
            precio_promedio DECIMAL(10, 2),
            precio_min DECIMAL(10, 2),
            precio_max DECIMAL(10, 2),
            stock_promedio DECIMAL(10, 2),
            promociones_count INTEGER DEFAULT 0,
            last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (year_quarter, insumo, tienda_id, producto_ean)
        )
    """)

    # Create indexes for fast queries
    conn.execute("""
        CREATE INDEX idx_shelf_facts_insumo_quarter
        ON shelf_facts_quarterly (insumo, year_quarter)
    """)

    conn.execute("""
        CREATE INDEX idx_shelf_facts_tienda_quarter
        ON shelf_facts_quarterly (tienda_id, year_quarter)
    """)

    print("✅ shelf_facts_quarterly created with indexes")
    conn.close()


def populate_dummy_data():
    """Insert dummy data for Q2 2026 (June) and Q3 2026 (Sept)."""
    print("\n📊 Populating dummy data...")

    conn = duckdb.connect(str(DB_PATH))

    row_count = 0

    # Sample EANs for each crop
    sample_products = {
        "quinua": ["7501234567890", "7501234567891", "7501234567892"],
        "palto": ["7502111111111", "7502111111112"],
        "espárrago": ["7503222222221", "7503222222222"],
        "mango": ["7504333333331", "7504333333332", "7504333333333"],
        "arándano": ["7505444444441", "7505444444442"],
    }

    # Quarters to populate
    quarters = ["2026Q2", "2026Q3"]

    # Sample prices per insumo (realistic ranges)
    price_ranges = {
        "quinua": {"min": 3.50, "max": 5.50, "avg": 4.50},
        "palto": {"min": 8.00, "max": 12.00, "avg": 10.00},
        "espárrago": {"min": 5.00, "max": 8.00, "avg": 6.50},
        "mango": {"min": 2.00, "max": 4.00, "avg": 3.00},
        "arándano": {"min": 12.00, "max": 18.00, "avg": 15.00},
    }

    for quarter in quarters:
        for insumo in INSUMOS_PILOTO:
            for tienda in TIENDAS_MUESTRA:
                for ean in sample_products[insumo]:
                    # Add some variance quarter-over-quarter
                    prices = price_ranges[insumo]

                    # Q3 slightly higher than Q2 (seasonal)
                    if quarter == "2026Q3":
                        offset = 1.05  # 5% increase
                    else:
                        offset = 1.0

                    precio_min = prices["min"] * offset
                    precio_max = prices["max"] * offset
                    precio_promedio = prices["avg"] * offset

                    conn.execute("""
                        INSERT INTO shelf_facts_quarterly
                        (year_quarter, insumo, tienda_id, producto_ean,
                         precio_promedio, precio_min, precio_max,
                         stock_promedio, promociones_count, last_update)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        quarter,
                        insumo,
                        tienda["id"],
                        ean,
                        round(precio_promedio, 2),
                        round(precio_min, 2),
                        round(precio_max, 2),
                        100 + (hash(ean) % 200),  # Stock 100-300
                        hash(ean) % 5,  # 0-4 promotions
                        datetime.now(timezone.utc),
                    ))
                    row_count += 1

    conn.commit()
    print(f"✅ Inserted {row_count} rows across {len(quarters)} quarters")

    # Show summary
    print("\n📋 Data summary:")
    summary = conn.execute("""
        SELECT
            year_quarter,
            COUNT(DISTINCT insumo) as unique_crops,
            COUNT(DISTINCT tienda_id) as unique_stores,
            COUNT(*) as total_products,
            ROUND(AVG(precio_promedio), 2) as avg_price
        FROM shelf_facts_quarterly
        GROUP BY year_quarter
        ORDER BY year_quarter
    """).fetchall()

    for row in summary:
        quarter, crops, stores, products, avg_price = row
        print(f"  {quarter}: {crops} crops × {stores} stores, {products} products, avg price S/. {avg_price}")

    conn.close()


def verify_schema():
    """Verify DuckDB file and schema are correct."""
    print("\n✅ Verification:")

    conn = duckdb.connect(str(DB_PATH))

    # Get table info
    tables = conn.execute("SELECT table_name FROM duckdb_tables()").fetchall()
    print(f"   Tables: {[t[0] for t in tables]}")

    # Get indexes (if available)
    try:
        indexes = conn.execute("SELECT index_name FROM duckdb_indexes()").fetchall()
        if indexes:
            print(f"   Indexes: {[idx[0] for idx in indexes]}")
    except Exception:
        print(f"   Indexes: [built-in]")

    # Get table schema
    schema = conn.execute("DESCRIBE shelf_facts_quarterly").fetchall()
    print(f"   Columns: {len(schema)}")
    for col_name, col_type, *rest in schema:
        print(f"     - {col_name}: {col_type}")

    # Get row count
    row_count = conn.execute("SELECT COUNT(*) FROM shelf_facts_quarterly").fetchone()[0]
    print(f"   Total rows: {row_count}")

    # Sample data
    print("\n📊 Sample row:")
    sample = conn.execute("""
        SELECT * FROM shelf_facts_quarterly LIMIT 1
    """).fetchone()
    if sample:
        schema_dict = {col[0]: sample[i] for i, col in enumerate(schema)}
        for key, val in schema_dict.items():
            print(f"     {key}: {val}")

    conn.close()


def main():
    """Initialize DuckDB shelf_facts database."""
    print("=" * 70)
    print(" 🦆 S3.4 DUCKDB SHELF_FACTS INITIALIZATION")
    print("=" * 70)

    print(f"\n📍 Database: {DB_PATH.absolute()}")
    print(f"   Size (before): {DB_PATH.stat().st_size if DB_PATH.exists() else 0} bytes")

    # Step 1: Create schema
    create_schema()

    # Step 2: Populate dummy data
    populate_dummy_data()

    # Step 3: Verify
    verify_schema()

    print(f"\n   Size (after): {DB_PATH.stat().st_size} bytes")

    print("\n" + "=" * 70)
    print(" ✅ SHELF_FACTS READY")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Run motor de tendencias:")
    print("     python scripts/test_motor_tendencias.py")
    print("\n  2. Or integrate into job_mim_etl for nightly runs")
    print("=" * 70)


if __name__ == "__main__":
    main()
