"""
Calculador de severidad/risk score para alertas de retiro.

Convierte una alerta (riesgo + fecha + país) en un scoring de 1-5 escala.
Parametrizable: pesos se pueden ajustar desde BD o config.

Scoring basado en:
  1. Tipo de riesgo (patógeno=4, alérgeno=3, residuo=2, otro=1) - BASE SCORE
  2. Antigüedad: si < 30 días, multiply by 1.5 (reciente = más peligroso)
  3. País relevante: si mismo país que insumo, multiply by 2
  4. Cap final: score máximo = 5.0
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from adaptadores.db import pool
from puertos.descargador_alertas import AlertaNormalizada

logger = logging.getLogger(__name__)

# Pesos configurables (por defecto)
PESOS_RIESGO_DEFAULT = {
    "patogeno": 4.0,
    "alérgeno": 3.0,
    "residuo": 2.0,
    "otro": 1.0,
}

MULTIPLICADOR_RECIENTE = 1.5  # Si < 30 días
MULTIPLICADOR_PAIS_RELEVANTE = 2.0  # Si mismo país que insumo
SCORE_MAX = 5.0
DIAS_RECIENTE_THRESHOLD = 30


class CalculadorRiskScore:
    """Calcula risk score para una alerta."""

    def __init__(self, pesos: Optional[Dict[str, float]] = None):
        """
        Args:
            pesos: Dict con pesos para categorías de riesgo.
                   Si None, usa defaults.
        """
        self.pesos = pesos or PESOS_RIESGO_DEFAULT.copy()
        self.logger = logger

    def calcular_severity(
        self,
        alerta: AlertaNormalizada,
        pais_insumo: str = "PE",
    ) -> tuple[float, str]:
        """
        Calcular score y label de severidad para una alerta.

        Args:
            alerta: Alerta normalizada
            pais_insumo: País de origen del insumo (para comparar con alerta)

        Returns:
            (score: float 1-5, label: 'critical'/'high'/'medium'/'low')
        """
        # 1. Score base según categoría de riesgo
        base_score = self.pesos.get(alerta.riesgo_categoria, 1.0)

        score = base_score

        # 2. Multiplicador por antigüedad
        dias_desde = (datetime.utcnow().date() - alerta.fecha_emitida.date()).days
        if dias_desde < DIAS_RECIENTE_THRESHOLD:
            score *= MULTIPLICADOR_RECIENTE
            self.logger.debug(
                f"  ↑ Alerta reciente ({dias_desde}d): multiply by {MULTIPLICADOR_RECIENTE}"
            )

        # 3. Multiplicador por país relevante
        if alerta.pais_origen.upper() == pais_insumo.upper():
            score *= MULTIPLICADOR_PAIS_RELEVANTE
            self.logger.debug(
                f"  ↑ Pais relevante ({alerta.pais_origen}=={pais_insumo}): multiply by {MULTIPLICADOR_PAIS_RELEVANTE}"
            )

        # 4. Cap at MAX
        score = min(score, SCORE_MAX)

        # 5. Generar label
        label = self._score_a_label(score)

        self.logger.debug(
            f"  📊 Score: {score:.2f} → {label} "
            f"(base={base_score}, días={dias_desde}, país={alerta.pais_origen})"
        )

        return score, label

    def _score_a_label(self, score: float) -> str:
        """Convertir score numérico a label."""
        if score >= 4.5:
            return "critical"
        elif score >= 3.5:
            return "high"
        elif score >= 2.5:
            return "medium"
        else:
            return "low"

    async def guardar_score_en_bd(
        self,
        alert_id: str,
        alert_tipo: str,
        score: float,
        severity_label: str,
        dias_desde_emitida: int,
    ) -> bool:
        """
        Guardar score en tabla alert_scores.

        Args:
            alert_id: ID de la alerta
            alert_tipo: 'openfda' o 'rasff'
            score: Score 1-5
            severity_label: 'critical'/'high'/'medium'/'low'
            dias_desde_emitida: Días desde que se emitió

        Returns:
            True si guardó correctamente
        """
        try:
            conn = pool().connection()
            with conn.cursor() as cur:
                # Upsert: si existe, actualizar; si no, insertar
                cur.execute(
                    """
                    INSERT INTO alert_scores (alert_id, alert_tipo, score, severity_label, dias_desde_emitida)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (alert_id) DO UPDATE SET
                        score = EXCLUDED.score,
                        severity_label = EXCLUDED.severity_label,
                        dias_desde_emitida = EXCLUDED.dias_desde_emitida
                    """,
                    (alert_id, alert_tipo, score, severity_label, dias_desde_emitida),
                )
                conn.commit()
                self.logger.debug(
                    f"  ✅ Score guardado: {alert_id} = {severity_label} ({score:.2f})"
                )
                return True

        except Exception as e:
            self.logger.error(f"❌ Error guardando score: {e}")
            return False

    @staticmethod
    async def calcular_y_guardar(
        alerta: AlertaNormalizada,
        pais_insumo: str = "PE",
        pesos: Optional[Dict[str, float]] = None,
    ) -> tuple[float, str]:
        """
        Conveniencia: calcular score y guardarlo en BD en una sola llamada.

        Args:
            alerta: Alerta normalizada
            pais_insumo: País de origen del insumo
            pesos: Pesos personalizados (opcional)

        Returns:
            (score, label)
        """
        calculador = CalculadorRiskScore(pesos)
        score, label = calculador.calcular_severity(alerta, pais_insumo)

        dias_desde = (datetime.utcnow().date() - alerta.fecha_emitida.date()).days

        await calculador.guardar_score_en_bd(
            alerta.alert_id,
            alerta.fuente,
            score,
            label,
            dias_desde,
        )

        return score, label


# ============================================================================
# Funciones de conveniencia
# ============================================================================


async def calcular_severity_alerta(
    alerta: AlertaNormalizada,
    pais_insumo: str = "PE",
) -> tuple[float, str]:
    """
    Función de conveniencia: calcular score + label para una alerta.

    Args:
        alerta: AlertaNormalizada
        pais_insumo: País de origen del insumo

    Returns:
        (score: 1-5, label: 'critical'/'high'/'medium'/'low')
    """
    return CalculadorRiskScore.calcular_y_guardar(alerta, pais_insumo)


# ============================================================================
# Configuración: Guardar/Cargar pesos desde BD
# ============================================================================


async def obtener_pesos_de_bd() -> Dict[str, float]:
    """
    Cargar pesos de scoring desde configuración en BD.

    Permite que CITE ajuste manualmente los pesos sin redeploy.

    Estructura esperada en tabla 'config' o similar:
        clave='risk_score_pesos', valor=JSON con pesos
    """
    try:
        conn = pool().connection()
        with conn.cursor() as cur:
            # Buscar configuración (asume tabla 'config')
            cur.execute(
                """
                SELECT valor FROM config
                WHERE clave = 'risk_score_pesos'
                LIMIT 1
                """
            )
            row = cur.fetchone()

            if row:
                import json
                pesos_str = row[0]
                pesos = json.loads(pesos_str)
                logger.info(f"📋 Pesos cargados de BD: {pesos}")
                return pesos

    except Exception as e:
        logger.warning(f"⚠️  No se pudieron cargar pesos de BD: {e}")

    # Fallback a defaults
    logger.info(f"📋 Usando pesos defaults: {PESOS_RIESGO_DEFAULT}")
    return PESOS_RIESGO_DEFAULT.copy()


# ============================================================================
# Ejemplos de uso
# ============================================================================

"""
# Ejemplo 1: Calcular score solo
calculador = CalculadorRiskScore()
alerta = AlertaNormalizada(...)
score, label = calculador.calcular_severity(alerta, pais_insumo="PE")
print(f"Score: {score} ({label})")

# Ejemplo 2: Calcular y guardar en BD
score, label = await calcular_severity_alerta(alerta)

# Ejemplo 3: Con pesos personalizados
pesos_custom = {
    "patogeno": 5.0,      # Más peligroso
    "alérgeno": 2.0,      # Menos peligroso
    "residuo": 2.0,
    "otro": 1.0,
}
calculador = CalculadorRiskScore(pesos_custom)
score, label = calculador.calcular_severity(alerta)
"""
