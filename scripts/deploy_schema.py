#!/usr/bin/env python3
"""Deploy schema to Supabase database."""

import os
import psycopg
from dotenv import load_dotenv

def deploy_schema():
    load_dotenv(".env")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not found in .env")
        return False

    print("🔗 Connecting to Supabase...")

    try:
        # Conectar a Supabase
        conn = psycopg.connect(database_url)
        cursor = conn.cursor()

        # Leer el SQL con UTF-8 encoding
        with open("scripts/create_schema_s1.sql", "r", encoding="utf-8") as f:
            sql = f.read()

        # Ejecutar el SQL
        print("📝 Creating schema...")
        cursor.execute(sql)
        conn.commit()

        print("✅ Schema created successfully!")

        # Verificar tablas creadas
        cursor.execute("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        tables = cursor.fetchall()

        print("\n📋 Tables created:")
        for (table,) in tables:
            print(f"  - {table}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = deploy_schema()
    exit(0 if success else 1)
