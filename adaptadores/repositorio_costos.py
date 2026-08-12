"""
S8.2 - El cost-meter: en que se va el dinero.

## Todo se agrega en SQL, en un solo viaje

El propio documento de S8 lista como **primer riesgo** que la agregacion se
haga en el cliente. No es un riesgo teorico: son 190 ejecuciones y 690 etapas
hoy, y la respuesta natural —traerse las filas y sumarlas en JavaScript— crece
con el historico hasta que el navegador se atraganta, justo cuando el panel
lleva un ano de datos y por fin es util.

Ademas va en **una sola consulta con CTE**, no en cuatro. El RTT medido a
Supabase es de ~112 ms: cuatro consultas serian ~450 ms de red antes de contar
un solo dolar, y el DoD de la fase pide responder por debajo de 500 ms.

## La serie lleva los dias vacios

`generate_series` genera los 30 dias y el gasto se le pega por la izquierda.
Sin eso, un dia sin consultas simplemente no aparece, y una grafica que une el
lunes con el miercoles dibuja una linea continua donde no hubo nada. En un
panel de costes eso se lee como "gastamos todos los dias".

## El coste se atribuye al dia del RUN, no al de la etapa

Un run que empieza a las 23:58 y acaba a las 00:03 tiene etapas de dos dias.
Repartirlas haria que la suma de la serie no cuadrase con el total por usuario,
y una tabla de costes que no cuadra consigo misma no la usa nadie.
"""

import logging
import os
from calendar import monthrange
from datetime import date
from typing import Any

from adaptadores.db import pool

logger = logging.getLogger(__name__)

MAXIMO_DIAS = 365

_CONSULTA = """
with ventana as (
    select (current_date - ((%(dias)s - 1) || ' days')::interval)::date as desde
),
dias as (
    select generate_series((select desde from ventana), current_date,
                           '1 day')::date as dia
),
runs as (
    select id, usuario_id, creado_en::date as dia, estado, motivo_parcial
      from public.ejecuciones
     where creado_en::date >= (select desde from ventana)
),
etapas as (
    select x.ejecucion_id, x.etapa, x.modelo, x.costo_usd, x.tokens,
           x.cache_hit, r.dia, r.usuario_id
      from public.etapas_ejecucion x
      join runs r on r.id = x.ejecucion_id
),
-- Agregado una vez y pegado por la izquierda, no con subconsultas
-- correlacionadas dentro de `serie`. Escrito asi la primera vez, cada dia
-- de la ventana recorria las etapas por su cuenta —O(dias x etapas)— y la
-- consulta tardaba 864 ms, por encima del techo de 500 ms del DoD.
gasto_dia as (
    select dia, sum(costo_usd) as costo_usd, sum(tokens) as tokens
      from etapas group by dia
),
runs_dia as (
    select dia, count(*) as runs from runs group by dia
),
serie as (
    select d.dia::text as dia,
           coalesce(g.costo_usd, 0)::float8 as costo_usd,
           coalesce(g.tokens, 0)::bigint as tokens,
           coalesce(r.runs, 0)::bigint as runs
      from dias d
      left join gasto_dia g on g.dia = d.dia
      left join runs_dia r on r.dia = d.dia
),
por_etapa as (
    select etapa,
           sum(costo_usd)::float8 as costo_usd,
           coalesce(sum(tokens), 0)::bigint as tokens,
           count(*)::bigint as veces,
           count(*) filter (where cache_hit)::bigint as cache_hits
      from etapas
     group by etapa
),
por_usuario as (
    select r.usuario_id::text as usuario_id,
           count(distinct r.id)::bigint as runs,
           coalesce(sum(e.costo_usd), 0)::float8 as costo_usd,
           coalesce(sum(e.tokens), 0)::bigint as tokens
      from runs r
      left join etapas e on e.ejecucion_id = r.id
     group by r.usuario_id
),
usuarios as (
    select u.usuario_id, u.runs, u.costo_usd, u.tokens,
           p.email, coalesce(p.plan, 'gratuito') as plan
      from por_usuario u
      left join public.perfiles p on p.id = u.usuario_id::uuid
),
estados as (
    select coalesce(motivo_parcial, estado, 'sin_estado') as motivo,
           count(*)::bigint as runs
      from runs group by 1
),
mes as (
    select coalesce(sum(x.costo_usd), 0)::float8 as costo_mes_usd,
           count(distinct j.id)::bigint as runs_mes
      from public.ejecuciones j
      left join public.etapas_ejecucion x on x.ejecucion_id = j.id
     where j.creado_en >= date_trunc('month', now())
)
select
    (select json_agg(row_to_json(s) order by s.dia) from serie s),
    (select json_agg(row_to_json(p) order by p.costo_usd desc) from por_etapa p),
    (select json_agg(row_to_json(u) order by u.costo_usd desc) from usuarios u),
    (select json_agg(row_to_json(e) order by e.runs desc) from estados e),
    (select costo_mes_usd from mes),
    (select runs_mes from mes)
"""


def _tope_global() -> float:
    """El mismo tope que aplica el kill-switch por umbral (T6.3)."""
    try:
        return float(os.getenv("PRESUPUESTO_GLOBAL_MES_USD", 10.0))
    except (TypeError, ValueError):
        return 10.0


def _proyeccion(costo_mes_usd: float, hoy: date | None = None) -> float:
    """A cuanto cerraria el mes al ritmo que lleva.

    Regla de tres sobre los dias transcurridos. Es deliberadamente simple: con
    dos meses de historico, cualquier cosa mas sofisticada —tendencia,
    estacionalidad— seria precision inventada sobre una muestra que no la
    aguanta. Se enseña como estimacion y no como cifra.
    """
    hoy = hoy or date.today()
    dias_del_mes = monthrange(hoy.year, hoy.month)[1]
    return round(costo_mes_usd / hoy.day * dias_del_mes, 6)


class RepositorioCostos:
    def resumen(self, dias: int = 30) -> dict[str, Any]:
        dias = max(1, min(int(dias), MAXIMO_DIAS))

        with pool().connection() as conn, conn.cursor() as cur:
            fila = cur.execute(_CONSULTA, {"dias": dias}).fetchone()

        serie, por_etapa, por_usuario, estados, costo_mes, runs_mes = fila
        costo_mes = float(costo_mes or 0.0)
        tope = _tope_global()

        return {
            "dias": dias,
            "serie": serie or [],
            "por_etapa": por_etapa or [],
            "por_usuario": por_usuario or [],
            "por_estado": estados or [],
            "mes": {
                "costo_usd": round(costo_mes, 6),
                "runs": int(runs_mes or 0),
                "tope_global_usd": tope,
                # Sin tope no hay porcentaje: un 0 se leeria como "no se ha
                # gastado nada", que es lo contrario de "no se sabe".
                "pct_del_tope": (round(costo_mes / tope * 100, 1)
                                 if tope > 0 else None),
                "proyeccion_cierre_usd": _proyeccion(costo_mes),
            },
        }
