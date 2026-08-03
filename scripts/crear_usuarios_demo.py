#!/usr/bin/env python
"""
T4.3 - Cuentas demo en Supabase Auth (y en la rama sqlite del plan B).

Uso:
  # contrasenas elegidas por ti
  uv run python scripts/crear_usuarios_demo.py \
      --password-gratuita "..." --password-premium "..."

  # o generadas al azar y guardadas en .env.local (que esta en .gitignore)
  uv run python scripts/crear_usuarios_demo.py --generar

Las contrasenas se pasan por argumento y **no se escriben en el repositorio**.
Este script sustituye a `update_schema.py`, que las llevaba en claro dentro del
codigo (punto 14 de la auditoria). Ademas, la fila que ese script habia dejado
en `usuarios` guardaba la contrasena literal en la columna `password_hash`,
mientras el login la comprueba con bcrypt: el resultado es que **el login del
plan B fallaba para todo el mundo**. Aqui se guarda un hash bcrypt de verdad.

Es idempotente: si la cuenta ya existe le cambia la contrasena en vez de
duplicarla.

| Cuenta                      | Plan     |
|-----------------------------|----------|
| demo-gratuita@cite.gob.pe   | gratuito |
| demo-premium@cite.gob.pe    | premium  |
"""

import argparse
import re
import secrets
import sqlite3
import sys
from pathlib import Path

CUENTAS = (
    ("demo-gratuita@cite.gob.pe", "gratuito", "password_gratuita"),
    ("demo-premium@cite.gob.pe", "premium", "password_premium"),
)

# Fuera del control de versiones (.gitignore). Es el unico sitio del disco
# donde quedan las contrasenas demo.
ARCHIVO_LOCAL = Path(".env.local")
VARIABLES = {"password_gratuita": "PASSWORD_DEMO_GRATUITA",
             "password_premium": "PASSWORD_DEMO_PREMIUM"}


def _leer_local() -> dict[str, str]:
    if not ARCHIVO_LOCAL.is_file():
        return {}
    encontradas = {}
    for linea in ARCHIVO_LOCAL.read_text(encoding="utf-8").splitlines():
        coincide = re.match(r"^([A-Z_]+)=(.*)$", linea.strip())
        if coincide:
            encontradas[coincide.group(1)] = coincide.group(2)
    return encontradas


def _escribir_local(valores: dict[str, str]) -> None:
    """Reescribe solo las lineas de las dos variables, conservando el resto."""
    existentes = ARCHIVO_LOCAL.read_text(encoding="utf-8").splitlines() \
        if ARCHIVO_LOCAL.is_file() else []
    conservadas = [ln for ln in existentes
                   if not any(ln.startswith(f"{v}=") for v in valores)]
    cuerpo = conservadas + [f"{clave}={valor}" for clave, valor in valores.items()]
    ARCHIVO_LOCAL.write_text("\n".join(cuerpo).strip() + "\n", encoding="utf-8")


def _buscar(cliente, url: str, email: str) -> str | None:
    respuesta = cliente.get(f"{url}/auth/v1/admin/users", params={"page": 1, "per_page": 200})
    respuesta.raise_for_status()
    for usuario in respuesta.json().get("users", []):
        if usuario.get("email", "").lower() == email.lower():
            return usuario["id"]
    return None


def _crear_o_actualizar(cliente, url: str, email: str, password: str) -> tuple[str, str]:
    existente = _buscar(cliente, url, email)

    if existente:
        respuesta = cliente.put(f"{url}/auth/v1/admin/users/{existente}",
                                json={"password": password, "email_confirm": True})
        respuesta.raise_for_status()
        return existente, "contrasena actualizada"

    respuesta = cliente.post(f"{url}/auth/v1/admin/users",
                             json={"email": email, "password": password,
                                   "email_confirm": True})
    if respuesta.status_code >= 300:
        raise RuntimeError(f"No se pudo crear {email}: {respuesta.status_code} "
                           f"{respuesta.text[:200]}")
    return respuesta.json()["id"], "creada"


def _fijar_plan(conexion, uuid_usuario: str, email: str, plan: str) -> None:
    """El trigger de 003 crea el perfil con plan 'gratuito' por defecto; aqui se
    corrige el del premium. El upsert cubre el caso de una cuenta creada antes
    de que existiera el trigger."""
    conexion.execute("""
        insert into public.perfiles (id, email, plan)
        values (%s, %s, %s)
        on conflict (id) do update set plan = excluded.plan, email = excluded.email
    """, (uuid_usuario, email, plan))


def _sembrar_sqlite(db_path: str, credenciales: dict[str, tuple[str, str]]) -> None:
    """Rama sqlite (plan B de la demo). Guarda un hash bcrypt de verdad y el
    plan, para que el paywall se pueda ensayar sin red."""
    from adaptadores.autenticacion import Autenticacion
    from adaptadores.migracion_sqlite import asegurar_esquema

    autenticacion = Autenticacion()
    asegurar_esquema(db_path)

    with sqlite3.connect(db_path) as conexion:
        conexion.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                org_id INTEGER,
                creado_en TEXT DEFAULT (datetime('now'))
            )
        """)
        for email, (password, plan) in credenciales.items():
            hash_bcrypt = autenticacion.hash_password(password)
            fila = conexion.execute(
                "SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
            if fila:
                conexion.execute(
                    "UPDATE usuarios SET password_hash = ?, plan = ? WHERE id = ?",
                    (hash_bcrypt, plan, fila[0]))
            else:
                conexion.execute(
                    "INSERT INTO usuarios (email, password_hash, plan) VALUES (?, ?, ?)",
                    (email, hash_bcrypt, plan))
    print(f"[OK]   Rama sqlite sembrada con hashes bcrypt y plan ({db_path})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password-gratuita")
    parser.add_argument("--password-premium")
    parser.add_argument("--generar", action="store_true",
                        help=f"Genera contrasenas al azar y las deja en {ARCHIVO_LOCAL}")
    parser.add_argument("--sin-sqlite", action="store_true",
                        help="No sembrar la rama local del plan B")
    args = parser.parse_args()

    # Orden: lo que se pase por argumento manda; si no, lo que ya haya en
    # .env.local; si tampoco, se genera cuando se pide --generar.
    guardadas = _leer_local()
    for atributo, variable in VARIABLES.items():
        if not getattr(args, atributo):
            setattr(args, atributo, guardadas.get(variable) or
                    (secrets.token_urlsafe(16) if args.generar else None))

    faltan = [v for a, v in VARIABLES.items() if not getattr(args, a)]
    if faltan:
        print(f"[ERROR] Sin contrasena para: {', '.join(faltan)}.\n"
              f"        Pasala con --password-gratuita/--password-premium, "
              f"ponla en {ARCHIVO_LOCAL}, o usa --generar.")
        return 2

    from dotenv import load_dotenv
    load_dotenv()

    import httpx
    import psycopg

    from adaptadores.entorno import (cabeceras_servicio, ruta_db_sqlite,
                                     url_base_datos, url_supabase)

    url = url_supabase()
    credenciales: dict[str, tuple[str, str]] = {}

    print("=== T4.3 - Cuentas demo ===")
    with httpx.Client(headers={**cabeceras_servicio(),
                               "Content-Type": "application/json"},
                      timeout=30) as cliente, \
            psycopg.connect(url_base_datos(), prepare_threshold=None,
                            autocommit=True) as conexion:
        for email, plan, atributo in CUENTAS:
            password = getattr(args, atributo)
            uuid_usuario, que_paso = _crear_o_actualizar(cliente, url, email, password)
            _fijar_plan(conexion, uuid_usuario, email, plan)
            credenciales[email] = (password, plan)
            print(f"[OK]   {email:28} plan={plan:8} ({que_paso})")

        perfiles = conexion.execute(
            "select email, plan from public.perfiles order by email").fetchall()

    print(f"[INFO] perfiles: {len(perfiles)} fila(s)")
    for email, plan in perfiles:
        print(f"          {email:28} {plan}")

    if not args.sin_sqlite:
        _sembrar_sqlite(ruta_db_sqlite(), credenciales)

    _escribir_local({VARIABLES[a]: getattr(args, a) for a in VARIABLES})
    print(f"[OK]   Contrasenas guardadas en {ARCHIVO_LOCAL} (esta en .gitignore).")
    print("[OK]   No estan en el repositorio ni en ningun archivo versionado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
