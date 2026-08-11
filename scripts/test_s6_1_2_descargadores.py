"""
Test básico S6.1 + S6.2: Validar descargadores openFDA + RASFF

Ejecutar con:
  python scripts/test_s6_1_2_descargadores.py

Verifica:
  1. openFDA API accesible
  2. RASFF feed accesible
  3. Descarga de últimas 24h
  4. Normalización correcta
  5. Dedup por hash funciona
  6. Estructura de AlertaNormalizada válida
"""

import asyncio
import sys
from datetime import datetime

# Imports
from adaptadores.descargador_openfda_alerts import DescargadorOpenFDAAlerts
from adaptadores.descargador_rasff_alerts import DescargadorRASFFAlerts


async def test_openfda():
    """Test descargador openFDA."""
    print("\n" + "=" * 80)
    print("🧪 TEST S6.1: Descargador openFDA")
    print("=" * 80)

    descargador = DescargadorOpenFDAAlerts(timeout=30)

    # 1. Validar acceso
    print("\n1️⃣  Validando acceso a openFDA API...")
    accesible = await descargador.validar_acceso()
    if not accesible:
        print("   ❌ openFDA API no accesible")
        return False
    print("   ✅ openFDA API accesible")

    # 2. Descargar últimas 24h
    print("\n2️⃣  Descargando alertas de últimas 24h...")
    alertas = await descargador.descargar_ultimas_24h()
    print(f"   ✅ Descargadas {len(alertas)} alertas")

    if not alertas:
        print("   ℹ️  Sin alertas en últimas 24h (posible - no siempre hay recalls)")
        return True

    # 3. Validar estructura de alertas
    print("\n3️⃣  Validando estructura de alertas...")
    for i, alerta in enumerate(alertas[:3]):  # Mostrar primeras 3
        print(f"\n   Alerta {i + 1}:")
        print(f"     - ID: {alerta.alert_id[:16]}...")
        print(f"     - Fuente: {alerta.fuente}")
        print(f"     - Producto: {alerta.producto_nombre}")
        print(f"     - Riesgo: {alerta.riesgo_categoria} ({alerta.riesgo_texto[:50]}...)")
        print(f"     - Fecha: {alerta.fecha_emitida}")
        print(f"     - URL: {alerta.url_oficial[:60]}...")

        # Validar campos obligatorios
        assert alerta.alert_id, "alert_id vacío"
        assert alerta.fuente == "openfda", "fuente incorrecta"
        assert alerta.producto_nombre, "producto_nombre vacío"
        assert alerta.riesgo_categoria in ["patogeno", "alérgeno", "residuo", "otro"], "categoría inválida"
        assert alerta.fecha_emitida, "fecha_emitida vacía"
        assert alerta.url_oficial, "url_oficial vacía"

    print("\n   ✅ Estructura validada")

    # 4. Test de dedup
    print("\n4️⃣  Validando dedup por hash...")
    hashes = [a.alert_id for a in alertas]
    hashes_unicos = set(hashes)
    print(f"   - Total alertas: {len(alertas)}")
    print(f"   - Hashes únicos: {len(hashes_unicos)}")
    if len(hashes) != len(hashes_unicos):
        print(f"   ⚠️  Hay {len(hashes) - len(hashes_unicos)} duplicados en la misma descarga")
    else:
        print("   ✅ Todos los hashes son únicos")

    return True


async def test_rasff():
    """Test descargador RASFF."""
    print("\n" + "=" * 80)
    print("🧪 TEST S6.2: Descargador RASFF")
    print("=" * 80)

    descargador = DescargadorRASFFAlerts(timeout=30)

    # 1. Validar acceso
    print("\n1️⃣  Validando acceso a RASFF feed...")
    accesible = await descargador.validar_acceso()
    if not accesible:
        print("   ❌ RASFF feed no accesible")
        return False
    print("   ✅ RASFF feed accesible")

    # 2. Descargar últimas 24h
    print("\n2️⃣  Descargando alertas de últimas 24h...")
    alertas = await descargador.descargar_ultimas_24h()
    print(f"   ✅ Descargadas {len(alertas)} alertas")

    if not alertas:
        print("   ℹ️  Sin alertas en últimas 24h (posible - depende del feed)")
        return True

    # 3. Validar estructura de alertas
    print("\n3️⃣  Validando estructura de alertas...")
    for i, alerta in enumerate(alertas[:3]):  # Mostrar primeras 3
        print(f"\n   Alerta {i + 1}:")
        print(f"     - ID: {alerta.alert_id[:16]}...")
        print(f"     - Fuente: {alerta.fuente}")
        print(f"     - Producto: {alerta.producto_nombre}")
        print(f"     - Riesgo: {alerta.riesgo_categoria} ({alerta.riesgo_texto[:50]}...)")
        print(f"     - Origen: {alerta.pais_origen} → Destino: {alerta.pais_destino}")
        print(f"     - Fecha: {alerta.fecha_emitida}")
        print(f"     - URL: {alerta.url_oficial[:60]}...")

        # Validar campos obligatorios
        assert alerta.alert_id, "alert_id vacío"
        assert alerta.fuente == "rasff", "fuente incorrecta"
        assert alerta.producto_nombre, "producto_nombre vacío"
        assert alerta.riesgo_categoria in ["patogeno", "alérgeno", "residuo", "otro"], "categoría inválida"
        assert alerta.fecha_emitida, "fecha_emitida vacía"
        assert alerta.pais_destino == "EU", "destino debe ser EU para RASFF"

    print("\n   ✅ Estructura validada")

    # 4. Test de dedup
    print("\n4️⃣  Validando dedup por hash...")
    hashes = [a.alert_id for a in alertas]
    hashes_unicos = set(hashes)
    print(f"   - Total alertas: {len(alertas)}")
    print(f"   - Hashes únicos: {len(hashes_unicos)}")
    if len(hashes) != len(hashes_unicos):
        print(f"   ⚠️  Hay {len(hashes) - len(hashes_unicos)} duplicados en la misma descarga")
    else:
        print("   ✅ Todos los hashes son únicos")

    return True


async def main():
    """Ejecutar todos los tests."""
    print("\n" + "=" * 80)
    print("S6 FASE 1: TEST DESCARGADORES OPENFDA + RASFF")
    print("=" * 80)

    resultados = {}

    try:
        resultados["openFDA"] = await test_openfda()
    except Exception as e:
        print(f"\n❌ Error en test openFDA: {e}")
        import traceback
        traceback.print_exc()
        resultados["openFDA"] = False

    try:
        resultados["RASFF"] = await test_rasff()
    except Exception as e:
        print(f"\n❌ Error en test RASFF: {e}")
        import traceback
        traceback.print_exc()
        resultados["RASFF"] = False

    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN")
    print("=" * 80)
    for nombre, resultado in resultados.items():
        status = "✅ PASÓ" if resultado else "❌ FALLÓ"
        print(f"{status}: {nombre}")

    total_ok = sum(1 for v in resultados.values() if v)
    print(f"\nTotal: {total_ok}/{len(resultados)} tests pasaron")

    if total_ok == len(resultados):
        print("\n✅ S6 FASE 1 COMPLETADA - Descargadores funcionan correctamente")
        return 0
    else:
        print("\n❌ S6 FASE 1 - Algunos tests fallaron")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
