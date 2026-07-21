from datetime import date
from pydantic import BaseModel

class ProductoExistente(BaseModel):
    id_fuente: str
    nombre: str
    categoria: str
    usa_insumo_directo: bool
    fecha_dato: date
    ingredientes: str = ""
    url: str = ""
