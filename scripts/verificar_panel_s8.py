#!/usr/bin/env python
"""
S8.0.7 - Comprueba que el panel tiene sobre que apoyarse.

Hasta S8 la aplicacion configurada con APP_DB=supabase **no permitia iniciar
sesion**: auth.users estaba a 0. Esto verifica de punta a punta que eso quedo
resuelto, y de paso que el rol de admin llega hasta el endpoint.

No monta un servidor: usa el TestClient de FastAPI contra api.main, que es la
misma aplicacion que sirve uvicorn.

  uv run python scripts/verificar_panel_s8.py
"""

import os
import sys


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()

    if os.getenv("APP_DB", "").strip().lower() != "supabase":
        print("[ERROR] APP_DB no es 'supabase'; este panel corre contra Postgres")
        return 1

    from fastapi.testclient import TestClient
    from api.main import app

    cuentas = {
        "demo-gratuita@cite.gob.pe": os.getenv("PASSWORD_DEMO_GRATUITA"),
        "demo-premium@cite.gob.pe": os.getenv("PASSWORD_DEMO_PREMIUM"),
    }
    if not all(cuentas.values()):
        # crear_usuarios_demo.py las deja en .env.local, que load_dotenv() no
        # lee por defecto.
        load_dotenv(".env.local")
        cuentas = {e: os.getenv(v) for e, v in
                   (("demo-gratuita@cite.gob.pe", "PASSWORD_DEMO_GRATUITA"),
                    ("demo-premium@cite.gob.pe", "PASSWORD_DEMO_PREMIUM"))}

    ok = True
    print("=== S8.0 - Verificacion del panel ===")

    with TestClient(app) as cliente:
        tokens = {}
        for email, password in cuentas.items():
            if not password:
                print(f"[ERROR] Sin contrasena para {email} (mira .env.local)")
                ok = False
                continue
            r = cliente.post("/token", json={"email": email, "password": password})
            if r.status_code == 200:
                tokens[email] = r.json()["access_token"]
                print(f"[OK]   login {email}")
            else:
                print(f"[ERROR] login {email}: {r.status_code} {r.text[:120]}")
                ok = False

        for email, token in tokens.items():
            cab = {"Authorization": f"Bearer {token}"}

            r = cliente.get("/uso", headers=cab)
            if r.status_code == 200:
                d = r.json()
                print(f"[OK]   /uso {email:28} plan={d['plan']:8} "
                      f"runs={d['runs']} gasto=${d['costo_mes_usd']}")
            else:
                print(f"[ERROR] /uso {email}: {r.status_code} {r.text[:120]}")
                ok = False

            # La cola de promocion la ve cualquiera; promover, solo el admin.
            # Se comprueba con un uuid que no existe: lo que se mide es si pasa
            # el guard de rol (403 o no), no si promueve.
            r = cliente.post(
                "/api/promociones/00000000-0000-0000-0000-000000000000/promover",
                headers=cab)
            es_admin = r.status_code != 403
            esperado = email.startswith("demo-premium")
            marca = "OK" if es_admin == esperado else "ERROR"
            print(f"[{marca}]   rol de {email:28} "
                  f"{'admin' if es_admin else 'operador'} "
                  f"(se esperaba {'admin' if esperado else 'operador'})")
            ok = ok and es_admin == esperado

    print("[OK]   Fase 0 verificada: hay login, datos y admin" if ok
          else "[ERROR] Fase 0 incompleta")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
