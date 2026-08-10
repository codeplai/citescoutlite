"""
Descargador de EFSA (European Food Safety Authority).

Source: https://www.efsa.europa.eu/
Additives register con E-numbers autorizados.
"""

import logging
from typing import List, Dict, Any
import httpx

from puertos.descargador_regulaciones import DescargadorEFSA as IDescargadorEFSA

logger = logging.getLogger(__name__)

EFSA_API_BASE = "https://www.efsa.europa.eu"


class DescargadorEFSA(IDescargadorEFSA):
    """Implementación de descargador para EFSA."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logger

    async def validar_acceso(self) -> bool:
        """Verificar que EFSA es accesible."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(EFSA_API_BASE)
                is_ok = response.status_code < 400
                status = "✅" if is_ok else "❌"
                self.logger.info(f"{status} EFSA: {response.status_code}")
                return is_ok
        except Exception as e:
            self.logger.error(f"❌ Error validando EFSA: {e}")
            return False

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar registro de aditivos EFSA.

        TODO (S4.2): Implementar descarga real.
        Actualmente retorna lista vacía.
        """
        self.logger.info("📥 Descargando EFSA (TODO: implementar)")

        # TODO: Implementar
        # EFSA Additives register está en:
        # https://www.efsa.europa.eu/en/topics/topic/food-additives
        # Buscar "Register of authorised substances"

        return []

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir datos EFSA a formato regulacion_cita."""
        # TODO: Implementar
        return []
