#!/usr/bin/env python
"""
S8.0.3 - Nombra administrador a una cuenta.

`perfiles.rol` llego en la migracion 008 con default 'operador', asi que tras
crear las cuentas demo **nadie es admin** y los endpoints protegidos por
`requiere_admin` (promover, rechazar, y el kill-switch de 8.5) responden 403 a
todo el mundo. Esto lo arregla sin abrir una consola SQL.

Por defecto demo-premium@cite.gob.pe: es la cuenta con la que se ensena el
panel, y crear una tercera cuenta solo para administrar dejaria `perfiles` con
3 filas, rompiendo el DoD de TIER 4.

Uso:
  uv run python scripts/nombrar_admin.py
  uv run python scripts/nombrar_admin.py --email otro@cite.gob.pe
  uv run python scripts/nombrar_admin.py --email demo-gratuita@cite.gob.pe --quitar
"""

import argparse
import sys

POR_DEFECTO = "demo-premium@cite.gob.pe"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default=POR_DEFECTO)
    parser.add_argument("--quitar", action="store_true",
                        help="Devuelve la cuenta a rol 'operador'")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg
    from adaptadores.entorno import url_base_datos

    rol = "operador" if args.quitar else "admin"

    with psycopg.connect(url_base_datos(), prepare_threshold=None,
                         autocommit=True, connect_timeout=15) as conexion:
        fila = conexion.execute(
            "update public.perfiles set rol = %s where email = %s returning id, plan",
            (rol, args.email)).fetchone()

        if fila is None:
            print(f"[ERROR] No hay perfil para {args.email}.\n"
                  f"        Crea las cuentas primero: "
                  f"uv run python scripts/crear_usuarios_demo.py")
            return 1

        print(f"[OK]   {args.email} -> rol={rol} (plan={fila[1]})")

        print("[INFO] perfiles:")
        for email, plan, rol_actual in conexion.execute(
                "select email, plan, rol from public.perfiles order by email"):
            marca = " <- admin" if rol_actual == "admin" else ""
            print(f"          {email:28} plan={plan:8} rol={rol_actual}{marca}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
