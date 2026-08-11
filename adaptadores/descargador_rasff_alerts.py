"""
Descargador de alertas RASFF (Rapid Alert System for Food and Feed).

Sistema europeo de alerta rápida para peligros alimentarios.
Portal: https://ec.europa.eu/food/safetyhealthanimals/rasff/

Descarga alertas de las últimas 24h desde el RSS feed de RASFF.
Normaliza a AlertaNormalizada para inserción en BD.
"""

import logging
import hashlib
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

from puertos.descargador_alertas import DescargadorAlertas, AlertaNormalizada

logger = logging.getLogger(__name__)

# URL del RSS feed de RASFF
RASFF_FEED_URL = "https://ec.europa.eu/food/safetyhealthanimals/rasff/rss.php"
RASFF_TIMEOUT = 30
RASFF_MAX_RETRIES = 3


class DescargadorRASFFAlerts(DescargadorAlertas):
    """Descargador de alertas RASFF (Rapid Alert System for Food and Feed)."""

    def __init__(self, timeout: int = RASFF_TIMEOUT, max_retries: int = RASFF_MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries
        self.logger = logger

    async def validar_acceso(self) -> bool:
        """Verificar que RASFF feed es accesible."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(RASFF_FEED_URL, timeout=self.timeout)
                is_ok = response.status_code < 400
                status = "✅" if is_ok else "❌"
                self.logger.info(f"{status} RASFF feed: {response.status_code}")
                return is_ok
        except Exception as e:
            self.logger.error(f"❌ Error validando RASFF: {e}")
            return False

    async def descargar_ultimas_24h(self) -> List[AlertaNormalizada]:
        """
        Descargar alertas RASFF de las últimas 24 horas.

        Parsea el RSS feed oficial y retorna lista normalizada.
        """
        alertas = []
        ayer = datetime.utcnow() - timedelta(days=1)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                self.logger.info(f"📥 Descargando RASFF alerts (últimas 24h)...")

                # Reintentos exponencial
                xml_content = None
                for intento in range(self.max_retries):
                    try:
                        response = await client.get(RASFF_FEED_URL, timeout=self.timeout)

                        if response.status_code == 200:
                            xml_content = response.text
                            self.logger.debug(f"  → RASFF feed descargado ({len(xml_content)} bytes)")
                            break

                        elif response.status_code == 429:
                            self.logger.warning(f"  ⚠️  Rate limit (429). Intento {intento + 1}/{self.max_retries}")
                            if intento < self.max_retries - 1:
                                import asyncio
                                await asyncio.sleep(2 ** intento)
                            continue

                        else:
                            self.logger.warning(f"  ⚠️  RASFF {response.status_code}")
                            if intento < self.max_retries - 1:
                                import asyncio
                                await asyncio.sleep(2 ** intento)
                            continue

                    except httpx.TimeoutException:
                        self.logger.warning(f"  ⏱️  Timeout en intento {intento + 1}/{self.max_retries}")
                        if intento < self.max_retries - 1:
                            import asyncio
                            await asyncio.sleep(2 ** intento)
                        continue

                    except Exception as e:
                        self.logger.warning(f"  ❌ Error en intento {intento + 1}: {e}")
                        if intento < self.max_retries - 1:
                            import asyncio
                            await asyncio.sleep(2 ** intento)
                        continue

                if xml_content:
                    # Parsear XML
                    alertas = self.normalizar(xml_content)

                    # Filtrar últimas 24h
                    alertas_24h = [a for a in alertas if a.fecha_emitida >= ayer]

                    self.logger.info(f"  ✅ RASFF: {len(alertas_24h)} alertas en últimas 24h (total descargadas: {len(alertas)})")
                    return alertas_24h
                else:
                    self.logger.error(f"❌ No se pudo descargar RASFF feed")
                    return alertas

        except Exception as e:
            self.logger.error(f"❌ Error descargando RASFF: {e}")
            return alertas

    def normalizar(self, xml_content: str) -> List[AlertaNormalizada]:
        """
        Parsear XML de RASFF RSS feed y convertir a AlertaNormalizada.

        Estructura esperada del RSS:
        <rss>
          <channel>
            <item>
              <title>Dangerous pathogenic microorganism in peanuts</title>
              <link>https://ec.europa.eu/food/.../alert.php?id=123</link>
              <description>Product: peanuts, Origin: China, ...</description>
              <pubDate>Mon, 09 Aug 2024 08:00:00 +0000</pubDate>
            </item>
          </channel>
        </rss>
        """
        alertas = []

        try:
            root = ET.fromstring(xml_content)

            # Namespace para RSS
            ns = {'': 'http://www.rss-specification.com/rss-spec-v2.html'}

            # Encontrar todos los items (alertas)
            items = root.findall(".//item")
            self.logger.debug(f"  → Parseadas {len(items)} alertas del RSS")

            for item in items:
                try:
                    # Extraer campos
                    titulo = item.findtext("title", "Unknown")
                    descripcion = item.findtext("description", "")
                    link = item.findtext("link", "")
                    pubdate_str = item.findtext("pubDate", "")

                    # Parsear fecha (formato RFC 2822)
                    try:
                        fecha = self._parsear_fecha_rfc2822(pubdate_str)
                    except:
                        fecha = datetime.utcnow()

                    # Extraer información de descripción
                    # Formato típico: "Product: X, Origin: Y, Distribution: Z, Hazard: A"
                    producto, origen, peligro, accion = self._extraer_campos_descripcion(descripcion, titulo)

                    # Categorizar riesgo
                    riesgo_categoria = self._categorizar_riesgo(peligro)

                    # Generar reference_number (extraer ID de URL)
                    reference_number = self._extraer_id_alerta(link)

                    # Crear alerta normalizada
                    alerta_temp = AlertaNormalizada(
                        alert_id="",  # Se llena después
                        fuente="rasff",
                        fecha_emitida=fecha,
                        producto_nombre=producto,
                        riesgo_texto=peligro,
                        riesgo_categoria=riesgo_categoria,
                        pais_origen=origen,
                        pais_destino="EU",  # RASFF es sistema europeo
                        accion=accion,
                        url_oficial=link,
                        reference_number=reference_number,
                        metadatos={
                            "titulo": titulo,
                            "descripcion": descripcion[:500],  # Primeros 500 chars
                        }
                    )

                    # Calcular hash
                    alert_id = self.hashear_alerta(alerta_temp)
                    alerta_temp.alert_id = alert_id

                    alertas.append(alerta_temp)

                except Exception as e:
                    self.logger.warning(f"  ❌ Error normalizando alerta RASFF: {e}")
                    continue

        except ET.ParseError as e:
            self.logger.error(f"❌ Error parseando XML de RASFF: {e}")
            return alertas

        except Exception as e:
            self.logger.error(f"❌ Error normalizando RASFF: {e}")
            return alertas

        return alertas

    def _parsear_fecha_rfc2822(self, fecha_str: str) -> datetime:
        """Parsear fecha en formato RFC 2822 (pubDate de RSS)."""
        # Formato: "Mon, 09 Aug 2024 08:00:00 +0000"
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(fecha_str)

    def _extraer_campos_descripcion(self, descripcion: str, titulo: str) -> tuple[str, str, str, str]:
        """
        Extraer producto, origen, peligro, acción de la descripción y título.

        Returns: (producto, origen, peligro, accion)
        """
        producto = "Unknown"
        origen = "Unknown"
        peligro = titulo  # Usar título como peligro por defecto
        accion = "alert"

        # Parsear descripción (formato: "Product: X, Origin: Y, Hazard: Z, Action: A")
        campos = {}
        for linea in descripcion.split(","):
            if ":" in linea:
                key, val = linea.split(":", 1)
                campos[key.strip().lower()] = val.strip()

        producto = campos.get("product", campos.get("products", "Unknown"))
        origen = campos.get("origin", campos.get("country of origin", "Unknown"))
        peligro = campos.get("hazard", campos.get("hazard description", titulo))
        accion = campos.get("action", campos.get("action taken", "alert")).lower()

        # Limpiar valores
        producto = producto.strip() or "Unknown"
        origen = origen.strip() or "Unknown"
        peligro = peligro.strip() or titulo
        accion = accion.strip() or "alert"

        return producto, origen, peligro, accion

    def _extraer_id_alerta(self, link: str) -> Optional[str]:
        """Extraer ID de la alerta de la URL."""
        # Formato típico: https://ec.europa.eu/food/.../alert.php?id=123
        try:
            if "id=" in link:
                return link.split("id=")[-1].split("&")[0]
        except:
            pass
        return None

    def _categorizar_riesgo(self, peligro: str) -> str:
        """Categorizar tipo de riesgo basado en descripción."""
        peligro_lower = peligro.lower()

        # Patógenos
        if any(x in peligro_lower for x in ["e. coli", "listeria", "salmonella", "campylobacter", "botulism", "shigella", "pathogenic"]):
            return "patogeno"

        # Alérgenos
        if any(x in peligro_lower for x in ["allergen", "milk", "peanut", "tree nut", "shellfish", "gluten", "soy", "allergens"]):
            return "alérgeno"

        # Residuos químicos/pesticidas
        if any(x in peligro_lower for x in ["pesticide", "residue", "heavy metal", "lead", "cadmium", "mercury", "chemical"]):
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
