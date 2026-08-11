"""
Autenticación compartida por los routers.

Estaba dentro de api/main.py, que es también quien monta los routers. En
cuanto un router necesita saber quién es el usuario —el de promociones, porque
promover es una acción con autor— importarlo desde allí crea un ciclo. Así que
vive aquí y main.py lo reexporta: sus endpoints siguen usando los mismos
nombres.
"""

import os
from typing import Optional

from fastapi import Depends, Header, HTTPException

from adaptadores.autenticacion import Autenticacion

# T3.4 - Conmutador de backend de estado. La rama 'sqlite' se conserva a
# proposito: es el plan B de la demo (D5) y el modo en que corren los tests que
# no deben depender de la red. Tambien decide como se autentica.
APP_DB = os.getenv("APP_DB", "sqlite").strip().lower()
USA_SUPABASE = APP_DB == "supabase"

if APP_DB not in ("supabase", "sqlite"):
    raise RuntimeError(
        f"APP_DB={APP_DB!r} no es un valor valido. Usar 'supabase' o 'sqlite'.")

autenticacion = Autenticacion(
    secret_key=os.getenv("JWT_SECRET_KEY", "agroscout-secret-key-change-in-production"))

if USA_SUPABASE:
    from adaptadores.auth_supabase import (TokenInvalido, VerificadorSupabase,
                                           extraer_bearer)
    # SUPABASE_JWT_SECRET solo se usa si el proyecto firmara con HS256; el
    # nuestro firma con ES256 y se verifica por JWKS (T1.2).
    verificador_jwt = VerificadorSupabase(os.getenv("SUPABASE_JWT_SECRET"))
else:
    verificador_jwt = None


async def get_current_user(authorization: Optional[str] = Header(None)):
    """Verifica el JWT del header Authorization.

    Con APP_DB=supabase el token lo emite Supabase Auth y se verifica contra su
    JWKS. Con APP_DB=sqlite sigue el JWT propio de S1, que es el plan B.

    Todos los fallos —ausente, mal formado, firma invalida, expirado, emisor o
    audiencia que no cuadran— responden 401 sin detalle: precisar el motivo solo
    ayudaria a quien esta probando tokens.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Token no proporcionado")

    if not USA_SUPABASE:
        token = autenticacion.extraer_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=401, detail="Formato de token inválido")
        payload = autenticacion.verificar_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
        return payload

    token = extraer_bearer(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Formato de token inválido")
    try:
        return verificador_jwt.verificar(token)
    except TokenInvalido:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def usuario_actual_id(current_user: dict) -> str | None:
    """Identidad con la que se filtran ejecuciones e informes.

    Con Supabase es el `sub` del JWT, que es el uuid de auth.users al que
    apuntan las claves ajenas del esquema.
    """
    if USA_SUPABASE:
        return current_user.get("sub")
    return str(current_user["user_id"]) if current_user.get("user_id") else None


def rol_de(usuario_id: str | None) -> str:
    """Rol del usuario según public.perfiles. 'operador' si no consta.

    Fuera de Supabase no hay tabla de perfiles: la rama sqlite es la demo local
    de un solo usuario, y alli se trata como admin para no dejar el panel
    inutilizable en el plan B.
    """
    if not USA_SUPABASE:
        return "admin"

    if not usuario_id:
        return "operador"

    from adaptadores.db import pool

    with pool().connection() as conn, conn.cursor() as cur:
        fila = cur.execute(
            "select rol from public.perfiles where id = %s", (usuario_id,)).fetchone()

    return fila[0] if fila else "operador"


async def requiere_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Deja pasar solo a los administradores.

    Promover cambia lo que ve todo el mundo, asi que no basta con estar
    autenticado. El listado no usa esta dependencia: mirar la cola de revision
    puede hacerlo cualquiera del equipo.
    """
    if rol_de(usuario_actual_id(current_user)) != "admin":
        raise HTTPException(
            status_code=403,
            detail="Requiere rol de administrador")
    return current_user
