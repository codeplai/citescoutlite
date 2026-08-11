#!/usr/bin/env python
"""
Aplica contra Postgres las migraciones que quedaron escritas y sin correr (S1 -> S6).

Auditoria de S7 (TIERSV3/S7_AUDITORIA_PREVIA.md): tres semanas se cerraron con su
SQL sin aplicar. Este runner las pone al dia en el orden correcto.

A diferencia de `aplicar_migracion.py`, que verifica el DoD concreto de TIER 2 y
por eso da error con cualquier otro archivo, este aplica una lista ordenada y
verifica que las tablas resultantes existan.

PASO 0 -- El esquema viejo de S1 (`create_schema_s1.sql`) dejo en Postgres tres
tablas que colisionan con la migracion 001 y tres huerfanas. Ninguna tiene filas
ni la referencia el codigo. `create table if not exists` no las alteraria: la
migracion pasaria en verde dejando la aplicacion rota igual, asi que hay que
eliminarlas antes.

Uso:
  uv run python scripts/aplicar_migraciones_pendientes.py            # dry-run
  uv run python scripts/aplicar_migraciones_pendientes.py --aplicar
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Tablas del esquema S1 a eliminar antes de 001, con la columna que delata que
# la tabla es la version S1 y no la que crea 001. Tres de los nombres los reusa
# 001, asi que sin esa comprobacion una segunda pasada del runner borraria el
# esquema bueno recien creado. None = legado puro, no lo recrea nadie.
#
# Orden: primero las que tienen FK hacia `consultas`. CASCADE cubre el resto.
TABLAS_S1 = [
    ("etapas_ejecucion", "consulta_id"),  # 001 usa ejecucion_id
    ("informes", "consulta_id"),          # 001 usa ejecucion_id + ruta_storage
    ("cache_llm", "ttl_days"),            # 001 no tiene esa columna
    ("consultas", None),                  # huerfana: nadie la consulta en Postgres
    ("usuarios", None),                   # huerfana: el modo demo usa la de SQLite
    ("organizaciones", None),             # huerfana: el MVP es de una institucion
]

# (ruta, descripcion). El orden importa: 005 y 006 tienen FK hacia lo de 001.
MIGRACIONES = [
    ("supabase/migraciones/001_esquema_s3.sql",
     "S3 - perfiles, ejecuciones, etapas_ejecucion, cache_llm, informes + uso_mensual"),
    ("supabase/migraciones/002_cache_hit.sql",
     "S3 - columna cache_hit en etapas_ejecucion"),
    ("supabase/migraciones/003_perfiles_trigger.sql",
     "S3 - trigger de perfil automatico sobre auth.users"),
    ("supabase/migraciones/005_presupuesto_uso.sql",
     "S2.6 - presupuesto_uso, presupuesto_config + vistas de gasto"),
    ("migrations/006_create_regulaciones_s4.sql",
     "S4 - corpus regulatorio (8 tablas)"),
    ("scripts/migration_s6_alertas_tablas.sql",
     "S6 - alertas de retiro openFDA + RASFF (6 tablas)"),
    ("supabase/migraciones/006_promotion_source.sql",
     "S7.7 (D1) - promotion_source en staging_agente + vista staging_promovido"),
    ("supabase/migraciones/007_promocion_s7.sql",
     "S7.1-7.4 - promotion_rules, watermark_log, validation_log, promotion_log"),
    ("supabase/migraciones/008_rol_perfiles.sql",
     "S7.6 - rol (operador/admin) en perfiles"),
]

# Lo que debe existir al terminar.
TABLAS_ESPERADAS = [
    # 001
    "perfiles", "ejecuciones", "etapas_ejecucion", "cache_llm", "informes",
    # 004 (ya estaba)
    "staging_agente",
    # 005
    "presupuesto_uso", "presupuesto_config",
    # 006 (S4)
    "ecfr_regulations", "efsa_regulations", "codex_standards", "inacal_nts",
    "digesa_directivas", "mapping_regulaciones", "regulacion_cita",
    "audit_regulaciones",
    # S6
    "openfda_alerts", "rasff_alerts", "alert_scores", "alert_lookup_log",
    "alert_ingest_log", "alert_notification_history",
    # 007 (S7)
    "promotion_rules", "promotion_watermark_log", "promotion_validation_log",
    "promotion_log",
]

VISTAS_ESPERADAS = ["uso_mensual", "staging_pendiente", "staging_promovido",
                    "gasto_usuario_mes", "gasto_global_dia"]


def soltar_tablas_s1(conexion) -> None:
    """PASO 0: elimina el esquema S1 que bloquea 001.

    Aborta si alguna tiene filas: la premisa de que estan vacias es lo que hace
    que esto sea seguro, y si cambio hay que mirarlo a mano.
    """
    print("\n--- PASO 0: esquema S1 ---")
    for tabla, columna_s1 in TABLAS_S1:
        existe = conexion.execute(
            "select to_regclass(%s)", (f"public.{tabla}",)).fetchone()[0]
        if not existe:
            print(f"[SKIP] public.{tabla} no existe")
            continue

        if columna_s1:
            es_s1 = conexion.execute("""
                select count(*) from information_schema.columns
                where table_schema = 'public' and table_name = %s
                  and column_name = %s
            """, (tabla, columna_s1)).fetchone()[0]
            if not es_s1:
                print(f"[SKIP] public.{tabla} ya tiene el esquema S3")
                continue

        filas = conexion.execute(f"select count(*) from public.{tabla}").fetchone()[0]
        if filas:
            raise SystemExit(
                f"[ABORTA] public.{tabla} tiene {filas} filas. Se esperaban 0. "
                "Revisar a mano antes de continuar.")

        conexion.execute(f"drop table if exists public.{tabla} cascade")
        print(f"[OK]   drop public.{tabla} (0 filas)")


def aplicar(conexion, ruta: Path, descripcion: str) -> None:
    """Aplica un .sql.

    Los archivos de `migrations/` y `scripts/` traen su propio BEGIN/COMMIT; los
    de `supabase/migraciones/` no. psycopg abre transaccion sola, asi que en
    ambos casos basta con ejecutar el texto entero y confirmar al final: el
    COMMIT interno cierra la suya y el commit de fuera no encuentra nada que
    hacer.
    """
    sql = ruta.read_text(encoding="utf-8")
    conexion.execute(sql)
    conexion.commit()
    print(f"[OK]   {ruta}\n       {descripcion}")


def verificar(conexion) -> bool:
    print("\n--- VERIFICACION ---")
    ok = True

    presentes = {f[0] for f in conexion.execute("""
        select tablename from pg_tables where schemaname = 'public'
    """).fetchall()}

    faltan = [t for t in TABLAS_ESPERADAS if t not in presentes]
    if faltan:
        print(f"[ERROR] Tablas ausentes ({len(faltan)}): {', '.join(faltan)}")
        ok = False
    else:
        print(f"[OK]   {len(TABLAS_ESPERADAS)} tablas esperadas presentes")

    sobran = [t for t, _ in TABLAS_S1 if t in presentes and t not in TABLAS_ESPERADAS]
    if sobran:
        print(f"[ERROR] Esquema S1 aun presente: {', '.join(sobran)}")
        ok = False

    vistas = {f[0] for f in conexion.execute("""
        select viewname from pg_views where schemaname = 'public'
    """).fetchall()}
    faltan_vistas = [v for v in VISTAS_ESPERADAS if v not in vistas]
    if faltan_vistas:
        print(f"[ERROR] Vistas ausentes: {', '.join(faltan_vistas)}")
        ok = False
    else:
        print(f"[OK]   {len(VISTAS_ESPERADAS)} vistas presentes")

    # La forma de etapas_ejecucion es lo que rompia /uso y /consultas.
    columnas = {f[0] for f in conexion.execute("""
        select column_name from information_schema.columns
        where table_schema = 'public' and table_name = 'etapas_ejecucion'
    """).fetchall()}
    requeridas = {"ejecucion_id", "costo_usd", "tokens", "tokens_entrada",
                  "tokens_salida", "cache_hit", "modelo"}
    if requeridas <= columnas:
        print("[OK]   etapas_ejecucion tiene el esquema S3 que espera el codigo")
    else:
        print(f"[ERROR] etapas_ejecucion sin: {', '.join(sorted(requeridas - columnas))}")
        ok = False

    return ok


def main() -> int:
    aplicar_de_verdad = "--aplicar" in sys.argv

    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    import psycopg

    print("=== Migraciones pendientes (S1 -> S6) ===")
    if not aplicar_de_verdad:
        print("\nDRY-RUN. Se aplicaria, en este orden:\n")
        print("  PASO 0: drop de " + ", ".join(t for t, _ in TABLAS_S1))
        for ruta, descripcion in MIGRACIONES:
            print(f"  {ruta}\n      {descripcion}")
        print("\nRepetir con --aplicar para ejecutarlo.")
        return 0

    with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None,
                         connect_timeout=15, autocommit=False) as conexion:
        soltar_tablas_s1(conexion)
        conexion.commit()

        print("\n--- MIGRACIONES ---")
        for ruta, descripcion in MIGRACIONES:
            aplicar(conexion, RAIZ / ruta, descripcion)

        ok = verificar(conexion)

    print("\n[OK]   Migraciones al dia" if ok else "\n[ERROR] Quedan huecos")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
