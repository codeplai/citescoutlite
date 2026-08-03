"""
T3.2 - Auditoria sobre Postgres (Supabase).

Traduccion del adaptador SQLite con tres cambios de fondo:

1. El run tiene dueno: `usuario_id` viaja en la Ejecucion.
2. `cerrar()` fija el estado final. Hasta S2 se escribia 'ok' al empezar y no
   se corregia nunca.
3. Las etapas NO se escriben una a una. Se acumulan en memoria y se vuelcan en
   un solo viaje al cerrar el run.

El punto 3 merece explicacion, porque es una decision de latencia y no de
estilo. El RTT medido a Supabase en T1.1 es de 107 ms (p50). Escribiendo cada
etapa al vuelo, un run de 3 etapas gasta 1 + 3 + 1 = 5 viajes solo en auditoria,
~535 ms, y con las 5 etapas de T5 serian ~750 ms: el gate de T3.4 (sobrecoste
< 1 s por run) se agota antes de contar el cache. Acumulando, la auditoria
entera cuesta 2 viajes.

Lo que se paga a cambio: si el proceso muere a mitad del run, las etapas de ese
run se pierden. La fila de `ejecuciones` no, porque esa si se escribe al
empezar; queda en 'ok' y sin etapas, que es un estado reconocible. Por eso
evaluar_insumo llama a cerrar() dentro de un finally.
"""

import json
import uuid

from adaptadores.db import pool
from adaptadores.ejecucion import EjecucionConcreta
from puertos.auditoria import Auditoria, Ejecucion

_INSERT_ETAPA = """
    insert into public.etapas_ejecucion
        (ejecucion_id, etapa, modelo, entrada_json, salida_json, duracion_ms,
         costo_usd, tokens, tokens_entrada, tokens_salida, snapshot_version,
         cache_hit)
    values (%s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
"""


class AuditoriaPostgres(Auditoria):
    def __init__(self):
        # Buffer por ejecucion. La clave es el id del run, asi que dos runs
        # concurrentes no se pisan las etapas.
        self._pendientes: dict[str, list[tuple]] = {}

    def iniciar(self, texto: str, snapshot_version: str,
                usuario_id: str | None = None) -> Ejecucion:
        if not usuario_id:
            raise ValueError(
                "AuditoriaPostgres necesita usuario_id: ejecuciones.usuario_id "
                "es not null y apunta a auth.users")

        id_ej = str(uuid.uuid4())
        with pool().connection() as conexion:
            conexion.execute("""
                insert into public.ejecuciones
                    (id, usuario_id, insumo_texto, snapshot_version, estado)
                values (%s, %s, %s, %s, 'ok')
            """, (id_ej, usuario_id, texto, snapshot_version))

        self._pendientes[id_ej] = []
        return EjecucionConcreta(id_ej, snapshot_version, texto, usuario_id)

    def registrar_etapa(self, ejecucion: Ejecucion, etapa: str, entrada: dict,
                        salida: dict, duracion_ms: int, costo_usd: float,
                        tokens: int = 0, tokens_entrada: int = 0,
                        tokens_salida: int = 0, modelo: str | None = None,
                        cache_hit: bool = False) -> None:
        self._pendientes.setdefault(ejecucion.id, []).append((
            ejecucion.id, str(etapa), modelo,
            json.dumps(entrada, ensure_ascii=False),
            json.dumps(salida, ensure_ascii=False),
            duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida,
            ejecucion.snapshot_version, cache_hit,
        ))

    def cerrar(self, ejecucion: Ejecucion, estado: str,
               motivo_parcial: str | None = None) -> None:
        filas = self._pendientes.pop(ejecucion.id, [])
        with pool().connection() as conexion:
            # Transaccion explicita (el pool va en autocommit): las etapas y el
            # estado final entran juntos o no entra ninguno. Un run cerrado
            # como 'ok' sin sus etapas seria peor que un run sin cerrar.
            with conexion.transaction(), conexion.cursor() as cursor:
                # El pipeline manda las dos sentencias en un solo viaje en vez
                # de esperar la respuesta de la primera para enviar la segunda.
                with conexion.pipeline():
                    if filas:
                        cursor.executemany(_INSERT_ETAPA, filas)
                    cursor.execute("""
                        update public.ejecuciones
                           set estado = %s, motivo_parcial = %s
                         where id = %s
                    """, (estado, motivo_parcial, ejecucion.id))

    def descartar(self, ejecucion: Ejecucion) -> None:
        """Suelta el buffer sin escribir. Solo para tests."""
        self._pendientes.pop(ejecucion.id, None)
