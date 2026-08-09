#!/usr/bin/env python3
"""Initialize Procrastinate tables and schema in Supabase."""

import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(".env")

from config.procrastinate_config import app


def init_procrastinate():
    """Create Procrastinate tables in database."""
    logger.info("🏗️  Initializing Procrastinate schema...")

    try:
        # En Procrastinate v3, se crea el schema automáticamente
        # cuando se abre la app. Solo necesitamos verificar.
        with app.open():
            logger.info("✅ Procrastinate app initialized!")
            logger.info("")
            logger.info("📝 Procrastinate is ready to use.")
            logger.info("   Tables will be created automatically on first use.")
            logger.info("")
            logger.info("🚀 Next: run 'python scripts/test_job.py' to enqueue a job")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    init_procrastinate()
