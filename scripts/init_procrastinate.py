#!/usr/bin/env python3
"""Initialize Procrastinate tables and schema in Supabase."""

import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(".env")

from config.procrastinate_config import app


def ya_aplicado() -> bool:
    """True si el schema de Procrastinate ya esta en la base."""
    import os
    import psycopg

    with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None,
                         connect_timeout=15) as conexion:
        return conexion.execute(
            "select to_regclass('public.procrastinate_jobs')").fetchone()[0] is not None


def init_procrastinate():
    """Create Procrastinate tables in database.

    Abrir la app NO crea el schema: hay que pedirlo con apply_schema(). Este
    script decia lo contrario y por eso terminaba en verde sin crear nada, con
    lo que el worker de S3 nunca tuvo donde encolar.

    apply_schema() tampoco es idempotente —revienta con DuplicateObject sobre el
    tipo procrastinate_job_status— asi que hay que mirar antes si ya esta.
    """
    logger.info("🏗️  Initializing Procrastinate schema...")

    if ya_aplicado():
        logger.info("✅ Procrastinate schema ya estaba aplicado. Nada que hacer.")
        return

    try:
        with app.open():
            app.schema_manager.apply_schema()
            logger.info("✅ Procrastinate schema applied!")
            logger.info("   Tablas: procrastinate_jobs, procrastinate_events,")
            logger.info("           procrastinate_periodic_defers, procrastinate_workers")
            logger.info("")
            logger.info("🚀 Next: run 'python scripts/test_job.py' to enqueue a job")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    init_procrastinate()
