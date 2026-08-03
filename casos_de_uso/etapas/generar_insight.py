from casos_de_uso.dependencias import Dependencias
from dominio.insight_mercado import InsightDeMercado
from dominio.resultado_busqueda import ResultadoBusqueda


# Las dos son la misma llamada a proposito: el guard tecnico decide si el
# informe sale marcado como parcial, no cambia como se redacta el insight.
# Comparten entrada, etapa y modelo, asi que comparten clave de cache.

async def generar_insight_parcial(d: Dependencias, resultado: ResultadoBusqueda,
                                  **kwargs) -> InsightDeMercado:
    return await d.redactor.redactar_insight(resultado)


async def generar_insight(d: Dependencias, resultado: ResultadoBusqueda,
                          **kwargs) -> InsightDeMercado:
    return await d.redactor.redactar_insight(resultado)
