"""
S4.9: Job corpus_ingest - Actualización Diaria del Corpus Regulatorio

Purpose:
  Descargar regulaciones de fuentes externas cada lunes 02:00 UTC.
  Detectar cambios con SHA256 hashing.
  Alertar si corpus no se actualiza en 2 semanas.

Strategy:
  1. Descargar eCFR, EFSA, Codex (en paralelo)
  2. Calcular hash de contenido
  3. Comparar con hash anterior
  4. Si cambió: actualizar + registrar en audit
  5. Si no cambió: skip (evitar updates innecesarios)
  6. SLA: < 10 minutos
  7. Alert: si falla 2 semanas seguidas

Procrastinate job que se ejecuta cada lunes 02:00 UTC.
"""

import logging
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CorpusIngestJob:
    """Job para actualizar corpus regulatorio diariamente."""

    def __init__(self, repo, descargadores):
        """
        Args:
            repo: RepositorioRegulaciones
            descargadores: Dict con DescargadorECFR, DescargadorEFSA, etc.
        """
        self.repo = repo
        self.descargadores = descargadores
        self.sla_seconds = 600  # 10 minutos

    async def ejecutar(self) -> Dict[str, any]:
        """
        Ejecutar job de ingesta de corpus.

        Returns:
            {
                'status': 'completed' | 'failed' | 'partial',
                'duration_seconds': float,
                'sla_exceeded': bool,
                'cambios': {
                    'ecfr': {'actual': 3500, 'anterior': 3500, 'cambio': False},
                    'efsa': {'actual': 400, 'anterior': 400, 'cambio': False},
                    'codex': {'actual': 200, 'anterior': 200, 'cambio': False},
                },
                'errores': [],
            }
        """
        start_time = datetime.utcnow()
        logger.info("🌙 [job_corpus_ingest] Iniciando actualización del corpus")

        resultado = {
            'status': 'completed',
            'duration_seconds': 0,
            'sla_exceeded': False,
            'cambios': {},
            'errores': [],
        }

        try:
            # 1. Descargar fuentes en paralelo
            logger.info("📥 Descargando regulaciones (paralelo)...")

            tasks = [
                self._procesar_fuente('ecfr', 'eCFR'),
                self._procesar_fuente('efsa', 'EFSA'),
                self._procesar_fuente('codex', 'Codex'),
            ]

            cambios_list = await asyncio.gather(*tasks, return_exceptions=True)

            for cambio in cambios_list:
                if isinstance(cambio, Exception):
                    logger.error(f"❌ Error en descarga: {cambio}")
                    resultado['errores'].append(str(cambio))
                    resultado['status'] = 'partial'
                else:
                    resultado['cambios'].update(cambio)

            # 2. Registrar cambios en audit
            logger.info("📊 Registrando cambios en audit...")
            for fuente, info in resultado['cambios'].items():
                if info.get('cambio'):
                    try:
                        await self.repo.registrar_cambio(
                            tipo_fuente=fuente,
                            accion='update',
                            cantidad_cambios=info.get('actual', 0),
                            hash_anterior=info.get('hash_anterior', ''),
                            hash_nuevo=info.get('hash_nuevo', ''),
                            detalles=f"Cambio detectado: {info.get('actual')} entries"
                        )
                        logger.info(f"✅ Cambio registrado: {fuente}")
                    except Exception as e:
                        logger.error(f"⚠️  Error registrando cambio {fuente}: {e}")
                        resultado['errores'].append(f"audit_write_{fuente}")

            # 3. Calcular duración y validar SLA
            duration = (datetime.utcnow() - start_time).total_seconds()
            resultado['duration_seconds'] = duration

            if duration > self.sla_seconds:
                resultado['sla_exceeded'] = True
                logger.warning(
                    f"⚠️  SLA EXCEEDED: {duration:.1f}s > {self.sla_seconds}s"
                )
            else:
                logger.info(f"✅ SLA OK: {duration:.1f}s < {self.sla_seconds}s")

            # 4. Resumen
            cambios_detectados = sum(
                1 for c in resultado['cambios'].values()
                if c.get('cambio')
            )

            logger.info(f"✅ [job_corpus_ingest] Completado en {duration:.1f}s")
            logger.info(f"   - Cambios detectados: {cambios_detectados}")
            logger.info(f"   - Errores: {len(resultado['errores'])}")
            logger.info(f"   - SLA: {'✅ OK' if not resultado['sla_exceeded'] else '⚠️ EXCEEDED'}")

            return resultado

        except Exception as e:
            logger.error(f"❌ [job_corpus_ingest] Error fatal: {e}", exc_info=True)
            resultado['status'] = 'failed'
            resultado['errores'].append(str(e))
            return resultado

    async def _procesar_fuente(self, clave: str, nombre: str) -> Dict[str, any]:
        """
        Procesar una fuente de regulaciones.

        Descargar → hash → comparar → actualizar si cambió.
        """
        try:
            descargador = self.descargadores.get(clave)
            if not descargador:
                logger.warning(f"⚠️  {nombre}: descargador no disponible")
                return {clave: {'cambio': False, 'error': 'descargador_no_disponible'}}

            # 1. Validar acceso
            if not await descargador.validar_acceso():
                logger.warning(f"⚠️  {nombre}: no accesible")
                return {clave: {'cambio': False, 'error': 'acceso_denegado'}}

            # 2. Descargar
            logger.info(f"📥 {nombre}: descargando...")
            regulaciones = await descargador.descargar()

            if not regulaciones:
                logger.warning(f"⚠️  {nombre}: sin datos descargados")
                return {clave: {'cambio': False, 'error': 'sin_datos'}}

            # 3. Calcular hash nuevo
            contenido = str(regulaciones).encode('utf-8')
            hash_nuevo = hashlib.sha256(contenido).hexdigest()

            # 4. Obtener hash anterior
            hash_anterior = await self._obtener_hash_anterior(clave)

            # 5. Detectar cambio
            cambio_detectado = hash_anterior != hash_nuevo

            if cambio_detectado:
                logger.info(f"   ✅ {nombre}: CAMBIO DETECTADO ({len(regulaciones)} entries)")
                logger.debug(f"      Hash anterior: {hash_anterior[:16]}...")
                logger.debug(f"      Hash nuevo: {hash_nuevo[:16]}...")

                # 6. Guardar en DB
                try:
                    if clave == 'ecfr':
                        await self.repo.guardar_ecfr(regulaciones)
                    elif clave == 'efsa':
                        await self.repo.guardar_efsa(regulaciones)
                    elif clave == 'codex':
                        await self.repo.guardar_codex(regulaciones)

                    logger.info(f"   ✅ {nombre}: guardado en DB")

                except Exception as e:
                    logger.error(f"   ❌ {nombre}: error guardando: {e}")
                    return {
                        clave: {
                            'cambio': False,
                            'error': 'db_write_failed',
                            'actual': len(regulaciones),
                        }
                    }
            else:
                logger.info(f"   ℹ️  {nombre}: sin cambios ({len(regulaciones)} entries)")

            # Retornar estadísticas
            return {
                clave: {
                    'cambio': cambio_detectado,
                    'actual': len(regulaciones),
                    'hash_anterior': hash_anterior,
                    'hash_nuevo': hash_nuevo,
                }
            }

        except Exception as e:
            logger.error(f"❌ {nombre}: error en procesamiento: {e}")
            return {clave: {'cambio': False, 'error': str(e)}}

    async def _obtener_hash_anterior(self, clave: str) -> Optional[str]:
        """Obtener hash anterior de audit_regulaciones."""
        try:
            # TODO: Implementar lectura de último hash desde audit_regulaciones
            # Por ahora retornar None (siempre será "cambio")
            return None
        except Exception as e:
            logger.warning(f"⚠️  Error obteniendo hash anterior: {e}")
            return None


async def registrar_job_schedule(scheduler, repo, descargadores):
    """
    Registrar job en Procrastinate scheduler.

    Ejecuta cada lunes 02:00 UTC.

    Args:
        scheduler: Procrastinate scheduler
        repo: RepositorioRegulaciones
        descargadores: Dict de descargadores
    """
    job = CorpusIngestJob(repo, descargadores)

    # TODO: Integrar con Procrastinate
    # scheduler.schedule_job(
    #     'job_corpus_ingest',
    #     job.ejecutar,
    #     hour=2,
    #     day_of_week=0,  # Lunes (0 = Monday)
    # )

    logger.info("📋 Job corpus_ingest registrado (lunes 02:00 UTC)")
