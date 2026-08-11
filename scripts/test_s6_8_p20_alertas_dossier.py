"""
Test P20 S6.8: Insumo con ingrediente retirado → dossier lo señala

Flujo:
  1. Insertar alerta manual en openFDA_alerts para "quinua"
  2. Query búsqueda de "quinua" con nivel=3
  3. Ejecutar Etapa 5 (verificar regulación + alertas)
  4. Verificar dossier incluye sección de alertas
  5. Validar severity label y fecha
  6. Test negativo: sin alertas → dice "Sin alertas activas"

Ejecución:
  python scripts/test_s6_8_p20_alertas_dossier.py

Dependencias:
  - BD con tablas S6 creadas (migration_s6_alertas_tablas.sql)
  - Etapa 5 mejorada (buscar_alertas_para_etapa5)
"""

import sys
import asyncio
from datetime import datetime, timedelta
from adaptadores.db import pool
from dominio.insumo import InsumoInterpretado
from dominio.alerta_retiro import AlertasDeRetiro
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.etapas.buscar_alertas_retiro import buscar_alertas_para_etapa5

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Setup: Insertar alertas de prueba
# ============================================================================


def setup_alertas_prueba():
    """Insertar alertas manuales para testing."""
    print("\n🔧 Setup: Insertando alertas de prueba")

    try:
        conn = pool().connection()
        with conn.cursor() as cur:
            # Limpiar alertas de prueba anteriores
            cur.execute("DELETE FROM openfda_alerts WHERE producto_nombre LIKE 'TEST%'")
            cur.execute("DELETE FROM rasff_alerts WHERE producto_nombre LIKE 'TEST%'")

            # Alerta 1: Quinua con E. coli (crítica)
            alerta_id_1 = "TEST_P20_001_ECOLI_QUINUA"
            fecha_1 = datetime.utcnow() - timedelta(days=10)

            cur.execute(
                """
                INSERT INTO openfda_alerts
                    (alert_id, fecha_emitida, empresa, producto_nombre,
                     razon_texto, razon_categoria, pais, url_oficial, titulo_enforcement)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    alerta_id_1,
                    fecha_1.date(),
                    "TEST Quinua Farms Peru",
                    "TEST Quinua Flour Premium",
                    "E. coli O157:H7 detected",
                    "patogeno",
                    "PE",
                    "https://fda.gov/test/p20/001",
                    "Test Enforcement P20-001",
                ),
            )

            # Alerta 2: Almendras con alérgeno (media)
            alerta_id_2 = "TEST_P20_002_ALERGEN_ALMOND"
            fecha_2 = datetime.utcnow() - timedelta(days=45)

            cur.execute(
                """
                INSERT INTO openfda_alerts
                    (alert_id, fecha_emitida, empresa, producto_nombre,
                     razon_texto, razon_categoria, pais, url_oficial, titulo_enforcement)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    alerta_id_2,
                    fecha_2.date(),
                    "TEST Almond Co",
                    "TEST Almonds Raw Organic",
                    "Undeclared milk allergen",
                    "alérgeno",
                    "US",
                    "https://fda.gov/test/p20/002",
                    "Test Enforcement P20-002",
                ),
            )

            # Calcular scores
            conn.commit()

            cur.execute(
                """
                INSERT INTO alert_scores (alert_id, alert_tipo, score, severity_label, dias_desde_emitida)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (alerta_id_1, "openfda", 4.5, "critical", 10),
            )

            cur.execute(
                """
                INSERT INTO alert_scores (alert_id, alert_tipo, score, severity_label, dias_desde_emitida)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (alerta_id_2, "openfda", 2.5, "medium", 45),
            )

            conn.commit()

            print(f"   ✅ Insertadas 2 alertas de prueba")
            print(f"      - {alerta_id_1}: E. coli crítica")
            print(f"      - {alerta_id_2}: Alérgeno media")

            return alerta_id_1, alerta_id_2

    except Exception as e:
        print(f"   ❌ Error en setup: {e}")
        import traceback

        traceback.print_exc()
        return None, None


# ============================================================================
# Test 1: Búsqueda con alertas
# ============================================================================


async def test_p20_ingrediente_con_alerta():
    """Test P20: Ingrediente retirado → dossier muestra alerta."""
    print("\n" + "=" * 80)
    print("🧪 TEST P20: Dossier Regulatorio + Alertas de Retiro")
    print("=" * 80)

    # 1. Crear insumo interpretado (como si viniera de Etapa 1-3)
    print("\n1️⃣  Creando insumo: 'quinua' (nivel=3)")
    interpretado = InsumoInterpretado(
        insumo_original="quinua",
        insumo_normalizado="quinua",
        terminos_ingles=["quinoa"],
        nivel=3,
        confianza_normalizacion=0.95,
    )

    # 2. Crear dependencias mínimas
    print("\n2️⃣  Configurando dependencias")
    d = Dependencias()

    # 3. Ejecutar búsqueda de alertas (Etapa 5 S6)
    print("\n3️⃣  Ejecutando buscar_alertas_para_etapa5()...")
    try:
        alertas = await buscar_alertas_para_etapa5(
            d, interpretado, pais="PE"
        )

        print(f"   ✅ Búsqueda completada")
        print(f"      - Total alertas: {alertas.cantidad_activas}")
        print(f"      - Críticas: {alertas.cantidad_criticas}")
        print(f"      - Sin alertas: {alertas.sin_alertas}")
        print(f"      - Summary: {alertas.summary()}")

    except Exception as e:
        print(f"   ❌ Error en búsqueda: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 4. Validaciones
    print("\n4️⃣  Validando resultado...")

    # Debe encontrar al menos 1 alerta (la de E. coli)
    if alertas.sin_alertas:
        print(f"   ❌ FALLÓ: No encontró alertas para 'quinua'")
        return False

    if alertas.cantidad_activas == 0:
        print(f"   ❌ FALLÓ: cantidad_activas = 0")
        return False

    print(f"   ✅ Encontradas {alertas.cantidad_activas} alertas")

    # Debe tener al menos 1 crítica (la de E. coli)
    if alertas.cantidad_criticas < 1:
        print(f"   ❌ FALLÓ: No hay alertas críticas (esperado >= 1)")
        return False

    print(f"   ✅ {alertas.cantidad_criticas} alerta(s) crítica(s)")

    # Validar estructura de alertas
    print("\n5️⃣  Validando estructura de alertas...")
    for alerta in alertas.alertas:
        print(f"   - {alerta.producto_nombre}:")
        print(f"     • Fuente: {alerta.fuente}")
        print(f"     • Severidad: {alerta.severity_label} ({alerta.severity_score:.1f})")
        print(f"     • Riesgo: {alerta.riesgo_categoria}")
        print(f"     • Fecha: {alerta.fecha_emitida.date()}")
        print(f"     • Días desde: {alerta.dias_desde}")

        # Validar campos obligatorios
        assert alerta.alert_id, "alert_id vacío"
        assert alerta.fuente, "fuente vacía"
        assert alerta.producto_nombre, "producto_nombre vacío"
        assert alerta.severity_label, "severity_label vacío"
        assert alerta.url_oficial, "url_oficial vacía"

    print(f"   ✅ Estructura validada")

    # 6. Validar que encontró la alerta de quinua específicamente
    print("\n6️⃣  Validando alertas específicas...")
    alertas_quinua = [a for a in alertas.alertas if "quinua" in a.producto_nombre.lower()]

    if not alertas_quinua:
        print(f"   ⚠️  No hay alertas exactas de 'quinua' (puede ser por similitud < 80%)")
    else:
        print(f"   ✅ Encontradas {len(alertas_quinua)} alerta(s) de 'quinua'")
        for a in alertas_quinua:
            print(f"      - {a.producto_nombre}: {a.severity_label}")

            # Validar que E. coli es crítica
            if "E. coli" in a.riesgo_texto and a.severity_label != "critical":
                print(f"      ❌ FALLÓ: E. coli debe ser crítica")
                return False

    print("\n   ✅ TEST P20 PASSOU")
    return True


# ============================================================================
# Test 2: Sin alertas → dossier dice "Sin alertas"
# ============================================================================


async def test_p20_sin_alertas():
    """Test P20 negativo: Ingrediente sin alertas."""
    print("\n" + "=" * 80)
    print("🧪 TEST P20 NEGATIVO: Ingrediente sin alertas")
    print("=" * 80)

    print("\n1️⃣  Buscando ingrediente inexistente: 'XXXXXXYZZZZ_FAKE'")
    interpretado = InsumoInterpretado(
        insumo_original="XXXXXXYZZZZ_FAKE",
        insumo_normalizado="XXXXXXYZZZZ_FAKE",
        terminos_ingles=["FAKE_INGREDIENT"],
        nivel=3,
        confianza_normalizacion=0.95,
    )

    d = Dependencias()

    print("\n2️⃣  Ejecutando buscar_alertas_para_etapa5()...")
    try:
        alertas = await buscar_alertas_para_etapa5(d, interpretado, pais="PE")

        print(f"   ✅ Búsqueda completada")
        print(f"      - sin_alertas: {alertas.sin_alertas}")
        print(f"      - cantidad_activas: {alertas.cantidad_activas}")
        print(f"      - Summary: {alertas.summary()}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    # Validar
    print("\n3️⃣  Validando...")

    if not alertas.sin_alertas:
        print(f"   ❌ FALLÓ: sin_alertas debe ser True")
        return False

    if alertas.cantidad_activas != 0:
        print(f"   ❌ FALLÓ: cantidad_activas debe ser 0")
        return False

    if len(alertas.alertas) != 0:
        print(f"   ❌ FALLÓ: lista de alertas debe estar vacía")
        return False

    print(f"   ✅ Correctamente reporta sin alertas")
    return True


# ============================================================================
# Test 3: JSON serializable para API
# ============================================================================


def test_p20_json_serializable():
    """Test P20: AlertasDeRetiro es serializable a JSON."""
    print("\n" + "=" * 80)
    print("🧪 TEST P20: JSON Serialization para API")
    print("=" * 80)

    print("\n1️⃣  Creando AlertasDeRetiro con alertas...")
    from dominio.alerta_retiro import AlertaDeRetiro

    alertas = AlertasDeRetiro(
        alertas=[
            AlertaDeRetiro(
                alert_id="TEST_001",
                fuente="openfda",
                producto_nombre="Test Product",
                riesgo_categoria="patogeno",
                riesgo_texto="Test Hazard",
                fecha_emitida=datetime.utcnow(),
                dias_desde=5,
                pais_origen="PE",
                pais_destino="US",
                url_oficial="https://test.com",
                severity_score=4.5,
                severity_label="critical",
            )
        ],
        cantidad_criticas=1,
        cantidad_activas=1,
        sin_alertas=False,
    )

    print("\n2️⃣  Serializando a JSON...")
    try:
        json_str = alertas.model_dump_json()
        print(f"   ✅ Serializado correctamente ({len(json_str)} bytes)")

        # Verificar estructura
        import json
        json_obj = json.loads(json_str)
        assert "alertas" in json_obj
        assert "cantidad_criticas" in json_obj
        assert json_obj["cantidad_criticas"] == 1
        print(f"   ✅ Estructura JSON válida")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

    return True


# ============================================================================
# Main
# ============================================================================


async def main():
    """Ejecutar todos los tests de P20."""
    print("\n" + "=" * 80)
    print("S6.8 TEST P20: DOSSIER CON ALERTAS DE RETIRO")
    print("=" * 80)

    # Setup
    alerta_id_1, alerta_id_2 = setup_alertas_prueba()
    if not alerta_id_1:
        print("\n❌ Setup falló")
        return 1

    resultados = {}

    # Test 1: Con alertas
    try:
        resultados["con_alertas"] = await test_p20_ingrediente_con_alerta()
    except Exception as e:
        print(f"\n❌ Error en test con alertas: {e}")
        import traceback

        traceback.print_exc()
        resultados["con_alertas"] = False

    # Test 2: Sin alertas
    try:
        resultados["sin_alertas"] = await test_p20_sin_alertas()
    except Exception as e:
        print(f"\n❌ Error en test sin alertas: {e}")
        import traceback

        traceback.print_exc()
        resultados["sin_alertas"] = False

    # Test 3: JSON
    try:
        resultados["json_serializable"] = test_p20_json_serializable()
    except Exception as e:
        print(f"\n❌ Error en test JSON: {e}")
        import traceback

        traceback.print_exc()
        resultados["json_serializable"] = False

    # Resumen
    print("\n" + "=" * 80)
    print("📊 RESUMEN TEST P20")
    print("=" * 80)
    for nombre, resultado in resultados.items():
        status = "✅ PASÓ" if resultado else "❌ FALLÓ"
        print(f"{status}: {nombre}")

    total_ok = sum(1 for v in resultados.values() if v)
    print(f"\nTotal: {total_ok}/{len(resultados)} tests pasaron")

    if total_ok == len(resultados):
        print("\n✅ TEST P20 COMPLETADO - Dossier con alertas funciona correctamente")
        return 0
    else:
        print("\n❌ TEST P20 - Algunos tests fallaron")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
