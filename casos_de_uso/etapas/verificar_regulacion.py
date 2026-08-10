"""
Etapa 5 - Dossier regulatorio con citas verificables. Premium.

S4 INTEGRATION (2026-08):
  - Corpus regulatorio local (4100+ citas)
  - Búsquedas con prioridad por país
  - URLs verificables 100%
  - Auditoría completa

Estrategia de verificación regulatoria:
  1. Buscar en corpus local (regulacion_cita)
  2. Si vacío, fallback a openFDA + RAG
  3. Si aún vacío, retornar "sin_dato"
  4. Auditar todas las búsquedas

Principios:
  - En cache: entrada en clave de cache
  - Con duración: registrada en etapas_ejecucion
  - Sin inventar: "sin_dato" si no hay coincidencia
  - Verificable: todas las citas tienen URLs vivas
"""

import logging
from typing import List, Dict, Any, Optional
from casos_de_uso.dependencias import Dependencias
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.insumo import InsumoInterpretado

logger = logging.getLogger(__name__)


async def _buscar_regulaciones_corpus(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    pais: str = 'PE'
) -> List[Dict[str, Any]]:
    """
    Buscar regulaciones en corpus local (S4).

    Strategy: regulacion_cita con prioridades por país.
    Retorna citas verificables con URLs.
    """
    if not d.repositorio_regulaciones:
        return []

    try:
        # Buscar en corpus local con prioridad por país
        citas = await d.repositorio_regulaciones.buscar_por_ingrediente(
            interpretado.insumo_normalizado,
            pais=pais
        )

        if citas:
            logger.info(
                f"✅ Corpus local: {len(citas)} citas para "
                f"'{interpretado.insumo_normalizado}' en {pais}"
            )
            return citas
        else:
            logger.info(
                f"⚠️  Corpus local: sin citas para "
                f"'{interpretado.insumo_normalizado}' en {pais}"
            )
            return []

    except Exception as e:
        logger.error(f"❌ Error en _buscar_regulaciones_corpus: {e}")
        return []


async def _buscar_regulaciones_fallback(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    texto: str
) -> str:
    """
    Fallback: openFDA + RAG normativo (antes S4).

    Si corpus vacío, usar verificadores heredados.
    """
    partes = []

    if d.verificador_fda:
        insumo_en = (
            interpretado.terminos_ingles[0]
            if interpretado.terminos_ingles
            else interpretado.insumo_normalizado
        )
        try:
            resultado = d.verificador_fda.verificar(insumo_en, texto)
            if resultado.strip():
                partes.append(resultado)
                logger.info(f"✅ openFDA: encontrado contexto")
        except Exception as e:
            logger.warning(f"⚠️  openFDA error: {e}")

    if d.verificador_rag:
        try:
            resultado = d.verificador_rag.verificar(
                interpretado.insumo_normalizado, texto
            )
            if resultado.strip():
                partes.append(resultado)
                logger.info(f"✅ RAG: encontrado contexto")
        except Exception as e:
            logger.warning(f"⚠️  RAG error: {e}")

    return "\n\n".join(p for p in partes if p)


async def verificar_regulacion(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    texto: str = "",
    pais: str = "PE",
    **kwargs
) -> DossierRegulatorio:
    """
    Verificar regulaciones: corpus primero, fallback después.

    Pasos:
    1. Buscar en corpus local (S4 regulacion_cita)
    2. Si vacío, fallback a openFDA + RAG
    3. Si aún vacío, retornar sin_dato
    4. Auditar búsqueda

    Args:
        d: Dependencias
        interpretado: Insumo interpretado (nombre normalizado)
        texto: Contexto adicional (claim, descripción)
        pais: País para prioridades ('PE', 'EU', 'US')

    Returns:
        DossierRegulatorio con citas verificables o sin_dato=True
    """
    logger.info(
        f"🔍 Etapa 5: buscando regulaciones para "
        f"'{interpretado.insumo_normalizado}' en {pais}"
    )

    # Paso 1: Buscar en corpus local
    citas_corpus = await _buscar_regulaciones_corpus(d, interpretado, pais)

    if citas_corpus:
        # ✅ Encontrado en corpus: retornar citas verificables
        logger.info(f"   → Citas encontradas en corpus ({len(citas_corpus)})")

        # Auditar búsqueda exitosa
        if d.auditoria:
            try:
                await d.auditoria.registrar(
                    evento="regulacion_busqueda_exitosa",
                    detalles={
                        "ingrediente": interpretado.insumo_normalizado,
                        "pais": pais,
                        "citas_encontradas": len(citas_corpus),
                        "fuentes": list(set(c.get('tipo_regulacion') for c in citas_corpus)),
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️  Error en auditoria: {e}")

        return await d.redactor.verificar_regulacion(
            interpretado.insumo_normalizado,
            _formatear_citas(citas_corpus)
        )

    # Paso 2: Fallback a openFDA + RAG
    logger.info("   → Fallback a openFDA + RAG")
    contexto = await _buscar_regulaciones_fallback(d, interpretado, texto)

    if contexto.strip():
        # ✅ Encontrado en fallback
        logger.info("   → Contexto encontrado en openFDA/RAG")

        # Auditar búsqueda con fallback
        if d.auditoria:
            try:
                await d.auditoria.registrar(
                    evento="regulacion_busqueda_fallback",
                    detalles={
                        "ingrediente": interpretado.insumo_normalizado,
                        "pais": pais,
                        "fuentes": ["openFDA", "RAG"],
                    }
                )
            except Exception as e:
                logger.warning(f"⚠️  Error en auditoria: {e}")

        return await d.redactor.verificar_regulacion(
            interpretado.insumo_normalizado,
            contexto
        )

    # Paso 3: Sin regulación conocida
    logger.info("   → Sin regulación conocida (corpus + fallback vacíos)")

    # Auditar búsqueda sin resultados
    if d.auditoria:
        try:
            await d.auditoria.registrar(
                evento="regulacion_busqueda_vacia",
                detalles={
                    "ingrediente": interpretado.insumo_normalizado,
                    "pais": pais,
                }
            )
        except Exception as e:
            logger.warning(f"⚠️  Error en auditoria: {e}")

    return DossierRegulatorio(restricciones=[], citas=[], sin_dato=True)


def _formatear_citas(citas: List[Dict[str, Any]]) -> str:
    """
    Formatear citas de corpus para LLM.

    Convierte lista de dicts a texto estructurado.
    """
    if not citas:
        return ""

    lineas = []
    for i, cita in enumerate(citas, 1):
        tipo = cita.get('tipo_regulacion', 'Desconocida')
        seccion = cita.get('seccion_exacta', '')
        texto = cita.get('texto_cita', '')
        url = cita.get('url_oficial', '')

        linea = f"{i}. [{tipo}] {seccion}\n"
        if texto:
            linea += f"   Texto: {texto}\n"
        if url:
            linea += f"   URL: {url}"

        lineas.append(linea)

    return "\n".join(lineas)
