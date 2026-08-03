from typing import Protocol

from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from puertos.auditoria import Ejecucion


class RepositorioInformes(Protocol):
    def pide_reformulacion(self, ejecucion: Ejecucion) -> InformeScout:
        ...

    def emitir(self, ejecucion: Ejecucion, insight: InsightDeMercado | None,
               parcial: bool,
               hipotesis: HipotesisFormulacion | None = None,
               dossier: DossierRegulatorio | None = None) -> InformeScout:
        """Compone el informe con lo que haya.

        `hipotesis` y `dossier` llegan a None en el plan gratuito: no es que
        fallaran, es que no se ejecutaron sus etapas. La plantilla los sustituye
        por el bloque de paywall.

        `insight` puede ser None si el presupuesto se agoto antes de la etapa 3
        (T6.3). Tambien entonces se emite informe: degradar a "sin dato", nunca
        a error.
        """
        ...
