"""
S7 - Acceso a datos de la promoción.

Todo lo que el job y el panel necesitan tocar en Postgres: las reglas, la
cuarentena y los tres logs. La decisión de promover no está aquí, sino en
`casos_de_uso/promocion`; esto solo lee y escribe.

Recordatorio de D1: promover es marcar la fila de `staging_agente`
(`promoted_at` + `promotion_source`), no moverla a otra tabla.
"""

import json
import logging
from datetime import date
from typing import Any, Optional
from uuid import UUID

from adaptadores.db import pool
from casos_de_uso.promocion import Regla

logger = logging.getLogger(__name__)


class RepositorioPromocion:
    """Lecturas y escrituras de S7 sobre Postgres."""

    # --- Reglas -------------------------------------------------------------

    def leer_reglas(self, solo_activas: bool = True) -> list[Regla]:
        """Las reglas tal como CITE las tenga configuradas."""
        consulta = "select nombre_regla, expresion, activo from public.promotion_rules"
        if solo_activas:
            consulta += " where activo"
        consulta += " order by nombre_regla"

        with pool().connection() as conn, conn.cursor() as cur:
            filas = cur.execute(consulta).fetchall()

        return [Regla(nombre=n, expresion=e, activo=a) for n, e, a in filas]

    # --- Cuarentena ---------------------------------------------------------

    def ofertas_en_cuarentena(self, limite: int = 1000) -> list[dict[str, Any]]:
        """Ofertas sin promover, de la más antigua a la más nueva.

        Se sirven en orden de llegada porque la cuarentena tiene TTL de 24 h:
        lo que lleva más tiempo es lo que está más cerca de perderse.
        """
        with pool().connection() as conn, conn.cursor() as cur:
            filas = cur.execute("""
                select staging_id, usuario_id, insumo, pais, producto_json,
                       fuente_url, grounding_check_status, creado_en
                  from public.staging_agente
                 where promoted_at is null
                 order by creado_en asc
                 limit %s
            """, (limite,)).fetchall()

        return [{
            "staging_id": f[0],
            "usuario_id": f[1],
            "insumo": f[2],
            "pais": f[3],
            "producto_json": f[4],
            "fuente_url": f[5],
            "grounding_check_status": f[6],
            "creado_en": f[7],
        } for f in filas]

    # --- Logs ---------------------------------------------------------------

    def registrar_watermark(self, staging_id: UUID, semilla: str,
                            lunes: date, cubo: int, porcentaje: int,
                            automatica: bool) -> None:
        """Deja escrito de qué lado cayó la oferta esta semana.

        Idempotente por (staging_id, semilla): si el job se repite dentro de la
        misma semana actualiza la fila en vez de duplicarla. Dos filas distintas
        para la misma oferta y semana significarían que el watermark no es
        determinista, que es justo lo que promete.
        """
        with pool().connection() as conn, conn.cursor() as cur:
            cur.execute("""
                insert into public.promotion_watermark_log
                       (staging_id, semilla, lunes_semana, cubo, porcentaje, automatica)
                values (%s, %s, %s, %s, %s, %s)
                on conflict (staging_id, semilla) do update
                   set cubo = excluded.cubo,
                       porcentaje = excluded.porcentaje,
                       automatica = excluded.automatica
            """, (staging_id, semilla, lunes, cubo, porcentaje, automatica))

    def registrar_validacion(self, staging_id: UUID, passed: bool,
                             errores: list[dict], reglas: list[str]) -> None:
        with pool().connection() as conn, conn.cursor() as cur:
            cur.execute("""
                insert into public.promotion_validation_log
                       (staging_id, passed, errores, reglas_evaluadas)
                values (%s, %s, %s, %s)
            """, (staging_id, passed, json.dumps(errores), reglas))

    # --- Promoción ----------------------------------------------------------

    def promover(self, staging_id: UUID, promotion_source: str,
                 reglas: list[str], promoted_by: Optional[UUID] = None) -> bool:
        """Marca la oferta como promovida y lo registra, todo o nada.

        La marca y su registro van en una transacción explícita: el pool es
        autocommit, así que sin esto una caída entre ambas dejaría una oferta
        promovida sin rastro de quién ni por qué, que es exactamente lo que
        `promotion_log` existe para impedir.

        Devuelve False si la oferta ya estaba promovida (otro job, o el panel
        se adelantó). El `where promoted_at is null` hace de cerrojo.
        """
        tipo = "manual" if promoted_by else "auto"

        with pool().connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("""
                        update public.staging_agente
                           set promoted_at = now(),
                               no_verificado = false,
                               promotion_source = %s
                         where staging_id = %s
                           and promoted_at is null
                    """, (promotion_source, staging_id))

                    if cur.rowcount == 0:
                        logger.info(
                            f"Oferta {staging_id} ya estaba promovida; no se toca")
                        return False

                    cur.execute("""
                        insert into public.promotion_log
                               (staging_id, promotion_type, promoted_by,
                                rules_applied, validation_errors, result)
                        values (%s, %s, %s, %s, '[]'::jsonb, 'promoted')
                    """, (staging_id, tipo, promoted_by, reglas))

        return True

    def registrar_rechazo(self, staging_id: UUID, errores: list[dict],
                          reglas: list[str],
                          promoted_by: Optional[UUID] = None) -> None:
        """Anota que la oferta no pasó. La fila se queda en cuarentena.

        No se borra ni se marca: sigue viva para que el 20 % manual pueda
        revisarla, y el TTL de 24 h de staging_agente se encarga del resto.
        """
        tipo = "manual" if promoted_by else "auto"

        with pool().connection() as conn, conn.cursor() as cur:
            cur.execute("""
                insert into public.promotion_log
                       (staging_id, promotion_type, promoted_by,
                        rules_applied, validation_errors, result)
                values (%s, %s, %s, %s, %s, 'rejected')
            """, (staging_id, tipo, promoted_by, reglas, json.dumps(errores)))

    # --- Cola de revisión manual (7.6) --------------------------------------

    def cola_manual(self, semilla: str, limite: int = 100,
                    solo_con_errores: bool = False) -> list[dict[str, Any]]:
        """Ofertas que esperan revisión humana, con su último veredicto.

        Son las que el watermark mandó al 20 % manual, más las que el job
        intentó promover y rechazó: unas y otras siguen en cuarentena y ambas
        necesitan que alguien decida.

        El orden pone delante lo que tiene errores conocidos y, dentro de eso,
        lo más antiguo. Es el "smart filtering" de 7.6: lo que ya se sabe por
        qué falló se revisa antes, y el TTL de 24 h aprieta a lo más viejo.
        """
        filtro = "and v.errores is not null and jsonb_array_length(v.errores) > 0" \
            if solo_con_errores else ""

        with pool().connection() as conn, conn.cursor() as cur:
            filas = cur.execute(f"""
                select s.staging_id, s.insumo, s.pais, s.producto_json,
                       s.fuente_url, s.creado_en, s.grounding_check_status,
                       w.automatica, w.cubo,
                       v.errores, v.passed, v.created_at,
                       extract(epoch from (now() - s.creado_en)) / 3600 as horas
                  from public.staging_agente s
                  left join public.promotion_watermark_log w
                         on w.staging_id = s.staging_id and w.semilla = %s
                  -- Solo el veredicto mas reciente de cada oferta: si el job
                  -- corrio dos veces, la UI debe enseñar el ultimo.
                  left join lateral (
                        select errores, passed, created_at
                          from public.promotion_validation_log
                         where staging_id = s.staging_id
                         order by created_at desc
                         limit 1
                  ) v on true
                 where s.promoted_at is null
                   {filtro}
                 order by (v.errores is not null) desc, s.creado_en asc
                 limit %s
            """, (semilla, limite)).fetchall()

        return [{
            "staging_id": str(f[0]),
            "insumo": f[1],
            "pais": f[2],
            "producto": f[3],
            "fuente_url": f[4],
            "creado_en": f[5].isoformat() if f[5] else None,
            "grounding": f[6],
            # None = el job aun no la ha visto esta semana.
            "automatica": f[7],
            "cubo": f[8],
            "errores": f[9] or [],
            "validacion_passed": f[10],
            "validado_en": f[11].isoformat() if f[11] else None,
            "horas_en_cuarentena": round(float(f[12]), 1) if f[12] is not None else None,
        } for f in filas]

    def historial(self, dias: int = 7, limite: int = 200) -> list[dict[str, Any]]:
        """Promociones y rechazos recientes, para la pestaña de historial."""
        with pool().connection() as conn, conn.cursor() as cur:
            filas = cur.execute("""
                select l.log_id, l.staging_id, l.promotion_type, l.promoted_by,
                       l.result, l.rules_applied, l.validation_errors, l.created_at,
                       s.insumo, s.producto_json ->> 'nombre'
                  from public.promotion_log l
                  left join public.staging_agente s on s.staging_id = l.staging_id
                 where l.created_at >= now() - make_interval(days => %s)
                 order by l.created_at desc
                 limit %s
            """, (dias, limite)).fetchall()

        return [{
            "log_id": f[0],
            "staging_id": str(f[1]),
            "tipo": f[2],
            "promovido_por": str(f[3]) if f[3] else "system",
            "resultado": f[4],
            "reglas": f[5],
            "errores": f[6],
            "fecha": f[7].isoformat() if f[7] else None,
            "insumo": f[8],
            # La oferta puede haber caducado por TTL: el log sobrevive.
            "producto": f[9],
        } for f in filas]

    # --- Informes -----------------------------------------------------------

    def resumen_del_dia(self) -> dict[str, Any]:
        """"X promovidos automáticamente hoy, Y manual, Z rechazados" (7.4)."""
        with pool().connection() as conn, conn.cursor() as cur:
            fila = cur.execute("""
                select
                    count(*) filter (where result = 'promoted' and promotion_type = 'auto'),
                    count(*) filter (where result = 'promoted' and promotion_type = 'manual'),
                    count(*) filter (where result = 'rejected')
                  from public.promotion_log
                 where created_at >= date_trunc('day', now())
            """).fetchone()

            # Desglose por regla: "Precio fuera de rango (10), Stock (5)".
            motivos = cur.execute("""
                select e ->> 'regla' as regla, count(*) as veces
                  from public.promotion_log,
                       lateral jsonb_array_elements(validation_errors) as e
                 where result = 'rejected'
                   and created_at >= date_trunc('day', now())
                 group by 1
                 order by 2 desc
            """).fetchall()

        return {
            "promovidos_auto": fila[0],
            "promovidos_manual": fila[1],
            "rechazados": fila[2],
            "motivos_de_rechazo": {r: v for r, v in motivos},
        }
