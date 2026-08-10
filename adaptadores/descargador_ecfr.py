"""
Descargador de eCFR (FDA Code of Federal Regulations).

Source: https://www.ecfr.gov/api/versioner/v1/full/
API documentation: https://www.ecfr.gov/developers

Títulos relevantes:
  - 21: Food & Drugs (alimentos, aditivos, etiquetado)
  - 7: Agriculture (pesticidas, composición)

Estructura API:
  GET /full/{title}/{part}/{section}
  Returns:
    {
      "part": {...},
      "children": [
        {
          "label": "101",
          "type": "part",
          "title": "Food Labeling",
          "children": [
            {
              "label": "4",
              "type": "section",
              "title": "...",
              "text": "..."
            }
          ]
        }
      ]
    }
"""

import logging
import hashlib
import re
from typing import List, Dict, Any, Optional
import httpx

from puertos.descargador_regulaciones import DescargadorECFR as IDescargadorECFR

logger = logging.getLogger(__name__)

ECFR_API_BASE = "https://www.ecfr.gov/api/versioner/v1/full"
ECFR_TITLES = {
    '21': 'Food and Drugs',
    '7': 'Agriculture',
}

# Partes relevantes en cada título
ECFR_PARTS = {
    '21': [
        '101',  # Food Labeling
        '102',  # Food Standards of Identity and Composition
        '104',  # Nutrition Labeling
        '110',  # Current Good Manufacturing Practice in Manufacturing
        '150',  # Fruit Butters, Jellies, Preserves
        '200',  # Seafood
        '210',  # cgMP - General Rules
        '320',  # Flavoring Agents and Related Substances
        '700',  # Colors
    ],
    '7': [
        '100',  # Federal Insecticide, Fungicide, and Rodenticide Act
        '205',  # Domestic Residue Limits and Import Tolerances
        '300',  # Organic Foods Production Act
    ]
}


class DescargadorECFR(IDescargadorECFR):
    """Implementación de descargador para eCFR."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.logger = logger

    async def validar_acceso(self) -> bool:
        """Verificar que eCFR API responde."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Probar acceso a API base
                url = f"{ECFR_API_BASE}/21"
                response = await client.head(url)
                is_ok = response.status_code < 400
                status = "✅" if is_ok else "❌"
                self.logger.info(f"{status} eCFR API: {response.status_code}")
                return is_ok
        except Exception as e:
            self.logger.error(f"❌ Error validando eCFR: {e}")
            return False

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar eCFR títulos 21 y 7 con sus partes relevantes.

        Retorna lista normalizada de regulaciones.
        """
        regulaciones = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                for title, title_name in ECFR_TITLES.items():
                    self.logger.info(f"📥 Descargando eCFR Título {title} ({title_name})...")

                    # Descargar cada parte relevante
                    partes = ECFR_PARTS.get(title, [])

                    for part in partes:
                        try:
                            url = f"{ECFR_API_BASE}/{title}/{part}"
                            self.logger.debug(f"  → Título {title}, Parte {part}")

                            response = await client.get(url, timeout=self.timeout)

                            if response.status_code != 200:
                                self.logger.warning(f"  ⚠️  Parte {part} no disponible ({response.status_code})")
                                continue

                            data = response.json()

                            # Normalizar respuesta
                            regs = self.normalizar(data, title, part)
                            regulaciones.extend(regs)

                            self.logger.info(f"  ✅ Parte {part}: {len(regs)} secciones descargadas")

                        except Exception as e:
                            self.logger.warning(f"  ❌ Error en parte {part}: {e}")
                            continue

        except Exception as e:
            self.logger.error(f"❌ Error descargando eCFR: {e}")
            return regulaciones

        self.logger.info(f"✅ eCFR descargado: {len(regulaciones)} regulaciones totales")
        return regulaciones

    def normalizar(self, data: Dict[str, Any], title: str, part: str) -> List[Dict[str, Any]]:
        """
        Convertir respuesta JSON de eCFR a formato ecfr_regulations.

        Estructura esperada:
        {
            "part": {"label": "101", "title": "Food Labeling"},
            "children": [
                {
                    "label": "4",
                    "type": "section",
                    "title": "...",
                    "text": "..."
                }
            ]
        }

        Retorna: List[{
            'title': '21',
            'part': '101',
            'section': '4',
            'subsection': None,
            'texto_completo': '...',
            'url_oficial': 'https://...',
            'fecha_efectiva': None,
            'content_hash': 'abc123...'
        }]
        """
        regulaciones = []

        try:
            # Extraer información de la parte
            part_info = data.get('part', {})
            part_title = part_info.get('title', '')

            # Iterar sobre las secciones
            children = data.get('children', [])

            for child in children:
                if child.get('type') != 'section':
                    continue

                section = child.get('label', '')
                section_title = child.get('title', '')
                texto = child.get('text', '')

                if not texto:
                    continue

                # Buscar subsecciones
                subsections = child.get('children', [])

                if not subsections:
                    # Sin subsecciones, guardar como sección simple
                    reg = {
                        'title': title,
                        'part': part,
                        'section': section,
                        'subsection': None,
                        'texto_completo': texto,
                        'url_oficial': f"https://www.ecfr.gov/current/title-{title}/part-{part}#{title}.{part}.{section}",
                        'fecha_efectiva': None,
                        'content_hash': self._calcular_hash(texto)
                    }
                    regulaciones.append(reg)
                else:
                    # Con subsecciones, crear entrada para cada una
                    for subsec in subsections:
                        if subsec.get('type') != 'section':
                            continue

                        subsec_label = subsec.get('label', '')
                        subsec_text = subsec.get('text', '')

                        if not subsec_text:
                            continue

                        reg = {
                            'title': title,
                            'part': part,
                            'section': section,
                            'subsection': subsec_label,
                            'texto_completo': subsec_text,
                            'url_oficial': f"https://www.ecfr.gov/current/title-{title}/part-{part}#{title}.{part}.{section}({subsec_label})",
                            'fecha_efectiva': None,
                            'content_hash': self._calcular_hash(subsec_text)
                        }
                        regulaciones.append(reg)

        except Exception as e:
            self.logger.error(f"❌ Error normalizando parte {title}/{part}: {e}")

        return regulaciones

    @staticmethod
    def _calcular_hash(contenido: str) -> str:
        """Calcular SHA256 del contenido para change detection."""
        if not contenido:
            return ""
        return hashlib.sha256(contenido.encode('utf-8')).hexdigest()
