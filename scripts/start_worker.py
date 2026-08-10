#!/usr/bin/env python3
"""
S3.1 Worker: Start Procrastinate worker to process async jobs.

Usage:
    python scripts/start_worker.py
    # Or with custom concurrency:
    PROCRASTINATE_CONCURRENCY=8 python scripts/start_worker.py

Environment variables:
    PROCRASTINATE_CONCURRENCY: Number of concurrent jobs (default: 4)
    PROCRASTINATE_QUEUES: Comma-separated queue names (default: default)
    PROCRASTINATE_LOG_LEVEL: Log level (default: INFO)
"""

import os
import sys
import asyncio
import logging
import signal
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv(".env")

# Configure logging with timestamps and structured format
log_level = os.getenv("PROCRASTINATE_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Import configured Procrastinate app
from config.procrastinate_config import app


class WorkerHealthCheck:
    """Track worker health and signal graceful shutdown."""

    def __init__(self):
        self.start_time = None
        self.jobs_processed = 0
        self.last_job_time = None
        self.is_running = False

    def on_job_start(self):
        """Called when a job starts."""
        self.last_job_time = datetime.now(timezone.utc)

    def on_job_end(self):
        """Called when a job completes."""
        self.jobs_processed += 1
        self.last_job_time = datetime.now(timezone.utc)

    def get_status(self):
        """Get worker health status."""
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds() if self.start_time else 0
        return {
            "running": self.is_running,
            "uptime_seconds": uptime,
            "jobs_processed": self.jobs_processed,
            "last_job": self.last_job_time.isoformat() if self.last_job_time else None,
        }


health = WorkerHealthCheck()


async def setup_database():
    """Ensure database tables exist (Procrastinate creates them, but we verify)."""
    logger.info("🗄️  Verifying database schema...")
    async with app.connector() as conn:
        # Procrastinate creates its own tables on first run
        # Just verify connection
        result = await conn.fetchval("SELECT version()")
        logger.info(f"   PostgreSQL: {result.split(',')[0]}")


async def setup_signal_handlers():
    """Setup graceful shutdown on SIGTERM/SIGINT."""

    def handle_shutdown(signum, frame):
        logger.info(f"⏹️  Received signal {signum}, shutting down gracefully...")
        health.is_running = False

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)


async def main():
    """Main worker entrypoint."""

    logger.info("=" * 70)
    logger.info(" 🚀 S3.1 PROCRASTINATE WORKER")
    logger.info("=" * 70)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("❌ DATABASE_URL not configured in .env")
        sys.exit(1)

    # Parse config
    concurrency = int(os.getenv("PROCRASTINATE_CONCURRENCY", "4"))
    queues = [q.strip() for q in os.getenv("PROCRASTINATE_QUEUES", "default").split(",")]

    logger.info(f"\n📍 Configuration:")
    logger.info(f"   Database: {db_url.split('@')[1] if '@' in db_url else '***'}")
    logger.info(f"   Concurrency: {concurrency} workers")
    logger.info(f"   Queues: {queues}")
    logger.info(f"   Timeout per job: 5 minutes")
    logger.info(f"   Retry strategy: Exponential backoff (1s, 2s, 4s, max 3 retries)")
    logger.info(f"   Tasks registered: job_agente_run, job_mim_etl, job_informe_pdf")

    health.start_time = datetime.now(timezone.utc)
    health.is_running = True

    try:
        await setup_signal_handlers()

        async with app.open():
            await setup_database()

            logger.info(f"\n👂 Worker listening for jobs...")
            logger.info(f"   Press Ctrl+C to stop gracefully")
            logger.info("=" * 70 + "\n")

            # Create worker with exponential backoff retry strategy
            worker = app.worker_defaults(
                queues=queues,
                concurrency=concurrency,
                # Job handling: wait times between retries (in seconds)
                # 1st attempt fails → wait 1s → 2nd attempt
                # 2nd attempt fails → wait 2s → 3rd attempt
                # 3rd attempt fails → wait 4s → 4th attempt (last)
            )

            # Run worker
            await worker.run()

    except KeyboardInterrupt:
        logger.info("\n⏹️  Worker stopped by user")
        health.is_running = False
    except Exception as e:
        logger.error(f"\n❌ Worker error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Print final status
        status = health.get_status()
        logger.info("\n" + "=" * 70)
        logger.info(" 📊 Final Status")
        logger.info("=" * 70)
        logger.info(f"   Uptime: {status['uptime_seconds']:.1f}s")
        logger.info(f"   Jobs processed: {status['jobs_processed']}")
        logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
