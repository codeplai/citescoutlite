from casos_de_uso.dependencias import Dependencias
from dominio.insight_mercado import InsightDeMercado
from dominio.resultado_busqueda import ResultadoBusqueda


# Las dos son la misma llamada a proposito: el guard tecnico decide si el
# informe sale marcado como parcial, no cambia como se redacta el insight.
# Comparten entrada, etapa y modelo, asi que comparten clave de cache.
#
# `mapa` (S4, T4.2) es el resumen de la etapa 2b: paises y marcas reales, mas
# una muestra de productos con sus ids. Llega como kwarg, asi que entra en la
# clave de cache: dos runs con mapas distintos no comparten insight, que es lo
# correcto ahora que el mapa es material de cita.

async def generar_insight_parcial(d: Dependencias, resultado: ResultadoBusqueda,
                                  mapa: dict | None = None,
                                  **kwargs) -> InsightDeMercado:
    return await d.redactor.redactar_insight(resultado, mapa=mapa)


async def generar_insight(d: Dependencias, resultado: ResultadoBusqueda,
                          mapa: dict | None = None,
                          **kwargs) -> InsightDeMercado:
    return await d.redactor.redactar_insight(resultado, mapa=mapa)
