from dataclasses import dataclass


@dataclass
class EjecucionConcreta:
    """Portador de datos que devuelven los adaptadores de Auditoria.

    Cumple el Protocol puertos.auditoria.Ejecucion. Vive en adaptadores/ y no
    en puertos/ porque los puertos son interfaces; lo comparten los dos
    adaptadores para no duplicar la misma estructura dos veces.
    """

    id: str
    snapshot_version: str
    insumo_texto: str
    usuario_id: str | None = None
