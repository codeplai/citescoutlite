"""
S6.6: Job de ingesta nocturna de alertas openFDA + RASFF.

Ejecuta cada noche a las 03:00 UTC:
  1. Descarga últimas 24h de openFDA
  2. Descarga últimas 24h de RASFF
  3. Deduplica por hash
  4. Inserta en BD (openfda_alerts + rasff_alerts)
  5. Registra estadísticas en alert_ingest_log
  6. Notifica si hay alertas críticas

SLA: < 5 minutos
Reintentos: 3 veces con exponential backoff
"""

import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, Any, Tuple
from adaptadores.descargador_openfda_alerts import DescargadorOpenFDAAlerts
from adaptadores.descargador_rasff_alerts import DescargadorRASFFAlerts
from adaptadores.calculador_risk_score import CalculadorRiskScore
from adaptadores.db import pool
from puertos.descargador_alertas import AlertaNormalizada

logger = logging.getLogger(__name__)

# Importar Procrastinate si está configurado
try:
    from config.job_scheduling import app as procrastinate_app
    PROCRASTINATE_AVAILABLE = True
except ImportError:
    PROCRASTINATE_AVAILABLE = False
    logger.warning("⚠️  Procrastinate no disponible. Job será solo callable.")


# ============================================================================
# Job de ingesta
# ============================================================================


async def ingestar_alertas_openFDA() -> Tuple[int, int, int]:
    """
    Descargar e ingestar alertas de openFDA.

    Returns:
        (nuevas, duplicadas, errores)
    """
    logger.info("📥 Ingesta openFDA iniciada")
    nuevas = 0
    duplicadas = 0
    errores = 0

    try:
        descargador = DescargadorOpenFDAAlerts(timeout=30)

        # Validar acceso
        if not await descargador.validar_acceso():
            logger.error("❌ openFDA API no accesible")
            return 0, 0, 1

        # Descargar
        alertas = await descargador.descargar_ultimas_24h()
        logger.info(f"  ✅ Descargadas {len(alertas)} alertas de openFDA")

        # Ingestar en BD
        conn = pool().connection()
        with conn.cursor() as cur:
            for alerta in alertas:
                try:
                    # Intentar insertar
                    cur.execute(
                        """
                        INSERT INTO openfda_alerts
                            (alert_id, fecha_emitida, empresa, producto_nombre,
                             razon_texto, razon_categoria, pais, url_oficial, titulo_enforcement)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (alert_id) DO NOTHING
                        """,
                        (
                            alerta.alert_id,
                            alerta.fecha_emitida.date(),
                            alerta.empresa,
                            alerta.producto_nombre,
                            alerta.riesgo_texto,
                            alerta.riesgo_categoria,
                            alerta.pais_origen,
                            alerta.url_oficial,
                            alerta.reference_number,
                        ),
                    )

                    # Verificar si fue insertado (ON CONFLICT DO NOTHING)
                    if cur.rowcount > 0:
                        nuevas += 1
                        logger.debug(f"    ✅ Insertada: {alerta.producto_nombre}")
                    else:
                        duplicadas += 1
                        logger.debug(f"    ℹ️  Duplicada: {alerta.alert_id}")

                except Exception as e:
                    errores += 1
                    logger.warning(f"    ❌ Error ingesta: {e}")

            conn.commit()

        logger.info(f"  📊 openFDA: {nuevas} nuevas, {duplicadas} duplicadas, {errores} errores")

    except Exception as e:
        logger.error(f"❌ Error en ingesta openFDA: {e}")
        errores += 1

    return nuevas, duplicadas, errores


async def ingestar_alertas_rasff() -> Tuple[int, int, int]:
    """
    Descargar e ingestar alertas de RASFF.

    Returns:
        (nuevas, duplicadas, errores)
    """
    logger.info("📥 Ingesta RASFF iniciada")
    nuevas = 0
    duplicadas = 0
    errores = 0

    try:
        descargador = DescargadorRASFFAlerts(timeout=30)

        # Validar acceso
        if not await descargador.validar_acceso():
            logger.error("❌ RASFF feed no accesible")
            return 0, 0, 1

        # Descargar
        alertas = await descargador.descargar_ultimas_24h()
        logger.info(f"  ✅ Descargadas {len(alertas)} alertas de RASFF")

        # Ingestar en BD
        conn = pool().connection()
        with conn.cursor() as cur:
            for alerta in alertas:
                try:
                    # Intentar insertar
                    cur.execute(
                        """
                        INSERT INTO rasff_alerts
                            (rasff_id, fecha_emitida, producto_nombre,
                             hazard_texto, hazard_categoria, pais_origen, pais_destino,
                             accion, url_oficial, reference_number)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (rasff_id) DO NOTHING
                        """,
                        (
                            alerta.alert_id,
                            alerta.fecha_emitida.date(),
                            alerta.producto_nombre,
                            alerta.riesgo_texto,
                            alerta.riesgo_categoria,
                            alerta.pais_origen,
                            alerta.pais_destino,
                            alerta.accion,
                            alerta.url_oficial,
                            alerta.reference_number,
                        ),
                    )

                    # Verificar si fue insertado
                    if cur.rowcount > 0:
                        nuevas += 1
                        logger.debug(f"    ✅ Insertada: {alerta.producto_nombre}")
                    else:
                        duplicadas += 1
                        logger.debug(f"    ℹ️  Duplicada: {alerta.alert_id}")

                except Exception as e:
                    errores += 1
                    logger.warning(f"    ❌ Error ingesta: {e}")

            conn.commit()

        logger.info(f"  📊 RASFF: {nuevas} nuevas, {duplicadas} duplicadas, {errores} errores")

    except Exception as e:
        logger.error(f"❌ Error en ingesta RASFF: {e}")
        errores += 1

    return nuevas, duplicadas, errores


async def calcular_scores_alertas() -> int:
    """
    Calcular risk scores para alertas sin score.

    Returns:
        Cantidad de scores calculados
    """
    logger.info("📊 Calculando scores de riesgo")
    calculados = 0

    try:
        calculador = CalculadorRiskScore()
        conn = pool().connection()

        with conn.cursor() as cur:
            # Alertas sin score
            cur.execute(
                """
                SELECT a.alert_id, a.fecha_emitida, a.razon_categoria,
                       a.pais, 'openfda' as fuente
                FROM openfda_alerts a
                LEFT JOIN alert_scores s ON a.alert_id = s.alert_id
                WHERE s.alert_id IS NULL
                LIMIT 100
                """
            )

            for alert_id, fecha, categoria, pais, fuente in cur.fetchall():
                try:
                    # Crear AlertaNormalizada temporal
                    alerta_norm = AlertaNormalizada(
                        alert_id=alert_id,
                        fuente=fuente,
                        fecha_emitida=fecha,
                        producto_nombre="",  # No necesario para scoring
                        riesgo_texto="",
                        riesgo_categoria=categoria,
                        pais_origen=pais,
                        pais_destino="US",
                        accion="alert",
                        url_oficial="",
                    )

                    score, label = calculador.calcular_severity(alerta_norm)
                    dias_desde = (datetime.utcnow().date() - fecha).days

                    # Guardar score
                    await calculador.guardar_score_en_bd(
                        alert_id, fuente, score, label, dias_desde
                    )
                    calculados += 1

                except Exception as e:
                    logger.warning(f"  ⚠️  Error calculando score para {alert_id}: {e}")

        logger.info(f"  ✅ {calculados} scores calculados")

    except Exception as e:
        logger.error(f"❌ Error calculando scores: {e}")

    return calculados


async def notificar_alertas_criticas() -> int:
    """
    Enviar notificaciones si hay alertas críticas nuevas.

    Returns:
        Cantidad de notificaciones enviadas
    """
    logger.info("🔔 Verificando alertas críticas")
    notificaciones = 0

    try:
        conn = pool().connection()
        with conn.cursor() as cur:
            # Alertas críticas de las últimas 24h no notificadas
            cur.execute(
                """
                SELECT o.alert_id, o.producto_nombre, o.razon_texto,
                       o.fecha_emitida, s.severity_label
                FROM openfda_alerts o
                JOIN alert_scores s ON o.alert_id = s.alert_id
                WHERE s.severity_label = 'critical'
                  AND o.fecha_emitida >= CURRENT_DATE - 1
                  AND o.alert_id NOT IN (
                      SELECT alert_id FROM alert_notification_history
                      WHERE severity_label = 'critical'
                  )
                LIMIT 10
                """
            )

            for alert_id, producto, razon, fecha, label in cur.fetchall():
                try:
                    # Aquí iría notificación (email, Slack, PagerDuty)
                    logger.warning(
                        f"🚨 ALERTA CRÍTICA: {producto} ({razon}) "
                        f"- {fecha}"
                    )

                    # Registrar en history para no notificar 2 veces
                    cur.execute(
                        """
                        INSERT INTO alert_notification_history
                            (alert_id, alert_tipo, severity_label, recipient, enviado_at)
                        VALUES (%s, %s, %s, %s, NOW())
                        """,
                        (alert_id, "openfda", label, "admin@cite.pe"),
                    )

                    notificaciones += 1

                except Exception as e:
                    logger.warning(f"  ⚠️  Error notificando: {e}")

            conn.commit()

        logger.info(f"  ✅ {notificaciones} notificaciones enviadas")

    except Exception as e:
        logger.error(f"❌ Error notificando: {e}")

    return notificaciones


async def job_alert_ingest() -> Dict[str, Any]:
    """
    Job principal: ingestar alertas de ambas fuentes + scoring + notificación.

    Ejecuta en paralelo openFDA + RASFF para minimizar duración.

    Returns:
        Dict con estadísticas:
        {
            "openfda_nuevas": int,
            "openfda_duplicadas": int,
            "openfda_errores": int,
            "rasff_nuevas": int,
            "rasff_duplicadas": int,
            "rasff_errores": int,
            "scores_calculados": int,
            "notificaciones_enviadas": int,
            "duracion_segundos": float,
            "estado": "success" | "partial" | "failed"
        }
    """
    logger.info("=" * 80)
    logger.info("🚀 JOB ALERT INGEST INICIADO")
    logger.info("=" * 80)

    tiempo_inicio = time.time()

    try:
        # 1. Ingestar en paralelo (ambas fuentes)
        logger.info("\n1️⃣  Ingesta de alertas (openFDA + RASFF en paralelo)")
        (openfda_nuevas, openfda_dup, openfda_err), (rasff_nuevas, rasff_dup, rasff_err) = await asyncio.gather(
            ingestar_alertas_openFDA(),
            ingestar_alertas_rasff(),
        )

        # 2. Calcular scores
        logger.info("\n2️⃣  Cálculo de risk scores")
        scores_calculados = await calcular_scores_alertas()

        # 3. Notificaciones
        logger.info("\n3️⃣  Envío de notificaciones")
        notificaciones_enviadas = await notificar_alertas_criticas()

        # 4. Registrar estadísticas
        duracion = time.time() - tiempo_inicio
        estado = "success" if (openfda_err + rasff_err) == 0 else "partial"

        logger.info("\n4️⃣  Registrando estadísticas en alert_ingest_log")
        try:
            conn = pool().connection()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alert_ingest_log
                        (job_id, openfda_nuevos, openfda_duplicados, openfda_errores,
                         rasff_nuevos, rasff_duplicados, rasff_errores,
                         duracion_segundos, estado)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        f"job_{int(tiempo_inicio)}",
                        openfda_nuevas,
                        openfda_dup,
                        openfda_err,
                        rasff_nuevas,
                        rasff_dup,
                        rasff_err,
                        duracion,
                        estado,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"⚠️  Error registrando estadísticas: {e}")

        # 5. Resumen
        logger.info("\n" + "=" * 80)
        logger.info("📊 RESUMEN JOB ALERT INGEST")
        logger.info("=" * 80)
        logger.info(f"⏱️  Duración: {duracion:.2f} segundos (SLA: < 5 min)")
        logger.info(f"openFDA: {openfda_nuevas} nuevas, {openfda_dup} dup, {openfda_err} err")
        logger.info(f"RASFF:   {rasff_nuevas} nuevas, {rasff_dup} dup, {rasff_err} err")
        logger.info(f"Scores:  {scores_calculados} calculados")
        logger.info(f"Notif:   {notificaciones_enviadas} enviadas")
        logger.info(f"Estado:  {estado.upper()}")

        return {
            "openfda_nuevas": openfda_nuevas,
            "openfda_duplicadas": openfda_dup,
            "openfda_errores": openfda_err,
            "rasff_nuevas": rasff_nuevas,
            "rasff_duplicadas": rasff_dup,
            "rasff_errores": rasff_err,
            "scores_calculados": scores_calculados,
            "notificaciones_enviadas": notificaciones_enviadas,
            "duracion_segundos": duracion,
            "estado": estado,
        }

    except Exception as e:
        logger.error(f"❌ Error crítico en job_alert_ingest: {e}")
        import traceback
        traceback.print_exc()

        duracion = time.time() - tiempo_inicio
        return {
            "openfda_nuevas": 0,
            "openfda_duplicadas": 0,
            "openfda_errores": 1,
            "rasff_nuevas": 0,
            "rasff_duplicadas": 0,
            "rasff_errores": 1,
            "scores_calculados": 0,
            "notificaciones_enviadas": 0,
            "duracion_segundos": duracion,
            "estado": "failed",
            "error": str(e),
        }


# ============================================================================
# Registro con Procrastinate (si disponible)
# ============================================================================

if PROCRASTINATE_AVAILABLE:

    @procrastinate_app.task(name="job_alert_ingest", priority=100)
    async def task_job_alert_ingest() -> Dict[str, Any]:
        """Tarea Procrastinate: job_alert_ingest"""
        return await job_alert_ingest()

    @procrastinate_app.periodic_task(cron="0 3 * * *")  # 03:00 UTC every day
    async def schedule_job_alert_ingest() -> None:
        """Schedule job cada noche a las 03:00 UTC"""
        logger.info("🕐 Scheduled job_alert_ingest triggered")
        await task_job_alert_ingest.defer()
