from typing import Protocol

from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.insight_mercado import InsightDeMercado
from dominio.insumo import InsumoInterpretado
from dominio.resultado_busqueda import ResultadoBusqueda


class RedactorLLM(Protocol):
    async def interpretar(self, texto: str) -> InsumoInterpretado:
        """Etapa 1."""
        ...

    async def redactar_insight(self, productos: ResultadoBusqueda,
                               mapa: dict | None = None) -> InsightDeMercado:
        """Etapa 3. Gratuita.

        Ya no recibe contexto regulatorio: el parrafo que produce es
        orientativo. El contexto con fuentes lo arma la etapa 5, dentro de si
        misma, y solo para el plan premium.

        `mapa` es el resumen acotado de la etapa 2b (S4): paises, marcas y una
        muestra de productos con sus ids. Va como dict y no como modelo porque
        entra en la clave de cache del ejecutor, que serializa los kwargs con
        json.dumps (ejecutor.py:41). Opcional: sin el, la etapa redacta como en
        S3 y ningun llamador antiguo se rompe.
        """
        ...

    async def formular_hipotesis(self, productos: ResultadoBusqueda) -> HipotesisFormulacion:
        """Etapa 4. Premium."""
        ...

    async def verificar_regulacion(self, insumo: str, contexto: str) -> DossierRegulatorio:
        """Etapa 5. Premium.

        `contexto` lo arma la propia etapa a partir de los verificadores, no
        quien la llama: asi entra en la clave de cache y en la auditoria.
        """
        ...
