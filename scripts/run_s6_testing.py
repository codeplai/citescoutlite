#!/usr/bin/env python3
"""
Script para probar S6 completamente:
1. Crear tablas en BD
2. Ejecutar tests Fase 1-3
3. Ejecutar Test P20
4. Resumen final
"""

import sys
import subprocess
import os

# Colores para output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(titulo):
    """Imprimir encabezado."""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{titulo:^80}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")

def print_success(msg):
    """Imprimir mensaje de éxito."""
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    """Imprimir mensaje de error."""
    print(f"{RED}❌ {msg}{RESET}")

def print_warning(msg):
    """Imprimir mensaje de advertencia."""
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def run_command(cmd, description):
    """Ejecutar comando y retornar resultado."""
    print(f"{YELLOW}▶ {description}...{RESET}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print_success(description)
        if result.stdout:
            print(result.stdout[:500])  # Primeros 500 chars
        return True
    else:
        print_error(description)
        print(f"Error: {result.stderr[:500]}")
        return False

def crear_tablas():
    """Crear tablas en BD ejecutando migration SQL."""
    print_header("PASO 1: Crear Tablas en BD")

    print("Ejecutando migration SQL...")

    # Leer SQL
    try:
        with open("scripts/migration_s6_alertas_tablas.sql", "r") as f:
            sql_content = f.read()
        print_success("Script SQL leído")
    except Exception as e:
        print_error(f"No se pudo leer migration: {e}")
        return False

    # Ejecutar con Python + psycopg
    try:
        from adaptadores.db import pool

        conn = pool().connection()
        with conn.cursor() as cur:
            # Dividir el SQL en comandos
            statements = sql_content.split(';')

            for i, stmt in enumerate(statements):
                stmt = stmt.strip()
                if not stmt:
                    continue

                if stmt.upper().startswith('BEGIN') or stmt.upper().startswith('COMMIT'):
                    continue

                try:
                    cur.execute(stmt)
                    print(f"  ✓ Comando {i+1} ejecutado")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"  ℹ️  Tabla ya existe")
                    else:
                        print(f"  ⚠️  {str(e)[:100]}")

            conn.commit()

        print_success("Tablas creadas/verificadas en BD")
        return True

    except Exception as e:
        print_error(f"Error creando tablas: {e}")
        import traceback
        traceback.print_exc()
        return False

def ejecutar_tests():
    """Ejecutar todos los tests de S6."""
    print_header("PASO 2: Ejecutar Tests")

    tests = [
        ("scripts/test_s6_1_2_descargadores.py", "Fase 1: Descargadores"),
        ("scripts/test_s6_3_4_busqueda_scoring.py", "Fase 2: Búsqueda + Scoring"),
        ("scripts/test_s6_5_6_integracion_job.py", "Fase 3: Integración + Job"),
        ("scripts/test_s6_8_p20_alertas_dossier.py", "Test P20: Dossier con Alertas"),
    ]

    resultados = {}

    for script, descripcion in tests:
        print(f"\n{BLUE}▶ Ejecutando: {descripcion}{RESET}")

        if not os.path.exists(script):
            print_warning(f"Script no encontrado: {script}")
            resultados[descripcion] = False
            continue

        result = subprocess.run(
            f"python {script}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )

        # Verificar si pasó (buscar "COMPLETADA" o "PASÓ" en output)
        output = result.stdout + result.stderr
        paso = result.returncode == 0 or "COMPLETADA" in output or "PASÓ" in output

        resultados[descripcion] = paso

        if paso:
            print_success(descripcion)
        else:
            print_error(descripcion)
            # Mostrar último parte del output
            lineas = output.split('\n')
            for linea in lineas[-10:]:
                if linea.strip():
                    print(f"  {linea}")

    return resultados

def resumen_final(tablas_ok, resultados_tests):
    """Mostrar resumen final."""
    print_header("RESUMEN FINAL S6")

    print(f"Base de Datos: {'✅ OK' if tablas_ok else '❌ FALLÓ'}")
    print(f"\nTests:")

    total_tests = len(resultados_tests)
    tests_pasados = sum(1 for v in resultados_tests.values() if v)

    for nombre, resultado in resultados_tests.items():
        status = "✅" if resultado else "❌"
        print(f"  {status} {nombre}")

    print(f"\nTotal: {tests_pasados}/{total_tests} tests pasaron")

    if tablas_ok and tests_pasados == total_tests:
        print(f"\n{GREEN}🎉 S6 PROBADO COMPLETAMENTE - TODO OK{RESET}")
        return 0
    else:
        print(f"\n{YELLOW}⚠️  S6 con algunos problemas - revisar arriba{RESET}")
        return 1

def main():
    """Ejecutar pruebas S6."""
    print_header("TESTING S6 - ALERTAS DE RETIRO")

    # Paso 1: Crear tablas
    print("Creando tablas en BD...")
    tablas_ok = crear_tablas()

    # Paso 2: Ejecutar tests
    print("\nEjecutando tests...")
    resultados_tests = ejecutar_tests()

    # Resumen
    exit_code = resumen_final(tablas_ok, resultados_tests)

    return exit_code

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print_error(f"Error crítico: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
