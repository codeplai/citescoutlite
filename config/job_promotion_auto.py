"""
S7.5 - Job de promoción automática.

Cada noche a las 04:00 UTC:
  1. Coge las ofertas que siguen en cuarentena.
  2. Reparte con el watermark de la semana: ~80 % automáticas, ~20 % manuales.
  3. Valida las automáticas contra las reglas activas de promotion_rules.
  4. Las que pasan quedan promovidas (D1: marca en staging_agente).
  5. Todo queda en promotion_log, promotion_validation_log y eventos_job.

El 20 % que cae del lado manual NO se toca: se queda en cuarentena para que lo
revise una persona desde el panel. Tampoco se toca lo rechazado, por el mismo
motivo — una oferta que el job no quiso puede ser perfectamente promovible a
mano, y el TTL de 24 h de staging_agente ya se encarga de lo que nadie mire.

SLA: < 15 min. Son decenas de ofertas por noche, no miles.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from adaptadores.repositorio_promocion import RepositorioPromocion
from casos_de_uso.promocion import validar_oferta
from dominio.watermark import (
    PORCENTAJE_AUTOMATICO,
    cubo_de,
    lunes_de_la_semana,
    semilla_semanal,
)

logger = logging.getLogger(__name__)

# Tope de ofertas por pasada. Existe para que una acumulación rara no haga que
# el job se salte el SLA; lo que sobre entra en la pasada siguiente.
MAX_OFERTAS_POR_PASADA = 1000

SLA_SEGUNDOS = 15 * 60

try:
    from config.procrastinate_config import app as procrastinate_app
    PROCRASTINATE_AVAILABLE = True
except ImportError:  # pragma: no cover - depende del entorno
    PROCRASTINATE_AVAILABLE = False
    logger.warning("⚠️  Procrastinate no disponible. Job será solo callable.")


async def _emitir(run_id: str, evento: str, data: Optional[dict] = None) -> None:
    """Evento en eventos_job. Que falle el registro no debe tumbar el job."""
    try:
        from adaptadores.eventos_job import emit_event
        await emit_event(run_id=run_id, evento=evento, data=data or {})
    except Exception as e:
        logger.warning(f"No se pudo registrar el evento {evento}: {e}")


async def job_promotion_auto(
    porcentaje: int = PORCENTAJE_AUTOMATICO,
    momento: Optional[datetime] = None,
    repositorio: Optional[RepositorioPromocion] = None,
) -> Dict[str, Any]:
    """Promueve lo que el watermark marque como automático y pase las reglas.

    Args:
        porcentaje: cuánto va por la vía automática. Parametrizable para que
            CITE pueda estrecharlo mientras coge confianza en las reglas.
        momento: para fijar la semana en las pruebas. Por defecto, ahora.
        repositorio: inyectable en tests.

    Returns:
        Estadísticas de la pasada.
    """
    inicio = time.time()
    run_id = f"promotion_{uuid4().hex[:12]}"
    repo = repositorio or RepositorioPromocion()

    momento = momento or datetime.now(timezone.utc)
    semilla = semilla_semanal(momento)
    lunes = lunes_de_la_semana(momento)

    logger.info("=" * 70)
    logger.info(f"🚀 JOB PROMOTION AUTO — semana {semilla} (run {run_id})")
    logger.info("=" * 70)

    await _emitir(run_id, "started", {"semilla": semilla, "porcentaje": porcentaje})

    promovidas = rechazadas = manuales = ya_promovidas = errores = 0
    motivos: dict[str, int] = {}

    try:
        reglas = repo.leer_reglas(solo_activas=True)
        ofertas = repo.ofertas_en_cuarentena(limite=MAX_OFERTAS_POR_PASADA)

        logger.info(f"  {len(ofertas)} ofertas en cuarentena, "
                    f"{len(reglas)} reglas activas: "
                    f"{', '.join(r.nombre for r in reglas) or '(ninguna)'}")

        if reglas == []:
            # Sin reglas activas, validar no comprueba nada y todo el 80 %
            # entraria sin mirar. Es una situacion legitima —CITE puede
            # apagarlas todas— pero tiene que verse en el log.
            logger.warning("  ⚠️  Sin reglas activas: se promueve sin validar")

        for oferta in ofertas:
            staging_id = oferta["staging_id"]

            try:
                cubo = cubo_de(str(staging_id), semilla)
                automatica = cubo < porcentaje
                repo.registrar_watermark(staging_id, semilla, lunes, cubo,
                                         porcentaje, automatica)

                if not automatica:
                    # El 20 %: se queda en cuarentena para revisión humana.
                    manuales += 1
                    continue

                resultado = validar_oferta(oferta, reglas)
                repo.registrar_validacion(staging_id, resultado.passed,
                                          resultado.errores_json(),
                                          resultado.reglas_evaluadas)

                if resultado.passed:
                    if repo.promover(staging_id, "auto_watermark",
                                     resultado.reglas_evaluadas):
                        promovidas += 1
                    else:
                        ya_promovidas += 1
                else:
                    repo.registrar_rechazo(staging_id, resultado.errores_json(),
                                           resultado.reglas_evaluadas)
                    rechazadas += 1
                    for e in resultado.errores:
                        motivos[e.regla] = motivos.get(e.regla, 0) + 1

            except Exception as e:
                errores += 1
                logger.warning(f"  ❌ Error con la oferta {staging_id}: {e}")

        duracion = time.time() - inicio
        sla_ok = duracion < SLA_SEGUNDOS

        logger.info("-" * 70)
        logger.info(f"  ✅ {promovidas} promovidas automáticamente")
        logger.info(f"  ✋ {manuales} a revisión manual (20 %)")
        logger.info(f"  ⛔ {rechazadas} rechazadas por regla")
        for regla, veces in sorted(motivos.items(), key=lambda x: -x[1]):
            logger.info(f"       {regla}: {veces}")
        if ya_promovidas:
            logger.info(f"  ↩️  {ya_promovidas} ya estaban promovidas")
        if errores:
            logger.info(f"  ❌ {errores} con error")
        logger.info(f"  ⏱️  {duracion:.2f}s (SLA {SLA_SEGUNDOS}s): "
                    f"{'OK' if sla_ok else 'EXCEDIDO'}")

        resumen = {
            "run_id": run_id,
            "semilla": semilla,
            "porcentaje": porcentaje,
            "ofertas_revisadas": len(ofertas),
            "promovidas": promovidas,
            "manuales": manuales,
            "rechazadas": rechazadas,
            "ya_promovidas": ya_promovidas,
            "errores": errores,
            "motivos_de_rechazo": motivos,
            "duracion_segundos": round(duracion, 2),
            "sla_ok": sla_ok,
            "estado": "success" if errores == 0 else "partial",
        }

        await _emitir(run_id, "completed", resumen)
        return resumen

    except Exception as e:
        logger.error(f"❌ Error crítico en job_promotion_auto: {e}")
        duracion = time.time() - inicio
        await _emitir(run_id, "failed", {"error": str(e)[:200]})
        return {
            "run_id": run_id,
            "semilla": semilla,
            "ofertas_revisadas": 0,
            "promovidas": 0,
            "manuales": 0,
            "rechazadas": 0,
            "ya_promovidas": 0,
            "errores": 1,
            "motivos_de_rechazo": {},
            "duracion_segundos": round(duracion, 2),
            "sla_ok": duracion < SLA_SEGUNDOS,
            "estado": "failed",
            "error": str(e),
        }


if PROCRASTINATE_AVAILABLE:

    # `periodic` decora la Task y le pasa el timestamp del tick. 04:00 UTC,
    # una hora después del job de alertas, para no solaparlos.
    @procrastinate_app.periodic(cron="0 4 * * *")
    @procrastinate_app.task(name="job_promotion_auto", priority=90)
    async def task_job_promotion_auto(timestamp: int) -> Dict[str, Any]:
        """Tarea Procrastinate: job_promotion_auto."""
        logger.info(f"🕐 job_promotion_auto disparado (tick {timestamp})")
        return await job_promotion_auto()
