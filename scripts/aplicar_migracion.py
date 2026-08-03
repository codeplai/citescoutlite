#!/usr/bin/env python
"""
Aplica un archivo .sql contra la base de Supabase y verifica el DoD de TIER 2.

Uso:
  uv run python scripts/aplicar_migracion.py supabase/migraciones/001_esquema_s3.sql

Las migraciones son SQL plano a proposito: no hace falta la Supabase CLI
(arrastra Docker) para aplicar cinco tablas.
"""

import os
import sys
from pathlib import Path

TABLAS = ("perfiles", "ejecuciones", "etapas_ejecucion", "cache_llm", "informes")
POLITICAS_ESPERADAS = 3


def aplicar(conexion, ruta: Path) -> None:
    conexion.execute(ruta.read_text(encoding="utf-8"))
    print(f"[OK]   Aplicado {ruta}")


def verificar(conexion) -> bool:
    ok = True

    filas = dict(conexion.execute("""
        select tablename, rowsecurity from pg_tables
        where schemaname = 'public' and tablename = any(%s)
    """, (list(TABLAS),)).fetchall())

    faltan = [t for t in TABLAS if t not in filas]
    if faltan:
        print(f"[ERROR] Tablas ausentes: {', '.join(faltan)}")
        ok = False
    else:
        print(f"[OK]   {len(TABLAS)} tablas creadas")

    sin_rls = [t for t, activo in filas.items() if not activo]
    if sin_rls:
        print(f"[ERROR] RLS apagado en: {', '.join(sin_rls)}")
        ok = False
    elif filas:
        print(f"[OK]   rowsecurity = true en las {len(filas)} tablas")

    politicas = conexion.execute("""
        select tablename, policyname from pg_policies
        where schemaname = 'public' order by tablename
    """).fetchall()
    if len(politicas) == POLITICAS_ESPERADAS:
        print(f"[OK]   {len(politicas)} politicas: "
              + ", ".join(f"{t}.{p}" for t, p in politicas))
    else:
        print(f"[ERROR] Se esperaban {POLITICAS_ESPERADAS} politicas, hay {len(politicas)}")
        ok = False

    vista = conexion.execute("""
        select count(*) from pg_views
        where schemaname = 'public' and viewname = 'uso_mensual'
    """).fetchone()[0]
    if vista:
        print("[OK]   Vista uso_mensual creada")
    else:
        print("[ERROR] Falta la vista uso_mensual")
        ok = False

    return ok


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    ruta = Path(sys.argv[1])
    if not ruta.is_file():
        print(f"[ERROR] No existe {ruta}")
        return 1

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg

    print(f"=== Migracion {ruta.name} ===")
    with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None,
                         connect_timeout=15, autocommit=False) as conexion:
        aplicar(conexion, ruta)
        conexion.commit()
        ok = verificar(conexion)

    print("[OK]   DoD de esquema verificado" if ok else "[ERROR] DoD de esquema incompleto")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
