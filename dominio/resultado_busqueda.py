from pydantic import BaseModel
from .producto_existente import ProductoExistente

class ResultadoBusqueda(BaseModel):
    productos: list[ProductoExistente]
    n_directos: int
