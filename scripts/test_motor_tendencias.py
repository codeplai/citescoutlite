#!/usr/bin/env python3
"""
S3 Bloque B Test: Validate motor_tendencias_duckdb + tendencias_insumo storage.

Workflow:
1. Initialize shelf_facts.duckdb with dummy data
2. Calculate trends using motor_tendencias_duckdb
3. Save trends to PostgreSQL tendencias_insumo
4. Verify full lifecycle

Usage:
    python scripts/test_motor_tendencias.py
"""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not configured in .env")
    sys.exit(1)


def step1_setup_duckdb():
    """Step 1: Initialize DuckDB if needed."""
    print("\n" + "=" * 70)
    print(" STEP 1: Setup DuckDB")
    print("=" * 70)

    db_path = Path("shelf_facts.duckdb")

    if db_path.exists():
        print(f"✅ DuckDB already exists: {db_path}")
        return True

    print("📝 Initializing DuckDB...")
    try:
        # Import and run init script
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/init_duckdb_shelf_facts.py"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print(result.stdout)
            return True
        else:
            print(f"❌ Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error running init script: {e}")
        return False


def step2_create_table():
    """Step 2: Create tendencias_insumo table if needed."""
    print("\n" + "=" * 70)
    print(" STEP 2: Create tendencias_insumo table")
    print("=" * 70)

    try:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tendencias_insumo (
                    tendencia_id BIGSERIAL PRIMARY KEY,
                    insumo VARCHAR(100) NOT NULL,
                    year_quarter VARCHAR(8) NOT NULL,
                    precio_trend DECIMAL(10, 2),
                    precio_promedio DECIMAL(10, 2),
                    marcas_nuevas INTEGER DEFAULT 0,
                    marcas_salidas INTEGER DEFAULT 0,
                    volatilidad DECIMAL(10, 4),
                    promocion_pct DECIMAL(10, 2),
                    total_products INTEGER DEFAULT 0,
                    calculado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    CONSTRAINT tendencias_unique UNIQUE (insumo, year_quarter)
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_tendencias_insumo_quarter
                    ON tendencias_insumo (insumo, year_quarter)
            """)
            conn.commit()
            print("✅ tendencias_insumo table ready")
            conn.close()
            return True
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False


def step3_calculate_trends():
    """Step 3: Calculate trends from DuckDB."""
    print("\n" + "=" * 70)
    print(" STEP 3: Calculate trends")
    print("=" * 70)

    try:
        from adaptadores.motor_tendencias_duckdb import MotorTendenciasDuckDB

        motor = MotorTendenciasDuckDB("shelf_facts.duckdb")

        # Calculate trends for all ingredients
        print("🔄 Calculating trends...")
        tendencias = motor.calcular_todas_tendencias(ano_base=2026)

        if not tendencias:
            print("⚠️  No trends calculated")
            return None

        print(f"\n✅ Calculated {len(tendencias)} trends:")
        print("-" * 70)

        for tendencia in tendencias:
            print(f"\n📊 {tendencia['insumo'].upper()} ({tendencia['year_quarter']})")
            print(f"   Precio: S/. {tendencia['precio_promedio']} (cambio: {tendencia['precio_trend']:+.1f}%)")
            print(f"   Marcas: {tendencia['marcas_nuevas']} nuevas, {tendencia['marcas_salidas']} salidas")
            print(f"   Stock volatilidad: {tendencia['volatilidad']:.3f} (CV)")
            print(f"   Con promoción: {tendencia['promocion_pct']:.1f}%")
            print(f"   Total productos: {tendencia['total_products']}")

        motor.cerrar()
        return tendencias

    except Exception as e:
        print(f"❌ Error calculating trends: {e}")
        import traceback
        traceback.print_exc()
        return None


def step4_save_trends(tendencias):
    """Step 4: Save trends to PostgreSQL."""
    print("\n" + "=" * 70)
    print(" STEP 4: Save trends to PostgreSQL")
    print("=" * 70)

    if not tendencias:
        print("⚠️  No trends to save")
        return False

    try:
        from adaptadores.repositorio_tendencias import RepositorioTendencias

        repo = RepositorioTendencias(DATABASE_URL)

        print("💾 Saving trends...")
        saved_count = repo.guardar_tendencias_batch(tendencias)

        print(f"✅ Saved {saved_count}/{len(tendencias)} trends")
        return saved_count > 0

    except Exception as e:
        print(f"❌ Error saving trends: {e}")
        import traceback
        traceback.print_exc()
        return False


def step5_verify():
    """Step 5: Verify data in PostgreSQL."""
    print("\n" + "=" * 70)
    print(" STEP 5: Verify in PostgreSQL")
    print("=" * 70)

    try:
        import psycopg
        conn = psycopg.connect(DATABASE_URL)

        with conn.cursor() as cur:
            # Count trends
            cur.execute("SELECT COUNT(*) FROM tendencias_insumo")
            total_count = cur.fetchone()[0]
            print(f"📊 Total trends in DB: {total_count}")

            # Show latest by quarter
            cur.execute("""
                SELECT
                    insumo, year_quarter,
                    precio_promedio, precio_trend,
                    marcas_nuevas, volatilidad, promocion_pct
                FROM tendencias_insumo
                ORDER BY calculado_en DESC
                LIMIT 5
            """)

            print("\n📋 Latest trends:")
            print("-" * 70)
            for row in cur.fetchall():
                (insumo, quarter, precio, trend, marcas, vol, promo) = row
                print(f"  {insumo:15} {quarter}  S/.{precio:6.2f}  {trend:+5.1f}%  "
                      f"📦{marcas}  σ={vol:.3f}  promo={promo:.1f}%")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Error verifying: {e}")
        return False


def main():
    """Run full test suite."""
    print("=" * 70)
    print(" 🧪 S3 BLOQUE B TEST: Motor Tendencias + PostgreSQL Storage")
    print("=" * 70)

    # Step 1: Setup DuckDB
    if not step1_setup_duckdb():
        print("\n❌ Setup failed at DuckDB initialization")
        sys.exit(1)

    # Step 2: Create PostgreSQL table
    if not step2_create_table():
        print("\n❌ Setup failed at table creation")
        sys.exit(1)

    # Step 3: Calculate trends
    tendencias = step3_calculate_trends()
    if tendencias is None:
        print("\n❌ Calculation failed")
        sys.exit(1)

    # Step 4: Save to PostgreSQL
    if not step4_save_trends(tendencias):
        print("\n❌ Save failed")
        sys.exit(1)

    # Step 5: Verify
    if not step5_verify():
        print("\n⚠️  Verification had issues")

    print("\n" + "=" * 70)
    print(" ✅ BLOQUE B VALIDATION COMPLETE")
    print("=" * 70)
    print("\n📝 Next steps:")
    print("   1. Integrate motor_tendencias into job_mim_etl (config/procrastinate_config.py)")
    print("   2. Test: Run job_mim_etl and verify eventos_job + tendencias_insumo")
    print("   3. Create API endpoint to expose trends: GET /tendencias/{insumo}")
    print("=" * 70)


if __name__ == "__main__":
    main()
