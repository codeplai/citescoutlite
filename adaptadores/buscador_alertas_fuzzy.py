"""
Buscador de alertas con fuzzy matching (similitud de nombres).

Función: Vincular ingrediente en informe con alertas relevantes de openFDA/RASFF.
Técnica: Fuzzy string matching (difflib) con threshold 80%+ similarity.
Auditoría: Registrar todas las búsquedas en alert_lookup_log.
"""

import logging
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
from datetime import datetime, timedelta
from adaptadores.db import pool
from puertos.descargador_alertas import AlertaNormalizada

logger = logging.getLogger(__name__)

BUSQUEDA_SIMILARITY_THRESHOLD = 0.80  # 80%+ similarity


class AlertaEncontrada:
    """Resultado de búsqueda de alerta."""

    def __init__(
        self,
        alert_id: str,
        fuente: str,
        producto_nombre: str,
        producto_buscado: str,
        similitud: float,
        riesgo_categoria: str,
        riesgo_texto: str,
        fecha_emitida: datetime,
        url_oficial: str,
        severity_score: Optional[float] = None,
        severity_label: Optional[str] = None,
        dias_desde: Optional[int] = None,
    ):
        self.alert_id = alert_id
        self.fuente = fuente
        self.producto_nombre = producto_nombre
        self.producto_buscado = producto_buscado
        self.similitud = similitud
        self.riesgo_categoria = riesgo_categoria
        self.riesgo_texto = riesgo_texto
        self.fecha_emitida = fecha_emitida
        self.url_oficial = url_oficial
        self.severity_score = severity_score
        self.severity_label = severity_label
        self.dias_desde = dias_desde

    def __repr__(self):
        return (
            f"AlertaEncontrada("
            f"fuente={self.fuente}, "
            f"producto={self.producto_nombre}, "
            f"similitud={self.similitud:.1%}, "
            f"severity={self.severity_label})"
        )


class BuscadorAlertasFuzzy:
    """Busca alertas de ingredientes usando fuzzy matching."""

    def __init__(
        self,
        threshold: float = BUSQUEDA_SIMILARITY_THRESHOLD,
        dias_considerados: int = 90,
    ):
        self.threshold = threshold
        self.dias_considerados = dias_considerados
        self.logger = logger

    async def buscar_alertas_para_ingrediente(
        self,
        ingrediente_nombre: str,
        pais: str = "PE",
        verbose: bool = False,
    ) -> List[AlertaEncontrada]:
        """
        Buscar alertas relevantes para un ingrediente.

        Args:
            ingrediente_nombre: Nombre del ingrediente (ej: "quinua", "sodium bicarbonate")
            pais: País origen (PE, US, EU, etc). Determina qué fuentes buscar:
                  - PE/US: openFDA
                  - EU: RASFF
            verbose: Log detallado de búsqueda

        Returns:
            Lista de AlertaEncontrada ordenadas por similitud desc + severidad desc

        Auditoría:
            - Registra búsqueda en alert_lookup_log
            - Incluye: ingrediente, país, cantidad encontrada, fuentes
        """
        if verbose:
            self.logger.info(
                f"🔍 Buscando alertas para '{ingrediente_nombre}' (país={pais})"
            )

        alertas_encontradas = []

        try:
            # 1. Buscar en openFDA (USA)
            if pais in ["US", "PE"]:  # PE usa regulaciones USA principalmente
                alertas_openfda = await self._buscar_en_openfda(
                    ingrediente_nombre, verbose
                )
                alertas_encontradas.extend(alertas_openfda)

            # 2. Buscar en RASFF (EU)
            if pais in ["EU", "PE"]:  # PE también verifica regulaciones EU
                alertas_rasff = await self._buscar_en_rasff(
                    ingrediente_nombre, verbose
                )
                alertas_encontradas.extend(alertas_rasff)

            # 3. Ordenar por similitud (desc) + severity (desc)
            alertas_encontradas.sort(
                key=lambda a: (-a.similitud, -(a.severity_score or 0))
            )

            if verbose:
                self.logger.info(
                    f"  ✅ Encontradas {len(alertas_encontradas)} alertas relevantes"
                )

        except Exception as e:
            self.logger.error(f"❌ Error buscando alertas para {ingrediente_nombre}: {e}")
            return []

        # 4. Registrar búsqueda en auditoría
        await self._registrar_busqueda(
            ingrediente_nombre, pais, len(alertas_encontradas), alertas_encontradas
        )

        return alertas_encontradas

    async def _buscar_en_openfda(
        self, ingrediente_nombre: str, verbose: bool = False
    ) -> List[AlertaEncontrada]:
        """Buscar alertas en tabla openfda_alerts con fuzzy matching."""
        alertas = []

        try:
            with pool().connection() as conn, conn.cursor() as cur:
                # Query: últimas 90 días, ordenadas por fecha
                cur.execute(
                    """
                    SELECT
                        alert_id, producto_nombre, razon_categoria, razon_texto,
                        fecha_emitida, url_oficial
                    FROM openfda_alerts
                    WHERE fecha_emitida >= CURRENT_DATE - %s
                    ORDER BY fecha_emitida DESC
                    """,
                    (self.dias_considerados,),
                )

                for row in cur.fetchall():
                    alert_id, producto, categoria, riesgo_texto, fecha, url = row

                    # Calcular similitud
                    similitud = self._calcular_similitud(
                        ingrediente_nombre, producto
                    )

                    # Solo si supera threshold
                    if similitud >= self.threshold:
                        # Buscar scoring si existe
                        score, label = await self._obtener_score(alert_id, "openfda")

                        dias_desde = (datetime.utcnow().date() - fecha).days

                        alerta = AlertaEncontrada(
                            alert_id=alert_id,
                            fuente="openfda",
                            producto_nombre=producto,
                            producto_buscado=ingrediente_nombre,
                            similitud=similitud,
                            riesgo_categoria=categoria,
                            riesgo_texto=riesgo_texto,
                            fecha_emitida=fecha,
                            url_oficial=url,
                            severity_score=score,
                            severity_label=label,
                            dias_desde=dias_desde,
                        )

                        alertas.append(alerta)

                        if verbose:
                            self.logger.debug(
                                f"  → openFDA: '{producto}' ({similitud:.1%}) - {categoria}"
                            )

        except Exception as e:
            self.logger.error(f"❌ Error buscando en openFDA: {e}")

        return alertas

    async def _buscar_en_rasff(
        self, ingrediente_nombre: str, verbose: bool = False
    ) -> List[AlertaEncontrada]:
        """Buscar alertas en tabla rasff_alerts con fuzzy matching."""
        alertas = []

        try:
            with pool().connection() as conn, conn.cursor() as cur:
                # Query: últimas 90 días, ordenadas por fecha
                cur.execute(
                    """
                    SELECT
                        rasff_id, producto_nombre, hazard_categoria, hazard_texto,
                        fecha_emitida, url_oficial
                    FROM rasff_alerts
                    WHERE fecha_emitida >= CURRENT_DATE - %s
                    ORDER BY fecha_emitida DESC
                    """,
                    (self.dias_considerados,),
                )

                for row in cur.fetchall():
                    rasff_id, producto, categoria, riesgo_texto, fecha, url = row

                    # Calcular similitud
                    similitud = self._calcular_similitud(
                        ingrediente_nombre, producto
                    )

                    # Solo si supera threshold
                    if similitud >= self.threshold:
                        # Buscar scoring si existe
                        score, label = await self._obtener_score(rasff_id, "rasff")

                        dias_desde = (datetime.utcnow().date() - fecha).days

                        alerta = AlertaEncontrada(
                            alert_id=rasff_id,
                            fuente="rasff",
                            producto_nombre=producto,
                            producto_buscado=ingrediente_nombre,
                            similitud=similitud,
                            riesgo_categoria=categoria,
                            riesgo_texto=riesgo_texto,
                            fecha_emitida=fecha,
                            url_oficial=url,
                            severity_score=score,
                            severity_label=label,
                            dias_desde=dias_desde,
                        )

                        alertas.append(alerta)

                        if verbose:
                            self.logger.debug(
                                f"  → RASFF: '{producto}' ({similitud:.1%}) - {categoria}"
                            )

        except Exception as e:
            self.logger.error(f"❌ Error buscando en RASFF: {e}")

        return alertas

    async def _obtener_score(
        self, alert_id: str, alert_tipo: str
    ) -> tuple[Optional[float], Optional[str]]:
        """Obtener scoring y severity_label para una alerta, si existe."""
        try:
            with pool().connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT score, severity_label
                    FROM alert_scores
                    WHERE alert_id = %s AND alert_tipo = %s
                    LIMIT 1
                    """,
                    (alert_id, alert_tipo),
                )
                row = cur.fetchone()
                if row:
                    return row[0], row[1]
        except Exception as e:
            self.logger.debug(f"  ℹ️  No hay score para {alert_id}: {e}")

        return None, None

    def _calcular_similitud(self, texto1: str, texto2: str) -> float:
        """
        Calcular similitud entre dos strings usando SequenceMatcher.

        Returns: Similitud de 0.0 a 1.0
        """
        # Normalizar (minúsculas, trim)
        t1 = texto1.lower().strip()
        t2 = texto2.lower().strip()

        # Similitud simple
        matcher = SequenceMatcher(None, t1, t2)
        return matcher.ratio()

    async def _registrar_busqueda(
        self,
        ingrediente: str,
        pais: str,
        cantidad: int,
        alertas: List[AlertaEncontrada],
    ) -> None:
        """Registrar búsqueda en alert_lookup_log para auditoría."""
        try:
            fuentes = set(a.fuente for a in alertas)
            fuentes_str = ",".join(sorted(fuentes)) if fuentes else "ninguna"

            with pool().connection() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alert_lookup_log
                        (ingrediente, pais, alertas_encontradas, fuentes_consultadas, timestamp)
                    VALUES (%s, %s, %s, %s, NOW())
                    """,
                    (ingrediente, pais, cantidad, fuentes_str),
                )
                conn.commit()

        except Exception as e:
            self.logger.warning(f"⚠️  Error registrando búsqueda en auditoría: {e}")


# ============================================================================
# Función de conveniencia
# ============================================================================

async def buscar_alertas_para_ingrediente(
    ingrediente_nombre: str,
    pais: str = "PE",
    verbose: bool = False,
) -> List[AlertaEncontrada]:
    """
    Función de conveniencia para búsqueda de alertas.

    Crea un BuscadorAlertasFuzzy y ejecuta búsqueda.

    Args:
        ingrediente_nombre: Nombre del ingrediente
        pais: País (PE, US, EU)
        verbose: Log detallado

    Returns:
        Lista de AlertaEncontrada ordenadas por relevancia
    """
    buscador = BuscadorAlertasFuzzy()
    return await buscador.buscar_alertas_para_ingrediente(
        ingrediente_nombre, pais, verbose
    )
