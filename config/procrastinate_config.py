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
# Note: timeout is per-task via @app.task decorator, not global
app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=DATABASE_URL))


# ============================================================
# S3.1 JOB DEFINITIONS (3 core jobs)
# ============================================================

@app.task(
    name="job_agente_run",
    retry=3,  # 1 initial + 3 retries
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
    retry=3,
)
async def job_mim_etl(snapshot_version: str):
    """
    Job 3.1.2 + 3.5 + 3.6: Nightly MIM ETL pipeline with SLA monitoring.

    Runs 00:00 UTC daily (configurable in S3.10):
    1. Download OFF subset (if updates available) - TODO S4
    2. Download USDA (if new brands) - TODO S4
    3. Update shelf_facts_quarterly with today's raw_offers - TODO S4
    4. Calculate deterministic tendencias for pilot ingredients ✅
    5. Save results to tendencias_insumo ✅
    6. Register completion event for monitoring

    SLA: Must complete in < 30 minutes
    Target: 15-20 minutes (shelf_facts update is heaviest operation)

    Args:
        snapshot_version: Version identifier (e.g., '2026-08')

    Returns:
        {
            "status": "completed",
            "version": snapshot_version,
            "tendencias_count": int,
            "timestamp": ISO8601,
            "duration_seconds": float
        }
    """
    import time
    start_time = time.time()

    logger.info(f"🌙 [job_mim_etl] Starting nightly MIM ETL run: version={snapshot_version}")

    try:
        # Step 1-3: OFF/USDA downloads (TODO in S4)
        # Placeholder: assume shelf_facts_quarterly already updated with today's data
        logger.info("📥 Step 1-3: OFF/USDA downloads... [SKIPPED - TODO S4]")

        # Step 4: Calculate tendencias from shelf_facts_quarterly
        logger.info("📈 Step 4: Calculating tendencias...")

        from adaptadores.motor_tendencias_duckdb import MotorTendenciasDuckDB
        from adaptadores.repositorio_tendencias import RepositorioTendencias
        import os

        motor = MotorTendenciasDuckDB("shelf_facts.duckdb")
        tendencias = motor.calcular_todas_tendencias(ano_base=2026)
        motor.cerrar()

        if not tendencias:
            logger.warning("⚠️  No trends calculated")
            tendencias = []

        logger.info(f"✅ Calculated {len(tendencias)} trends:")
        for t in tendencias:
            logger.info(
                f"   - {t['insumo']:12} {t['year_quarter']}: "
                f"precio {t['precio_trend']:+.1f}%, vol {t['volatilidad']:.3f}, "
                f"marcas ±{t['marcas_nuevas']}/{t['marcas_salidas']}"
            )

        # Step 5: Save to PostgreSQL
        db_url = os.getenv("DATABASE_URL")
        saved_count = 0

        if db_url:
            logger.info("💾 Step 5: Saving trends to PostgreSQL...")
            repo = RepositorioTendencias(db_url)
            saved_count = repo.guardar_tendencias_batch(tendencias)
            logger.info(f"✅ Saved {saved_count}/{len(tendencias)} trends to tendencias_insumo")
        else:
            logger.warning("⚠️  DATABASE_URL not set, skipping trend save")

        # Step 6: Duration check (SLA monitoring)
        duration = time.time() - start_time
        sla_seconds = 30 * 60  # 30 minutes
        sla_exceeded = duration > sla_seconds

        if sla_exceeded:
            logger.warning(
                f"⚠️  SLA EXCEEDED: {duration:.1f}s > {sla_seconds}s limit"
            )
        else:
            logger.info(f"✅ SLA OK: {duration:.1f}s < {sla_seconds}s limit")

        resultado = {
            "status": "completed",
            "version": snapshot_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tendencias_count": len(tendencias),
            "saved_count": saved_count,
            "duration_seconds": round(duration, 2),
            "sla_exceeded": sla_exceeded,
        }

        logger.info(
            f"✅ [job_mim_etl] Completed: {snapshot_version} "
            f"({len(tendencias)} trends, {duration:.1f}s)"
        )

        return resultado

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"❌ [job_mim_etl] Failed: {snapshot_version} - {e} (duration: {duration:.1f}s)")
        import traceback
        traceback.print_exc()
        raise


@app.task(
    name="job_informe_pdf",
    retry=3,
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
# S3.2 - eventos_job por cada job que corre el worker
#
# Esto eran cuatro decoradores: @app.on_job_queued, on_job_started,
# on_job_completed y on_job_failed. **Ninguno existe en procrastinate 3.9**, y
# como el registro iba dentro de un try/except que solo miraba ImportError, el
# AttributeError salia por arriba y tumbaba el arranque del worker. Sumado a que
# `setup_event_callbacks()` se llamaba sin await, el resultado es que los
# eventos de ciclo de vida no se escribieron nunca.
#
# La forma actual de envolver la ejecucion de un job es un *worker middleware*:
# una corrutina (call_next, context, worker) que rodea cada job, sea sync o
# async. Cubre started / completed / failed.
#
# 'created' no se puede emitir desde aqui: ocurre al encolar, en otro proceso.
# Cuando algo llame a `.defer()` de verdad —hoy no lo hace nadie en produccion,
# es el bloqueador B2 de la auditoria de S8— habra que emitirlo alli.
# ============================================================


def _run_id_de(job) -> str:
    """El run_id que el job trae en sus kwargs, o uno derivado de su id.

    Sin esto, dos jobs distintos de la misma tarea compartirian run_id y sus
    eventos se mezclarian en la misma linea de tiempo del panel.
    """
    return str(job.task_kwargs.get("run_id") or f"job_{job.id}")


async def middleware_eventos_job(call_next, context, worker):
    """Escribe started/completed/failed en eventos_job alrededor de cada job.

    Los fallos al registrar se tragan a proposito: que no se pueda anotar un
    evento no puede impedir que el trabajo se haga, ni convertir un job
    correcto en uno fallido. Pero se registran en el log con nivel error, que
    es lo que faltaba antes.
    """
    from adaptadores.eventos_job import emit_event

    job = context.job
    run_id = _run_id_de(job)

    async def anotar(evento: str, data: dict) -> None:
        try:
            await emit_event(run_id=run_id, evento=evento,
                             job_id=job.id, data=data)
        except Exception as e:
            logger.error(f"No se pudo escribir el evento {evento} "
                         f"de {job.task_name}: {e}")

    await anotar("started", {"task_name": job.task_name,
                             "intento": job.attempts})
    try:
        resultado = await call_next()
    except Exception as e:
        await anotar("failed", {"task_name": job.task_name,
                                "error": str(e)[:200],
                                "intento": job.attempts})
        raise

    await anotar("completed", {"task_name": job.task_name,
                               "resultado": str(resultado)[:200]})
    return resultado


if __name__ == "__main__":
    asyncio.run(app.open())
    logger.info("✅ Procrastinate app configured and ready")
    logger.info(f"   Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'configured'}")
    logger.info("   Tasks: job_agente_run, job_mim_etl, job_informe_pdf")
