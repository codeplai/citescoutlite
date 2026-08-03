"""
T3.2 - Cache de respuestas LLM sobre Postgres (Supabase).

Diferencia de fondo con el adaptador SQLite: aqui `etapa`, `modelo` y
`snapshot_version` se llenan de verdad. En S2 quedaban siempre en NULL (punto 12
de la auditoria), y sin ellos **P02 no se puede probar**: un cache hit sin
modelo ni snapshot registrados demuestra que dos hashes coincidieron, no que la
clave incluya el modelo y el snapshot como exige la prueba.

Las escrituras se acumulan y se vuelcan de una vez (ver la nota de latencia en
auditoria_postgres). Las lecturas no se pueden acumular: el ejecutor necesita
la respuesta antes de decidir si llama al modelo.
"""

import json

from adaptadores.db import pool
from puertos.cache_llm import CacheLLM


class CachePostgres(CacheLLM):
    def __init__(self):
        self._pendientes: dict[str, tuple] = {}

    def obtener(self, clave: str) -> dict | None:
        # Un valor recien guardado todavia puede estar en el buffer.
        if clave in self._pendientes:
            return json.loads(self._pendientes[clave][3])

        with pool().connection() as conexion:
            fila = conexion.execute(
                "select respuesta_json from public.cache_llm where clave_hash = %s",
                (clave,)).fetchone()
        return fila[0] if fila else None

    def guardar(self, clave: str, valor: dict, etapa: str | None = None,
                modelo: str | None = None,
                snapshot_version: str | None = None) -> None:
        self._pendientes[clave] = (
            clave,
            str(etapa) if etapa is not None else None,
            modelo,
            json.dumps(valor, ensure_ascii=False),
            snapshot_version,
        )

    def vaciar_pendientes(self) -> None:
        if not self._pendientes:
            return
        filas = list(self._pendientes.values())
        self._pendientes.clear()

        with pool().connection() as conexion:
            with conexion.cursor() as cursor:
                cursor.executemany("""
                    insert into public.cache_llm
                        (clave_hash, etapa, modelo, respuesta_json, snapshot_version)
                    values (%s, %s, %s, %s::jsonb, %s)
                    on conflict (clave_hash) do update
                       set etapa            = excluded.etapa,
                           modelo           = excluded.modelo,
                           snapshot_version = excluded.snapshot_version
                """, filas)
