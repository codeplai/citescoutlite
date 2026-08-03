#!/usr/bin/env python
"""
T7.4 - Copia el cache de respuestas LLM de Supabase al archivo local.

Uso:
  uv run python scripts/sembrar_cache_local.py

Por que existe. El plan B de la demo es `APP_DB=sqlite` + `AGROSCOUT_OFFLINE=1`,
y el DoD pide que **complete un run sin red**. Sin red no hay LLM, asi que la
unica forma de completarlo es que las respuestas ya esten en el cache local. El
cache vive en Supabase desde T3, de modo que hay que traerlo antes de quedarse
sin conexion.

Se ejecuta con red, antes de la demo. Si el dia del ensayo hay que tirar del
plan B, ya esta todo abajo.

Copia solo las filas del snapshot en curso (o el que se pase con --snapshot):
traer entradas de snapshots viejos llenaria el archivo de respuestas que ninguna
consulta va a volver a pedir.
"""

import argparse
import sqlite3
import sys
from contextlib import closing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=None,
                        help="Version de snapshot a copiar (por defecto, la del dataset)")
    parser.add_argument("--todos", action="store_true",
                        help="Copiar todas las entradas, sea cual sea el snapshot")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()

    import json

    import psycopg

    from adaptadores.cache_sqlite import CacheSQLite
    from adaptadores.entorno import ruta_db_sqlite, url_base_datos

    if args.snapshot:
        snapshot = args.snapshot
    else:
        from api.main import cargar_snapshot_version
        snapshot = cargar_snapshot_version()

    destino = ruta_db_sqlite()
    CacheSQLite(destino)  # crea la tabla y pone el esquema al dia

    condicion = "" if args.todos else "where snapshot_version = %s"
    parametros = () if args.todos else (snapshot,)

    print("=== T7.4 - Cache de Supabase -> archivo local ===")
    print(f"[INFO] snapshot: {'(todos)' if args.todos else snapshot}")

    with psycopg.connect(url_base_datos(), prepare_threshold=None) as conexion:
        filas = conexion.execute(f"""
            select clave_hash, etapa, modelo, respuesta_json, snapshot_version
              from public.cache_llm {condicion}
        """, parametros).fetchall()

    if not filas:
        print("[AVISO] No hay entradas que copiar. Correr una consulta con red "
              "antes, o pasar --todos.")
        return 1

    with closing(sqlite3.connect(destino)) as local, local:
        local.executemany("""
            INSERT OR REPLACE INTO cache_llm
                (clave_hash, etapa, modelo, respuesta_json, snapshot_version)
            VALUES (?, ?, ?, ?, ?)
        """, [(clave, etapa, modelo, json.dumps(respuesta, ensure_ascii=False),
               version) for clave, etapa, modelo, respuesta, version in filas])

        total = local.execute("SELECT COUNT(*) FROM cache_llm").fetchone()[0]

    print(f"[OK]   {len(filas)} entradas copiadas a {destino}")
    print(f"[OK]   El archivo local tiene ahora {total} entradas de cache")
    print("[OK]   El plan B puede completar un run sin red para esos insumos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
