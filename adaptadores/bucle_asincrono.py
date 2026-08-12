"""
S8.0 - Compatibilidad del bucle de asyncio con psycopg en Windows.

## El sintoma

Al correr el job de promocion de S7 contra datos reales por primera vez:

    WARNING No se pudo registrar el evento started: Psycopg cannot use the
    'ProactorEventLoop' to run in async mode.

El job termino en verde —promovio 15 ofertas, rechazo 6— pero **no escribio ni
un evento en `eventos_job`**. El `try/except` de `_emitir` se traga el fallo a
proposito, para que un problema de registro no tumbe una promocion ya hecha. El
efecto secundario es que la tabla se queda vacia y nadie se entera.

Eso importa porque `eventos_job` es la unica fuente del dashboard de jobs
(S8.1). Construirlo sobre una tabla que en la maquina de desarrollo nunca se
llena habria dado una pantalla en blanco sin explicacion.

## La causa

Desde Python 3.8, el policy por defecto de asyncio en Windows es
`WindowsProactorEventLoopPolicy`. psycopg3 en modo asincrono necesita un bucle
de tipo selector: el Proactor no expone `add_reader`/`add_writer` sobre
sockets, que es como psycopg espera las notificaciones del servidor.

En Linux —donde corre el despliegue de Huawei Cloud— el policy por defecto ya
es de selector, asi que esto **solo afecta a la maquina de desarrollo**. Pero es
justo la maquina donde se construye y se enseña el panel.

## El arreglo

Fijar el policy antes de que se cree el bucle. Tiene que ser antes: un bucle ya
en marcha no se puede cambiar, y por eso esto se llama al importar los puntos de
entrada (el worker, la API) y no desde dentro de `emit_event`, que ya corre
dentro del bucle equivocado.

Es idempotente y no hace nada fuera de Windows.
"""

import asyncio
import sys

_aplicado = False


def asegurar_bucle_compatible() -> bool:
    """Deja el policy de asyncio en uno que psycopg pueda usar.

    Devuelve True si hubo que cambiarlo. Llamar antes de crear el bucle:
    en la practica, al importar el punto de entrada del proceso.
    """
    global _aplicado

    if _aplicado or sys.platform != "win32":
        return False

    politica = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if politica is None:  # pragma: no cover - solo existe en Windows
        return False

    if isinstance(asyncio.get_event_loop_policy(), politica):
        _aplicado = True
        return False

    asyncio.set_event_loop_policy(politica())
    _aplicado = True
    return True
