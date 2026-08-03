"""
T4.1 - Verificacion de los JWT que emite Supabase Auth.

MODO DE FIRMA DE ESTE PROYECTO (decidido en T1.2, 2026-08-02):
**asimetrico ES256**. `GET /auth/v1/.well-known/jwks.json` devuelve una clave EC
P-256, asi que la verificacion va por JWKS y `SUPABASE_JWT_SECRET` no se usa.
La ventaja practica es que la clave se puede rotar en el dashboard sin tocar ni
reiniciar el backend: al llegar un `kid` desconocido se vuelve a leer el JWKS.

Se conserva el camino HS256 porque Supabase cambio de esquema a mitad de vida y
un proyecto anterior puede seguir firmando con el secreto compartido. Cual de
los dos se usa no se configura: se deduce del propio endpoint.

Nada aqui confia en el cliente. Se validan firma, expiracion, emisor y
audiencia; el `sub` que sale es el uuid de auth.users con el que se filtran
ejecuciones e informes.
"""

import threading
import time

import httpx
from jose import jwt
from jose.exceptions import JWTError

from adaptadores.entorno import url_supabase

AUDIENCIA = "authenticated"
# Margen para desfases de reloj entre esta maquina y Supabase.
TOLERANCIA_SEGUNDOS = 10
# Cuanto se conserva el JWKS antes de releerlo aunque no falle nada.
VIDA_JWKS_SEGUNDOS = 3600


class TokenInvalido(Exception):
    """El token no se pudo verificar. El motivo va en el mensaje, para el log;
    al cliente se le responde 401 sin detalle."""


class VerificadorSupabase:
    def __init__(self, secreto_hs256: str | None = None):
        self._url = url_supabase()
        self._emisor = f"{self._url}/auth/v1"
        self._secreto = (secreto_hs256 or "").strip() or None
        self._claves: dict[str, dict] = {}
        self._leido_en = 0.0
        self._cerrojo = threading.Lock()

    # -- JWKS ---------------------------------------------------------------

    def _leer_jwks(self) -> dict[str, dict]:
        respuesta = httpx.get(f"{self._emisor}/.well-known/jwks.json", timeout=10)
        respuesta.raise_for_status()
        claves = respuesta.json().get("keys", [])
        return {clave["kid"]: clave for clave in claves if clave.get("kid")}

    def _clave_para(self, kid: str | None) -> dict | None:
        """Devuelve la clave publica del `kid`, releyendo el JWKS si hace falta.

        La relectura ante un kid desconocido es lo que permite rotar la clave
        sin reiniciar; el candado evita que veinte peticiones simultaneas
        disparen veinte lecturas.
        """
        ahora = time.time()
        with self._cerrojo:
            caducado = ahora - self._leido_en > VIDA_JWKS_SEGUNDOS
            if not self._claves or caducado or (kid and kid not in self._claves):
                try:
                    self._claves = self._leer_jwks()
                    self._leido_en = ahora
                except httpx.HTTPError as e:
                    if not self._claves:
                        raise TokenInvalido(f"No se pudo leer el JWKS: {e}") from e
            return self._claves.get(kid) if kid else None

    # -- Verificacion -------------------------------------------------------

    def verificar(self, token: str) -> dict:
        """Devuelve el payload con `sub` y `email`, o levanta TokenInvalido."""
        try:
            cabecera = jwt.get_unverified_header(token)
        except JWTError as e:
            raise TokenInvalido(f"Cabecera ilegible: {e}") from e

        algoritmo = cabecera.get("alg", "")

        if algoritmo.startswith("HS"):
            if not self._secreto:
                raise TokenInvalido(
                    "Token firmado con HS256 pero no hay SUPABASE_JWT_SECRET "
                    "configurado. Este proyecto usa ES256/JWKS (ver T1.2).")
            clave = self._secreto
        else:
            clave = self._clave_para(cabecera.get("kid"))
            if clave is None:
                raise TokenInvalido(f"kid {cabecera.get('kid')!r} no esta en el JWKS")

        try:
            return jwt.decode(
                token,
                clave,
                algorithms=[algoritmo],
                audience=AUDIENCIA,
                issuer=self._emisor,
                options={"leeway": TOLERANCIA_SEGUNDOS},
            )
        except JWTError as e:
            # Firma mala, expirado, emisor o audiencia que no cuadran: todo
            # acaba aqui y todo responde 401. Distinguirlos hacia fuera solo
            # ayudaria a quien esta probando tokens.
            raise TokenInvalido(str(e)) from e


def extraer_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split()
    if len(partes) != 2 or partes[0].lower() != "bearer":
        return None
    return partes[1]
