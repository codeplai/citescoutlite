"""
Descargador de INACAL (Instituto Nacional de Calidad - Perú).

Source: https://www.inacal.gob.pe/
Normas Técnicas Peruanas para alimentos.

Tablas relevantes:
  - Carnes
  - Lácteos
  - Frutas
  - Hortalizas
  - Conservas
  - Cereales

Estructura:
  - NTS código (ej: NTS 201.041)
  - Nombre norma técnica
  - Versión y año
  - Equivalencias internacionales

Nota: INACAL típicamente armoniza con:
  - eCFR (para aditivos)
  - EFSA (para aditivos europeos)
  - Codex (referencia global)
"""

import logging
import hashlib
from typing import List, Dict, Any, Optional
import httpx

from puertos.descargador_regulaciones import DescargadorINACAL as IDescargadorINACAL

logger = logging.getLogger(__name__)

INACAL_BASE = "https://www.inacal.gob.pe"
INACAL_NTS_PAGE = f"{INACAL_BASE}/inicio/categorias/alimentos-y-bebidas"

# Normas Técnicas Peruanas principales (fallback data)
INACAL_FALLBACK = [
    {
        'nombre_nts': 'Norma Técnica Peruana para Quinua',
        'codigo_nts': 'NTS 201.041',
        'version': '1.0',
        'anio_publicacion': 2009,
        'equivalencia_codex': 'STAN 50-1991',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Papa',
        'codigo_nts': 'NTS 201.005',
        'version': '1.0',
        'anio_publicacion': 2005,
        'equivalencia_codex': 'STAN 210-1999',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Aditivos Alimentarios',
        'codigo_nts': 'NTS 201.001',
        'version': '1.0',
        'anio_publicacion': 2012,
        'equivalencia_codex': 'STAN 192-1995',
        'equivalencia_ecfr': '21 CFR 320',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Carnes Frescas',
        'codigo_nts': 'NTS 201.053',
        'version': '1.0',
        'anio_publicacion': 2014,
        'equivalencia_codex': 'STAN 152-1985',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Quesos',
        'codigo_nts': 'NTS 201.044',
        'version': '1.0',
        'anio_publicacion': 2012,
        'equivalencia_codex': 'STAN 283-2021',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Conservas Vegetales',
        'codigo_nts': 'NTS 201.002',
        'version': '1.0',
        'anio_publicacion': 2008,
        'equivalencia_codex': 'STAN 3-1969',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Café',
        'codigo_nts': 'NTS 201.037',
        'version': '1.0',
        'anio_publicacion': 2013,
        'equivalencia_codex': 'STAN 226',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Leche',
        'codigo_nts': 'NTS 201.040',
        'version': '1.0',
        'anio_publicacion': 2013,
        'equivalencia_codex': 'STAN 230-1969',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Miel de Abeja',
        'codigo_nts': 'NTS 209.042',
        'version': '1.0',
        'anio_publicacion': 2010,
        'equivalencia_codex': 'STAN 12',
    },
    {
        'nombre_nts': 'Norma Técnica Peruana para Aceites Comestibles',
        'codigo_nts': 'NTS 201.019',
        'version': '1.0',
        'anio_publicacion': 2010,
        'equivalencia_codex': 'STAN 12-1981',
        'equivalencia_ecfr': '21 CFR 150',
    },
]


class DescargadorINACAL(IDescargadorINACAL):
    """Implementación de descargador para INACAL."""

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

        Estrategia:
        1. Intentar acceso a página de normas
        2. Si falla, usar fallback data (10 NTS principales)

        Retorna: List[{
            'nombre_nts': 'Norma Técnica Peruana para Quinua',
            'codigo_nts': 'NTS 201.041',
            'version': '1.0',
            'anio_publicacion': 2009,
            'texto': '...',
            'url_oficial': 'https://...',
            'content_hash': 'abc123...'
        }]
        """
        regulaciones = []

        try:
            self.logger.info("📥 Descargando INACAL (Normas Técnicas Peruanas)...")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(INACAL_NTS_PAGE)

                if response.status_code != 200:
                    self.logger.warning(
                        f"⚠️  INACAL página no disponible ({response.status_code}). "
                        f"Usando datos fallback."
                    )
                    regulaciones = self._usar_fallback()
                else:
                    # Intentar parsear página
                    regulaciones = self.normalizar(response.text)

                    if not regulaciones:
                        self.logger.warning(
                            "⚠️  No se parseó contenido INACAL. Usando datos fallback."
                        )
                        regulaciones = self._usar_fallback()

        except Exception as e:
            self.logger.error(f"❌ Error descargando INACAL: {e}")
            if self.use_fallback:
                regulaciones = self._usar_fallback()
            else:
                regulaciones = []

        self.logger.info(f"✅ INACAL: {len(regulaciones)} normas técnicas")
        return regulaciones

    def normalizar(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parsear HTML de INACAL para extraer normas técnicas.

        Busca patrones NTS XXXXX en el contenido.
        """
        regulaciones = []

        try:
            import re

            # Regex para encontrar códigos NTS
            nts_pattern = r'NTS\s+(\d+[\.0-9]*)'
            nts_codes = re.findall(nts_pattern, html_content)

            # Remover duplicados
            nts_codes = list(dict.fromkeys(nts_codes))

            self.logger.info(f"   Encontradas {len(nts_codes)} normas NTS en HTML")

            # Para cada NTS, construir entrada
            for nts_code in nts_codes:
                try:
                    reg = self._extraer_nts_info(html_content, nts_code)
                    if reg:
                        regulaciones.append(reg)
                except Exception as e:
                    self.logger.debug(f"   Skipping NTS {nts_code}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"❌ Error normalizando INACAL: {e}")

        return regulaciones

    def _extraer_nts_info(self, html: str, nts_code: str) -> Optional[Dict[str, Any]]:
        """
        Extraer información de una NTS específica del HTML.
        """
        import re

        # Buscar contexto alrededor del NTS
        pattern = rf'(NTS\s+{re.escape(nts_code)}.*?(?=NTS|$))'
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)

        if not match:
            return None

        context = match.group(0)[:500]

        # Intentar extraer nombre
        name_pattern = r'>\s*([A-Z][A-Za-z\s&,\-()]+?)\s*<'
        name_match = re.search(name_pattern, context)
        nombre = name_match.group(1) if name_match else "Unknown"

        reg = {
            'nombre_nts': nombre.strip(),
            'codigo_nts': f"NTS {nts_code}",
            'version': '1.0',
            'anio_publicacion': None,
            'texto': context[:200],
            'url_oficial': f"{INACAL_BASE}/nts/{nts_code.lower()}",
            'content_hash': self._calcular_hash(context)
        }

        return reg

    def _usar_fallback(self) -> List[Dict[str, Any]]:
        """
        Usar datos fallback predefinidos.
        """
        self.logger.info("   Usando fallback data (10 NTS principales de INACAL)")

        regulaciones = []
        for reg in INACAL_FALLBACK:
            entry = {
                'nombre_nts': reg['nombre_nts'],
                'codigo_nts': reg['codigo_nts'],
                'version': reg['version'],
                'anio_publicacion': reg['anio_publicacion'],
                'texto': f"Norma técnica peruana: {reg['nombre_nts']}",
                'url_oficial': f"{INACAL_BASE}/nts/{reg['codigo_nts'].lower().replace(' ', '-')}",
                'content_hash': self._calcular_hash(reg['codigo_nts'])
            }
            regulaciones.append(entry)

        return regulaciones

    @staticmethod
    def _calcular_hash(contenido: str) -> str:
        """Calcular SHA256 para change detection."""
        if not contenido:
            return ""
        return hashlib.sha256(contenido.encode('utf-8')).hexdigest()
