from typing import Protocol
from dominio.insumo import InsumoInterpretado
from dominio.insight_mercado import InsightDeMercado
from dominio.resultado_busqueda import ResultadoBusqueda

class RedactorLLM(Protocol):
    async def interpretar(self, texto: str) -> InsumoInterpretado:
        ...

    async def redactar_insight(self, productos: ResultadoBusqueda, contexto_regulatorio: str = "") -> InsightDeMercado:
        ...
