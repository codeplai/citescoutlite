#!/usr/bin/env python3
"""
S3.9 Test P10: Validate MIM degraded (2-3 quarters) instead of full 8.

P10 = Market Intelligence Panel (panel de inteligencia de mercado)
Degraded = Menor histórico (2-3 trimestres en S3 vs 8+ en S4+)

Tests:
1. Histórico existe: Q2 2026, Q3 2026 (+ Q1 si aplica)
2. % cambio calculable y verificable
3. Marcas nuevas/salidas son números
4. Volatilidad es CV válido [0, ∞)
5. Todas las 5 categorías piloto representadas
6. P10 está VERDE (funcional) pero DEGRADADO
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not configured in .env")
    sys.exit(1)


def check_quarters():
    """Test 1: Verify available quarters in DuckDB."""
    print("\n" + "=" * 70)
    print(" TEST 1: Available Quarters")
    print("=" * 70)

    try:
        from adaptadores.motor_tendencias_duckdb import MotorTendenciasDuckDB

        motor = MotorTendenciasDuckDB("shelf_facts.duckdb")

        quarters_by_crop = {}
        for crop in ["quinua", "palto", "espárrago", "mango", "arándano"]:
            quarters = motor.get_available_quarters(crop)
            quarters_by_crop[crop] = quarters
            print(f"  {crop:12}: {quarters}")

        motor.cerrar()

        # Verify we have at least 2 quarters
        for crop, quarters in quarters_by_crop.items():
            assert len(quarters) >= 2, f"{crop} has only {len(quarters)} quarter(s)"

        print(f"\n✅ All crops have >= 2 quarters")
        print(f"✅ TEST 1 PASSED")

        return quarters_by_crop

    except Exception as e:
        print(f"❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_trend_calculations(quarters_by_crop):
    """Test 2: Verify trend calculations produce valid metrics."""
    print("\n" + "=" * 70)
    print(" TEST 2: Trend Calculations")
    print("=" * 70)

    try:
        from adaptadores.motor_tendencias_duckdb import MotorTendenciasDuckDB

        motor = MotorTendenciasDuckDB("shelf_facts.duckdb")

        all_trends = motor.calcular_todas_tendencias(ano_base=2026)

        print(f"✅ Calculated trends for {len(all_trends)} crops")

        for tendencia in all_trends:
            crop = tendencia["insumo"]
            quarter = tendencia["year_quarter"]
            trend_pct = tendencia["precio_trend"]
            vol = tendencia["volatilidad"]
            marcas_new = tendencia["marcas_nuevas"]
            marcas_old = tendencia["marcas_salidas"]
            promo_pct = tendencia["promocion_pct"]

            print(f"\n  {crop.upper()} ({quarter})")
            print(f"    Precio trend: {trend_pct:+.2f}%")
            print(f"    Volatilidad: {vol:.4f} (CV)")
            print(f"    Marcas nuevas/salidas: {marcas_new}/{marcas_old}")
            print(f"    Con promoción: {promo_pct:.1f}%")

            # Validations
            assert isinstance(trend_pct, (int, float)), "Precio trend should be number"
            assert isinstance(vol, (int, float)), "Volatilidad should be number"
            assert vol >= 0, "Volatilidad (CV) should be >= 0"
            assert isinstance(marcas_new, int), "Marcas nuevas should be int"
            assert isinstance(marcas_old, int), "Marcas salidas should be int"
            assert isinstance(promo_pct, (int, float)), "Promo % should be number"
            assert 0 <= promo_pct <= 100, "Promo % should be 0-100"

        motor.cerrar()

        print(f"\n✅ All metrics are valid and non-NaN")
        print(f"✅ TEST 2 PASSED")

        return all_trends

    except Exception as e:
        print(f"❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_postgres_storage(all_trends):
    """Test 3: Verify trends are stored in PostgreSQL."""
    print("\n" + "=" * 70)
    print(" TEST 3: PostgreSQL Storage")
    print("=" * 70)

    try:
        import psycopg

        conn = psycopg.connect(DATABASE_URL)

        with conn.cursor() as cur:
            # Count tendencias
            cur.execute("SELECT COUNT(*) FROM tendencias_insumo")
            count = cur.fetchone()[0]
            print(f"✅ Stored {count} trends in PostgreSQL")

            # Verify each crop
            for crop in ["quinua", "palto", "espárrago", "mango", "arándano"]:
                cur.execute(
                    "SELECT COUNT(*) FROM tendencias_insumo WHERE insumo = %s",
                    (crop,)
                )
                crop_count = cur.fetchone()[0]
                print(f"   {crop}: {crop_count} record(s)")

                assert crop_count > 0, f"No trends found for {crop}"

            # Check latest quarter
            cur.execute("""
                SELECT DISTINCT year_quarter
                FROM tendencias_insumo
                ORDER BY year_quarter DESC LIMIT 1
            """)
            result = cur.fetchone()
            latest_quarter = result[0] if result else None
            if latest_quarter:
                cur.execute("""
                    SELECT COUNT(*) FROM tendencias_insumo
                    WHERE year_quarter = %s
                """, (latest_quarter,))
                latest_count = cur.fetchone()[0]
                print(f"\n✅ Latest quarter {latest_quarter}: {latest_count} trends")

        conn.close()

        print(f"\n✅ TEST 3 PASSED")

        return True

    except Exception as e:
        print(f"❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_p10_metrics():
    """Test 4: P10 Panel is GREEN and DEGRADED."""
    print("\n" + "=" * 70)
    print(" TEST 4: P10 Panel Status")
    print("=" * 70)

    try:
        import duckdb
        import psycopg

        # DuckDB has the full historical data
        duck_conn = duckdb.connect("shelf_facts.duckdb")
        result = duck_conn.execute("""
            SELECT
                COUNT(DISTINCT insumo) as num_crops,
                COUNT(DISTINCT year_quarter) as num_quarters,
                MIN(year_quarter) as first_quarter,
                MAX(year_quarter) as latest_quarter
            FROM shelf_facts_quarterly
        """).fetchone()

        if result:
            num_crops, num_quarters, first_q, latest_q = result

            print(f"\nP10 Status (from DuckDB historical data):")
            print(f"  Crops: {num_crops}/5 piloto")
            print(f"  Quarters available: {num_quarters}")
            print(f"  Range: {first_q} → {latest_q}")

            # P10 is GREEN if:
            assert num_crops >= 5, "Should have >= 5 crops"
            assert num_quarters >= 2, "Should have >= 2 quarters"

            # P10 is DEGRADED if < 8 quarters
            if num_quarters < 8:
                print(f"\n⚠️  DEGRADED MODE: Only {num_quarters} quarter(s) available")
                print(f"   (Full P10 requires 8+ quarters)")
                print(f"   Status: 🟢 GREEN (funcional pero degradado)")
                print(f"   SLA: Available for basic market trends")
                print(f"   Next: Full P10 in S4 when real data accumulates")
            else:
                print(f"\n✅ FULL P10: {num_quarters} quarters available")

            # Verify PostgreSQL has latest calculation
            pg_conn = psycopg.connect(DATABASE_URL)
            with pg_conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM tendencias_insumo")
                pg_count = cur.fetchone()[0]
                print(f"\n✅ Latest trends cached in PostgreSQL: {pg_count} crops")
            pg_conn.close()

            print(f"\n✅ P10 is operative and ready for S3")
            print(f"✅ TEST 4 PASSED")

            duck_conn.close()
            return True

    except Exception as e:
        print(f"❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all P10 validation tests."""
    print("=" * 70)
    print(" 🧪 S3.9 TEST P10 DEGRADADA (2-3 Trimestres)")
    print("=" * 70)
    print(f"\nTimestamp: {datetime.now(timezone.utc).isoformat()}")

    # Test 1: Quarters
    quarters = check_quarters()
    if quarters is None:
        sys.exit(1)

    # Test 2: Calculations
    trends = check_trend_calculations(quarters)
    if trends is None:
        sys.exit(1)

    # Test 3: Storage
    if not check_postgres_storage(trends):
        sys.exit(1)

    # Test 4: P10 Status
    if not check_p10_metrics():
        sys.exit(1)

    print("\n" + "=" * 70)
    print(" ✅ S3.9 P10 VALIDATION COMPLETE")
    print("=" * 70)
    print("""
P10 (Market Intelligence Panel) Status:
  ✅ Operational: YES
  🟢 Color: GREEN
  ⚠️  Degraded: YES (2-3 trimestres en S3)
  📈 Capacity: Basic market trends (price, brands, promotions)
  ⏳ Full P10: Available in S4 when 8+ quarters accumulated

Next steps:
  1. Dashboard P10 widget can now show:
     - Price trends (%) for each crop
     - New/lost brand counts
     - Volatility indicators
     - Promotion coverage %
  2. API endpoint: GET /tendencias/{insumo}
  3. Export: Download P10 reports for stakeholders
""")
    print("=" * 70)


if __name__ == "__main__":
    main()
