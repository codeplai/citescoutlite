"""
T3.1 - Pool de conexiones a Postgres (Supabase).

El pool no es un lujo: abrir una conexion TLS contra Sao Paulo cuesta ~200 ms
de handshake, y un run toca la base entre 6 y 8 veces. Sin pool se pagaria ese
handshake en cada una.

prepare_threshold=None es obligatorio si DATABASE_URL apunta al pooler de
transacciones: pgbouncer en modo transaction no conserva las sentencias
preparadas entre checkouts y psycopg3 las usa por defecto, lo que produce
errores intermitentes 'prepared statement "_pg3_0" already exists'. Contra la
conexion directa es inofensivo, asi que se deja puesto siempre.
"""

import atexit
import threading

from psycopg_pool import ConnectionPool

from adaptadores.entorno import url_base_datos

_pool: ConnectionPool | None = None
_cerrojo = threading.Lock()


def pool() -> ConnectionPool:
    """Pool unico del proceso, creado la primera vez que se pide.

    Perezoso a proposito: importar este modulo no debe abrir conexiones, para
    que los tests que corren con APP_DB=sqlite no toquen la red.
    """
    global _pool
    if _pool is None:
        with _cerrojo:
            if _pool is None:
                creado = ConnectionPool(
                    url_base_datos(),
                    min_size=1,
                    max_size=5,
                    # autocommit=True ahorra un viaje por bloque. Sin el,
                    # psycopg abre transaccion implicita en cada
                    # `with pool().connection()` y el COMMIT del cierre es un
                    # viaje mas: a 107 ms de RTT, eso duplicaba el coste de la
                    # auditoria y hacia fallar el gate de T3.4 (1,35 s medidos).
                    # Donde hace falta atomicidad se abre transaccion explicita.
                    kwargs={"prepare_threshold": None, "autocommit": True},
                    open=False,
                )
                creado.open(wait=True, timeout=30)
                _pool = creado
                atexit.register(cerrar_pool)
    return _pool


def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
