"""
T3.2 - Auditoria sobre Postgres (Supabase).

Traduccion del adaptador SQLite con tres cambios de fondo:

1. El run tiene dueno: `usuario_id` viaja en la Ejecucion.
2. `cerrar()` fija el estado final. Hasta S2 se escribia 'ok' al empezar y no
   se corregia nunca.
3. **Nada se escribe hasta cerrar el run.** Ni la ejecucion ni las etapas: se
   acumulan en memoria y salen en un unico viaje.

El punto 3 es una decision de latencia, no de estilo. El RTT medido a Supabase
en T1.1 es de ~112 ms, y el gate de T3.4 es sobrecoste < 1 s por run. Medido
sobre un run de 3 etapas:

    escribiendo la ejecucion al empezar y cada etapa al vuelo ... 5 viajes
    acumulando solo las etapas ................................. 3 viajes (475 ms)
    todo el run en una sentencia al cerrar ..................... 1 viaje  (136 ms)

La ultima es la de este adaptador: 372 ms recuperados de un presupuesto de
1.000, que es lo que dejo el sobrecoste total en 642 ms con margen para las
dos etapas que anade T5.

Lo que se paga a cambio: si el proceso muere a mitad del run, no queda rastro
del intento. Por eso evaluar_insumo llama a cerrar() dentro de un finally, que
cubre tambien el camino de excepcion y deja el run escrito como 'error'. El
unico caso que se pierde es la muerte subita del proceso.

Consecuencia de orden que hay que respetar: `informes.ejecucion_id` tiene FK a
`ejecuciones`, asi que el informe se emite **despues** de cerrar, nunca antes.
"""

import json
import uuid

from adaptadores.db import pool
from adaptadores.ejecucion import EjecucionConcreta
from puertos.auditoria import Auditoria, Ejecucion

# El run entero en UNA sentencia: la cabecera va en un CTE que modifica datos
# y las etapas se expanden desde arrays con unnest.
#
# Por que asi y no `with conexion.transaction()` envolviendo dos sentencias:
# transaction() fuerza un sync que rompe el pipeline, de modo que BEGIN y
# COMMIT se cobran cada uno su viaje. Medido contra Supabase (RTT 112 ms):
#
#   pipeline > transaction > insert + executemany ..... 450 ms  (4 viajes)
#   pipeline > insert + executemany, sin transaction .. 113 ms  (1 viaje, NO atomico)
#   esta sentencia unica ............................. 114 ms  (1 viaje, atomica)
#
# Una sola sentencia es atomica por definicion, asi que no hace falta la
# transaccion explicita para que las etapas y su cabecera entren juntas. Un CTE
# que modifica datos se ejecuta siempre y una sola vez, lo lea o no la consulta
# principal, y la comprobacion de la clave ajena ocurre al final de la
# sentencia, cuando la cabecera ya existe.
_ESCRIBIR_RUN = """
    with cabecera as (
        insert into public.ejecuciones
            (id, usuario_id, insumo_texto, snapshot_version, estado, motivo_parcial)
        values (%s, %s, %s, %s, %s, %s)
    )
    insert into public.etapas_ejecucion
        (ejecucion_id, etapa, modelo, entrada_json, salida_json, duracion_ms,
         costo_usd, tokens, tokens_entrada, tokens_salida, snapshot_version,
         cache_hit)
    select * from unnest(
        %s::uuid[], %s::text[], %s::text[], %s::jsonb[], %s::jsonb[],
        %s::int[], %s::numeric[], %s::int[], %s::int[], %s::int[],
        %s::text[], %s::boolean[])
"""

COLUMNAS_ETAPA = 12


class AuditoriaPostgres(Auditoria):
    def __init__(self):
        # Un buffer por ejecucion, indexado por id: dos runs concurrentes no se
        # pisan ni las etapas ni la cabecera.
        self._pendientes: dict[str, dict] = {}

    def iniciar(self, texto: str, snapshot_version: str,
                usuario_id: str | None = None) -> Ejecucion:
        if not usuario_id:
            raise ValueError(
                "AuditoriaPostgres necesita usuario_id: ejecuciones.usuario_id "
                "es not null y apunta a auth.users")

        # El id se genera aqui, no lo devuelve la base: por eso se puede
        # aplazar la escritura sin que nadie espere.
        id_ej = str(uuid.uuid4())
        self._pendientes[id_ej] = {
            "cabecera": (id_ej, usuario_id, texto, snapshot_version),
            "etapas": [],
        }
        return EjecucionConcreta(id_ej, snapshot_version, texto, usuario_id)

    def registrar_etapa(self, ejecucion: Ejecucion, etapa: str, entrada: dict,
                        salida: dict, duracion_ms: int, costo_usd: float,
                        tokens: int = 0, tokens_entrada: int = 0,
                        tokens_salida: int = 0, modelo: str | None = None,
                        cache_hit: bool = False) -> None:
        pendiente = self._pendientes.get(ejecucion.id)
        if pendiente is None:
            raise RuntimeError(
                f"Etapa {etapa!r} registrada sobre un run ya cerrado o nunca "
                f"iniciado ({ejecucion.id})")

        pendiente["etapas"].append((
            ejecucion.id, str(etapa), modelo,
            json.dumps(entrada, ensure_ascii=False),
            json.dumps(salida, ensure_ascii=False),
            duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida,
            ejecucion.snapshot_version, cache_hit,
        ))

    def cerrar(self, ejecucion: Ejecucion, estado: str,
               motivo_parcial: str | None = None) -> None:
        """Escribe el run entero. Idempotente: la segunda llamada no hace nada.

        Lo es a proposito, porque evaluar_insumo cierra explicitamente antes de
        emitir el informe y ademas tiene un finally de red de seguridad.
        """
        pendiente = self._pendientes.pop(ejecucion.id, None)
        if pendiente is None:
            return

        # Las etapas viajan transpuestas: una lista por columna, no una tupla
        # por fila, que es lo que unnest espera. Sin etapas se mandan arrays
        # vacios y la sentencia escribe solo la cabecera.
        etapas = pendiente["etapas"]
        columnas = ([list(columna) for columna in zip(*etapas)] if etapas
                    else [[] for _ in range(COLUMNAS_ETAPA)])

        with pool().connection() as conexion:
            conexion.execute(_ESCRIBIR_RUN,
                             (*pendiente["cabecera"], estado, motivo_parcial,
                              *columnas))

    def descartar(self, ejecucion: Ejecucion) -> None:
        """Suelta el buffer sin escribir. Solo para tests."""
        self._pendientes.pop(ejecucion.id, None)
