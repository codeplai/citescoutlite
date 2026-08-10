"""
Descargador de INACAL (Instituto Nacional de Calidad - Perú).

Source: https://www.inacal.gob.pe/
Normas técnicas peruanas para alimentos.
"""

import logging
from typing import List, Dict, Any
import httpx

from puertos.descargador_regulaciones import DescargadorINACAL as IDescargadorINACAL

logger = logging.getLogger(__name__)

INACAL_BASE = "https://www.inacal.gob.pe"


class DescargadorINACAL(IDescargadorINACAL):
    """Implementación de descargador para INACAL."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logger

    async def validar_acceso(self) -> bool:
        """Verificar que INACAL es accesible."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(INACAL_BASE)
                is_ok = response.status_code < 400
                status = "✅" if is_ok else "❌"
                self.logger.info(f"{status} INACAL: {response.status_code}")
                return is_ok
        except Exception as e:
            self.logger.error(f"❌ Error validando INACAL: {e}")
            return False

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar Normas Técnicas Peruanas para alimentos.

        TODO (S4.4): Implementar descarga real.
        Actualmente retorna lista vacía.
        """
        self.logger.info("📥 Descargando INACAL (TODO: implementar)")

        # TODO: Implementar
        # Tablas relevantes: carnes, lácteos, frutas, hortalizas, conservas
        # NTS 201.041: Norma para quinua
        # NTS 201.005: Norma para papa
        # etc.

        return []

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir datos INACAL a formato regulacion_cita."""
        # TODO: Implementar
        return []
