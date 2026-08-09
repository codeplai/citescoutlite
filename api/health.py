"""Health check endpoint for AgroScout."""

import os
from datetime import datetime
from fastapi import APIRouter, HTTPException
import psycopg
from dotenv import load_dotenv

load_dotenv(".env")

router = APIRouter()


def test_supabase_connection():
    """Test Postgres/Supabase connection."""
    try:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            return {"status": "error", "message": "DATABASE_URL not configured"}

        conn = psycopg.connect(db_url, connect_timeout=5)
        cursor = conn.cursor()
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        return {"status": "ok", "version": version[:50]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def test_redis():
    """Test Redis connection (if enabled)."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return {"status": "skipped", "message": "REDIS_URL not configured"}

    try:
        import redis
        r = redis.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "warning", "message": str(e)}


def check_duckdb():
    """Check if DuckDB file exists and is readable."""
    try:
        import duckdb
        db_path = "data/shelf_facts.duckdb"
        if not os.path.exists(db_path):
            return {"status": "warning", "message": "DuckDB file not found"}

        db = duckdb.connect(db_path)
        db.execute("SELECT 1").fetchall()
        db.close()
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/health")
async def health():
    """
    Health check endpoint that validates all critical components.

    Returns:
        - status: overall health (ok, degraded, error)
        - timestamp: when check was run
        - supabase: database connection status
        - redis: cache status (if configured)
        - duckdb: analytics DB status
        - components: detailed status of each
    """

    supabase_status = test_supabase_connection()
    redis_status = test_redis()
    duckdb_status = check_duckdb()

    # Determine overall status
    all_statuses = [supabase_status["status"], redis_status["status"], duckdb_status["status"]]
    if "error" in all_statuses:
        overall_status = "error"
    elif "warning" in all_statuses:
        overall_status = "degraded"
    else:
        overall_status = "ok"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "components": {
            "supabase": supabase_status,
            "redis": redis_status,
            "duckdb": duckdb_status,
        },
        "environment": {
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "app_db": os.getenv("APP_DB", "unknown"),
        }
    }


@router.get("/ready")
async def readiness():
    """Readiness probe for Kubernetes/orchestration."""
    health_data = await health()
    if health_data["status"] == "error":
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"ready": True}
