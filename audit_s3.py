#!/usr/bin/env python3
"""S3 Audit: Review current DB state before implementing queue + worker."""

import os
from dotenv import load_dotenv
import psycopg

load_dotenv()
db_url = os.getenv('DATABASE_URL')

print("\n" + "="*70)
print(" 🔍 AUDITORÍA SEMANA 3: Estado Actual del Proyecto")
print("="*70)

if not db_url:
    print("❌ DATABASE_URL no configurada en .env")
    exit(1)

# Connect
try:
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            # 1. List tables
            print("\n📊 TABLAS EXISTENTES EN POSTGRES:")
            print("-" * 70)
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cur.fetchall()
            if tables:
                for (table_name,) in tables:
                    print(f"  ✅ {table_name}")
            else:
                print("  ⚠️  NO HAY TABLAS")

            # 2. Check Procrastinate tables
            print("\n📋 TABLAS DE PROCRASTINATE:")
            print("-" * 70)
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'procrastinate_jobs'
                )
            """)
            has_procrastinate = cur.fetchone()[0]
            if has_procrastinate:
                print("  ✅ procrastinate_jobs existe")
                cur.execute("SELECT COUNT(*) FROM procrastinate_jobs")
                job_count = cur.fetchone()[0]
                print(f"     └─ Jobs en cola: {job_count}")
            else:
                print("  ❌ procrastinate_jobs NO existe (necesita crearse)")

            # 3. Check if eventos_job table exists
            print("\n📌 TABLAS DE EVENTOS (para S3.2):")
            print("-" * 70)
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'eventos_job'
                )
            """)
            has_eventos = cur.fetchone()[0]
            if has_eventos:
                print("  ✅ eventos_job existe")
            else:
                print("  ❌ eventos_job NO existe (necesita crearse en 3.2)")

            # 4. Check DuckDB file
            print("\n🦆 DUCKDB:")
            print("-" * 70)
            import os.path
            duckdb_path = "shelf_facts.duckdb"
            if os.path.exists(duckdb_path):
                print(f"  ✅ {duckdb_path} existe")
                try:
                    import duckdb
                    conn_duck = duckdb.connect(duckdb_path)
                    cur_duck = conn_duck.cursor()
                    cur_duck.execute("SELECT name FROM duckdb_views() UNION ALL SELECT name FROM duckdb_tables()")
                    tables_duck = cur_duck.fetchall()
                    if tables_duck:
                        for (tbl,) in tables_duck:
                            print(f"     └─ {tbl}")
                    else:
                        print("     └─ Sin tablas aún")
                    conn_duck.close()
                except Exception as e:
                    print(f"     └─ ⚠️  Error leyendo DuckDB: {e}")
            else:
                print(f"  ❌ {duckdb_path} NO existe (necesita crearse en 3.4)")

            # 5. Check taxonomy table
            print("\n📚 TAXONOMÍA CITE (para S3.7):")
            print("-" * 70)
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'taxonomia_cite'
                )
            """)
            has_taxonomy = cur.fetchone()[0]
            if has_taxonomy:
                print("  ✅ taxonomia_cite existe")
                cur.execute("SELECT COUNT(*) FROM taxonomia_cite")
                count = cur.fetchone()[0]
                print(f"     └─ Registros: {count}")
            else:
                print("  ❌ taxonomia_cite NO existe (necesita crearse en 3.7)")

            # 6. Check tendencias table
            print("\n📈 TABLA TENDENCIAS (para S3.5):")
            print("-" * 70)
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'tendencias_insumo'
                )
            """)
            has_tendencias = cur.fetchone()[0]
            if has_tendencias:
                print("  ✅ tendencias_insumo existe")
                cur.execute("SELECT COUNT(*) FROM tendencias_insumo")
                count = cur.fetchone()[0]
                print(f"     └─ Registros: {count}")
            else:
                print("  ❌ tendencias_insumo NO existe (necesita crearse en 3.5)")

except Exception as e:
    print(f"\n❌ Error conectando a DB: {e}")
    import traceback
    traceback.print_exc()

# 7. Check Procrastinate config
print("\n⚙️  CONFIGURACIÓN PROCRASTINATE:")
print("-" * 70)
try:
    from config.procrastinate_config import app
    print(f"  ✅ config.procrastinate_config cargado")
    print(f"     └─ Tareas registradas: {list(app._tasks.keys())}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "="*70)
print(" ✅ Auditoría completada")
print("="*70 + "\n")
