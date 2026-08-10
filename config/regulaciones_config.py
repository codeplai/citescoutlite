"""
Configuración de regulaciones para S4.

Factory para crear instancias de descargadores y repositorio.
Se usa en el startup de la aplicación (main.py, worker, etc.)
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def crear_repositorio_regulaciones():
    """
    Factory: crear instancia del repositorio de regulaciones.

    Usa DATABASE_URL de variables de entorno (Supabase).
    Retorna None si no está configurado (degradación graceful a sin_dato).
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        logger.warning("⚠️  DATABASE_URL no configurado, regulaciones deshabilitadas")
        return None

    try:
        from adaptadores.repositorio_regulaciones_postgres import RepositorioRegulacionesPostgres
        return RepositorioRegulacionesPostgres(database_url)
    except ImportError:
        logger.warning("⚠️  No se pudo importar adaptador PostgreSQL")
        return None


def crear_descargadores():
    """
    Factory: crear instancias de todos los descargadores.

    Retorna diccionario con descargadores listos para usar.
    Cada uno validará acceso en su método validar_acceso().
    """
    # TODO: Implementar en S4.1 onwards
    # from adaptadores.descargador_ecfr import DescargadorECFR
    # from adaptadores.descargador_efsa import DescargadorEFSA
    # from adaptadores.descargador_codex import DescargadorCodex
    # from adaptadores.descargador_inacal import DescargadorINACAL
    # from adaptadores.descargador_digesa import DescargadorDIGESA

    return {
        # 'ecfr': DescargadorECFR(),
        # 'efsa': DescargadorEFSA(),
        # 'codex': DescargadorCodex(),
        # 'inacal': DescargadorINACAL(),
        # 'digesa': DescargadorDIGESA(),
    }


# Inicialización lazy (al primer acceso)
_repositorio_cache: Optional[object] = None
_descargadores_cache: Optional[dict] = None


def get_repositorio():
    """Obtener instancia del repositorio (singleton lazy)."""
    global _repositorio_cache
    if _repositorio_cache is None:
        _repositorio_cache = crear_repositorio_regulaciones()
    return _repositorio_cache


def get_descargadores():
    """Obtener diccionario de descargadores (singleton lazy)."""
    global _descargadores_cache
    if _descargadores_cache is None:
        _descargadores_cache = crear_descargadores()
    return _descargadores_cache
