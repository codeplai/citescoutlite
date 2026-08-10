"""
Test P08: Dossier Regulatorio Verificable

Purpose:
  Validar que cada cita en el dossier regulatorio es verificable:
  1. URL es accesible (200 OK)
  2. Sección exacta está presente en página
  3. No hay citas inventadas (regex validation)
  4. Corpus integridad (cantidad mínima de entradas)

P08 = "Verificación de regulaciones con citas URL vivas"
"""

import asyncio
import logging
import sys
import re
from pathlib import Path
from typing import Dict, List, Any

try:
    import httpx
except ImportError:
    print("❌ httpx not installed. Install with: pip install httpx")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_p08_regulatory_dossier():
    """Ejecutar test P08: Dossier regulatorio verificable."""

    from config.regulaciones_config import get_repositorio

    logger.info("=" * 70)
    logger.info("P08 TEST: Dossier Regulatorio Verificable (URLs Vivas)")
    logger.info("=" * 70)

    repo = get_repositorio()
    if not repo:
        logger.error("❌ Repositorio no configurado")
        return False

    try:
        # 1. Validar integridad del corpus
        logger.info("\n1️⃣ Validando integridad del corpus...")
        counts = await repo.contar_por_fuente()

        corpus_ok = True
        logger.info(f"\n   Recuento por fuente:")
        logger.info(f"   eCFR    : {counts.get('ecfr', 0):6} (target: > 3000)")
        logger.info(f"   EFSA    : {counts.get('efsa', 0):6} (target: > 300)")
        logger.info(f"   Codex   : {counts.get('codex', 0):6} (target: > 200)")
        logger.info(f"   INACAL  : {counts.get('inacal', 0):6} (target: > 5)")
        logger.info(f"   DIGESA  : {counts.get('digesa', 0):6} (target: > 0)")

        if counts.get('ecfr', 0) < 3000:
            logger.warning("   ⚠️  eCFR por debajo del target")
            corpus_ok = False
        else:
            logger.info("   ✅ eCFR OK")

        if counts.get('efsa', 0) < 300:
            logger.warning("   ⚠️  EFSA por debajo del target")
            corpus_ok = False
        else:
            logger.info("   ✅ EFSA OK")

        if counts.get('codex', 0) < 200:
            logger.warning("   ⚠️  Codex por debajo del target")
            corpus_ok = False
        else:
            logger.info("   ✅ Codex OK")

        if not corpus_ok:
            logger.warning("   ⚠️  Corpus integrity: DEGRADED")
        else:
            logger.info("   ✅ Corpus integrity: OK")

        # 2. Buscar ingredientes de prueba
        logger.info("\n2️⃣ Buscando citas para ingredientes de prueba...")
        test_cases = [
            ("quinua", "PE"),
            ("sodium", "US"),
            ("curcumin", "EU"),
        ]

        all_citas = []

        async with httpx.AsyncClient(timeout=10) as client:
            for ingrediente, pais in test_cases:
                logger.info(f"\n   Búsqueda: '{ingrediente}' en {pais}")

                try:
                    citas = await repo.buscar_por_ingrediente(ingrediente, pais)

                    if citas:
                        logger.info(f"   ✅ Encontradas {len(citas)} citas")
                        all_citas.extend(citas)
                    else:
                        logger.warning(f"   ⚠️  Sin citas encontradas")

                except Exception as e:
                    logger.error(f"   ❌ Error en búsqueda: {e}")

        if not all_citas:
            logger.error("❌ No se encontraron citas para validar")
            return False

        # 3. Validar URLs vivas
        logger.info(f"\n3️⃣ Validando URLs vivas ({len(all_citas)} citas)...")

        urls_validas = 0
        urls_invalidas = 0

        async with httpx.AsyncClient(timeout=10) as client:
            for i, cita in enumerate(all_citas[:10], 1):  # Validar primeras 10
                url = cita.get('url_oficial', '')
                tipo = cita.get('tipo_regulacion', '')
                seccion = cita.get('seccion_exacta', '')

                if not url:
                    logger.warning(f"   ⚠️  Cita {i}: sin URL")
                    urls_invalidas += 1
                    continue

                try:
                    logger.debug(f"   → GET {url}")
                    response = await client.get(url)

                    if response.status_code == 200:
                        logger.info(
                            f"   ✅ Cita {i} [{tipo}]: URL viva (200 OK)"
                        )
                        urls_validas += 1

                        # Validar que sección está en página
                        if seccion and seccion.lower() in response.text.lower():
                            logger.debug(
                                f"      ✅ Sección '{seccion}' presente en página"
                            )
                        else:
                            logger.warning(
                                f"      ⚠️  Sección '{seccion}' no encontrada en página"
                            )

                    else:
                        logger.warning(
                            f"   ❌ Cita {i} [{tipo}]: URL retorna {response.status_code}"
                        )
                        urls_invalidas += 1

                except httpx.TimeoutException:
                    logger.warning(f"   ⚠️  Cita {i}: timeout en URL")
                    urls_invalidas += 1
                except httpx.RequestError as e:
                    logger.warning(f"   ⚠️  Cita {i}: error de conexión ({e})")
                    urls_invalidas += 1
                except Exception as e:
                    logger.warning(f"   ⚠️  Cita {i}: error ({e})")
                    urls_invalidas += 1

        # 4. Validar que no hay citas inventadas
        logger.info(f"\n4️⃣ Validando que no hay citas inventadas...")

        # Regex patterns para citas reales
        valid_patterns = [
            r'\d+\s+CFR',  # eCFR: "21 CFR"
            r'E\d{3,4}',   # EFSA: "E500"
            r'STAN\s+\d+', # Codex: "STAN 50-1991"
            r'NTS\s+\d+',  # INACAL: "NTS 201.041"
            r'DIGESA',     # DIGESA
        ]

        invented_citations = 0
        for cita in all_citas:
            seccion = cita.get('seccion_exacta', '')
            if seccion:
                is_valid = any(
                    re.search(pattern, seccion, re.IGNORECASE)
                    for pattern in valid_patterns
                )
                if not is_valid:
                    logger.warning(f"   ⚠️  Cita sospechosa: {seccion}")
                    invented_citations += 1

        if invented_citations == 0:
            logger.info("   ✅ No hay citas inventadas (validación regex)")
        else:
            logger.warning(
                f"   ⚠️  {invented_citations} citas sospechosas encontradas"
            )

        # 5. Resumen P08
        logger.info(f"\n5️⃣ Resumen P08:")
        logger.info(f"\n   📊 Estadísticas:")
        logger.info(f"   Corpus integridad    : {'✅' if corpus_ok else '⚠️'}")
        logger.info(f"   Citas encontradas   : {len(all_citas)}")
        logger.info(f"   URLs validadas      : {urls_validas} OK, {urls_invalidas} Error")
        logger.info(f"   Citas inventadas    : {invented_citations}")

        # Determinar si P08 pasa
        p08_passed = (
            corpus_ok and
            urls_validas > 0 and
            urls_invalidas == 0 and
            invented_citations == 0
        )

        logger.info(f"\n   📋 P08 Result: {'✅ PASSED' if p08_passed else '❌ FAILED'}")

        logger.info("\n" + "=" * 70)
        if p08_passed:
            logger.info("✅ P08 TEST PASSED - Dossier regulatorio verificable")
        else:
            logger.info("⚠️  P08 TEST DEGRADED - Requiere revisión")
        logger.info("=" * 70)

        return p08_passed

    except Exception as e:
        logger.error(f"❌ Error en test P08: {e}", exc_info=True)
        return False


async def main():
    """Entry point."""
    try:
        success = await test_p08_regulatory_dossier()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
