"""
S6.7: Endpoint API para dashboard de alertas de retiro.

GET /api/alertas/activas - Retorna alertas activas (últimas 90 días)
GET /api/alertas/criticas - Retorna solo alertas críticas
GET /api/alertas/{alert_id} - Detalles de una alerta específica
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from adaptadores.db import pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alertas", tags=["alertas"])


# ============================================================================
# Modelos de respuesta
# ============================================================================


class AlertaItemResponse(BaseModel):
    """Item de alerta para listado en dashboard."""

    alert_id: str
    fuente: str  # 'openfda' o 'rasff'
    producto_nombre: str
    riesgo_categoria: str
    riesgo_texto: str
    fecha_emitida: str  # ISO format
    dias_desde: int
    url_oficial: str
    severity_score: Optional[float] = None
    severity_label: str
    pais_origen: str


class AlertasActivasResponse(BaseModel):
    """Respuesta para listado de alertas activas.

    Ojo con las tres cantidades: son de **la pagina devuelta**, ya filtrada por
    severidad y recortada por `limite`. No son totales del sistema. Para eso
    esta /estadisticas/resumen, que cuenta sobre la tabla entera.
    """

    alertas: List[AlertaItemResponse]
    cantidad_total: int
    cantidad_criticas: int
    cantidad_activas: int
    ultima_actualizacion: Optional[str] = None  # ISO format


class AlertaDetalleResponse(BaseModel):
    """Respuesta detallada de una alerta."""

    alert_id: str
    fuente: str
    producto_nombre: str
    riesgo_categoria: str
    riesgo_texto: str
    fecha_emitida: str
    dias_desde: int
    pais_origen: str
    pais_destino: str
    url_oficial: str
    empresa: Optional[str] = None
    reference_number: Optional[str] = None
    severity_score: Optional[float] = None
    severity_label: str

    # Metadata
    similitud: Optional[float] = None
    creado_en: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/activas", response_model=AlertasActivasResponse)
async def obtener_alertas_activas(
    limite: int = Query(50, ge=1, le=200),
    dias: int = Query(90, ge=1, le=365),
    severidad: Optional[str] = Query(None, pattern="^(critical|high|medium|low)$"),
):
    """
    Obtener alertas activas (últimas N días).

    Query params:
    - limite: Máximo número de alertas (default 50, max 200)
    - dias: Considerar últimas N días (default 90)
    - severidad: Filtrar por nivel (critical, high, medium, low)

    Returns:
        AlertasActivasResponse con listado + estadísticas
    """
    try:
        with pool().connection() as conn, conn.cursor() as cur:
            # El filtro de severidad y el ORDER BY van FUERA del UNION, envuelto
            # en una subconsulta: Postgres solo admite en el ORDER BY de un UNION
            # las columnas del resultado, no alias de las tablas de cada rama.
            #
            # La columna de score se llama `score` en alert_scores; el nombre
            # severity_score es el del contrato de la API, y se traduce aqui.
            cur.execute(
                """
                SELECT * FROM (
                    SELECT o.alert_id, o.producto_nombre, o.razon_categoria,
                           o.razon_texto, o.fecha_emitida, o.url_oficial,
                           o.pais, 'openfda' AS fuente,
                           s.score, s.severity_label
                      FROM openfda_alerts o
                      LEFT JOIN alert_scores s
                             ON s.alert_id = o.alert_id AND s.alert_tipo = 'openfda'
                     WHERE o.fecha_emitida >= CURRENT_DATE - %(dias)s

                    UNION ALL

                    SELECT r.rasff_id, r.producto_nombre, r.hazard_categoria,
                           r.hazard_texto, r.fecha_emitida, r.url_oficial,
                           r.pais_destino, 'rasff' AS fuente,
                           s.score, s.severity_label
                      FROM rasff_alerts r
                      LEFT JOIN alert_scores s
                             ON s.alert_id = r.rasff_id AND s.alert_tipo = 'rasff'
                     WHERE r.fecha_emitida >= CURRENT_DATE - %(dias)s
                ) a
                 -- El ::text no es decorativo: sin el, Postgres no puede
                 -- inferir el tipo del parametro suelto en `$n IS NULL`.
                 WHERE %(severidad)s::text IS NULL
                    OR a.severity_label = %(severidad)s::text
                 ORDER BY CASE a.severity_label
                              WHEN 'critical' THEN 1
                              WHEN 'high'     THEN 2
                              WHEN 'medium'   THEN 3
                              ELSE 4
                          END,
                          a.fecha_emitida DESC
                 LIMIT %(limite)s
                """,
                {"dias": dias, "severidad": severidad, "limite": limite},
            )

            alertas = []
            cantidad_criticas = 0

            for row in cur.fetchall():
                (
                    alert_id,
                    producto,
                    categoria,
                    riesgo_texto,
                    fecha_emitida,
                    url_oficial,
                    pais,
                    fuente,
                    score,
                    label,
                ) = row

                dias_desde = (datetime.utcnow().date() - fecha_emitida).days

                alerta = AlertaItemResponse(
                    alert_id=alert_id,
                    fuente=fuente,
                    producto_nombre=producto,
                    riesgo_categoria=categoria,
                    riesgo_texto=riesgo_texto,
                    fecha_emitida=fecha_emitida.isoformat() if fecha_emitida else None,
                    dias_desde=dias_desde,
                    url_oficial=url_oficial,
                    severity_score=score,
                    severity_label=label or "medium",
                    pais_origen=pais,
                )

                alertas.append(alerta)

                if (label or "medium") == "critical":
                    cantidad_criticas += 1

            # Fecha de última actualización (del job)
            cur.execute(
                """
                SELECT MAX(created_at) FROM alert_ingest_log
                WHERE estado = 'success'
                """
            )
            last_update_row = cur.fetchone()
            ultima_actualizacion = (
                last_update_row[0].isoformat() if last_update_row and last_update_row[0] else None
            )

            return AlertasActivasResponse(
                alertas=alertas,
                cantidad_total=len(alertas),
                cantidad_criticas=cantidad_criticas,
                cantidad_activas=len(alertas),
                ultima_actualizacion=ultima_actualizacion,
            )

    except Exception as e:
        logger.error(f"❌ Error obteniendo alertas activas: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/criticas", response_model=AlertasActivasResponse)
async def obtener_alertas_criticas(
    limite: int = Query(20, ge=1, le=100),
):
    """
    Obtener SOLO alertas críticas (últimas 90 días).

    Query params:
    - limite: Máximo número de alertas (default 20)

    Returns:
        AlertasActivasResponse con solo críticas
    """
    # `dias` va explicito aunque su valor sea el mismo que el de por defecto:
    # esto es una llamada de Python normal, no una peticion HTTP, asi que
    # FastAPI no resuelve los Query() y el default llegaria como objeto Query.
    return await obtener_alertas_activas(limite=limite, dias=90, severidad="critical")


@router.get("/{alert_id}", response_model=AlertaDetalleResponse)
async def obtener_alerta_detalle(alert_id: str):
    """
    Obtener detalles completos de una alerta específica.

    Path params:
    - alert_id: ID/hash de la alerta

    Returns:
        AlertaDetalleResponse con todos los campos
    """
    try:
        with pool().connection() as conn, conn.cursor() as cur:
            # Buscar en openFDA
            cur.execute(
                """
                SELECT
                    o.alert_id, 'openfda' as fuente, o.producto_nombre,
                    o.razon_categoria, o.razon_texto, o.fecha_emitida,
                    o.url_oficial, o.pais, o.pais,  -- pais_destino = pais
                    o.empresa, o.titulo_enforcement,
                    s.score, s.severity_label,
                    NULL as similitud, o.created_at
                FROM openfda_alerts o
                LEFT JOIN alert_scores s
                       ON s.alert_id = o.alert_id AND s.alert_tipo = 'openfda'
                WHERE o.alert_id = %s
                """,
                (alert_id,),
            )

            row = cur.fetchone()

            if not row:
                # Buscar en RASFF
                cur.execute(
                    """
                    SELECT
                        r.rasff_id, 'rasff' as fuente, r.producto_nombre,
                        r.hazard_categoria, r.hazard_texto, r.fecha_emitida,
                        r.url_oficial, r.pais_origen, r.pais_destino,
                        NULL, r.reference_number,
                        s.score, s.severity_label,
                        NULL as similitud, r.created_at
                    FROM rasff_alerts r
                    LEFT JOIN alert_scores s
                           ON s.alert_id = r.rasff_id AND s.alert_tipo = 'rasff'
                    WHERE r.rasff_id = %s
                    """,
                    (alert_id,),
                )

                row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Alerta no encontrada")

            (
                alert_id_ret,
                fuente,
                producto,
                categoria,
                riesgo_texto,
                fecha_emitida,
                url_oficial,
                pais_origen,
                pais_destino,
                empresa,
                reference_number,
                score,
                label,
                similitud,
                creado_en,
            ) = row

            dias_desde = (datetime.utcnow().date() - fecha_emitida).days

            return AlertaDetalleResponse(
                alert_id=alert_id_ret,
                fuente=fuente,
                producto_nombre=producto,
                riesgo_categoria=categoria,
                riesgo_texto=riesgo_texto,
                fecha_emitida=fecha_emitida.isoformat() if fecha_emitida else None,
                dias_desde=dias_desde,
                pais_origen=pais_origen,
                pais_destino=pais_destino,
                url_oficial=url_oficial,
                empresa=empresa,
                reference_number=reference_number,
                severity_score=score,
                severity_label=label or "medium",
                similitud=similitud,
                creado_en=creado_en.isoformat() if creado_en else None,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo detalles de alerta: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/estadisticas/resumen")
async def obtener_estadisticas_resumen():
    """
    Obtener estadísticas resumidas de alertas.

    Returns:
        {
            "total_alertas": int,
            "alertas_criticas": int,
            "alertas_activas_90d": int,
            "ultima_actualizacion": str (ISO),
            "job_estado": str,
            "job_duracion_segundos": float
        }
    """
    try:
        with pool().connection() as conn, conn.cursor() as cur:
            # Total de alertas
            cur.execute("SELECT COUNT(*) FROM openfda_alerts")
            total_openfda = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM rasff_alerts")
            total_rasff = cur.fetchone()[0]

            # Críticas
            cur.execute(
                """
                SELECT COUNT(*) FROM alert_scores
                WHERE severity_label = 'critical'
                """
            )
            cantidad_criticas = cur.fetchone()[0]

            # Activas (últimas 90 días)
            cur.execute(
                """
                SELECT COUNT(*) FROM openfda_alerts
                WHERE fecha_emitida >= CURRENT_DATE - 90

                UNION ALL

                SELECT COUNT(*) FROM rasff_alerts
                WHERE fecha_emitida >= CURRENT_DATE - 90
                """
            )
            activas = sum(row[0] for row in cur.fetchall())

            # Último job exitoso
            cur.execute(
                """
                SELECT
                    estado, duracion_segundos, created_at
                FROM alert_ingest_log
                WHERE estado = 'success'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )

            job_info = cur.fetchone()
            job_estado = job_info[0] if job_info else "never_run"
            job_duracion = job_info[1] if job_info else None
            ultima_actualizacion = job_info[2].isoformat() if job_info and job_info[2] else None

            return {
                "total_alertas": total_openfda + total_rasff,
                "alertas_criticas": cantidad_criticas,
                "alertas_activas_90d": activas,
                "ultima_actualizacion": ultima_actualizacion,
                "job_estado": job_estado,
                "job_duracion_segundos": job_duracion,
            }

    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
