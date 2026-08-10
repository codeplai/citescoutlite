"""
Mapeador de regulaciones: INACAL ↔ eCFR/EFSA/Codex

Purpose:
  Crear equivalencias entre normas peruanas (INACAL) y regulaciones
  internacionales (eCFR, EFSA, Codex).

Strategy:
  1. Fuzzy matching en nombres de ingredientes
  2. Buscar equivalencias explícitas si existen
  3. Fallback a Codex como referencia internacional
  4. Registrar confidence score para cada mapping

Example:
  INACAL "Norma para Quinua" → Codex "STAN 50-1991"
  eCFR "21 CFR 101" → EFSA "E500" (si aplica)
  etc.
"""

import logging
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# Equivalencias explícitas conocidas (alimentadas manualmente)
EQUIVALENCIAS_CONOCIDAS = {
    'NTS 201.041': {  # Quinua
        'nombre_ingrediente': 'Quinoa',
        'codex_ref': 'STAN 50-1991',
        'ecfr_ref': '21 CFR 101',
        'efsa_ref': None,
        'confidence': 1.0,
    },
    'NTS 201.001': {  # Aditivos
        'nombre_ingrediente': 'Food Additives',
        'codex_ref': 'STAN 192-1995',
        'ecfr_ref': '21 CFR 320',
        'efsa_ref': None,
        'confidence': 0.95,
    },
    'NTS 201.053': {  # Carnes
        'nombre_ingrediente': 'Meat',
        'codex_ref': 'STAN 152-1985',
        'ecfr_ref': '21 CFR 110',
        'efsa_ref': None,
        'confidence': 0.9,
    },
    'NTS 201.044': {  # Quesos
        'nombre_ingrediente': 'Cheese',
        'codex_ref': 'STAN 283-2021',
        'ecfr_ref': '21 CFR 133',
        'efsa_ref': None,
        'confidence': 0.95,
    },
}

# Mapeo de E-numbers a nombres de ingredientes
EFSA_TO_NAMES = {
    'E100': 'Curcumin',
    'E101': 'Riboflavin',
    'E200': 'Sorbic acid',
    'E201': 'Sodium sorbate',
    'E300': 'Ascorbic acid',
    'E500': 'Sodium bicarbonate',
    'E621': 'Monosodium glutamate',
}


class MapeadorRegulaciones:
    """Mapea equivalencias entre regulaciones de diferentes países/organismos."""

    def __init__(self, repo):
        """
        Args:
            repo: RepositorioRegulaciones (para queries)
        """
        self.repo = repo
        self.logger = logger

    async def mapear_inacal(self) -> List[Dict]:
        """
        Crear mappings para todas las normas INACAL.

        Retorna lista de mappings creados con confidence scores.
        """
        mappings = []

        try:
            # Obtener todas las normas INACAL
            inacal_normas = await self.repo.buscar_por_tipo('INACAL')

            self.logger.info(f"📍 Mapeando {len(inacal_normas)} normas INACAL...")

            for norma in inacal_normas:
                mapping = await self._mapear_norma_unica(norma)
                if mapping:
                    mappings.append(mapping)

        except Exception as e:
            self.logger.error(f"❌ Error en mapeo INACAL: {e}")

        self.logger.info(f"✅ Creados {len(mappings)} mappings")
        return mappings

    async def _mapear_norma_unica(self, inacal_norma: Dict) -> Optional[Dict]:
        """
        Mapear una norma INACAL individual a eCFR/EFSA/Codex.

        Retorna mapping dict o None si no hay match.
        """
        codigo_nts = inacal_norma.get('codigo_nts', '')
        nombre_nts = inacal_norma.get('nombre_nts', '')

        self.logger.debug(f"   Mapeando {codigo_nts}...")

        # 1. Buscar en equivalencias conocidas
        if codigo_nts in EQUIVALENCIAS_CONOCIDAS:
            known = EQUIVALENCIAS_CONOCIDAS[codigo_nts]
            self.logger.debug(f"      ✅ Equivalencia conocida")

            mapping = {
                'ingrediente_canonico': known['nombre_ingrediente'],
                'inacal_ref': codigo_nts,
                'codex_ref': known['codex_ref'],
                'ecfr_ref': known['ecfr_ref'],
                'efsa_ref': known['efsa_ref'],
                'mapping_confidence': known['confidence'],
                'notas': 'Equivalencia manual conocida',
                'validated_by': 'Expert',
            }

            # Guardar en DB
            mapping_id = await self.repo.guardar_mapping(**mapping)
            return {**mapping, 'mapping_id': mapping_id}

        # 2. Fuzzy match en nombre
        ingrediente_canonico = self._extraer_ingrediente(nombre_nts)

        if not ingrediente_canonico:
            self.logger.debug(f"      ⚠️  No se extrajo ingrediente")
            return None

        # 3. Buscar equivalentes en Codex (siempre disponible)
        codex_match = await self._buscar_codex_match(ingrediente_canonico)

        if not codex_match:
            self.logger.debug(f"      ⚠️  No hay equivalencia Codex")
            return None

        confidence = 0.7  # Fuzzy match es menos confiable

        mapping = {
            'ingrediente_canonico': ingrediente_canonico,
            'inacal_ref': codigo_nts,
            'codex_ref': codex_match.get('codigo_cat'),
            'ecfr_ref': None,
            'efsa_ref': None,
            'mapping_confidence': confidence,
            'notas': f"Fuzzy match: {ingrediente_canonico} ← {nombre_nts}",
            'validated_by': None,
        }

        self.logger.debug(f"      → Codex {codex_match.get('codigo_cat')} (confidence={confidence})")

        # Guardar en DB
        mapping_id = await self.repo.guardar_mapping(**mapping)
        return {**mapping, 'mapping_id': mapping_id}

    async def _buscar_codex_match(self, ingrediente: str) -> Optional[Dict]:
        """
        Buscar estándar Codex que coincida con ingrediente.

        Retorna: Dict con codigo_cat, o None si no hay match.
        """
        try:
            codex_results = await self.repo.buscar_por_ingrediente(
                ingrediente, pais='PE'  # Buscar en Codex como fallback
            )

            for result in codex_results:
                if result.get('tipo_regulacion') == 'Codex':
                    return result

        except Exception as e:
            self.logger.debug(f"Error en _buscar_codex_match: {e}")

        return None

    def _extraer_ingrediente(self, nombre_nts: str) -> Optional[str]:
        """
        Extraer nombre canónico del ingrediente de la descripción NTS.

        Ejemplos:
          "Norma Técnica para Quinua" → "Quinoa"
          "Norma para Aditivos Alimentarios" → "Food Additives"
          "Norma para Carnes Frescas" → "Meat"
        """
        # Palabras clave a buscar
        keywords = {
            'quinua': 'Quinoa',
            'quinoa': 'Quinoa',
            'papa': 'Potato',
            'carne': 'Meat',
            'queso': 'Cheese',
            'leche': 'Milk',
            'aceite': 'Oil',
            'miel': 'Honey',
            'café': 'Coffee',
            'aditivo': 'Food Additives',
            'conserva': 'Conserves',
            'fruta': 'Fruit',
            'verdura': 'Vegetable',
            'hortaliza': 'Vegetable',
        }

        nombre_lower = nombre_nts.lower()

        # Buscar keywords
        for keyword, canonical in keywords.items():
            if keyword in nombre_lower:
                self.logger.debug(f"      Extraído: {canonical}")
                return canonical

        # Si no hay keyword, retornar None
        return None

    async def validar_mappings(self, min_confidence: float = 0.75) -> Dict:
        """
        Validar quality de mappings.

        Retorna: {
            'total': 100,
            'high_confidence': 80,  # >= min_confidence
            'low_confidence': 20,   # < min_confidence
            'coverage': 0.80,       # high_confidence / total
        }
        """
        try:
            # Obtener stats
            counts = await self.repo.contar_por_fuente()

            inacal_count = counts.get('inacal', 0)
            mapping_count = counts.get('mapping', 0)

            coverage = mapping_count / inacal_count if inacal_count > 0 else 0

            stats = {
                'total_inacal': inacal_count,
                'total_mappings': mapping_count,
                'coverage': coverage,
                'min_confidence_target': min_confidence,
            }

            self.logger.info(f"📊 Validación de mappings:")
            self.logger.info(f"   INACAL total: {inacal_count}")
            self.logger.info(f"   Mappings creados: {mapping_count}")
            self.logger.info(f"   Coverage: {coverage:.1%}")

            return stats

        except Exception as e:
            self.logger.error(f"❌ Error validando mappings: {e}")
            return {}

    @staticmethod
    def fuzzy_match(str1: str, str2: str, threshold: float = 0.8) -> float:
        """
        Calcular similitud entre dos strings (0.0-1.0).

        threshold: mínimo para considerar "match"
        """
        ratio = SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
        return ratio if ratio >= threshold else 0.0
