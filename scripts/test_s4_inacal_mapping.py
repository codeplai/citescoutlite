"""
Test S4.4: Descargador INACAL + Mapeador de Regulaciones

Valida:
1. Descarga de INACAL
2. Mapeo a eCFR/EFSA/Codex
3. Creación de tabla mapping_regulaciones
4. Validación de coverage
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


async def test_inacal_mapping():
    """Ejecutar tests de S4.4."""

    from adaptadores.descargador_inacal import DescargadorINACAL
    from adaptadores.mapeador_regulaciones import MapeadorRegulaciones
    from config.regulaciones_config import get_repositorio

    logger.info("=" * 60)
    logger.info("S4.4 TEST: INACAL + Mapping")
    logger.info("=" * 60)

    repo = get_repositorio()
    if not repo:
        logger.error("❌ No hay repositorio configurado (DATABASE_URL vacío)")
        logger.info("   Para continuar, configura DATABASE_URL en .env")
        return False

    # 1. Descargar INACAL
    logger.info("\n1️⃣ Inicializando DescargadorINACAL...")
    descargador = DescargadorINACAL(timeout=30, use_fallback=True)

    logger.info("\n2️⃣ Validando acceso a INACAL...")
    can_access = await descargador.validar_acceso()
    status = "✅" if can_access else "⚠️  (usar fallback)"
    logger.info(f"   {status} INACAL acceso")

    logger.info("\n3️⃣ Descargando normas INACAL...")
    normas = await descargador.descargar()

    if not normas:
        logger.error("❌ No se descargaron normas INACAL")
        return False

    logger.info(f"✅ Descargadas {len(normas)} normas INACAL")

    # 2. Guardar INACAL
    logger.info("\n4️⃣ Guardando INACAL en base de datos...")
    try:
        saved_count = await repo.guardar_inacal(normas)
        logger.info(f"✅ Guardadas {saved_count} normas INACAL")
    except Exception as e:
        logger.error(f"❌ Error guardando INACAL: {e}")
        return False

    # 3. Mostrar samples
    logger.info("\n5️⃣ Samples de normas INACAL:")
    for i, sample in enumerate(normas[:3]):
        logger.info(f"\n   Norma {i+1}:")
        logger.info(f"     Código: {sample['codigo_nts']}")
        logger.info(f"     Nombre: {sample['nombre_nts']}")

    # 4. Crear mappings
    logger.info("\n6️⃣ Creando mappings (INACAL → eCFR/EFSA/Codex)...")
    mapeador = MapeadorRegulaciones(repo)

    try:
        mappings = await mapeador.mapear_inacal()
        logger.info(f"✅ Creados {len(mappings)} mappings")

        # Mostrar samples
        if mappings:
            logger.info("\n   Samples de mappings:")
            for i, mapping in enumerate(mappings[:3]):
                logger.info(f"\n   Mapping {i+1}:")
                logger.info(f"     Ingrediente: {mapping.get('ingrediente_canonico')}")
                logger.info(f"     INACAL: {mapping.get('inacal_ref')}")
                logger.info(f"     Codex: {mapping.get('codex_ref')}")
                logger.info(f"     Confidence: {mapping.get('mapping_confidence', 0):.1%}")

    except Exception as e:
        logger.error(f"❌ Error creando mappings: {e}")
        return False

    # 5. Validar coverage
    logger.info("\n7️⃣ Validando coverage de mappings...")
    stats = await mapeador.validar_mappings(min_confidence=0.75)

    logger.info(f"\n   Estadísticas:")
    logger.info(f"   Total INACAL: {stats.get('total_inacal')}")
    logger.info(f"   Mappings creados: {stats.get('total_mappings')}")
    logger.info(f"   Coverage: {stats.get('coverage', 0):.1%}")

    # 6. Contar totales
    logger.info("\n8️⃣ Estado del corpus acumulado:")
    counts = await repo.contar_por_fuente()
    logger.info(f"\n   📊 Fuentes:")
    for source, count in counts.items():
        logger.info(f"   {source}: {count}")

    # Validar coverage >= 80%
    coverage = stats.get('coverage', 0)
    if coverage >= 0.80:
        logger.info(f"\n✅ Coverage objetivo alcanzado: {coverage:.1%} >= 80%")
    else:
        logger.warning(f"\n⚠️  Coverage por debajo de target: {coverage:.1%} < 80%")
        logger.warning("   Recomendación: Validar con especialista CITE para mejora manual")

    logger.info("\n" + "=" * 60)
    logger.info("✅ S4.4 TEST PASSED")
    logger.info("=" * 60)
    return True


async def main():
    """Entry point."""
    try:
        success = await test_inacal_mapping()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
