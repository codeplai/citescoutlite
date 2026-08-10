"""
Puertos para descargadores de regulaciones externas.

Cada fuente (eCFR, EFSA, Codex, INACAL, DIGESA) tiene su propio
descargador que implementa esta interfaz.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class DescargadorRegulaciones(ABC):
    """
    Interfaz base para descargar regulaciones de fuentes externas.

    Implementaciones específicas:
    - DescargadorECFR: FDA (https://www.ecfr.gov/api/)
    - DescargadorEFSA: European additive register
    - DescargadorCodex: FAO/WHO Codex Alimentarius
    - DescargadorINACAL: Peruvian standards (PDF)
    - DescargadorDIGESA: Peruvian health authority (PDF + OCR)
    """

    @abstractmethod
    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar regulaciones desde la fuente externa.

        Returns:
            List de diccionarios normalizados. Estructura específica
            depende de la implementación (ecfr_regulations, efsa_regulations, etc.)

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
    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """
        Normalizar datos crudos al formato estándar de regulacion_cita.

        Implementación específica por fuente.
        """
        pass


class DescargadorECFR(DescargadorRegulaciones):
    """Descargador de eCFR (FDA Code of Federal Regulations)."""

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar títulos 21 (Food & Drugs) y 7 (Agriculture) de eCFR.

        API: https://www.ecfr.gov/api/versioner/v1/full/
        Estructura esperada:
        {
            "title": 21,
            "parts": [
                {
                    "part": "101",
                    "sections": [
                        {
                            "section": "4",
                            "paragraphs": [...]
                        }
                    ]
                }
            ]
        }
        """
        pass

    async def validar_acceso(self) -> bool:
        """Verificar que eCFR API responde."""
        pass

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir eCFR JSON al formato ecfr_regulations."""
        pass


class DescargadorEFSA(DescargadorRegulaciones):
    """Descargador de EFSA (European Food Safety Authority additives)."""

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar registro de aditivos autorizados de EFSA.

        Fuente: https://www.efsa.europa.eu/en/topics/topic/food-additives
        Buscar "Register of authorised substances"

        Estructura esperada por ingrediente:
        {
            "e_number": "E500",
            "name": "Sodium bicarbonate",
            "authorized_uses": ["Bread", "Biscuits"],
            "max_level": "0.5%"
        }
        """
        pass

    async def validar_acceso(self) -> bool:
        """Verificar que EFSA Register es accesible."""
        pass

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir EFSA data al formato efsa_regulations."""
        pass


class DescargadorCodex(DescargadorRegulaciones):
    """Descargador de Codex Alimentarius (UN/FAO standards)."""

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar estándares Codex relevantes para alimentos.

        Fuente: https://www.fao.org/fao-who-codexalimentarius/
        Estándares relevantes: composición, etiquetado, higiene, residuos

        Estructura esperada:
        {
            "name": "Standard for Quinoa",
            "code": "STAN 50-1991",
            "version": "1.0",
            "year": 1991,
            "text": "..."
        }
        """
        pass

    async def validar_acceso(self) -> bool:
        """Verificar que Codex es accesible."""
        pass

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir Codex data al formato codex_standards."""
        pass


class DescargadorINACAL(DescargadorRegulaciones):
    """Descargador de INACAL (Peruvian technical standards)."""

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar Normas Técnicas Peruanas para alimentos.

        Fuente: https://www.inacal.gob.pe/
        Tablas relevantes: carnes, lácteos, frutas, hortalizas, conservas

        Estructura esperada:
        {
            "nombre": "Norma Técnica Peruana para Quinua",
            "codigo": "NTS 201.041",
            "version": "1.0",
            "texto": "..."
        }
        """
        pass

    async def validar_acceso(self) -> bool:
        """Verificar que INACAL es accesible."""
        pass

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir INACAL data al formato inacal_nts."""
        pass


class DescargadorDIGESA(DescargadorRegulaciones):
    """
    Descargador de DIGESA (Peruvian health authority directives).

    Procesa PDFs con OCR para extraer directivas de importación, etiquetado, etc.
    """

    async def descargar(self) -> List[Dict[str, Any]]:
        """
        Descargar PDFs de DIGESA y procesar con OCR.

        Fuente: https://www.digesa.minsa.gob.pe/
        Buscar: Directivas de importación, etiquetado, vigilancia

        Estructura esperada (tras OCR):
        {
            "asunto": "Prohibición de quitosano",
            "ingrediente": "quitosano",
            "accion": "bloqueado",
            "limite": None,
            "justificacion": "No autorizado según resolución...",
            "fecha": "2026-01-15",
            "ocr_accuracy": 0.85
        }
        """
        pass

    async def validar_acceso(self) -> bool:
        """Verificar que DIGESA PDFs son descargables."""
        pass

    def normalizar(self, datos_brutos: Any) -> List[Dict[str, Any]]:
        """Convertir DIGESA OCR al formato digesa_directivas."""
        pass

    @abstractmethod
    async def procesar_ocr(self, archivo_pdf: str) -> str:
        """
        Procesar PDF con OCR (Tesseract o Google Vision).

        Args:
            archivo_pdf: Ruta o URL del PDF

        Returns:
            Texto extraído
        """
        pass
