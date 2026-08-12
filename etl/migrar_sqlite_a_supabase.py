#!/usr/bin/env python
"""
T2.2 - Migra el historico de agroscout.db (SQLite) a Supabase.

Uso:
  uv run python etl/migrar_sqlite_a_supabase.py
  uv run python etl/migrar_sqlite_a_supabase.py --db agroscout.db --email admin@cite.gob.pe

Es idempotente: volver a correrlo no duplica filas ni deja atras un cambio de
mapeo (los conflictos actualizan, no se ignoran).

## A quien se le cuelga cada run (revisado en S8.0)

El historico de SQLite tiene tres origenes distintos en `usuario_id`, y hasta
S8 se colapsaban los tres en la cuenta tecnica. Eso dejaba el desglose por
usuario del cost-meter (8.2) reducido a una sola barra, y la cuota de plan sin
nada contra lo que compararse. Ahora se reparten:

| `usuario_id` en SQLite | Va a | Por que |
|---|---|---|
| `NULL` | cuenta tecnica (`--email`) | Runs anteriores a que existiera el campo |
| un uuid | `--email-premium` | Los hizo un usuario real de Supabase, borrado desde entonces: el uuid ya no resuelve contra `auth.users` y la clave ajena lo rechazaria |
| `plan-b` | `--email-gratuita` | Marca de la rama sqlite, la demo local sin red |

No es una atribucion inventada: los tres grupos existen en el origen y el
mapeo esta aqui por escrito. Lo que no se puede es conservar el uuid original,
porque `ejecuciones.usuario_id` tiene clave ajena a `auth.users` y esa cuenta
ya no existe.

La cuenta tecnica se crea si no existe, con una contrasena aleatoria que NO se
imprime ni se guarda: nada inicia sesion como admin, y si algun dia hace falta
se resetea desde el dashboard.

**Nota corregida en S8.0:** este docstring afirmaba que a la cuenta tecnica no
se le crea fila en 'perfiles', y que por eso la tabla terminaba con las 2
cuentas demo y ni una mas (el DoD de TIER 4). Eso era cierto cuando se escribio,
porque el trigger de la migracion 003 todavia no estaba aplicado. Ahora si lo
esta, dispara con cada alta en auth.users, y 'perfiles' queda con **3 filas**.

No se borra la de la cuenta tecnica: pelearse con el trigger para sostener una
cifra es peor que ajustar la cifra. En el panel aparecera como un usuario mas,
con plan 'gratuito' por defecto, y conviene saber que ese gasto es historico y
no de un cliente.

## Columnas que se copian (revisado en S8.0)

La version de T2.2 dejaba fuera `motivo_parcial`, `modelo`, `snapshot_version`
y `cache_hit` porque el archivo SQLite de entonces no las tenia. Hoy si las
tiene, y son justo las que alimentan el desglose por etapa y modelo de 8.2 y el
cache hit rate de 8.8. Se copian.

El volumen sigue siendo pequeno. El valor de este paso no es el dato: es probar
el camino de escritura con datos reales antes de que el panel dependa de el.
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
#
# Las filas mas recientes del archivo ya llegan con '2a' y '2b' escritos: son
# posteriores al arreglo de T2.3. El mapeo solo toca las viejas.
MAPEO_ETAPA = {"2": "2a"}
ETAPAS_VALIDAS = {"1", "2a", "2b", "3", "4", "5", "6"}

# Marca que la rama sqlite escribe en usuario_id cuando no hay sesion Supabase.
MARCA_PLAN_B = "plan-b"


def _utc(texto: str | None) -> datetime | None:
    """SQLite guardo datetime('now'), que es UTC sin zona. Se la ponemos."""
    if not texto:
        return None
    return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def resolver_usuario(conexion, email: str, crear: bool = True) -> str:
    """Devuelve el uuid de una cuenta, creandola si no existe y se permite.

    `crear=False` para las cuentas demo: si no estan, lo que hay que hacer es
    correr scripts/crear_usuarios_demo.py, no fabricar aqui una cuenta sin
    contrasena conocida y sin perfil que luego nadie sabria de donde salio.
    """
    fila = conexion.execute(
        "select id from auth.users where email = %s", (email,)).fetchone()
    if fila:
        print(f"[OK]   {email} (ya existia)")
        return str(fila[0])

    if not crear:
        raise RuntimeError(
            f"No existe la cuenta {email}. Creala primero con:\n"
            f"    uv run python scripts/crear_usuarios_demo.py")

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
    print(f"[OK]   {email} (creado; contrasena aleatoria no guardada, "
          "resetear desde el dashboard si hiciera falta)")
    return uuid_usuario


def elegir_dueno(origen: str | None, tecnica: str, premium: str,
                 gratuita: str) -> str:
    """A quien se le cuelga un run del historico. Ver la tabla del docstring.

    Un uuid de Supabase que ya no resuelve contra auth.users no se puede
    conservar: `ejecuciones.usuario_id` tiene clave ajena y lo rechazaria.
    """
    if not origen:
        return tecnica
    if origen == MARCA_PLAN_B:
        return gratuita
    return premium


def migrar(conexion, sqlite_conn, tecnica: str, premium: str,
           gratuita: str) -> None:
    ejecuciones = sqlite_conn.execute(
        "select id, insumo_texto, snapshot_version, estado, creado_en, "
        "usuario_id, motivo_parcial from ejecuciones").fetchall()

    reparto: dict[str, int] = {}
    filas_ej = []
    for i, texto, snapshot, estado, creado, origen, motivo in ejecuciones:
        destino = elegir_dueno(origen, tecnica, premium, gratuita)
        reparto[destino] = reparto.get(destino, 0) + 1
        filas_ej.append((i, destino, texto, snapshot, estado,
                         motivo, _utc(creado)))

    # do update y no do nothing: si el mapeo de duenos cambia, una segunda
    # pasada tiene que converger. Con 'do nothing' se quedaria el reparto viejo
    # sin avisar.
    conexion.cursor().executemany("""
        insert into public.ejecuciones
            (id, usuario_id, insumo_texto, snapshot_version, estado,
             motivo_parcial, creado_en)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (id) do update set
            usuario_id     = excluded.usuario_id,
            estado         = excluded.estado,
            motivo_parcial = excluded.motivo_parcial
    """, filas_ej)
    print(f"[OK]   ejecuciones: {len(filas_ej)} filas")
    for uuid_destino, n in sorted(reparto.items(), key=lambda kv: -kv[1]):
        print(f"          {n:3} runs -> {uuid_destino}")

    # etapas_ejecucion no tiene clave natural (el id es bigserial), asi que la
    # idempotencia se consigue borrando antes las etapas de estos runs.
    ids = [fila[0] for fila in ejecuciones]
    conexion.execute(
        "delete from public.etapas_ejecucion where ejecucion_id = any(%s::uuid[])",
        (ids,))

    etapas = sqlite_conn.execute(
        "select ejecucion_id, etapa, entrada_json, salida_json, duracion_ms, "
        "costo_usd, tokens, tokens_entrada, tokens_salida, modelo, "
        "snapshot_version, cache_hit from etapas_ejecucion"
    ).fetchall()

    filas = []
    convertidas = 0
    for (ej, etapa, entrada, salida, duracion, costo, tok, tok_in, tok_out,
         modelo, snapshot_etapa, cache_hit) in etapas:
        # SQLite es de tipado dinamico y la columna, aun declarada TEXT, guarda
        # enteros: esas filas las escribio una version del adaptador anterior
        # al str(etapa) de auditoria_sqlite.py (ver T2.3).
        etapa = str(etapa).strip()
        if etapa in MAPEO_ETAPA:
            etapa = MAPEO_ETAPA[etapa]
            convertidas += 1
        if etapa not in ETAPAS_VALIDAS:
            raise ValueError(f"Etapa {etapa!r} fuera del check del esquema")
        filas.append((ej, etapa, entrada, salida, duracion, costo or 0,
                      tok or 0, tok_in or 0, tok_out or 0,
                      # SQLite guarda el booleano como 0/1; Postgres lo quiere
                      # boolean, y null cuenta como 'no fue cache'.
                      modelo, snapshot_etapa, bool(cache_hit)))

    conexion.cursor().executemany("""
        insert into public.etapas_ejecucion
            (ejecucion_id, etapa, entrada_json, salida_json, duracion_ms,
             costo_usd, tokens, tokens_entrada, tokens_salida,
             modelo, snapshot_version, cache_hit)
        values (%s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)
    """, filas)
    con_modelo = sum(1 for f in filas if f[9])
    en_cache = sum(1 for f in filas if f[11])
    print(f"[OK]   etapas_ejecucion: {len(filas)} filas "
          f"({convertidas} con etapa '2' migradas a '2a')")
    print(f"          {con_modelo} con modelo, {en_cache} servidas de cache")

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


def contar_origen(sqlite_conn) -> dict[str, int]:
    """Lo que hay en el archivo, no una cifra escrita a mano.

    La version de T2.2 llevaba {54, 94, 47} incrustados en el codigo. El
    archivo lleva creciendo desde entonces, asi que la verificacion daba ERROR
    con una migracion perfectamente correcta.
    """
    return {tabla: sqlite_conn.execute(
                f"select count(*) from {tabla}").fetchone()[0]
            for tabla in ("ejecuciones", "etapas_ejecucion", "cache_llm")}


def verificar(conexion, esperado: dict[str, int]) -> bool:
    ok = True
    for tabla, cuantas in esperado.items():
        real = conexion.execute(f"select count(*) from public.{tabla}").fetchone()[0]
        if real == cuantas:
            print(f"[OK]   {tabla}: {real} filas")
        else:
            print(f"[ERROR] {tabla}: {real} filas, se esperaban {cuantas}")
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

    # Lo que sigue no es del DoD de T2.2: es lo que el panel de S8 va a leer.
    # Si alguna de estas tres sale a cero, la pantalla correspondiente se
    # entrega vacia, y mejor enterarse aqui que en la demo.
    usuarios = conexion.execute(
        "select count(distinct usuario_id) from public.ejecuciones").fetchone()[0]
    print(f"[{'OK' if usuarios > 1 else 'AVISO'}]   usuarios distintos en el "
          f"historico: {usuarios} (8.2 desglosa por usuario)")

    con_modelo = conexion.execute(
        "select count(*) from public.etapas_ejecucion where modelo is not null"
    ).fetchone()[0]
    print(f"[{'OK' if con_modelo else 'AVISO'}]   etapas con modelo: "
          f"{con_modelo} (8.2 desglosa por modelo)")

    cache = conexion.execute(
        "select count(*) filter (where cache_hit), count(*) "
        "from public.etapas_ejecucion").fetchone()
    pct = round(100 * cache[0] / cache[1], 1) if cache[1] else 0
    print(f"[{'OK' if cache[0] else 'AVISO'}]   cache hit rate: {pct} % "
          f"({cache[0]}/{cache[1]}) (SLO de 8.8)")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="agroscout.db", type=Path)
    parser.add_argument("--email", default="admin@cite.gob.pe",
                        help="Cuenta tecnica para los runs sin dueno")
    parser.add_argument("--email-premium", default="demo-premium@cite.gob.pe")
    parser.add_argument("--email-gratuita", default="demo-gratuita@cite.gob.pe")
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"[ERROR] No existe {args.db}")
        return 1

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg
    from adaptadores.entorno import url_base_datos

    print("=== Migracion SQLite -> Supabase (T2.2, revisada en S8.0) ===")
    sqlite_conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        esperado = contar_origen(sqlite_conn)
        print("[INFO] En el archivo: "
              + ", ".join(f"{t}={n}" for t, n in esperado.items()))

        with psycopg.connect(url_base_datos(), prepare_threshold=None,
                             connect_timeout=15) as conexion:
            tecnica = resolver_usuario(conexion, args.email)
            premium = resolver_usuario(conexion, args.email_premium, crear=False)
            gratuita = resolver_usuario(conexion, args.email_gratuita, crear=False)

            migrar(conexion, sqlite_conn, tecnica, premium, gratuita)
            conexion.commit()
            ok = verificar(conexion, esperado)
    finally:
        sqlite_conn.close()

    print("[OK]   DoD de migracion verificado" if ok
          else "[ERROR] DoD de migracion incompleto")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
