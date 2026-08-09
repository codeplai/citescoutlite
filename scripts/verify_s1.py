#!/usr/bin/env python3
"""Verify S1 setup: test Supabase, Redis, DuckDB, and FastAPI."""

import os
import sys
import time
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv(".env")

print("=" * 60)
print("  S1 SETUP VERIFICATION")
print("=" * 60)
print()

# 1. Test .env configuration
print("1️⃣  Checking .env configuration...")
required_vars = [
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SECRET_KEY",
    "DATABASE_URL",
    "HUAWEI_MAAS_API_KEY",
    "TAVILY_API_KEY",
]

missing = []
for var in required_vars:
    value = os.getenv(var)
    status = "✅" if value else "❌"
    print(f"  {status} {var}")
    if not value:
        missing.append(var)

if missing:
    print(f"\n⚠️  Missing: {', '.join(missing)}")
else:
    print("  ✅ All required variables configured")

print()

# 2. Test Supabase connection
print("2️⃣  Testing Supabase connection...")
try:
    import psycopg
    db_url = os.getenv("DATABASE_URL")
    conn = psycopg.connect(db_url, connect_timeout=5)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pg_tables WHERE schemaname='public'")
    table_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    print(f"  ✅ Connected to Supabase ({table_count} tables)")
except Exception as e:
    print(f"  ❌ Error: {e}")

print()

# 3. Test DuckDB
print("3️⃣  Testing DuckDB...")
try:
    import duckdb
    db_path = "data/shelf_facts.duckdb"
    if os.path.exists(db_path):
        db = duckdb.connect(db_path)
        result = db.execute("SELECT COUNT(*) FROM shelf_facts_quarterly").fetchall()
        db.close()
        print(f"  ✅ DuckDB ready ({db_path})")
    else:
        print(f"  ❌ DuckDB file not found: {db_path}")
except Exception as e:
    print(f"  ❌ Error: {e}")

print()

# 4. Test Redis (if configured)
print("4️⃣  Testing Redis...")
redis_url = os.getenv("REDIS_URL", "").strip()
if redis_url:
    try:
        import redis
        r = redis.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        print(f"  ✅ Redis connected")
    except Exception as e:
        print(f"  ⚠️  Redis not available (optional): {e}")
else:
    print(f"  ⏭️  Redis not configured (optional)")

print()

# 5. Test FastAPI (start in background)
print("5️⃣  Testing FastAPI...")
print("  Starting FastAPI server in background...")

# Start FastAPI in background
proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

# Wait for server to start
time.sleep(3)

try:
    response = requests.get("http://127.0.0.1:8000/health", timeout=5)
    if response.status_code == 200:
        data = response.json()
        print(f"  ✅ FastAPI running, health status: {data['status']}")
        print(f"     Components:")
        for comp, status in data.get("components", {}).items():
            comp_status = status.get("status", "unknown")
            print(f"       - {comp}: {comp_status}")
    else:
        print(f"  ❌ FastAPI error: {response.status_code}")
except Exception as e:
    print(f"  ⚠️  FastAPI not responding: {e}")

# Stop FastAPI
proc.terminate()
proc.wait(timeout=5)

print()
print("=" * 60)
print("  ✅ S1 SETUP VERIFICATION COMPLETE")
print("=" * 60)
print()
print("📝 Next steps:")
print("  1. Review any ❌ errors above")
print("  2. Run: python -m uvicorn api.main:app --reload")
print("  3. Open: http://localhost:8000/health")
print("  4. Proceed to S2: ETL and data migration")
