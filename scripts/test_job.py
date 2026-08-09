#!/usr/bin/env python3
"""Test enqueuing a job to Procrastinate."""

import asyncio
import logging
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv(".env")

from config.procrastinate_config import app, hello_world, generate_report


def main():
    """Enqueue test jobs."""

    logger.info("📨 Enqueueing test jobs...")

    try:
        with app.open():
            # Job 1: Hello world
            job1 = hello_world.defer(name="AgroScout MVP")
            logger.info(f"✅ Job 1 enqueued (ID: {job1.id})")

            # Job 2: Generate report (stub)
            job2 = generate_report.defer(consulta_id=1, etapa="3")
            logger.info(f"✅ Job 2 enqueued (ID: {job2.id})")

            logger.info("")
            logger.info("📝 Next steps:")
            logger.info("  1. Run: python scripts/start_worker.py")
            logger.info("  2. Worker will execute jobs automatically")
            logger.info("  3. Check Supabase > SQL Editor for procrastinate_jobs table")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
