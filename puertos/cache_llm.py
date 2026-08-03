from typing import Protocol


class CacheLLM(Protocol):
    def obtener(self, clave: str) -> dict | None:
        ...

    def guardar(self, clave: str, valor: dict, etapa: str | None = None,
                modelo: str | None = None,
                snapshot_version: str | None = None) -> None:
        """Guarda la respuesta con su procedencia.

        Los tres metadatos son opcionales en la firma pero no en la practica:
        hasta S2 se guardaban siempre en NULL y por eso P02 no se podia probar.
        Un cache hit sin modelo ni snapshot registrados no demuestra que la
        clave sea la correcta, solo que dos cadenas coincidieron.
        """
        ...

    def vaciar_pendientes(self) -> None:
        """Fuerza la escritura de lo que el adaptador tenga en memoria.

        Los adaptadores locales escriben al vuelo y no hacen nada aqui; el de
        Postgres acumula para no pagar un viaje a Sao Paulo por etapa.
        """
        ...
