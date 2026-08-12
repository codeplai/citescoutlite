"""
S8.9 - Lectura y cambio del plan de un usuario.

`perfiles` ya se leia en dos sitios —`rol_de()` para el permiso y
`SuscripcionesPostgres` para el plan y el gasto—, pero nadie la escribia: el
plan solo se podia cambiar con un `update` a mano contra la base. 8.9 pide
poder hacerlo desde el panel, y para eso hace falta saber tambien **que habia
antes**, porque el cambio se audita.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from adaptadores.db import pool

logger = logging.getLogger(__name__)

# Los mismos que acepta el check de la tabla. Se repiten aqui para poder
# rechazar un valor malo con un 400 legible en vez de dejar que Postgres
# devuelva una violacion de constraint como un 500.
PLANES = ("gratuito", "premium")


class RepositorioPerfiles:
    def listar(self, limite: int = 200) -> list[dict[str, Any]]:
        """Los usuarios con su plan, su rol y su gasto del mes.

        El gasto va en la misma consulta porque es lo que hace util la
        pantalla: cambiar el plan de alguien sin ver lo que consume es decidir
        a ciegas.
        """
        with pool().connection() as conn, conn.cursor() as cur:
            filas = cur.execute("""
                select p.id, p.email, p.plan, p.rol, p.creado_en,
                       coalesce(u.runs, 0), coalesce(u.costo_usd, 0)
                  from public.perfiles p
                  left join (
                        select usuario_id, sum(runs) as runs,
                               sum(costo_usd) as costo_usd
                          from public.uso_mensual
                         where mes = date_trunc('month', now())
                         group by usuario_id
                  ) u on u.usuario_id = p.id
                 order by p.email
                 limit %s
            """, (limite,)).fetchall()

        return [{
            "id": str(f[0]), "email": f[1], "plan": f[2], "rol": f[3],
            "creado_en": f[4].isoformat() if f[4] else None,
            "runs_mes": int(f[5]), "costo_mes_usd": round(float(f[6]), 6),
        } for f in filas]

    def plan_de(self, usuario_id: str) -> Optional[str]:
        with pool().connection() as conn, conn.cursor() as cur:
            fila = cur.execute(
                "select plan from public.perfiles where id = %s",
                (UUID(usuario_id),)).fetchone()
        return fila[0] if fila else None

    def cambiar_plan(self, usuario_id: str, plan: str) -> Optional[dict[str, str]]:
        """Cambia el plan y devuelve {antes, despues}, o None si no existe.

        Devuelve el valor anterior en la misma sentencia y no con un `select`
        previo: entre leer y escribir, otro administrador puede haber cambiado
        el mismo plan, y la auditoria acabaria diciendo que se paso de un valor
        que ya no era el que habia.
        """
        with pool().connection() as conn, conn.cursor() as cur:
            fila = cur.execute("""
                update public.perfiles nuevo
                   set plan = %s
                  from public.perfiles viejo
                 where nuevo.id = %s and viejo.id = nuevo.id
                returning viejo.plan, nuevo.plan
            """, (plan, UUID(usuario_id))).fetchone()

        if not fila:
            return None
        return {"antes": fila[0], "despues": fila[1]}
