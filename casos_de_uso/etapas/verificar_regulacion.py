"""
Etapa 5 - Dossier regulatorio con citas verificables. Premium.

Aqui se salda la parte mas concreta de la deuda de S1: el armado del contexto
regulatorio vivia en evaluar_insumo, **fuera** del envoltorio `etapa()`. Eso
significaba que las consultas a openFDA y al RAG normativo no se auditaban, no
se cacheaban y no tenian costo asignado, pese a ser la parte cara de la etapa.

Ahora el contexto se arma dentro. Consecuencias, todas buscadas:

  - entra en la clave de cache, asi que un segundo run identico no vuelve a
    embeber la consulta ni a buscar en LanceDB;
  - queda en `etapas_ejecucion` con su duracion;
  - si el corpus no tiene nada aplicable, la etapa devuelve `sin_dato=True` en
    vez de un error. El principio del ADR es degradar a "sin dato", nunca a
    error.
"""

from casos_de_uso.dependencias import Dependencias
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.insumo import InsumoInterpretado


def _contexto_regulatorio(d: Dependencias, interpretado: InsumoInterpretado,
                          texto: str) -> str:
    """Consulta openFDA y el RAG normativo. Lo que antes hacia evaluar_insumo."""
    partes = []
    if d.verificador_fda:
        insumo_en = (interpretado.terminos_ingles[0] if interpretado.terminos_ingles
                     else interpretado.insumo_normalizado)
        partes.append(d.verificador_fda.verificar(insumo_en, texto))
    if d.verificador_rag:
        partes.append(d.verificador_rag.verificar(interpretado.insumo_normalizado, texto))
    return "\n\n".join(p for p in partes if p)


async def verificar_regulacion(d: Dependencias, interpretado: InsumoInterpretado,
                               texto: str = "", **kwargs) -> DossierRegulatorio:
    contexto = _contexto_regulatorio(d, interpretado, texto)

    if not contexto.strip():
        # Sin verificadores configurados no hay nada que citar. Devolver un
        # dossier vacio marcado es honesto; inventarlo con el modelo, no.
        return DossierRegulatorio(restricciones=[], citas=[], sin_dato=True)

    return await d.redactor.verificar_regulacion(
        interpretado.insumo_normalizado, contexto)
