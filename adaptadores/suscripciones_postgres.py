"""
T6 - Plan del usuario y gasto del mes, en un solo viaje.

La consulta trae tres cosas de tres sitios distintos con un unico round trip:
el plan sale de `perfiles`, el gasto del usuario y el gasto global salen de
`uso_mensual`. Es la unica lectura que el run hace contra la base antes de la
primera etapa.
"""

from adaptadores.db import pool
from puertos.suscripciones import ContextoSuscripcion, Suscripciones

PLAN_POR_DEFECTO = "gratuito"

# left join y no join: un usuario sin perfil (la cuenta tecnica del historico,
# o una creada antes del trigger de T4.3) no debe quedarse sin contexto. Se le
# aplica el plan gratuito, que es el conservador.
_CONSULTA = """
    select coalesce(p.plan, %s) as plan,
           coalesce((select sum(u.costo_usd) from public.uso_mensual u
                      where u.usuario_id = %s
                        and u.mes = date_trunc('month', now())), 0) as gasto_usuario,
           coalesce((select sum(u.costo_usd) from public.uso_mensual u
                      where u.mes = date_trunc('month', now())), 0) as gasto_global
      from (select 1) as siempre
      left join public.perfiles p on p.id = %s
"""


class SuscripcionesPostgres(Suscripciones):
    def contexto_de(self, usuario_id: str | None) -> ContextoSuscripcion:
        if not usuario_id:
            return ContextoSuscripcion(PLAN_POR_DEFECTO, 0.0, 0.0)

        with pool().connection() as conexion:
            plan, gasto_usuario, gasto_global = conexion.execute(
                _CONSULTA, (PLAN_POR_DEFECTO, usuario_id, usuario_id)).fetchone()

        return ContextoSuscripcion(plan, float(gasto_usuario), float(gasto_global))
