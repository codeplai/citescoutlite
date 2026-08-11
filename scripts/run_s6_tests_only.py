#!/usr/bin/env python3
"""
Script para ejecutar tests de S6 (sin crear tablas)
Las tablas deben crearse manualmente con:
  psql -d cite_mvp < scripts/migration_s6_alertas_tablas.sql
"""

import sys
import subprocess
import os

# Agregar el directorio actual al path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

# Cargar .env explícitamente
from dotenv import load_dotenv
load_dotenv(os.path.join(base_dir, '.env'))

def print_header(titulo):
    """Imprimir encabezado."""
    print("\n" + "="*80)
    print(f"  {titulo}")
    print("="*80 + "\n")

def print_ok(msg):
    print(f"[OK] {msg}")

def print_fail(msg):
    print(f"[FAIL] {msg}")

def print_info(msg):
    print(f"[INFO] {msg}")

def ejecutar_test(script, descripcion):
    """Ejecutar un test específico."""
    print_info(f"Ejecutando: {descripcion}")

    if not os.path.exists(script):
        print_fail(f"Script no encontrado: {script}")
        return False

    try:
        result = subprocess.run(
            f"python {script}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Verificar si pasó
        output = result.stdout + result.stderr
        paso = result.returncode == 0 or "COMPLETADA" in output or "PASÓ" in output

        if paso:
            print_ok(descripcion)
            # Mostrar último línea del output
            lineas = [l for l in output.split('\n') if l.strip()]
            if lineas:
                print(f"    -> {lineas[-1]}")
        else:
            print_fail(descripcion)
            # Mostrar útlimas líneas del output
            lineas = [l for l in output.split('\n') if l.strip()]
            for linea in lineas[-10:]:
                print(f"    {linea}")

        return paso

    except subprocess.TimeoutExpired:
        print_fail(f"Timeout en {descripcion}")
        return False
    except Exception as e:
        print_fail(f"Error ejecutando {descripcion}: {e}")
        return False

def main():
    """Ejecutar pruebas S6."""
    print_header("TESTING S6 - ALERTAS DE RETIRO")

    print_info("NOTA: Las tablas deben estar creadas en BD")
    print_info("Ejecutar primero:")
    print("      psql -d cite_mvp < scripts/migration_s6_alertas_tablas.sql")

    # Paso: Ejecutar tests
    print_header("Ejecutando Tests")

    tests = [
        ("scripts/test_s6_1_2_descargadores.py", "Fase 1: Descargadores (openFDA + RASFF)"),
        ("scripts/test_s6_3_4_busqueda_scoring.py", "Fase 2: Busqueda Fuzzy + Scoring"),
        ("scripts/test_s6_5_6_integracion_job.py", "Fase 3: Integracion + Job Scheduler"),
        ("scripts/test_s6_8_p20_alertas_dossier.py", "Test P20: Dossier con Alertas"),
    ]

    resultados = {}

    for script, descripcion in tests:
        print()
        resultados[descripcion] = ejecutar_test(script, descripcion)

    # Resumen
    print_header("RESUMEN FINAL S6")

    print("Tests:")

    total_tests = len(resultados)
    tests_pasados = sum(1 for v in resultados.values() if v)

    for nombre, resultado in resultados.items():
        status = "[PASS]" if resultado else "[FAIL]"
        print(f"  {status} {nombre}")

    print(f"\nTotal: {tests_pasados}/{total_tests} tests pasaron")

    if tests_pasados == total_tests:
        print("\n" + "="*80)
        print("  S6 TESTS COMPLETADOS - TODO OK")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print("  S6 TESTS - Algunos fallaron - revisar arriba")
        print("="*80)
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print_fail(f"Error critico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
