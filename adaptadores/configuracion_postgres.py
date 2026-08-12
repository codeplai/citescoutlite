"""
S8.5 - Lectura y escritura de `sistema_config`.

El adaptador valida la forma del valor, porque la tabla es clave-valor con
jsonb y ahi Postgres no valida nada. Si la fila viniera con basura —un
`{"activo": "si"}` escrito a mano contra la base—, `bool("si")` seria True y el
sistema quedaria parado sin que nadie lo hubiera pedido.
"""

import json
import logging
from typing import Optional
from uuid import UUID

from adaptadores.db import pool
from puertos.configuracion_sistema import EstadoKillSwitch

logger = logging.getLogger(__name__)

CLAVE_KILL_SWITCH = "kill_switch"

# Un motivo largo no cabe en la barra del panel y no aporta: lo que hace falta
# es "incidente de coste 12-ago", no un parte completo.
MAXIMO_MOTIVO = 280


class ConfiguracionPostgres:
    """Implementa el puerto ConfiguracionSistema contra Supabase."""

    def kill_switch(self) -> EstadoKillSwitch:
        try:
            with pool().connection() as conn, conn.cursor() as cur:
                fila = cur.execute(
                    "select valor, actualizado_por, actualizado_en "
                    "  from public.sistema_config where clave = %s",
                    (CLAVE_KILL_SWITCH,)).fetchone()
        except Exception as e:
            # Apagado ante cualquier fallo. Un error de lectura que dejara el
            # sistema parado convertiria una incidencia de base de datos en una
            # caida del servicio; y el tope de gasto global, que se calcula
            # aparte, sigue protegiendo el bolsillo.
            logger.error(f"No se pudo leer el kill-switch, se asume apagado: "
                         f"{type(e).__name__}: {e}")
            return EstadoKillSwitch(activo=False)

        if not fila:
            return EstadoKillSwitch(activo=False)

        valor, por, cuando = fila
        return EstadoKillSwitch(
            # `is True` y no `bool(...)`: la columna es jsonb sin esquema, y un
            # "si" escrito a mano contra la base pararia el sistema entero.
            activo=(valor or {}).get("activo") is True,
            motivo=(valor or {}).get("motivo"),
            actualizado_por=str(por) if por else None,
            actualizado_en=cuando.isoformat() if cuando else None,
        )

    def fijar_kill_switch(self, activo: bool, *, motivo: Optional[str] = None,
                          por: Optional[str] = None) -> EstadoKillSwitch:
        """Acciona el interruptor y devuelve como queda.

        Escribir falla hacia arriba, al reves que leer: si un administrador
        pulsa "parar" y no se guarda, tiene que enterarse. Un boton que dice que
        ha parado el gasto sin haberlo parado es peor que uno que da error.
        """
        motivo_limpio = (motivo or "").strip()[:MAXIMO_MOTIVO] or None
        valor = json.dumps({"activo": bool(activo), "motivo": motivo_limpio})

        with pool().connection() as conn, conn.cursor() as cur:
            fila = cur.execute("""
                insert into public.sistema_config
                    (clave, valor, actualizado_por, actualizado_en)
                values (%s, %s::jsonb, %s, now())
                on conflict (clave) do update
                    set valor = excluded.valor,
                        actualizado_por = excluded.actualizado_por,
                        actualizado_en = now()
                returning valor, actualizado_por, actualizado_en
            """, (CLAVE_KILL_SWITCH, valor,
                  UUID(por) if por else None)).fetchone()

        return EstadoKillSwitch(
            activo=(fila[0] or {}).get("activo") is True,
            motivo=(fila[0] or {}).get("motivo"),
            actualizado_por=str(fila[1]) if fila[1] else None,
            actualizado_en=fila[2].isoformat() if fila[2] else None,
        )
