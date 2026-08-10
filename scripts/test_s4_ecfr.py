"""
Test S4.1: Descargador eCFR

Valida:
1. Acceso a API de eCFR
2. Descarga de regulaciones
3. Normalización de datos
4. Guardado en DB
"""

import asyncio
import logging
import os
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


async def test_ecfr():
    """Ejecutar tests de S4.1."""

    from adaptadores.descargador_ecfr import DescargadorECFR
    from config.regulaciones_config import get_repositorio

    logger.info("=" * 60)
    logger.info("S4.1 TEST: eCFR Descargador")
    logger.info("=" * 60)

    # 1. Crear descargador
    logger.info("\n1️⃣ Inicializando DescargadorECFR...")
    descargador = DescargadorECFR(timeout=30)

    # 2. Validar acceso
    logger.info("\n2️⃣ Validando acceso a eCFR API...")
    can_access = await descargador.validar_acceso()
    if not can_access:
        logger.error("❌ No se puede acceder a eCFR API. Aborting.")
        return False

    logger.info("✅ eCFR API accesible")

    # 3. Descargar
    logger.info("\n3️⃣ Descargando regulaciones eCFR...")
    logger.info("   (Esto puede tomar 2-5 minutos la primera vez)")
    regulaciones = await descargador.descargar()

    if not regulaciones:
        logger.error("❌ No se descargaron regulaciones")
        return False

    logger.info(f"✅ Descargadas {len(regulaciones)} regulaciones")

    # 4. Mostrar sample
    logger.info("\n4️⃣ Sample de regulaciones:")
    if regulaciones:
        sample = regulaciones[0]
        logger.info(f"   Título: {sample['title']}")
        logger.info(f"   Parte: {sample['part']}")
        logger.info(f"   Sección: {sample['section']}")
        logger.info(f"   Subsección: {sample['subsection']}")
        logger.info(f"   Texto: {sample['texto_completo'][:100]}...")
        logger.info(f"   URL: {sample['url_oficial']}")
        logger.info(f"   Hash: {sample['content_hash'][:16]}...")

    # 5. Estadísticas
    logger.info("\n5️⃣ Estadísticas de descarga:")
    stats = {}
    for reg in regulaciones:
        key = f"Title {reg['title']}, Part {reg['part']}"
        stats[key] = stats.get(key, 0) + 1

    for key, count in sorted(stats.items()):
        logger.info(f"   {key}: {count} entradas")

    # 6. Guardar en DB (si configurado)
    logger.info("\n6️⃣ Guardando en base de datos...")
    repo = get_repositorio()

    if not repo:
        logger.warning("⚠️  No hay repositorio configurado (DATABASE_URL vacío)")
        logger.info("   Para guardar, configura DATABASE_URL en .env")
        return True  # Test pasó, pero no guardó

    try:
        saved_count = await repo.guardar_ecfr(regulaciones)
        logger.info(f"✅ Guardadas {saved_count} regulaciones en ecfr_regulations")

        # Contar totales
        counts = await repo.contar_por_fuente()
        logger.info(f"\n📊 Estado del corpus:")
        for source, count in counts.items():
            logger.info(f"   {source}: {count}")

    except Exception as e:
        logger.error(f"❌ Error guardando en DB: {e}")
        return False

    logger.info("\n" + "=" * 60)
    logger.info("✅ S4.1 TEST PASSED")
    logger.info("=" * 60)
    return True


async def main():
    """Entry point."""
    try:
        success = await test_ecfr()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
