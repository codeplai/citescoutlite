"""
S8.3 - El registro de quien hizo que en el panel.

De las seis acciones que 8.3 enumera, hasta ahora dejaba rastro **una**: la
promocion manual, en `promotion_log` (S7.4). Y ese rastro sirve para
promociones, no para responder la pregunta de 8.3 —"quien cambio esto y que
habia antes"— sobre cualquier cosa que se toque desde el panel.

## Registrar nunca tumba la accion

`registrar()` no propaga excepciones. Si la auditoria falla, se anota en el log
y la operacion sigue.

Es una decision incomoda y va en la direccion que va a proposito: entre
"promover una oferta y no poder anotarlo" y "no poder promover porque la
auditoria esta caida", lo segundo convierte un fallo de un registro accesorio
en una caida del panel. El fallo queda a la vista en el log del servidor, que
es donde mira quien opera.

Lo que si se hace es no perder el evento en silencio: se registra con `error`,
no con `debug`.

## El correo se copia, no se resuelve al leer

Un registro de auditoria tiene que seguir siendo legible dentro de un ano,
cuando esa persona puede haber cambiado de correo o no estar dada de alta. Un
informe que diga "usuario 6976d1cc-..." no vale para nada.
"""

import json
import logging
from typing import Any, Optional

from adaptadores.db import pool

logger = logging.getLogger(__name__)

# Las acciones de 8.3. Es una lista cerrada a proposito: un evento con el
# nombre mal escrito no aparece en los filtros del panel y es como si no se
# hubiera registrado, asi que vale mas fallar aqui, en desarrollo, que
# descubrirlo cuando alguien busque por que desaparecio una oferta.
EVENTOS = (
    "promotion_manual",     # S7.6, ya existia en promotion_log
    "promotion_rejected",   # rechazo manual
    "plan_changed",         # 8.9
    "kill_switch_toggled",  # 8.5
    "rule_updated",         # 7.2, el editor de reglas
    "login",                # entrada al panel
    "export",               # 8.7
    # T5. Es el unico evento del panel que **cuesta dinero al ocurrir**: cada
    # consulta que no salga de cache lanza al agente del eCFR contra el modelo.
    # Por eso el detalle lleva `llamadas_agente` y no solo el veredicto: sin esa
    # cifra, el cost-meter no puede atribuir el gasto a esta pantalla.
    "analisis_aditivos_consultado",
)

_INSERTAR = """
    insert into public.auditoria_panel
        (evento, usuario_id, usuario_email, entidad, entidad_id,
         antes, despues, detalles)
    values (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
    returning audit_id
"""


def _json(valor: Any) -> Optional[str]:
    if valor is None:
        return None
    # ensure_ascii=False para que 'Perú' se guarde legible y no escapado: esto
    # lo va a leer una persona en una tabla, no un parser.
    return json.dumps(valor, ensure_ascii=False, default=str)


class AuditoriaPanel:
    """Escribe y lee `auditoria_panel`."""

    def registrar(self, evento: str, *, usuario_id: Optional[str] = None,
                  usuario_email: Optional[str] = None,
                  entidad: Optional[str] = None,
                  entidad_id: Optional[Any] = None,
                  antes: Optional[dict] = None,
                  despues: Optional[dict] = None,
                  detalles: Optional[dict] = None) -> Optional[int]:
        """Deja constancia de una accion. Devuelve el id, o None si fallo.

        `antes` y `despues` van tal cual: para un alta, `antes` es None; para
        una baja, lo es `despues`. Esa asimetria es informacion.
        """
        if evento not in EVENTOS:
            raise ValueError(
                f"Evento de auditoria desconocido: {evento!r}. "
                f"Los validos son {', '.join(EVENTOS)}")

        parametros = (evento, usuario_id, usuario_email, entidad,
                      str(entidad_id) if entidad_id is not None else None,
                      _json(antes), _json(despues), _json(detalles or {}))

        try:
            with pool().connection() as conn, conn.cursor() as cur:
                return cur.execute(_INSERTAR, parametros).fetchone()[0]
        except Exception as e:
            # A proposito: la auditoria no tumba la accion que audita.
            logger.error(f"No se pudo auditar {evento} sobre "
                         f"{entidad}/{entidad_id}: {type(e).__name__}: {e}")
            return None

    def leer(self, *, evento: Optional[str] = None,
             usuario_id: Optional[str] = None,
             usuario_email: Optional[str] = None,
             desde: Optional[str] = None, hasta: Optional[str] = None,
             limite: int = 50, desplazamiento: int = 0) -> dict[str, Any]:
        """Una pagina de la auditoria, con el total para poder paginar.

        Los filtros se componen: los tres que pide 8.3 son usuario, accion y
        fecha, y se usan a la vez ("que hizo Fulano la semana pasada").

        El total va en la misma llamada que las filas. Con dos endpoints, una
        pagina y su contador pueden venir de instantes distintos y la paginacion
        salta.
        """
        condiciones, parametros = [], []

        if evento:
            condiciones.append("evento = %s")
            parametros.append(evento)
        if usuario_id:
            condiciones.append("usuario_id = %s")
            parametros.append(usuario_id)
        if usuario_email:
            # Por correo y parcial, porque es lo unico que una persona puede
            # teclear: nadie busca por '6976d1cc-bb23-...'. El filtro por
            # usuario_id se conserva para enlazar desde otras pantallas, que si
            # tienen el uuid a mano.
            condiciones.append("usuario_email ilike %s")
            parametros.append(f"%{usuario_email}%")
        if desde:
            condiciones.append("ocurrido_en >= %s")
            parametros.append(desde)
        if hasta:
            # Inclusivo por el lado de arriba: quien filtra "hasta el 12" espera
            # que salga lo del dia 12, no lo anterior a su medianoche.
            condiciones.append("ocurrido_en < (%s::timestamptz + interval '1 day')")
            parametros.append(hasta)

        donde = ("where " + " and ".join(condiciones)) if condiciones else ""

        with pool().connection() as conn, conn.cursor() as cur:
            total = cur.execute(
                f"select count(*) from public.auditoria_panel {donde}",
                parametros).fetchone()[0]

            filas = cur.execute(f"""
                select audit_id, ocurrido_en, evento, usuario_id, usuario_email,
                       entidad, entidad_id, antes, despues, detalles
                  from public.auditoria_panel
                  {donde}
                 order by ocurrido_en desc, audit_id desc
                 limit %s offset %s
            """, [*parametros, limite, desplazamiento]).fetchall()

        return {
            "total": total,
            "entradas": [self._a_dict(f) for f in filas],
        }

    @staticmethod
    def _a_dict(fila: tuple) -> dict[str, Any]:
        return {
            "audit_id": fila[0],
            "ocurrido_en": fila[1].isoformat() if fila[1] else None,
            "evento": fila[2],
            "usuario_id": str(fila[3]) if fila[3] else None,
            "usuario_email": fila[4],
            "entidad": fila[5],
            "entidad_id": fila[6],
            "antes": fila[7],
            "despues": fila[8],
            "detalles": fila[9],
        }
