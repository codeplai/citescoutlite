"""
Lectura del entorno de Supabase.

Un solo sitio resuelve el nombre de cada variable. En particular la clave de
servicio, que Supabase renombro a mitad de camino: los proyectos anteriores la
llaman SUPABASE_SERVICE_ROLE_KEY y los nuevos entregan un sb_secret_... que la
gente pega en SUPABASE_SECRET_KEY. Las dos dan el mismo permiso y saltan RLS.
"""

import os

ALIAS_CLAVE_SERVICIO = ("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY")


class FaltaVariable(RuntimeError):
    """El entorno no trae una variable obligatoria. El mensaje nunca lleva valores."""


def _exigir(nombre: str) -> str:
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise FaltaVariable(f"Falta o esta vacia la variable {nombre} (ver .env.example)")
    return valor


def url_supabase() -> str:
    """URL del proyecto, sin barra final."""
    return _exigir("SUPABASE_URL").rstrip("/")


def url_base_datos() -> str:
    return _exigir("DATABASE_URL")


def clave_publica() -> str:
    """Clave anon/publishable. Puede viajar al navegador."""
    return _exigir("SUPABASE_ANON_KEY")


def nombre_clave_de_servicio() -> str | None:
    """Cual de los dos alias trae valor, o None si ninguno."""
    return next((n for n in ALIAS_CLAVE_SERVICIO if os.environ.get(n, "").strip()), None)


def clave_de_servicio() -> str:
    """Clave secreta. SOLO backend: salta RLS."""
    nombre = nombre_clave_de_servicio()
    if nombre is None:
        raise FaltaVariable(
            "Falta la clave de servicio: rellenar " + " o ".join(ALIAS_CLAVE_SERVICIO))
    return os.environ[nombre].strip()


def cabeceras_servicio() -> dict[str, str]:
    """Cabeceras para la API REST de Supabase (Auth y Storage) como servicio."""
    clave = clave_de_servicio()
    return {"apikey": clave, "Authorization": f"Bearer {clave}"}


def bucket_informes() -> str:
    return os.environ.get("SUPABASE_BUCKET_INFORMES", "informes").strip()


def ruta_db_sqlite() -> str:
    """Archivo SQLite de la rama local.

    Configurable porque agroscout.db esta versionado: sin esto, cada pasada de
    la suite anade filas al binario del repositorio y lo deja modificado en
    git. Los tests apuntan a un archivo temporal.
    """
    return os.environ.get("AGROSCOUT_DB_PATH", "agroscout.db").strip()
