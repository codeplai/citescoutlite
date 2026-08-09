#!/usr/bin/env python3
"""Start Procrastinate worker to process jobs from queue."""

import os
import asyncio
import logging
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv(".env")

# Importar la app configurada
from config.procrastinate_config import app


async def main():
    """Start worker and listen for jobs."""

    logger.info("🚀 Starting Procrastinate worker...")
    logger.info(f"📍 Database: {os.getenv('DATABASE_URL', 'not configured').split('@')[1] if os.getenv('DATABASE_URL') else 'unknown'}")

    try:
        async with app.open():
            # Crear tabla de jobs si no existe
            async with app.connector() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS procrastinate_jobs (
                        id BIGSERIAL PRIMARY KEY,
                        queue_name TEXT DEFAULT 'default',
                        task_name TEXT NOT NULL,
                        lock TEXT,
                        args JSONB NOT NULL DEFAULT '[]',
                        kwargs JSONB NOT NULL DEFAULT '{}',
                        scheduled_at TIMESTAMP WITH TIME ZONE,
                        attempts INT DEFAULT 0,
                        max_attempts INT DEFAULT 3,
                        last_error TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        started_at TIMESTAMP WITH TIME ZONE,
                        finished_at TIMESTAMP WITH TIME ZONE
                    )
                """)
                logger.info("✅ Jobs table ready")

            # Iniciar worker
            logger.info("👂 Listening for jobs...")
            logger.info("Press Ctrl+C to stop")

            worker = app.worker_defaults(queues=["default"], concurrency=4)
            await worker.run()

    except KeyboardInterrupt:
        logger.info("⏹️ Worker stopped by user")
    except Exception as e:
        logger.error(f"❌ Worker error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
