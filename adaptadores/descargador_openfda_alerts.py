"""
Descargador de alertas openFDA (FDA enforcement actions).

API: https://api.fda.gov/food/enforcement.json
Documentación: https://open.fda.gov/apis/food/enforcement/

Descarga enforcement actions (recalls, market withdrawals) de las últimas 24h.
Normaliza a AlertaNormalizada para inserción en BD.
"""

import logging
import hashlib
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta
import httpx

from puertos.descargador_alertas import DescargadorAlertas, AlertaNormalizada

logger = logging.getLogger(__name__)

OPENFDA_API_BASE = "https://api.fda.gov/food/enforcement.json"
OPENFDA_MAX_RETRIES = 3
OPENFDA_TIMEOUT = 30


class DescargadorOpenFDAAlerts(DescargadorAlertas):
    """Descargador de alertas de enforcement actions de FDA."""

    def __init__(self, timeout: int = OPENFDA_TIMEOUT, max_retries: int = OPENFDA_MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logger

    async def validar_acceso(self) -> bool:
        """Verificar que openFDA API responde.

        Sin filtro de fecha a proposito. Antes preguntaba por las ultimas 24h,
        pero openFDA responde 404 NOT_FOUND cuando una busqueda no tiene
        coincidencias —no un array vacio—, y los recalls de alimentos no son
        diarios. Cualquier dia tranquilo se leia como "API caida" y el job se
        saltaba la ingesta entera.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = OPENFDA_API_BASE
                params = {"limit": 1}

                response = await client.get(url, params=params, timeout=self.timeout)
                is_ok = response.status_code < 400
                status = "✅" if is_ok else "❌"
                self.logger.info(f"{status} openFDA API: {response.status_code}")
                return is_ok
        except Exception as e:
            self.logger.error(f"❌ Error validando openFDA: {e}")
            return False

    async def descargar_ultimas_24h(self) -> List[AlertaNormalizada]:
        """
        Descargar enforcement actions de las últimas 24 horas.

        Retorna lista normalizada de alertas.
        """
        alertas = []
        ahora = datetime.utcnow()
        ayer = ahora - timedelta(days=1)

        # Rango de fechas para query
        fecha_desde = ayer.strftime("%Y%m%d")
        fecha_hasta = ahora.strftime("%Y%m%d")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                self.logger.info(f"📥 Descargando openFDA alerts ({fecha_desde} a {fecha_hasta})...")

                # Query: enforcement actions de últimas 24h
                url = OPENFDA_API_BASE
                params = {
                    "search": f'report_date:[{fecha_desde} TO {fecha_hasta}]',
                    "limit": 100,  # openFDA permite hasta 100 por request
                    "skip": 0
                }

                # Reintentos exponencial
                for intento in range(self.max_retries):
                    try:
                        response = await client.get(url, params=params, timeout=self.timeout)

                        if response.status_code == 200:
                            data = response.json()
                            self.logger.debug(f"  → openFDA retornó {data.get('meta', {}).get('results', {}).get('total', 0)} resultados")

                            if "results" in data and data["results"]:
                                regs = self.normalizar(data["results"])
                                alertas.extend(regs)
                                self.logger.info(f"  ✅ openFDA: {len(regs)} alertas descargadas")
                            else:
                                self.logger.info(f"  ℹ️  openFDA: 0 alertas en las últimas 24h")

                            break

                        elif response.status_code == 404:
                            # openFDA devuelve 404 NOT_FOUND cuando la busqueda
                            # no tiene coincidencias. Es una respuesta valida
                            # que significa "0 alertas", no un fallo: sin este
                            # caso caia en el else y gastaba los 3 reintentos
                            # con backoff antes de rendirse.
                            self.logger.info("  ℹ️  openFDA: 0 alertas en las últimas 24h")
                            break

                        elif response.status_code == 429:
                            # Rate limit: esperar
                            self.logger.warning(f"  ⚠️  Rate limit (429). Intento {intento + 1}/{self.max_retries}")
                            if intento < self.max_retries - 1:
                                await asyncio.sleep(2 ** intento)  # Exponential backoff
                            continue

                        else:
                            self.logger.warning(f"  ⚠️  openFDA {response.status_code}")
                            if intento < self.max_retries - 1:
                                await asyncio.sleep(2 ** intento)
                            continue

                    except httpx.TimeoutException:
                        self.logger.warning(f"  ⏱️  Timeout en intento {intento + 1}/{self.max_retries}")
                        if intento < self.max_retries - 1:
                            await asyncio.sleep(2 ** intento)
                        continue

                    except Exception as e:
                        self.logger.warning(f"  ❌ Error en intento {intento + 1}: {e}")
                        if intento < self.max_retries - 1:
                            await asyncio.sleep(2 ** intento)
                        continue

        except Exception as e:
            self.logger.error(f"❌ Error descargando openFDA: {e}")
            return alertas

        self.logger.info(f"✅ openFDA descargado: {len(alertas)} alertas totales")
        return alertas

    def normalizar(self, resultados: List[Dict[str, Any]]) -> List[AlertaNormalizada]:
        """
        Convertir resultados de openFDA a AlertaNormalizada.

        Estructura de openFDA enforcement:
        {
            "recall_number": "F-0123-2024",
            "report_date": "20240810",
            "recall_initiation_date": "20240808",
            "product_description": "Almonds",
            "reason_for_recall": "E. coli O157:H7",
            "company_name": "XYZ Company",
            "product_type": "Nuts",
            "status": "Ongoing",
            "openfda": {"ndc_code": [...], ...}
        }
        """
        alertas = []

        for item in resultados:
            try:
                # Extraer campos
                recall_number = item.get("recall_number", "UNKNOWN")
                report_date_str = item.get("report_date", "")
                producto = item.get("product_description", "Unknown")
                razon = item.get("reason_for_recall", "Unknown")
                empresa = item.get("company_name", "Unknown")

                # Parsear fecha (formato YYYYMMDD en openFDA)
                try:
                    if report_date_str and len(report_date_str) == 8:
                        fecha = datetime.strptime(report_date_str, "%Y%m%d")
                    else:
                        fecha = datetime.utcnow()
                except ValueError:
                    fecha = datetime.utcnow()

                # Categorizar riesgo
                riesgo_categoria = self._categorizar_riesgo(razon)

                # Generar alert_id (hash)
                alerta_temp = AlertaNormalizada(
                    alert_id="",  # Se llena después
                    fuente="openfda",
                    fecha_emitida=fecha,
                    producto_nombre=producto,
                    riesgo_texto=razon,
                    riesgo_categoria=riesgo_categoria,
                    pais_origen="US",
                    pais_destino="US",
                    accion="recall",
                    url_oficial=f"https://www.fda.gov/safety/recalls-enforcement/enforcement-actions?recall_number={recall_number}",
                    empresa=empresa,
                    reference_number=recall_number,
                    metadatos={
                        "status": item.get("status", "Unknown"),
                        "product_type": item.get("product_type", "Unknown"),
                    }
                )

                # Calcular hash
                alert_id = self.hashear_alerta(alerta_temp)
                alerta_temp.alert_id = alert_id

                alertas.append(alerta_temp)

            except Exception as e:
                self.logger.warning(f"  ❌ Error normalizando alerta openFDA: {e}")
                continue

        return alertas

    def _categorizar_riesgo(self, razon: str) -> str:
        """Categorizar tipo de riesgo basado en descripción."""
        razon_lower = razon.lower()

        # Patógenos
        if any(x in razon_lower for x in ["e. coli", "listeria", "salmonella", "campylobacter", "botulism", "shigella"]):
            return "patogeno"

        # Alérgenos
        if any(x in razon_lower for x in ["allergen", "milk", "peanut", "tree nut", "shellfish", "gluten", "soy"]):
            return "alérgeno"

        # Residuos químicos/pesticidas
        if any(x in razon_lower for x in ["pesticide", "residue", "heavy metal", "lead", "cadmium", "mercury"]):
            return "residuo"

        # Otros
        return "otro"

    def hashear_alerta(self, alerta: AlertaNormalizada) -> str:
        """
        Generar hash SHA256 único y determinístico para dedup.

        Campos clave: fuente + reference_number + producto + fecha
        """
        contenido = "|".join([
            str(alerta.fuente),
            str(alerta.reference_number or alerta.alert_id),
            str(alerta.producto_nombre),
            str(alerta.fecha_emitida.date()),
        ])

        return hashlib.sha256(contenido.encode()).hexdigest()


# ============================================================================
# Importar asyncio si se usa descargar_ultimas_24h
# ============================================================================
import asyncio
