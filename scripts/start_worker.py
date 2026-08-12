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

# Antes de asyncio.run(), que es donde nace el bucle. En Windows el policy por
# defecto es el Proactor y psycopg en asincrono no puede usarlo: sin esto el
# worker corre, pero ni el propio Procrastinate ni eventos_job pueden escribir.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from adaptadores.bucle_asincrono import asegurar_bucle_compatible
asegurar_bucle_compatible()

# La consola de Windows viene en cp1252 y los emojis de estos mensajes la
# hacen lanzar UnicodeEncodeError por cada linea: el worker seguia vivo, pero
# el log quedaba sepultado bajo tracebacks de logging que no eran el problema.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

# Importar los modulos de los jobs es obligatorio, no decorativo: una tarea de
# Procrastinate se registra cuando se **ejecuta** su decorador, es decir cuando
# se importa el modulo que la define. Este proceso solo importaba
# procrastinate_config, donde viven job_agente_run, job_mim_etl y
# job_informe_pdf, pero no los dos periodicos, que estan en modulos aparte.
#
# Resultado hasta ahora: el worker arrancaba anunciando
# "No periodic task found, periodic deferrer will not run", y **ni el job de
# alertas de las 03:00 ni el de promocion de las 04:00 se dispararon jamas**.
# S7 arreglo el import roto que tenian dentro; faltaba que alguien los cargara.
import config.job_alert_ingest  # noqa: F401  (registra el periodico de las 03:00)
import config.job_promotion_auto  # noqa: F401  (registra el de las 04:00)


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
    """Comprueba que se llega a la base y que el esquema de Procrastinate esta.

    Lo que habia aqui estaba escrito contra asyncpg: `app.connector()` como si
    fuera invocable —es un atributo, un PsycopgConnector— y `conn.fetchval()`,
    que es API de asyncpg y no de psycopg. Reventaba con TypeError antes de
    llegar al worker.

    Se usa psycopg directamente en vez del connector de Procrastinate: es lo
    que usa el resto del proyecto, y asi esta comprobacion no depende de la
    forma interna del connector, que ya nos ha cambiado una vez.
    """
    logger.info("🗄️  Verificando el esquema...")

    import psycopg

    async with await psycopg.AsyncConnection.connect(
            os.getenv("DATABASE_URL"), connect_timeout=15) as conn:
        cur = await conn.execute("select version()")
        version = (await cur.fetchone())[0]
        logger.info(f"   PostgreSQL: {version.split(',')[0]}")

        # El esquema de Procrastinate no se crea solo al abrir la app: hay que
        # llamar a apply_schema(), y por creerlo automatico el worker de S3 se
        # quedo sin tablas donde encolar (lo arreglo S7 en
        # scripts/init_procrastinate.py). Si faltan, mejor decirlo aqui.
        cur = await conn.execute(
            "select count(*) from pg_tables "
            " where schemaname = 'public' and tablename like 'procrastinate%'")
        tablas = (await cur.fetchone())[0]

    if tablas == 0:
        raise RuntimeError(
            "No hay tablas procrastinate_* en la base. Aplica el esquema con:\n"
            "    uv run python scripts/init_procrastinate.py")

    logger.info(f"   Esquema de Procrastinate: {tablas} tablas")


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

        # open() es el context manager sincrono; el asincrono es open_async().
        # Con el primero, `async with` lanzaba TypeError antes de abrir
        # siquiera la conexion.
        async with app.open_async():
            await setup_database()

            # Setup event callbacks for S3.2 (job progress tracking)
            # S3.2: los eventos de ciclo de vida ya no son callbacks del app
            # (esa API no existe en procrastinate 3.9) sino un middleware que
            # se pasa al worker, unas lineas mas abajo.
            from config.procrastinate_config import middleware_eventos_job

            logger.info(f"\n👂 Worker listening for jobs...")
            logger.info(f"   Press Ctrl+C to stop gracefully")
            logger.info("=" * 70 + "\n")

            # `app.worker_defaults(...)` no existe en procrastinate 3.9: es la
            # misma clase de error que S7 encontro en procrastinate_config.py
            # (`max_attempts` y `schedule_in`). Aqui reventaba con
            # `AttributeError` dentro del try, el except lo registraba y el
            # proceso salia a los dos segundos. Por eso `procrastinate_workers`
            # y `procrastinate_jobs` estaban a 0 y los dos jobs periodicos
            # —alertas a las 03:00 y promocion a las 04:00— **nunca llegaron a
            # dispararse**: no habia worker que los atendiera.
            #
            # Los reintentos ya no se configuran aqui sino por tarea, con
            # `retry=` en el decorador @app.task.
            await app.run_worker_async(
                queues=queues,
                concurrency=concurrency,
                # S3.2: cada job deja started/completed/failed en eventos_job.
                worker_middleware=[middleware_eventos_job],
                # El worker instala sus propios manejadores de senal y ya
                # tenemos los nuestros unas lineas mas arriba; dos juegos
                # compitiendo hacen que Ctrl+C no cierre limpio.
                install_signal_handlers=False,
            )

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
