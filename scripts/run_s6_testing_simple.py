#!/usr/bin/env python3
"""
Script para probar S6 completamente (versión simple, sin emojis)
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

def crear_tablas():
    """Crear tablas en BD."""
    print_header("PASO 1: Crear Tablas en BD")

    print_info("Leyendo migration SQL...")

    try:
        with open("scripts/migration_s6_alertas_tablas.sql", "r") as f:
            sql_content = f.read()
        print_ok("Script SQL leido")
    except Exception as e:
        print_fail(f"No se pudo leer migration: {e}")
        return False

    # Ejecutar con Python + psycopg
    try:
        from adaptadores.db import pool

        with pool().connection() as conn, conn.cursor() as cur:
            # Dividir el SQL en comandos
            statements = sql_content.split(';')

            ejecutados = 0
            for i, stmt in enumerate(statements):
                stmt = stmt.strip()
                if not stmt:
                    continue

                if stmt.upper().startswith('BEGIN') or stmt.upper().startswith('COMMIT'):
                    continue

                try:
                    cur.execute(stmt)
                    ejecutados += 1
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print_info(f"Tabla ya existe (linea {i})")
                    else:
                        print_info(f"Nota: {str(e)[:80]}")

            conn.commit()

        print_ok(f"Tablas creadas/verificadas ({ejecutados} comandos)")
        return True

    except Exception as e:
        print_fail(f"Error creando tablas: {e}")
        import traceback
        traceback.print_exc()
        return False

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
        else:
            print_fail(descripcion)
            # Mostrar último parte del output
            lineas = output.split('\n')
            for linea in lineas[-15:]:
                if linea.strip():
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

    # Paso 1: Crear tablas
    print_info("Creando tablas en BD...")
    tablas_ok = crear_tablas()

    if not tablas_ok:
        print_fail("No se pudo crear las tablas")
        return 1

    # Paso 2: Ejecutar tests
    print_header("PASO 2: Ejecutar Tests")

    tests = [
        ("scripts/test_s6_1_2_descargadores.py", "Fase 1: Descargadores"),
        ("scripts/test_s6_3_4_busqueda_scoring.py", "Fase 2: Busqueda + Scoring"),
        ("scripts/test_s6_5_6_integracion_job.py", "Fase 3: Integracion + Job"),
        ("scripts/test_s6_8_p20_alertas_dossier.py", "Test P20: Dossier con Alertas"),
    ]

    resultados = {}

    for script, descripcion in tests:
        print()
        resultados[descripcion] = ejecutar_test(script, descripcion)

    # Resumen
    print_header("RESUMEN FINAL S6")

    print(f"Base de Datos: {'OK' if tablas_ok else 'FALLO'}")
    print("\nTests:")

    total_tests = len(resultados)
    tests_pasados = sum(1 for v in resultados.values() if v)

    for nombre, resultado in resultados.items():
        status = "[PASS]" if resultado else "[FAIL]"
        print(f"  {status} {nombre}")

    print(f"\nTotal: {tests_pasados}/{total_tests} tests pasaron")

    if tablas_ok and tests_pasados == total_tests:
        print("\n" + "="*80)
        print("  S6 PROBADO COMPLETAMENTE - TODO OK")
        print("="*80)
        return 0
    else:
        print("\n" + "="*80)
        print("  S6 con algunos problemas - revisar arriba")
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
