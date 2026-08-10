#!/usr/bin/env python3
"""
S3 Bloque A Test: Validate Procrastinate worker + WebSocket events.

This script:
1. Creates eventos_job table if needed
2. Lists Procrastinate system tables
3. Shows next steps for testing

Usage:
    python scripts/test_bloque_a.py
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not configured in .env")
    sys.exit(1)


def setup_database():
    """Create eventos_job table if it doesn't exist."""
    print("\n🗄️  Setting up database schema...")
    try:
        import psycopg
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS eventos_job (
                        event_id BIGSERIAL PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        job_id BIGINT,
                        evento VARCHAR(50) NOT NULL,
                        data_json JSONB DEFAULT '{}',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        CONSTRAINT evento_valid CHECK (evento IN ('created', 'started', 'progress', 'completed', 'failed'))
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_eventos_job_run_id_timestamp
                        ON eventos_job (run_id, created_at DESC)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_eventos_job_job_id
                        ON eventos_job (job_id)
                """)
                conn.commit()
                print("✅ eventos_job table ready")
    except Exception as e:
        print(f"❌ Database setup error: {e}")
        raise


def list_tables():
    """List all public tables."""
    print("\n📊 Database tables:")
    try:
        import psycopg
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cur.fetchall()
                if tables:
                    for (table_name,) in tables:
                        print(f"   ✅ {table_name}")
                    print(f"\n   Total: {len(tables)} tables")
                else:
                    print("   ⚠️  No tables found")
    except Exception as e:
        print(f"❌ Error: {e}")


def list_procrastinate_tables():
    """List Procrastinate system tables."""
    print("\n📋 Procrastinate system tables:")
    try:
        import psycopg
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name LIKE 'procrastinate%'
                    ORDER BY table_name
                """)
                tables = cur.fetchall()
                if tables:
                    for (table_name,) in tables:
                        print(f"   ✅ {table_name}")
                        # Count jobs in each table
                        if table_name == "procrastinate_jobs":
                            cur.execute("SELECT COUNT(*) FROM procrastinate_jobs")
                            count = cur.fetchone()[0]
                            print(f"      └─ Jobs in queue: {count}")
                else:
                    print("   ⚠️  No Procrastinate tables (will be created on first worker run)")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run full test suite."""
    print("=" * 70)
    print(" 🧪 S3 BLOQUE A TEST: Procrastinate Worker + WebSocket Events")
    print("=" * 70)

    try:
        # Step 1: Setup database
        setup_database()

        # Step 2: List existing tables
        list_tables()

        # Step 3: List Procrastinate tables
        list_procrastinate_tables()

        # Step 4: Show next steps
        print("\n" + "=" * 70)
        print(" ✅ BLOQUE A READY TO TEST")
        print("=" * 70)
        print("\n📝 Next steps:")
        print("\n   1️⃣  Start the API server (Terminal 1):")
        print("      python -m uvicorn api.main:app --reload --port 8000")
        print("")
        print("   2️⃣  Start the worker (Terminal 2):")
        print("      python scripts/start_worker.py")
        print("")
        print("   3️⃣  Run test jobs:")
        print("      python scripts/test_job.py")
        print("")
        print("   4️⃣  Monitor events:")
        print("      SELECT * FROM eventos_job ORDER BY created_at;")
        print("")
        print("   5️⃣  Test WebSocket (JavaScript/Vue3):")
        print("      ws = new WebSocket('ws://localhost:8000/ws/run/test_run_1')")
        print("      ws.onmessage = e => console.log(JSON.parse(e.data))")
        print("")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
