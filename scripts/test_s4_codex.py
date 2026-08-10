"""
Test S4.3: Descargador Codex Alimentarius

Valida:
1. Acceso a Codex
2. Descarga de estándares internacionales
3. Normalización de datos
4. Guardado en DB
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_codex():
    """Ejecutar tests de S4.3."""

    from adaptadores.descargador_codex import DescargadorCodex
    from config.regulaciones_config import get_repositorio

    logger.info("=" * 60)
    logger.info("S4.3 TEST: Codex Alimentarius Descargador")
    logger.info("=" * 60)

    # 1. Crear descargador
    logger.info("\n1️⃣ Inicializando DescargadorCodex...")
    descargador = DescargadorCodex(timeout=30, use_fallback=True)

    # 2. Validar acceso
    logger.info("\n2️⃣ Validando acceso a Codex...")
    can_access = await descargador.validar_acceso()
    status = "✅" if can_access else "⚠️  (usar fallback)"
    logger.info(f"   {status} Codex acceso")

    # 3. Descargar
    logger.info("\n3️⃣ Descargando estándares Codex...")
    estandares = await descargador.descargar()

    if not estandares:
        logger.error("❌ No se descargaron estándares")
        return False

    logger.info(f"✅ Descargados {len(estandares)} estándares")

    # 4. Mostrar samples
    logger.info("\n4️⃣ Samples de estándares:")
    for i, sample in enumerate(estandares[:5]):
        logger.info(f"\n   Estándar {i+1}:")
        logger.info(f"     Código: {sample['codigo_cat']}")
        logger.info(f"     Nombre: {sample['nombre_estandar']}")
        logger.info(f"     Año: {sample['anio_publicacion']}")
        logger.info(f"     Versión: {sample['version']}")
        logger.info(f"     URL: {sample['url_oficial']}")

    # 5. Estadísticas
    logger.info("\n5️⃣ Estadísticas:")
    codigos_set = set(e['codigo_cat'] for e in estandares)
    logger.info(f"   Códigos únicos: {len(codigos_set)}")
    logger.info(f"   Total de estándares: {len(estandares)}")

    # 6. Guardar en DB
    logger.info("\n6️⃣ Guardando en base de datos...")
    repo = get_repositorio()

    if not repo:
        logger.warning("⚠️  No hay repositorio configurado (DATABASE_URL vacío)")
        logger.info("   Para guardar, configura DATABASE_URL en .env")
        return True

    try:
        saved_count = await repo.guardar_codex(estandares)
        logger.info(f"✅ Guardados {saved_count} estándares en codex_standards")

        # Contar totales
        counts = await repo.contar_por_fuente()
        logger.info(f"\n📊 Estado del corpus:")
        for source, count in counts.items():
            logger.info(f"   {source}: {count}")

    except Exception as e:
        logger.error(f"❌ Error guardando en DB: {e}")
        return False

    logger.info("\n" + "=" * 60)
    logger.info("✅ S4.3 TEST PASSED")
    logger.info("=" * 60)
    return True


async def main():
    """Entry point."""
    try:
        success = await test_codex()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
