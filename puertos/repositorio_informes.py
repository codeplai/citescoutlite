from typing import Protocol
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from puertos.auditoria import Ejecucion

class RepositorioInformes(Protocol):
    def pide_reformulacion(self, ejecucion: Ejecucion) -> InformeScout:
        ...

    def emitir(self, ejecucion: Ejecucion, insight: InsightDeMercado, parcial: bool) -> InformeScout:
        ...
