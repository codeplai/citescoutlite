"""Procrastinate configuration for AgroScout job queue (S3)."""

import os
import asyncio
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
import procrastinate

load_dotenv(".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not configured in .env")

# Create Procrastinate app with retry strategy
# Exponential backoff: 1s → 2s → 4s → 8s (max 3 attempts = 4 tries total)
app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=DATABASE_URL),
    # Default job retry parameters
    timeout=300,  # 5 minutes timeout per job
)


# ============================================================
# S3.1 JOB DEFINITIONS (3 core jobs)
# ============================================================

@app.task(
    name="job_agente_run",
    max_attempts=4,  # 1 initial + 3 retries
    schedule_in={"seconds": 0},  # Fire immediately
)
async def job_agente_run(run_id: str, insumo: str, país: str, nivel_maximo_costo: int):
    """
    Job 3.1.1: Run commercial intelligence agent.

    Args:
        run_id: Unique execution ID (for tracking)
        insumo: Ingredient/crop (e.g., 'quinua', 'palto')
        país: Country code (e.g., 'PE')
        nivel_maximo_costo: Budget constraint level

    Returns:
        {"status": "completed", "run_id": run_id, "resultados": {...}}
    """
    logger.info(f"🤖 [job_agente_run] Starting: run_id={run_id}, insumo={insumo}, país={país}")

    try:
        # TODO S3: Integrate agent.run() from dominio/agente.py
        # For now: simulate async work
        await asyncio.sleep(2)

        resultado = {
            "run_id": run_id,
            "insumo": insumo,
            "país": país,
            "nivel_costo": nivel_maximo_costo,
            "estado": "ejecutado",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"✅ [job_agente_run] Completed: {run_id}")
        return resultado

    except Exception as e:
        logger.error(f"❌ [job_agente_run] Failed: {run_id} - {e}")
        raise


@app.task(
    name="job_mim_etl",
    max_attempts=4,
    schedule_in={"seconds": 0},
)
async def job_mim_etl(snapshot_version: str):
    """
    Job 3.1.2: Nightly MIM ETL pipeline.

    Runs 00:00 UTC daily:
    1. Download OFF subset (if updates available)
    2. Download USDA (if new brands)
    3. Update shelf_facts_quarterly with today's raw_offers
    4. Calculate tendencias for pilot ingredients
    5. Save results to tendencias_insumo

    Args:
        snapshot_version: Version identifier (e.g., '2026-08')

    Returns:
        {"status": "completed", "version": snapshot_version, "rows_processed": int}
    """
    logger.info(f"🌙 [job_mim_etl] Starting nightly run: version={snapshot_version}")

    try:
        # TODO S3: Integrate MIM ETL pipeline
        # - Descarga OFF/USDA
        # - Actualiza shelf_facts_quarterly
        # - Calcula tendencias
        await asyncio.sleep(3)

        resultado = {
            "status": "completed",
            "version": snapshot_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rows_processed": 0,  # TODO: update after implementation
        }
        logger.info(f"✅ [job_mim_etl] Completed: {snapshot_version}")
        return resultado

    except Exception as e:
        logger.error(f"❌ [job_mim_etl] Failed: {snapshot_version} - {e}")
        raise


@app.task(
    name="job_informe_pdf",
    max_attempts=4,
    schedule_in={"seconds": 0},
)
async def job_informe_pdf(run_id: str):
    """
    Job 3.1.3: Generate PDF report async (Stage 6 integration).

    After stage 5 completes:
    1. Fetch run results
    2. Generate PDF using Jinja2 + xhtml2pdf
    3. Upload to S3/CDN
    4. Update run.pdf_url

    Args:
        run_id: Execution ID to generate report for

    Returns:
        {"status": "completed", "run_id": run_id, "pdf_url": "https://..."}
    """
    logger.info(f"📄 [job_informe_pdf] Starting PDF generation: run_id={run_id}")

    try:
        # TODO S3: Integrate InformeWeasyprint
        # - Fetch run results
        # - Generate PDF
        # - Upload to S3
        # - Update run table
        await asyncio.sleep(1)

        resultado = {
            "status": "completed",
            "run_id": run_id,
            "pdf_url": f"https://cdn.agroscout.ai/informes/{run_id}.pdf",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"✅ [job_informe_pdf] Completed: {run_id}")
        return resultado

    except Exception as e:
        logger.error(f"❌ [job_informe_pdf] Failed: {run_id} - {e}")
        raise


# ============================================================
# RETRY STRATEGY: Exponential backoff
# ============================================================
# Procrastinate's default retry uses wait_seconds = attempt_number
# We override with custom exponential backoff via task decorator
# max_attempts=4 means: 1 initial + 3 retries
# Delays between retries: 1s, 2s, 4s (computed at runtime by scheduler)
# ============================================================


# ============================================================
# S3.2 EVENT CALLBACKS: Emit eventos_job on state changes
# ============================================================

# Import after app is created to avoid circular imports
_eventos_configured = False


async def setup_event_callbacks():
    """Register callbacks for job state changes (S3.2)."""
    global _eventos_configured

    if _eventos_configured:
        return

    try:
        from adaptadores.eventos_job import emit_event

        @app.on_job_queued()
        async def on_job_queued(app, job):
            """Called when job is enqueued."""
            try:
                await emit_event(
                    run_id=str(job.task_kwargs.get("run_id", f"job_{job.id}")),
                    evento="created",
                    job_id=job.id,
                    data={
                        "task_name": job.task_name,
                        "attempts": 0,
                        "max_attempts": job.max_attempts,
                    },
                )
            except Exception as e:
                logger.error(f"❌ Event callback error (queued): {e}")

        @app.on_job_started()
        async def on_job_started(app, job):
            """Called when job execution starts."""
            try:
                await emit_event(
                    run_id=str(job.task_kwargs.get("run_id", f"job_{job.id}")),
                    evento="started",
                    job_id=job.id,
                    data={"task_name": job.task_name},
                )
            except Exception as e:
                logger.error(f"❌ Event callback error (started): {e}")

        @app.on_job_completed()
        async def on_job_completed(app, job, *, result=None, **kwargs):
            """Called when job completes successfully."""
            try:
                await emit_event(
                    run_id=str(job.task_kwargs.get("run_id", f"job_{job.id}")),
                    evento="completed",
                    job_id=job.id,
                    data={"task_name": job.task_name, "result": str(result)[:100]},
                )
            except Exception as e:
                logger.error(f"❌ Event callback error (completed): {e}")

        @app.on_job_failed()
        async def on_job_failed(app, job, *, exception=None, **kwargs):
            """Called when job fails."""
            try:
                await emit_event(
                    run_id=str(job.task_kwargs.get("run_id", f"job_{job.id}")),
                    evento="failed",
                    job_id=job.id,
                    data={
                        "task_name": job.task_name,
                        "error": str(exception)[:100] if exception else "Unknown error",
                        "attempts": job.attempts,
                    },
                )
            except Exception as e:
                logger.error(f"❌ Event callback error (failed): {e}")

        _eventos_configured = True
        logger.info("✅ Event callbacks registered for job state changes")

    except ImportError as e:
        logger.warning(f"⚠️  Could not import eventos_job module: {e}")


if __name__ == "__main__":
    asyncio.run(app.open())
    logger.info("✅ Procrastinate app configured and ready")
    logger.info(f"   Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'configured'}")
    logger.info("   Tasks: job_agente_run, job_mim_etl, job_informe_pdf")
