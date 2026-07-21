from typing import Protocol

class Ejecucion(Protocol):
    id: str
    snapshot_version: str
    insumo_texto: str

class Auditoria(Protocol):
    def iniciar(self, texto: str, snapshot_version: str) -> Ejecucion:
        ...

    def registrar_etapa(self, ejecucion: Ejecucion, etapa: int, entrada: dict, salida: dict, duracion_ms: int, costo_usd: float, tokens: int = 0, tokens_entrada: int = 0, tokens_salida: int = 0) -> None:
        ...
