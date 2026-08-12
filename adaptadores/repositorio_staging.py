"""
S2.3 — El escritor de `staging_agente`. Deuda abierta desde S2, cerrada en S8.0.

`DescubrimientoCascada.descubrir_n3` arma la lista de items y la devuelve, y su
unico consumidor le contaba la longitud:

    mapa.productos_n3_staging = cascada_metadata.productos_n3_staging

No habia **un solo `insert into staging_agente`** en el repositorio. La
cuarentena de S2 nunca llego a persistirse, y todo lo que S7 construyo encima
—watermark, validador, job de promocion nocturno, panel de revision— corria
sobre cero filas. La auditoria de S7 lo registro como B2 y quedo sin cerrar.

Esto es ese INSERT, y es el unico sitio que escribe la tabla: lo usan tanto el
sembrado de demostracion como la cascada cuando se conecte.

**Lo que este modulo NO arregla**, y sigue pendiente:

1. La cascada no corre en el flujo principal. `api/main.py` inyecta
   `DescubrimientoSnapshot`, que solo tiene `descubrir()`, de modo que la rama
   `hasattr(d.descubrimiento, 'descubrir_sync')` de
   `casos_de_uso/etapas/mapear_comercio.py` es siempre falsa en produccion.
   Conectarla es una decision de producto —mete red, coste y latencia en el
   camino de `/consultas`—, no un cable suelto.
2. La credencial de ModelArts responde 403 (`ModelArts.81004`), asi que hoy el
   agente no puede extraer nada aunque se conectara.

Por eso `usuario_id` es un parametro explicito y no algo que se saque de un
contexto global: cuando la cascada se conecte, habra que propagarlo por las
firmas de `mapear_comercio` → `descubrir_sync` → `descubrir_n3`, y tenerlo aqui
como argumento obligatorio deja claro que es lo que falta.
"""

import json
from typing import Any, Iterable
from uuid import UUID

from adaptadores.db import pool

# Se insertan con unnest y no con executemany por el mismo motivo que en
# auditoria_postgres: un unico viaje a Supabase en vez de uno por fila. El RTT
# medido es de ~112 ms, y una tanda del agente puede traer decenas de ofertas.
_INSERTAR = """
    insert into public.staging_agente
        (usuario_id, insumo, pais, mes, producto_json, fuente_url,
         html_capturado, provenance, grounding_check_status)
    select * from unnest(
        %s::uuid[], %s::text[], %s::text[], %s::text[], %s::jsonb[],
        %s::text[], %s::text[], %s::text[], %s::jsonb[])
    returning staging_id
"""

COLUMNAS = 9


class RepositorioStaging:
    """Persiste la cuarentena del agente (N3)."""

    def guardar(self, items: Iterable[dict[str, Any]],
                usuario_id: str | UUID) -> list[UUID]:
        """Escribe una tanda de ofertas en cuarentena y devuelve sus ids.

        `items` tiene la forma que produce `descubrir_n3`: insumo, pais,
        producto_json, fuente_url, html_capturado, provenance. `mes` y
        `grounding_check_status` son opcionales.

        `no_verificado` y `promoted_at` no se pasan: los pone el esquema. Una
        fila recien insertada esta en cuarentena por definicion, y el check
        `staging_no_promovido` no admite otra cosa.

        `validation_errors` tampoco: quien decide si una oferta es valida es el
        validador de S7.3, y lo escribe en `promotion_validation_log`, que
        ademas guarda contra que reglas se evaluo y cuando. Rellenar aqui la
        columna de la tabla daria dos versiones de la misma verdad.
        """
        filas = [self._fila(item, usuario_id) for item in items]
        if not filas:
            return []

        columnas = [list(columna) for columna in zip(*filas)]

        with pool().connection() as conn, conn.cursor() as cur:
            devueltos = cur.execute(_INSERTAR, columnas).fetchall()

        return [fila[0] for fila in devueltos]

    @staticmethod
    def _fila(item: dict[str, Any], usuario_id: str | UUID) -> tuple:
        producto = item.get("producto_json") or {}
        grounding = item.get("grounding_check_status")

        return (
            str(usuario_id),
            item["insumo"],
            item["pais"],
            item.get("mes"),
            # jsonb quiere texto, no un dict de Python. ensure_ascii=False para
            # que 'Perú' se guarde como 'Perú' y no escapado.
            json.dumps(producto, ensure_ascii=False),
            item.get("fuente_url") or "",
            item.get("html_capturado"),
            item.get("provenance", "agente"),
            json.dumps(grounding, ensure_ascii=False) if grounding else None,
        )

    def contar_en_cuarentena(self) -> int:
        with pool().connection() as conn, conn.cursor() as cur:
            return cur.execute(
                "select count(*) from public.staging_agente "
                "where promoted_at is null").fetchone()[0]
