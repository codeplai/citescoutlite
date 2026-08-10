"""
Puertos (interfaces) para el corpus regulatorio.

Definen el contrato que debe cumplir cualquier implementación
de descarga y búsqueda de regulaciones.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class RepositorioRegulaciones(ABC):
    """
    Interfaz para guardar y buscar regulaciones en base de datos.

    Implementaciones:
    - repositorio_regulaciones_postgres.py: Guardado en PostgreSQL
    """

    # ============================================================
    # GUARDAR REGULACIONES
    # ============================================================

    @abstractmethod
    async def guardar_ecfr(self, regulaciones: List[Dict[str, Any]]) -> int:
        """
        Guardar regulaciones FDA (eCFR) en ecfr_regulations.

        Args:
            regulaciones: List[{
                'title': '21',
                'part': '101',
                'section': '4',
                'subsection': 'a',
                'texto_completo': '...',
                'url_oficial': 'https://...',
                'fecha_efectiva': '2026-01-01',
                'content_hash': 'abc123...'
            }]

        Returns:
            Cantidad de registros insertados/actualizados
        """
        pass

    @abstractmethod
    async def guardar_efsa(self, regulaciones: List[Dict[str, Any]]) -> int:
        """
        Guardar regulaciones EFSA (E-numbers) en efsa_regulations.

        Args:
            regulaciones: List[{
                'e_number': 'E500',
                'ingredient_name': 'Sodium bicarbonate',
                'authorized_uses': ['bread', 'biscuits'],
                'max_levels_pct': '0.5',
                'url_oficial': 'https://...',
                'content_hash': 'abc123...'
            }]

        Returns:
            Cantidad de registros insertados/actualizados
        """
        pass

    @abstractmethod
    async def guardar_codex(self, regulaciones: List[Dict[str, Any]]) -> int:
        """
        Guardar estándares Codex Alimentarius en codex_standards.

        Args:
            regulaciones: List[{
                'nombre_estandar': 'Standard for Quinoa',
                'codigo_cat': 'STAN 50-1991',
                'version': '1.0',
                'anio_publicacion': 1991,
                'texto': '...',
                'url_oficial': 'https://...',
                'content_hash': 'abc123...'
            }]

        Returns:
            Cantidad de registros insertados/actualizados
        """
        pass

    @abstractmethod
    async def guardar_inacal(self, regulaciones: List[Dict[str, Any]]) -> int:
        """
        Guardar normas técnicas peruanas (INACAL) en inacal_nts.

        Args:
            regulaciones: List[{
                'nombre_nts': 'Norma Técnica Peruana para Quinua',
                'codigo_nts': 'NTS 201.041',
                'version': '1.0',
                'texto': '...',
                'url_oficial': 'https://...',
                'content_hash': 'abc123...'
            }]

        Returns:
            Cantidad de registros insertados/actualizados
        """
        pass

    @abstractmethod
    async def guardar_digesa(self, regulaciones: List[Dict[str, Any]]) -> int:
        """
        Guardar directivas DIGESA (extraídas por OCR) en digesa_directivas.

        Args:
            regulaciones: List[{
                'asunto': 'Prohibición de quitosano',
                'ingrediente': 'quitosano',
                'accion': 'bloqueado',
                'limite': None,
                'justificacion': 'No autorizado...',
                'fecha_emitida': '2026-01-01',
                'archivo_pdf_url': 'https://...',
                'ocr_accuracy': 0.85
            }]

        Returns:
            Cantidad de registros insertados/actualizados
        """
        pass

    # ============================================================
    # BUSCAR REGULACIONES
    # ============================================================

    @abstractmethod
    async def buscar_por_ingrediente(
        self,
        ingrediente: str,
        pais: str = 'PE'
    ) -> List[Dict[str, Any]]:
        """
        Buscar regulaciones aplicables para un ingrediente en un país.

        Estrategia de prioridad:
        - 'PE': INACAL → DIGESA → Codex
        - 'EU': EFSA → Codex
        - 'US': eCFR → Codex

        Returns: List[{
            'tipo_regulacion': 'eCFR',
            'regulation_id': 123,
            'seccion_exacta': '21 CFR 101.4(a)',
            'texto_cita': '...',
            'url_oficial': 'https://...',
            'version_norma': '2026-01-01'
        }]
        """
        pass

    @abstractmethod
    async def buscar_por_tipo(
        self,
        tipo_regulacion: str
    ) -> List[Dict[str, Any]]:
        """
        Buscar todas las regulaciones de un tipo específico.

        Args:
            tipo_regulacion: 'eCFR', 'EFSA', 'Codex', 'INACAL', 'DIGESA'

        Returns:
            List de regulaciones del tipo especificado
        """
        pass

    @abstractmethod
    async def obtener_mapping(
        self,
        ingrediente: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtener el mapping unificado para un ingrediente.

        Returns: {
            'ingrediente_canonico': 'sodium bicarbonate',
            'ecfr_ref': 123,
            'efsa_ref': 456,
            'codex_ref': 789,
            'inacal_ref': None,
            'digesa_ref': None,
            'mapping_confidence': 0.95,
            'validated_by': 'CITE_expert'
        }
        """
        pass

    # ============================================================
    # MAPEO Y VALIDACIÓN
    # ============================================================

    @abstractmethod
    async def guardar_mapping(
        self,
        ingrediente_canonico: str,
        ecfr_ref: Optional[int] = None,
        efsa_ref: Optional[int] = None,
        codex_ref: Optional[int] = None,
        inacal_ref: Optional[int] = None,
        digesa_ref: Optional[int] = None,
        mapping_confidence: float = 1.0,
        notas: str = "",
        validated_by: str = ""
    ) -> int:
        """
        Guardar o actualizar mapping entre regulaciones.

        Returns:
            mapping_id
        """
        pass

    @abstractmethod
    async def contar_por_fuente(self) -> Dict[str, int]:
        """
        Obtener cantidad de registros por fuente.

        Returns: {
            'ecfr': 5234,
            'efsa': 487,
            'codex': 203,
            'inacal': 87,
            'digesa': 12,
            'mapping': 156
        }
        """
        pass

    # ============================================================
    # AUDITORÍA Y MANTENIMIENTO
    # ============================================================

    @abstractmethod
    async def registrar_cambio(
        self,
        tipo_fuente: str,
        accion: str,  # 'insert', 'update', 'delete'
        cantidad_cambios: int,
        hash_anterior: str,
        hash_nuevo: str,
        detalles: str = ""
    ) -> None:
        """
        Registrar cambios en audit_regulaciones para job_corpus_ingest.
        """
        pass

    @abstractmethod
    async def limpiar_corpus(self) -> None:
        """
        Borrar todo el corpus (útil para reiniciar descargas).
        """
        pass
