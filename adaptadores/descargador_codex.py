"""
Descargador de Codex Alimentarius (UN/FAO standards).

Source: https://www.fao.org/fao-who-codexalimentarius/
Estándares internacionales de alimentos (ONU/FAO).

Estructura:
  - STAN código (ej: STAN 50-1991)
  - Nombre estándar (ej: "Standard for Quinoa")
  - Versión y año
  - Áreas: composición, etiquetado, higiene, residuos, etc.

Estándares principales:
  - STAN 1: General standard
  - STAN 12: Oils and fats
  - STAN 30: Cocoa products
  - STAN 50-1991: Quinoa
  - STAN 152: Meat products
  - STAN 210: Cereals and legumes
  - STAN 230-1969: Fermented milks
  - STAN 240: Spices and seasoning plants
  - STAN 288: Seafood
"""

import logging
import hashlib
import re
from typing import List, Dict, Any, Optional
import httpx

from puertos.descargador_regulaciones import DescargadorCodex as IDescargadorCodex

logger = logging.getLogger(__name__)

CODEX_BASE = "https://www.fao.org/fao-who-codexalimentarius"
CODEX_STANDARDS_PAGE = f"{CODEX_BASE}/standards"

# Estándares Codex más relevantes (fallback data)
CODEX_FALLBACK = [
    {
        'nombre_estandar': 'General standard for food additives',
        'codigo_cat': 'STAN 192-1995',
        'version': '1.0',
        'anio_publicacion': 1995,
    },
    {
        'nombre_estandar': 'General standard for contaminants and toxins in foods',
        'codigo_cat': 'STAN 193-1995',
        'version': '1.0',
        'anio_publicacion': 1995,
    },
    {
        'nombre_estandar': 'Standard for Quinoa',
        'codigo_cat': 'STAN 50-1991',
        'version': '1.0',
        'anio_publicacion': 1991,
    },
    {
        'nombre_estandar': 'Standard for oils and fats',
        'codigo_cat': 'STAN 12-1981',
        'version': '2.0',
        'anio_publicacion': 1981,
    },
    {
        'nombre_estandar': 'Standard for cocoa products',
        'codigo_cat': 'STAN 30-1981',
        'version': '3.0',
        'anio_publicacion': 1981,
    },
    {
        'nombre_estandar': 'Standard for cheese',
        'codigo_cat': 'STAN 283-2021',
        'version': '1.0',
        'anio_publicacion': 2021,
    },
    {
        'nombre_estandar': 'Standard for meat and meat products',
        'codigo_cat': 'STAN 152-1985',
        'version': '2.0',
        'anio_publicacion': 1985,
    },
    {
        'nombre_estandar': 'Standard for cereals, pulses and legumes',
        'codigo_cat': 'STAN 210-1999',
        'version': '1.0',
        'anio_publicacion': 1999,
    },
    {
        'nombre_estandar': 'Standard for fermented milks',
        'codigo_cat': 'STAN 230-1969',
        'version': '2.0',
        'anio_publicacion': 1969,
    },
    {
        'nombre_estandar': 'Standard for spices and seasonings',
        'codigo_cat': 'STAN 240-2003',
        'version': '1.0',
        'anio_publicacion': 2003,
    },
    {
        'nombre_estandar': 'Standard for food hygiene',
        'codigo_cat': 'STAN 3-1969',
        'version': '2.0',
        'anio_publicacion': 1969,
    },
    {
        'nombre_estandar': 'Standard for seafood products',
        'codigo_cat': 'STAN 288-1976',
        'version': '1.0',
        'anio_publicacion': 1976,
    },
]


class DescargadorCodex(IDescargadorCodex):
    """Implementación de descargador para Codex Alimentarius."""

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
        """Verificar que Codex es accesible."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(CODEX_STANDARDS_PAGE)
                is_ok = response.status_code < 400
                status = "✅" if is_ok else "❌"
                self.logger.info(f"{status} Codex: {response.status_code}")
                return is_ok
        except Exception as e:
            self.logger.error(f"❌ Error validando Codex: {e}")
            return False

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar estándares Codex Alimentarius.

        Estrategia:
        1. Intentar acceso a página de estándares
        2. Si falla, usar fallback data (12 estándares principales)

        Retorna: List[{
            'nombre_estandar': 'Standard for Quinoa',
            'codigo_cat': 'STAN 50-1991',
            'version': '1.0',
            'anio_publicacion': 1991,
            'texto': '...',
            'url_oficial': 'https://...',
            'content_hash': 'abc123...'
        }]
        """
        regulaciones = []

        try:
            self.logger.info("📥 Descargando estándares Codex Alimentarius...")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(CODEX_STANDARDS_PAGE)

                if response.status_code != 200:
                    self.logger.warning(
                        f"⚠️  Codex página no disponible ({response.status_code}). "
                        f"Usando datos fallback."
                    )
                    regulaciones = self._usar_fallback()
                else:
                    # Intentar parsear página
                    regulaciones = self.normalizar(response.text)

                    if not regulaciones:
                        self.logger.warning(
                            "⚠️  No se parseó contenido Codex. Usando datos fallback."
                        )
                        regulaciones = self._usar_fallback()

        except Exception as e:
            self.logger.error(f"❌ Error descargando Codex: {e}")
            if self.use_fallback:
                regulaciones = self._usar_fallback()
            else:
                regulaciones = []

        self.logger.info(f"✅ Codex: {len(regulaciones)} estándares")
        return regulaciones

    def normalizar(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parsear HTML de Codex para extraer estándares.

        Busca patrones STAN XXXX en el contenido.
        """
        regulaciones = []

        try:
            # Regex para encontrar códigos STAN
            stan_pattern = r'STAN\s+(\d+[A-Z0-9\-]*)'
            stan_codes = re.findall(stan_pattern, html_content)

            # Remover duplicados
            stan_codes = list(dict.fromkeys(stan_codes))

            self.logger.info(f"   Encontrados {len(stan_codes)} estándares STAN en HTML")

            # Para cada STAN, construir entrada
            for stan_code in stan_codes:
                try:
                    reg = self._extraer_stan_info(html_content, stan_code)
                    if reg:
                        regulaciones.append(reg)
                except Exception as e:
                    self.logger.debug(f"   Skipping STAN {stan_code}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"❌ Error normalizando Codex: {e}")

        return regulaciones

    def _extraer_stan_info(self, html: str, stan_code: str) -> Optional[Dict[str, Any]]:
        """
        Extraer información de un STAN específico del HTML.
        """
        # Buscar contexto alrededor del STAN
        pattern = rf'(STAN\s+{re.escape(stan_code)}.*?(?=STAN|$))'
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)

        if not match:
            return None

        context = match.group(0)[:500]

        # Intentar extraer nombre
        name_pattern = r'>\s*([A-Z][A-Za-z\s&,\-()]+?)\s*<'
        name_match = re.search(name_pattern, context)
        nombre = name_match.group(1) if name_match else "Unknown"

        reg = {
            'nombre_estandar': nombre.strip(),
            'codigo_cat': f"STAN {stan_code}",
            'version': '1.0',
            'anio_publicacion': None,
            'texto': context[:200],
            'url_oficial': f"{CODEX_BASE}/standards/stan/{stan_code.lower()}",
            'content_hash': self._calcular_hash(context)
        }

        return reg

    def _usar_fallback(self) -> List[Dict[str, Any]]:
        """
        Usar datos fallback predefinidos.
        """
        self.logger.info("   Usando fallback data (12 estándares Codex principales)")

        regulaciones = []
        for reg in CODEX_FALLBACK:
            entry = {
                'nombre_estandar': reg['nombre_estandar'],
                'codigo_cat': reg['codigo_cat'],
                'version': reg['version'],
                'anio_publicacion': reg['anio_publicacion'],
                'texto': f"Estándar internacional: {reg['nombre_estandar']}",
                'url_oficial': f"{CODEX_BASE}/standards/{reg['codigo_cat'].lower().replace(' ', '-')}",
                'content_hash': self._calcular_hash(reg['codigo_cat'])
            }
            regulaciones.append(entry)

        return regulaciones

    @staticmethod
    def _calcular_hash(contenido: str) -> str:
        """Calcular SHA256 para change detection."""
        if not contenido:
            return ""
        return hashlib.sha256(contenido.encode('utf-8')).hexdigest()
