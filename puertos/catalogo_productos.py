from typing import Protocol
from dominio.resultado_busqueda import ResultadoBusqueda

class CatalogoProductos(Protocol):
    def buscar(self, sinonimos: list[str], k: int = 30) -> ResultadoBusqueda:
        ...
