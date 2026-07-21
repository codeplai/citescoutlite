from typing import Protocol

class CacheLLM(Protocol):
    def obtener(self, clave: str) -> dict | None:
        ...

    def guardar(self, clave: str, valor: dict) -> None:
        ...
