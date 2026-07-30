from datetime import date
from pydantic import BaseModel
from typing import Optional

class ProductoExistente(BaseModel):
    id_fuente: str
    nombre: str
    categoria: str
    usa_insumo_directo: bool
    fecha_dato: Optional[date] = None
    ingredientes: str = ""
    url: str = ""
