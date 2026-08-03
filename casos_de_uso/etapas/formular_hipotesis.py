"""
Etapa 4 - Hipotesis de formulacion. Premium.

Hasta S2 esto era el campo `hipotesis_formulacion` del insight, generado por la
misma llamada al modelo que el resumen gratuito. Como etapa propia pasa por
`etapa()`, asi que tiene cache, auditoria, modelo y **costo propio**: sin eso,
el paywall solo podria recortar un texto ya pagado.
"""

from casos_de_uso.dependencias import Dependencias
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.resultado_busqueda import ResultadoBusqueda


async def formular_hipotesis(d: Dependencias, resultado: ResultadoBusqueda,
                             **kwargs) -> HipotesisFormulacion:
    return await d.redactor.formular_hipotesis(resultado)
