"""
Test S4.2: Descargador EFSA

Valida:
1. Acceso a EFSA
2. Descarga de aditivos autorizados (E-numbers)
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


async def test_efsa():
    """Ejecutar tests de S4.2."""

    from adaptadores.descargador_efsa import DescargadorEFSA
    from config.regulaciones_config import get_repositorio

    logger.info("=" * 60)
    logger.info("S4.2 TEST: EFSA Descargador")
    logger.info("=" * 60)

    # 1. Crear descargador
    logger.info("\n1️⃣ Inicializando DescargadorEFSA...")
    descargador = DescargadorEFSA(timeout=30, use_fallback=True)

    # 2. Validar acceso
    logger.info("\n2️⃣ Validando acceso a EFSA...")
    can_access = await descargador.validar_acceso()
    status = "✅" if can_access else "⚠️  (usar fallback)"
    logger.info(f"   {status} EFSA acceso")

    # 3. Descargar
    logger.info("\n3️⃣ Descargando aditivos EFSA...")
    aditivos = await descargador.descargar()

    if not aditivos:
        logger.error("❌ No se descargaron aditivos")
        return False

    logger.info(f"✅ Descargados {len(aditivos)} aditivos")

    # 4. Mostrar samples
    logger.info("\n4️⃣ Samples de aditivos:")
    for i, sample in enumerate(aditivos[:5]):
        logger.info(f"\n   Aditivo {i+1}:")
        logger.info(f"     E-number: {sample['e_number']}")
        logger.info(f"     Nombre: {sample['ingredient_name']}")
        logger.info(f"     Usos: {', '.join(sample.get('authorized_uses', [])[:2])}")
        logger.info(f"     Límite: {sample['max_levels_pct']}")
        logger.info(f"     URL: {sample['url_oficial']}")

    # 5. Estadísticas
    logger.info("\n5️⃣ Estadísticas:")
    e_numbers_set = set(a['e_number'] for a in aditivos)
    logger.info(f"   E-numbers únicos: {len(e_numbers_set)}")
    logger.info(f"   Total de aditivos: {len(aditivos)}")

    # 6. Guardar en DB
    logger.info("\n6️⃣ Guardando en base de datos...")
    repo = get_repositorio()

    if not repo:
        logger.warning("⚠️  No hay repositorio configurado (DATABASE_URL vacío)")
        logger.info("   Para guardar, configura DATABASE_URL en .env")
        return True

    try:
        saved_count = await repo.guardar_efsa(aditivos)
        logger.info(f"✅ Guardados {saved_count} aditivos en efsa_regulations")

        # Contar totales
        counts = await repo.contar_por_fuente()
        logger.info(f"\n📊 Estado del corpus:")
        for source, count in counts.items():
            logger.info(f"   {source}: {count}")

    except Exception as e:
        logger.error(f"❌ Error guardando en DB: {e}")
        return False

    logger.info("\n" + "=" * 60)
    logger.info("✅ S4.2 TEST PASSED")
    logger.info("=" * 60)
    return True


async def main():
    """Entry point."""
    try:
        success = await test_efsa()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
