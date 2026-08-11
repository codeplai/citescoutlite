"""
Puertos para descargadores de alertas de retiro (openFDA + RASFF).

Estructura normalizada para alertas de retiro de alimentos desde:
- openFDA: FDA enforcement actions (USA)
- RASFF: Rapid Alert System for Food and Feed (EU)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AlertaNormalizada:
    """Estructura normalizada de alerta de retiro."""
    alert_id: str                   # Hash único para dedup
    fuente: str                     # 'openfda' o 'rasff'
    fecha_emitida: datetime
    producto_nombre: str
    riesgo_texto: str              # Descripción del peligro
    riesgo_categoria: str           # 'patogeno', 'alérgeno', 'residuo', 'otro'
    pais_origen: str               # País donde se originó
    pais_destino: str              # País o región destino
    accion: str                    # 'recall', 'blocked', 'detained', etc
    url_oficial: str               # Link a documentación oficial
    empresa: str = None            # Empresa responsable (si aplica)
    reference_number: str = None   # Número de referencia único
    metadatos: Dict[str, Any] = None  # Campos específicos de cada fuente


class DescargadorAlertas(ABC):
    """
    Interfaz base para descargar alertas de retiro de alimentos.

    Implementaciones específicas:
    - DescargadorOpenFDAAlerts: FDA enforcement actions
    - DescargadorRASFFAlerts: RASFF rapid alerts
    """

    @abstractmethod
    async def descargar_ultimas_24h(self) -> List[AlertaNormalizada]:
        """
        Descargar alertas de las últimas 24 horas desde la fuente.

        Returns:
            Lista de AlertaNormalizada normalizadas

        Raises:
            ConnectionError: Si la API no es accesible
            ValueError: Si la respuesta no es parseable
        """
        pass

    @abstractmethod
    async def validar_acceso(self) -> bool:
        """
        Validar que la fuente es accesible antes de descargar.

        Returns:
            True si accesible, False si no
        """
        pass

    @abstractmethod
    def normalizar(self, datos_brutos: Any) -> List[AlertaNormalizada]:
        """
        Convertir datos brutos de API a estructura normalizada.

        Args:
            datos_brutos: Respuesta JSON de la API

        Returns:
            Lista de AlertaNormalizada
        """
        pass

    @abstractmethod
    def hashear_alerta(self, alerta: AlertaNormalizada) -> str:
        """
        Generar hash único para dedup de alertas.

        Debe ser determinístico: misma alerta siempre produce mismo hash.

        Args:
            alerta: Alerta normalizada

        Returns:
            Hash SHA256 en formato hex
        """
        pass
