from dominio.insumo import InsumoInterpretado
from casos_de_uso.dependencias import Dependencias

async def interpretar_insumo(d: Dependencias, texto: str) -> InsumoInterpretado:
    return await d.redactor.interpretar(texto)
