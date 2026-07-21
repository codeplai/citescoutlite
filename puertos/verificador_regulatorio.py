from typing import Protocol

class VerificadorRegulatorio(Protocol):
    def verificar(self, insumo_en: str, insumo_es: str) -> str:
        """
        Verifica un insumo en una base regulatoria y devuelve
        un resumen en texto plano de los hallazgos relevantes.
        """
        ...
