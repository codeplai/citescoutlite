"""
Búsqueda de alertas de retiro para Etapa 5 (S6 Integration).

Busca alertas en openFDA + RASFF para ingredientes verificados en regulaciones.
Integrado en verificar_regulacion() como nueva sección del dossier.
"""

import logging
from datetime import datetime
from typing import Optional
from casos_de_uso.dependencias import Dependencias
from dominio.insumo import InsumoInterpretado
from dominio.alerta_retiro import AlertasDeRetiro, AlertaDeRetiro
from adaptadores.buscador_alertas_fuzzy import BuscadorAlertasFuzzy
from adaptadores.calculador_risk_score import CalculadorRiskScore

logger = logging.getLogger(__name__)


async def buscar_alertas_para_etapa5(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    pais: str = "PE",
) -> AlertasDeRetiro:
    """
    Buscar alertas de retiro para un ingrediente en Etapa 5.

    Integra búsqueda fuzzy + scoring de riesgo.

    Args:
        d: Dependencias
        interpretado: Insumo interpretado con nombre normalizado
        pais: País para filtrar alertas ('PE', 'US', 'EU')

    Returns:
        AlertasDeRetiro con alertas encontradas, críticas, y summary

    Auditoría:
        - Registra búsqueda en alert_lookup_log
        - Incluye cantidad encontrada y fuentes
    """
    logger.info(
        f"🔍 Etapa 5: buscando alertas de retiro para "
        f"'{interpretado.insumo_normalizado}' en {pais}"
    )

    alertas_retiro = AlertasDeRetiro(
        alertas=[],
        cantidad_criticas=0,
        cantidad_activas=0,
        sin_alertas=True,
        fecha_ultima_actualizacion=None,
    )

    # Si no hay BD de alertas configurada, retornar sin alertas
    try:
        from adaptadores.db import pool
        # Verificar que las tablas existen (query rápida)
        conn = pool().connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'openfda_alerts' LIMIT 1"
            )
            tabla_existe = cur.fetchone() is not None
    except Exception as e:
        logger.warning(f"⚠️  No se puede verificar BD de alertas: {e}")
        tabla_existe = False

    if not tabla_existe:
        logger.info("⚠️  Tablas de alertas no existen. S6 no configurado.")
        return alertas_retiro

    # Buscar alertas con fuzzy matching
    try:
        buscador = BuscadorAlertasFuzzy(threshold=0.80)
        alertas_encontradas = await buscador.buscar_alertas_para_ingrediente(
            interpretado.insumo_normalizado,
            pais=pais,
            verbose=False,
        )

        if not alertas_encontradas:
            logger.info(
                f"  ✅ Sin alertas de retiro para '{interpretado.insumo_normalizado}'"
            )
            return alertas_retiro

        # Convertir AlertaEncontrada → AlertaDeRetiro
        calculador = CalculadorRiskScore()
        alertas_modelo = []
        cantidad_criticas = 0

        for alerta_encontrada in alertas_encontradas:
            # Recalcular/verificar score si no existe
            if alerta_encontrada.severity_score is None:
                # Reconstruir AlertaNormalizada para calcular score
                from puertos.descargador_alertas import AlertaNormalizada

                alerta_norm = AlertaNormalizada(
                    alert_id=alerta_encontrada.alert_id,
                    fuente=alerta_encontrada.fuente,
                    fecha_emitida=alerta_encontrada.fecha_emitida,
                    producto_nombre=alerta_encontrada.producto_nombre,
                    riesgo_texto=alerta_encontrada.riesgo_texto,
                    riesgo_categoria=alerta_encontrada.riesgo_categoria,
                    pais_origen=alerta_encontrada.producto_buscado,
                    pais_destino="US" if alerta_encontrada.fuente == "openfda" else "EU",
                    accion="alert",
                    url_oficial=alerta_encontrada.url_oficial,
                )

                score, label = calculador.calcular_severity(alerta_norm, pais)
                severity_score = score
                severity_label = label
            else:
                severity_score = alerta_encontrada.severity_score
                severity_label = alerta_encontrada.severity_label

            # Crear modelo para dossier
            alerta_modelo = AlertaDeRetiro(
                alert_id=alerta_encontrada.alert_id,
                fuente=alerta_encontrada.fuente,
                producto_nombre=alerta_encontrada.producto_nombre,
                riesgo_categoria=alerta_encontrada.riesgo_categoria,
                riesgo_texto=alerta_encontrada.riesgo_texto,
                fecha_emitida=alerta_encontrada.fecha_emitida,
                dias_desde=alerta_encontrada.dias_desde,
                pais_origen=alerta_encontrada.producto_buscado,
                pais_destino="US" if alerta_encontrada.fuente == "openfda" else "EU",
                url_oficial=alerta_encontrada.url_oficial,
                similitud=alerta_encontrada.similitud,
                severity_score=severity_score,
                severity_label=severity_label,
            )

            alertas_modelo.append(alerta_modelo)

            if severity_label == "critical":
                cantidad_criticas += 1

            logger.debug(
                f"  → {alerta_encontrada.fuente.upper()}: "
                f"{alerta_encontrada.producto_nombre} "
                f"({severity_label})"
            )

        # Actualizar resultado
        alertas_retiro.alertas = alertas_modelo
        alertas_retiro.cantidad_criticas = cantidad_criticas
        alertas_retiro.cantidad_activas = len(alertas_modelo)
        alertas_retiro.sin_alertas = False
        alertas_retiro.fecha_ultima_actualizacion = datetime.utcnow()

        logger.info(
            f"  ✅ Alertas encontradas: {len(alertas_modelo)} "
            f"({cantidad_criticas} críticas)"
        )

    except Exception as e:
        logger.error(f"❌ Error buscando alertas de retiro: {e}")
        import traceback
        traceback.print_exc()
        # Retornar sin alertas en caso de error
        return alertas_retiro

    return alertas_retiro


# ============================================================================
# Integración con Etapa 5: verificar_regulacion()
# ============================================================================

async def verificar_regulacion_con_alertas(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    texto: str = "",
    pais: str = "PE",
    incluir_alertas: bool = True,
    **kwargs
) -> dict:
    """
    Versión mejorada de verificar_regulacion() que incluye alertas.

    Combina:
    1. Dossier regulatorio (S4)
    2. Alertas de retiro (S6) - NUEVO

    Args:
        d: Dependencias
        interpretado: Insumo interpretado
        texto: Contexto adicional
        pais: País para filtros
        incluir_alertas: Si True, busca alertas (S6)
        **kwargs: Args adicionales

    Returns:
        Dict con:
        {
            "regulaciones": DossierRegulatorio,
            "alertas": AlertasDeRetiro,
            "premium": true (porque incluye alertas)
        }
    """
    from casos_de_uso.etapas.verificar_regulacion import verificar_regulacion

    # 1. Buscar regulaciones (S4 original)
    regulaciones = await verificar_regulacion(
        d, interpretado, texto, pais, **kwargs
    )

    # 2. Buscar alertas (S6 nuevo)
    alertas = AlertasDeRetiro(
        alertas=[],
        cantidad_criticas=0,
        cantidad_activas=0,
        sin_alertas=True,
    )

    if incluir_alertas:
        try:
            alertas = await buscar_alertas_para_etapa5(d, interpretado, pais)
        except Exception as e:
            logger.warning(f"⚠️  No se pudieron buscar alertas: {e}")

    return {
        "regulaciones": regulaciones,
        "alertas": alertas,
        "premium": True,  # Ahora siempre premium porque incluye alertas
    }
