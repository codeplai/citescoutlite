from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class EstadoKillSwitch:
    """El interruptor de 8.5, con lo que hace falta para explicarlo.

    `motivo`, `actualizado_por` y `actualizado_en` no son adorno: un panel que
    solo diga "parado" obliga a quien lo ve a buscar por el chat quien lo apago
    y por que, que es justo lo que no se puede hacer en mitad de un incidente.
    """

    activo: bool
    motivo: Optional[str] = None
    actualizado_por: Optional[str] = None
    actualizado_en: Optional[str] = None


class ConfiguracionSistema(Protocol):
    def kill_switch(self) -> EstadoKillSwitch:
        """Estado actual del interruptor.

        Ante cualquier fallo se devuelve APAGADO. Es la unica direccion segura:
        un error de lectura que dejara el sistema parado convertiria una
        incidencia de base de datos en una caida del servicio, y el tope de
        gasto global —que se calcula aparte— sigue protegiendo el bolsillo.
        """
        ...
