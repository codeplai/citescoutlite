"""
Descargador de EFSA (European Food Safety Authority).

Source: https://www.efsa.europa.eu/
Registro de aditivos autorizados (E-numbers).

Estructura de datos:
  - E-number: Código único (E100-E1521)
  - Nombre: Nombre del aditivo (Curcumin, Sodium Nitrite, etc.)
  - Usos autorizados: Array de categorías de alimentos
  - Nivel máximo: Límite permitido en % o mg/kg
  - URL oficial: Enlace a ficha técnica EFSA

Fuentes:
  - https://www.efsa.europa.eu/en/topics/topic/food-additives
  - Registro de aditivos autorizados (web scraping)
"""

import logging
import re
import hashlib
from typing import List, Dict, Any, Optional
import httpx

from puertos.descargador_regulaciones import DescargadorEFSA as IDescargadorEFSA

logger = logging.getLogger(__name__)

EFSA_BASE = "https://www.efsa.europa.eu"
EFSA_ADDITIVES_PAGE = f"{EFSA_BASE}/en/topics/topic/food-additives"


# E-numbers más comunes (fallback data si descarga falla)
EFSA_FALLBACK = [
    {
        'e_number': 'E100', 'ingredient_name': 'Curcumin',
        'authorized_uses': ['Beverages', 'Fats and oils', 'Dairy products'],
        'max_levels_pct': '200 mg/kg'
    },
    {
        'e_number': 'E101', 'ingredient_name': 'Riboflavin',
        'authorized_uses': ['All food categories'],
        'max_levels_pct': 'q.s.'
    },
    {
        'e_number': 'E200', 'ingredient_name': 'Sorbic acid',
        'authorized_uses': ['Cheese', 'Bakery', 'Beverages'],
        'max_levels_pct': '2000 mg/kg'
    },
    {
        'e_number': 'E201', 'ingredient_name': 'Sodium sorbate',
        'authorized_uses': ['Cheese', 'Bakery'],
        'max_levels_pct': '2000 mg/kg'
    },
    {
        'e_number': 'E202', 'ingredient_name': 'Potassium sorbate',
        'authorized_uses': ['Cheese', 'Bakery', 'Jams'],
        'max_levels_pct': '2000 mg/kg'
    },
    {
        'e_number': 'E300', 'ingredient_name': 'Ascorbic acid (Vitamin C)',
        'authorized_uses': ['All food categories'],
        'max_levels_pct': 'q.s.'
    },
    {
        'e_number': 'E500', 'ingredient_name': 'Sodium bicarbonate',
        'authorized_uses': ['Bread', 'Biscuits', 'Cakes', 'Flour'],
        'max_levels_pct': 'q.s.'
    },
    {
        'e_number': 'E501', 'ingredient_name': 'Potassium bicarbonate',
        'authorized_uses': ['Bread', 'Biscuits'],
        'max_levels_pct': 'q.s.'
    },
    {
        'e_number': 'E621', 'ingredient_name': 'Monosodium glutamate (MSG)',
        'authorized_uses': ['Seasonings', 'Processed foods', 'Soups'],
        'max_levels_pct': '10000 mg/kg'
    },
    {
        'e_number': 'E635', 'ingredient_name': 'Sodium 5\'-ribonucleotide',
        'authorized_uses': ['Snacks', 'Seasonings'],
        'max_levels_pct': '500 mg/kg'
    },
]


class DescargadorEFSA(IDescargadorEFSA):
    """Implementación de descargador para EFSA."""

    def __init__(self, timeout: int = 30, use_fallback: bool = True):
        """
        Args:
            timeout: Timeout para requests HTTP
            use_fallback: Si True, usa datos fallback si descarga falla
        """
        self.timeout = timeout
        self.use_fallback = use_fallback
        self.logger = logger

    async def validar_acceso(self) -> bool:
        """Verificar que EFSA es accesible."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(EFSA_ADDITIVES_PAGE)
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

        Estrategia:
        1. Intentar acceso a página de aditivos autorizados
        2. Parsear HTML para extraer E-numbers
        3. Si falla, usar fallback data (E-numbers más comunes)

        Retorna: List[{
            'e_number': 'E500',
            'ingredient_name': 'Sodium bicarbonate',
            'authorized_uses': ['Bread', 'Biscuits'],
            'max_levels_pct': 'q.s.',
            'url_oficial': 'https://...',
            'content_hash': 'abc123...'
        }]
        """
        regulaciones = []

        try:
            self.logger.info("📥 Descargando EFSA aditivos autorizados...")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(EFSA_ADDITIVES_PAGE)

                if response.status_code != 200:
                    self.logger.warning(
                        f"⚠️  EFSA página no disponible ({response.status_code}). "
                        f"Usando datos fallback."
                    )
                    regulaciones = self._usar_fallback()
                else:
                    # Intentar parsear página
                    regulaciones = self.normalizar(response.text)

                    if not regulaciones:
                        self.logger.warning(
                            "⚠️  No se parseó contenido EFSA. Usando datos fallback."
                        )
                        regulaciones = self._usar_fallback()

        except Exception as e:
            self.logger.error(f"❌ Error descargando EFSA: {e}")
            if self.use_fallback:
                regulaciones = self._usar_fallback()
            else:
                regulaciones = []

        self.logger.info(f"✅ EFSA: {len(regulaciones)} aditivos")
        return regulaciones

    def normalizar(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parsear HTML de EFSA para extraer E-numbers.

        Estructura HTML variable, usa regex flexible para encontrar patrones.
        """
        regulaciones = []

        try:
            # Regex para encontrar E-numbers (E + 3-4 dígitos)
            e_number_pattern = r'E\d{3,4}'
            e_numbers = re.findall(e_number_pattern, html_content)

            # Remover duplicados manteniendo orden
            e_numbers = list(dict.fromkeys(e_numbers))

            self.logger.info(f"   Encontrados {len(e_numbers)} E-numbers en HTML")

            # Para cada E-number, construir entrada
            for e_num in e_numbers:
                try:
                    reg = self._extraer_e_number_info(html_content, e_num)
                    if reg:
                        regulaciones.append(reg)
                except Exception as e:
                    self.logger.debug(f"   Skipping {e_num}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"❌ Error normalizando EFSA: {e}")

        return regulaciones

    def _extraer_e_number_info(self, html: str, e_number: str) -> Optional[Dict[str, Any]]:
        """
        Extraer información de un E-number específico del HTML.
        """
        # Buscar contexto alrededor del E-number
        pattern = rf'({e_number}.*?(?=E\d{{3,4}}|$))'
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)

        if not match:
            return None

        context = match.group(0)[:500]  # Limitar contexto

        # Intentar extraer nombre
        name_pattern = r'>\s*([A-Z][A-Za-z\s&,\-()]+?)\s*<'
        name_match = re.search(name_pattern, context)
        ingredient_name = name_match.group(1) if name_match else "Unknown"

        reg = {
            'e_number': e_number,
            'ingredient_name': ingredient_name.strip(),
            'authorized_uses': [],
            'max_levels_pct': 'Variable',
            'url_oficial': f"{EFSA_BASE}/en/additives/{e_number.lower()}",
            'content_hash': self._calcular_hash(context)
        }

        return reg

    def _usar_fallback(self) -> List[Dict[str, Any]]:
        """
        Usar datos fallback predefinidos.
        """
        self.logger.info("   Usando fallback data (E-numbers comunes)")

        regulaciones = []
        for reg in EFSA_FALLBACK:
            entry = {
                'e_number': reg['e_number'],
                'ingredient_name': reg['ingredient_name'],
                'authorized_uses': reg['authorized_uses'],
                'max_levels_pct': reg['max_levels_pct'],
                'url_oficial': f"{EFSA_BASE}/en/additives/{reg['e_number'].lower()}",
                'content_hash': self._calcular_hash(reg['e_number'])
            }
            regulaciones.append(entry)

        return regulaciones

    @staticmethod
    def _calcular_hash(contenido: str) -> str:
        """Calcular SHA256 para change detection."""
        if not contenido:
            return ""
        return hashlib.sha256(contenido.encode('utf-8')).hexdigest()
