#!/usr/bin/env python
"""
T2.2 - Migra el historico de agroscout.db (SQLite) a Supabase.

Uso:
  uv run python etl/migrar_sqlite_a_supabase.py
  uv run python etl/migrar_sqlite_a_supabase.py --db agroscout.db --email admin@cite.gob.pe

Es idempotente: volver a correrlo no duplica filas.

El historico no tiene usuario asociado, asi que se cuelga de una cuenta tecnica
(admin@cite.gob.pe por defecto) que se crea si no existe. Esa cuenta se crea con
una contrasena aleatoria que NO se imprime ni se guarda: nada en S3 inicia sesion
como admin, y si algun dia hace falta se resetea desde el dashboard.

A esa cuenta NO se le crea fila en 'perfiles' a proposito: el trigger de T4.3
solo dispara para altas posteriores, de modo que 'perfiles' termine con las 2
cuentas demo y ni una mas, que es lo que verifica el DoD de TIER 4.

El volumen es ridiculo (54/94/47). El valor de este paso no es el dato: es
probar el camino de escritura con datos reales antes de que los tests dependan
de el.
"""

import argparse
import sqlite3
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# D6: en SQLite la busqueda sobre el snapshot se registro como etapa '2'.
# El esquema de S3 la llama '2a' y reserva '2b' para el descubrimiento
# comercial de S4. El historico son busquedas sobre el snapshot, asi que
# '2' es exactamente '2a'; admitir los dos valores reintroduciria la
# ambiguedad que D6 viene a cerrar.
MAPEO_ETAPA = {"2": "2a"}
ETAPAS_VALIDAS = {"1", "2a", "2b", "3", "4", "5", "6"}

ESPERADO = {"ejecuciones": 54, "etapas_ejecucion": 94, "cache_llm": 47}


def _utc(texto: str | None) -> datetime | None:
    """SQLite guardo datetime('now'), que es UTC sin zona. Se la ponemos."""
    if not texto:
        return None
    return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def resolver_usuario(conexion, email: str) -> str:
    """Devuelve el uuid del dueno del historico, creandolo si no existe."""
    fila = conexion.execute(
        "select id from auth.users where email = %s", (email,)).fetchone()
    if fila:
        print(f"[OK]   Dueno del historico: {email} (ya existia)")
        return str(fila[0])

    import httpx
    from adaptadores.entorno import cabeceras_servicio, url_supabase

    respuesta = httpx.post(
        f"{url_supabase()}/auth/v1/admin/users",
        headers={**cabeceras_servicio(), "Content-Type": "application/json"},
        json={"email": email,
              "password": secrets.token_urlsafe(32),
              "email_confirm": True},
        timeout=30,
    )
    if respuesta.status_code >= 300:
        raise RuntimeError(f"No se pudo crear {email}: {respuesta.status_code} "
                           f"{respuesta.text[:200]}")

    uuid_usuario = respuesta.json()["id"]
    print(f"[OK]   Dueno del historico: {email} (creado; contrasena aleatoria "
          "no guardada, resetear desde el dashboard si hiciera falta)")
    return uuid_usuario


def migrar(conexion, sqlite_conn, usuario_id: str) -> None:
    ejecuciones = sqlite_conn.execute(
        "select id, insumo_texto, snapshot_version, estado, creado_en "
        "from ejecuciones").fetchall()

    conexion.cursor().executemany("""
        insert into public.ejecuciones
            (id, usuario_id, insumo_texto, snapshot_version, estado, creado_en)
        values (%s, %s, %s, %s, %s, %s)
        on conflict (id) do nothing
    """, [(i, usuario_id, texto, snapshot, estado, _utc(creado))
          for i, texto, snapshot, estado, creado in ejecuciones])
    print(f"[OK]   ejecuciones: {len(ejecuciones)} filas")

    # etapas_ejecucion no tiene clave natural (el id es bigserial), asi que la
    # idempotencia se consigue borrando antes las etapas de estos runs.
    ids = [fila[0] for fila in ejecuciones]
    conexion.execute(
        "delete from public.etapas_ejecucion where ejecucion_id = any(%s::uuid[])",
        (ids,))

    etapas = sqlite_conn.execute(
        "select ejecucion_id, etapa, entrada_json, salida_json, duracion_ms, "
        "costo_usd, tokens, tokens_entrada, tokens_salida from etapas_ejecucion"
    ).fetchall()

    filas = []
    convertidas = 0
    for (ej, etapa, entrada, salida, duracion, costo,
         tok, tok_in, tok_out) in etapas:
        # SQLite es de tipado dinamico y la columna, aun declarada TEXT, guarda
        # enteros: estas 94 filas las escribio una version del adaptador
        # anterior al str(etapa) de auditoria_sqlite.py (ver T2.3).
        etapa = str(etapa).strip()
        if etapa in MAPEO_ETAPA:
            etapa = MAPEO_ETAPA[etapa]
            convertidas += 1
        if etapa not in ETAPAS_VALIDAS:
            raise ValueError(f"Etapa {etapa!r} fuera del check del esquema")
        filas.append((ej, etapa, entrada, salida, duracion, costo or 0,
                      tok or 0, tok_in or 0, tok_out or 0))

    # modelo y snapshot_version quedan en null: el archivo SQLite del repo
    # nunca llego a tener esas columnas (ver T2.3).
    conexion.cursor().executemany("""
        insert into public.etapas_ejecucion
            (ejecucion_id, etapa, entrada_json, salida_json, duracion_ms,
             costo_usd, tokens, tokens_entrada, tokens_salida)
        values (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s)
    """, filas)
    print(f"[OK]   etapas_ejecucion: {len(filas)} filas "
          f"({convertidas} con etapa '2' migradas a '2a')")

    cache = sqlite_conn.execute(
        "select clave_hash, etapa, modelo, respuesta_json, snapshot_version, "
        "creado_en from cache_llm").fetchall()
    conexion.cursor().executemany("""
        insert into public.cache_llm
            (clave_hash, etapa, modelo, respuesta_json, snapshot_version, creado_en)
        values (%s, %s, %s, %s::jsonb, %s, %s)
        on conflict (clave_hash) do nothing
    """, [(clave, etapa, modelo, respuesta, snapshot, _utc(creado))
          for clave, etapa, modelo, respuesta, snapshot, creado in cache])
    print(f"[OK]   cache_llm: {len(cache)} filas")


def verificar(conexion) -> bool:
    ok = True
    for tabla, esperado in ESPERADO.items():
        real = conexion.execute(f"select count(*) from public.{tabla}").fetchone()[0]
        if real == esperado:
            print(f"[OK]   {tabla}: {real} filas")
        else:
            print(f"[ERROR] {tabla}: {real} filas, se esperaban {esperado}")
            ok = False

    nulos = conexion.execute(
        "select count(*) from public.etapas_ejecucion where costo_usd is null"
    ).fetchone()[0]
    print(f"[{'OK' if nulos == 0 else 'ERROR'}]   costo_usd nulos: {nulos}")
    ok = ok and nulos == 0

    fuera = conexion.execute(
        "select count(*) from public.etapas_ejecucion where etapa <> all(%s)",
        (sorted(ETAPAS_VALIDAS),)).fetchone()[0]
    print(f"[{'OK' if fuera == 0 else 'ERROR'}]   etapas fuera del check: {fuera}")
    ok = ok and fuera == 0

    reparto = conexion.execute(
        "select etapa, count(*) from public.etapas_ejecucion group by 1 order by 1"
    ).fetchall()
    print("[INFO] Reparto por etapa: "
          + ", ".join(f"{e}={n}" for e, n in reparto))
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="agroscout.db", type=Path)
    parser.add_argument("--email", default="admin@cite.gob.pe")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[ERROR] No existe {args.db}")
        return 1

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg
    from adaptadores.entorno import url_base_datos

    print("=== T2.2 - Migracion SQLite -> Supabase ===")
    sqlite_conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        with psycopg.connect(url_base_datos(), prepare_threshold=None,
                             connect_timeout=15) as conexion:
            usuario_id = resolver_usuario(conexion, args.email)
            migrar(conexion, sqlite_conn, usuario_id)
            conexion.commit()
            ok = verificar(conexion)
    finally:
        sqlite_conn.close()

    print("[OK]   DoD de migracion verificado" if ok
          else "[ERROR] DoD de migracion incompleto")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
