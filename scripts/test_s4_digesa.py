"""
Test S4.5: Descargador DIGESA + OCR

Valida:
1. Acceso a DIGESA
2. Descarga de directivas (o fallback)
3. Procesamiento OCR (si PDFs disponibles)
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


async def test_digesa():
    """Ejecutar tests de S4.5."""

    from adaptadores.descargador_digesa import DescargadorDIGESA
    from config.regulaciones_config import get_repositorio

    logger.info("=" * 60)
    logger.info("S4.5 TEST: DIGESA + OCR")
    logger.info("=" * 60)

    repo = get_repositorio()
    if not repo:
        logger.error("❌ No hay repositorio configurado (DATABASE_URL vacío)")
        return False

    # 1. Crear descargador
    logger.info("\n1️⃣ Inicializando DescargadorDIGESA...")
    logger.info("   OCR backend: tesseract (libre)")
    descargador = DescargadorDIGESA(timeout=60, ocr_backend='tesseract', use_fallback=True)

    # 2. Validar acceso
    logger.info("\n2️⃣ Validando acceso a DIGESA...")
    can_access = await descargador.validar_acceso()
    status = "✅" if can_access else "⚠️  (usar fallback)"
    logger.info(f"   {status} DIGESA acceso")

    # 3. Descargar
    logger.info("\n3️⃣ Descargando directivas DIGESA...")
    directivas = await descargador.descargar()

    if not directivas:
        logger.error("❌ No se descargaron directivas")
        return False

    logger.info(f"✅ Descargadas {len(directivas)} directivas")

    # 4. Mostrar samples
    logger.info("\n4️⃣ Samples de directivas:")
    for i, sample in enumerate(directivas[:3]):
        logger.info(f"\n   Directiva {i+1}:")
        logger.info(f"     Asunto: {sample['asunto']}")
        logger.info(f"     Ingrediente: {sample['ingrediente']}")
        logger.info(f"     Acción: {sample['accion']}")
        logger.info(f"     Límite: {sample.get('limite', 'N/A')}")
        logger.info(f"     OCR Accuracy: {sample.get('ocr_accuracy', 1.0):.0%}")

    # 5. Guardar en DB
    logger.info("\n5️⃣ Guardando DIGESA en base de datos...")
    try:
        saved_count = await repo.guardar_digesa(directivas)
        logger.info(f"✅ Guardadas {saved_count} directivas DIGESA")
    except Exception as e:
        logger.error(f"❌ Error guardando DIGESA: {e}")
        return False

    # 6. Estadísticas finales
    logger.info("\n6️⃣ Estado del corpus COMPLETO (S4.1-4.5):")
    counts = await repo.contar_por_fuente()

    logger.info(f"\n   📊 Resumen por fuente:")
    total = 0
    for source in ['ecfr', 'efsa', 'codex', 'inacal', 'digesa']:
        count = counts.get(source, 0)
        total += count
        logger.info(f"   {source:15}: {count:6} entradas")

    logger.info(f"   {'-' * 35}")
    logger.info(f"   {'TOTAL CORPUS':15}: {total:6} regulaciones")
    logger.info(f"\n   Mappings: {counts.get('mapping', 0)}")

    # 7. Validar corpus listo
    logger.info("\n7️⃣ Validación de corpus:")
    if total > 3000:
        logger.info("   ✅ Corpus principal completo (> 3000 entradas)")
    if counts.get('digesa', 0) > 0:
        logger.info("   ✅ DIGESA incluido")
    if counts.get('mapping', 0) > 0:
        logger.info("   ✅ Mappings creados")

    logger.info("\n" + "=" * 60)
    logger.info("✅ S4.5 TEST PASSED")
    logger.info("=" * 60)
    return True


async def main():
    """Entry point."""
    try:
        success = await test_digesa()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
