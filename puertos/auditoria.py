from typing import Protocol


class Ejecucion(Protocol):
    id: str
    snapshot_version: str
    insumo_texto: str
    # Dueno del run. Viaja aqui para que registrar_etapa y emitir() no tengan
    # que recibirlo por parametro (PLAN-TIERS-S3 §T3.2).
    usuario_id: str | None


class Auditoria(Protocol):
    def iniciar(self, texto: str, snapshot_version: str,
                usuario_id: str | None = None) -> Ejecucion:
        ...

    # 'etapa' es str y no int: el esquema de S3 numera '1','2a','2b','3','4','5','6'
    # para poder partir la etapa 2 sin reescribir el historial (D6).
    def registrar_etapa(self, ejecucion: Ejecucion, etapa: str, entrada: dict,
                        salida: dict, duracion_ms: int, costo_usd: float,
                        tokens: int = 0, tokens_entrada: int = 0,
                        tokens_salida: int = 0, modelo: str | None = None,
                        cache_hit: bool = False) -> None:
        """Registra una etapa, se haya resuelto por cache o llamando al modelo.

        `cache_hit` no es cosmetico: es lo que permite comprobar P02 con una
        consulta en vez de deducirlo de que los tokens sean 0.
        """
        ...

    def cerrar(self, ejecucion: Ejecucion, estado: str,
               motivo_parcial: str | None = None) -> None:
        """Fija el estado final del run.

        Hasta S2 el estado se escribia 'ok' al empezar y no se corregia nunca,
        asi que las 54 ejecuciones migradas en T2.2 son todas 'ok' aunque
        algunas fueran parciales.
        """
        ...
