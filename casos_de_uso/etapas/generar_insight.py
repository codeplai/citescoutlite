from dominio.resultado_busqueda import ResultadoBusqueda
from dominio.insight_mercado import InsightDeMercado
from casos_de_uso.dependencias import Dependencias

async def generar_insight_parcial(d: Dependencias, resultado: ResultadoBusqueda, **kwargs) -> InsightDeMercado:
    return await d.redactor.redactar_insight(resultado, **kwargs)

async def generar_insight(d: Dependencias, resultado: ResultadoBusqueda, **kwargs) -> InsightDeMercado:
    return await d.redactor.redactar_insight(resultado, **kwargs)
