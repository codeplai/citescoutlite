"""
T2.3 — La celda de la Unión Europea: del Anexo II a un veredicto.

## La columna que manda

De las 17.890 filas de uso ingeridas, la sexta columna —«Restricciones o
excepciones»— se reparte así (medido el 2026-08-14):

    52,0 %  vacía                      autorización limpia
    31,1 %  "solo …"                   restringida a ciertos alimentos
     6,2 %  "… excepto …"              excluye ciertos alimentos
     1,2 %  "solo … excepto …"         las dos cosas
     9,4 %  otras                      referencias cruzadas, coletillas

Casi el 40 % de las filas restringen por alimento. **Ignorar esa columna
convertiría el sistema en un generador de falsos «sí»**: E 200 aparece en la
categoría 04.2.4.1 con 1.000 mg/kg, y aun así la respuesta correcta para una
pulpa es que no está cubierta.

## Dónde este módulo se planta: no interpreta, señala

La restricción del caso 1 dice «… **excepto el puré**, la mousse, la compota,
las ensaladas y los productos similares en conserva». La matriz consultada es
«pulpa de maracuyá». Y **«pulpa» no aparece en esa frase**: que una pulpa sea un
«producto similar» al puré es un juicio de un tecnólogo de alimentos, razonable
y probablemente correcto, pero un juicio.

`acido1.pptx` lo hizo y concluyó `NO*`. Este módulo **no lo hace**: devuelve
`SI_CONDICIONADO` con la dosis, la restricción entera y una nota que dice qué
hay que confirmar. Es la misma información con la que el autor del PPTX decidió,
puesta delante de quien tiene que decidir.

Fingir la interpretación tendría dos formas y las dos son peores:

- **Sinónimos cableados** (pulpa→puré) — inventaría equivalencias regulatorias
  que nadie ha validado, y en cuanto una fuera discutible el error viajaría con
  aspecto de dato.
- **Pasárselo al modelo** — es la tentación fácil, y aquí no hay nada que
  *leer*: el texto ya está delante, entero y en dos líneas. Lo que falta no es
  lectura, es criterio regulatorio sobre un producto concreto. Un modelo
  produciría una respuesta segura de sí misma sobre exactamente la clase de
  pregunta que el proyecto promete no responder a ciegas.

Lo que sí se resuelve solo es la coincidencia **literal**: si la matriz nombra
algo que la cláusula excluye —«compota», «mermelada»— eso no es interpretar, es
leer, y entonces sí sale `NO_CONDICIONADO`.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from adaptadores.corpus_anexo_ii import (
    URL_CITA,
    CorpusAnexoII,
    UsoUE,
    _normaliza_e,
    corpus,
)
from dominio.analisis_aditivos import EvaluacionMercado

logger = logging.getLogger(__name__)

# Palabras de la matriz que no distinguen nada. Sin esto, «preparados de fruta»
# casaria con casi cualquier restriccion del anexo.
PALABRAS_VACIAS = {
    "de", "del", "la", "las", "el", "los", "y", "o", "con", "sin", "en", "a",
    "para", "producto", "productos", "alimento", "alimentos", "base",
}

_ESPACIOS = re.compile(r"\s+")

# La gramatica de la columna. `solo X, excepto Y` es la forma canonica; los dos
# trozos pueden aparecer sueltos.
_SOLO = re.compile(r"\bsolo\b(.*?)(?:\bexcepto\b|$)", re.I | re.S)
_EXCEPTO = re.compile(r"\bexcepto\b(.*)$", re.I | re.S)


def _plegar(texto: str) -> str:
    texto = (texto or "").lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    return _ESPACIOS.sub(" ", re.sub(r"[^a-z0-9 ]", " ", texto)).strip()


def terminos(matriz: str | None) -> set[str]:
    """Las palabras de la matriz que sirven para buscar en una cláusula."""
    if not matriz:
        return set()
    return {p for p in _plegar(matriz).split()
            if len(p) >= 4 and p not in PALABRAS_VACIAS}


def _menciona(clausula: str, terminos_matriz: set[str]) -> bool:
    """¿La cláusula nombra literalmente algo de la matriz?

    Coincidencia por prefijo de 4 letras para que «purés» case con «puré» y
    «mermeladas» con «mermelada». No va más allá: los sinónimos son juicio, no
    lectura, y este módulo no juzga.
    """
    plegada = _plegar(clausula)
    return any(re.search(rf"\b{re.escape(t[:5])}", plegada) for t in terminos_matriz)


def analizar_restriccion(restriccion: str,
                         terminos_matriz: set[str]) -> tuple[str, str | None]:
    """La restricción frente a la matriz: `(situacion, motivo)`.

    Situaciones: `sin_restriccion` · `excluido` · `incluido` · `indeterminado`.
    `indeterminado` es un resultado de primera clase y el más frecuente cuando
    la matriz viene del texto libre de OpenFoodFacts.
    """
    if not restriccion or not restriccion.strip():
        return "sin_restriccion", None

    excepto = _EXCEPTO.search(restriccion)
    if excepto and terminos_matriz and _menciona(excepto.group(1), terminos_matriz):
        return "excluido", f"la norma excluye: «{excepto.group(1).strip()[:120]}»"

    solo = _SOLO.search(restriccion)
    if solo and terminos_matriz and _menciona(solo.group(1), terminos_matriz):
        return "incluido", f"la norma lo limita a: «{solo.group(1).strip()[:120]}»"

    return "indeterminado", None


class EvaluadorUE:
    """Consulta local. Sin red y sin modelo: son 17.890 filas en memoria."""

    def __init__(self, corpus_local: CorpusAnexoII | None = None):
        self._corpus = corpus_local

    @property
    def corpus(self) -> CorpusAnexoII:
        if self._corpus is None:
            self._corpus = corpus()
        return self._corpus

    def evaluar(self, e_number: str | None, nombre: str = "",
                categoria_ue: str | None = None,
                matriz: str | None = None) -> EvaluacionMercado:
        """La celda de la UE para un aditivo en una matriz.

        `categoria_ue` es el código del Anexo II (04.2.4.1). Cuando no se sabe
        —que es lo normal, porque el snapshot trae texto libre— se consultan
        todas las categorías y el veredicto sale condicionado: se puede afirmar
        que el aditivo está autorizado en la UE, no en qué categoría cae este
        producto.
        """
        if not e_number:
            return self._sin_dato(nombre, "el aditivo no tiene número E asignado")

        clave = _normaliza_e(e_number)
        en_categoria = self.corpus.usos(clave, categoria_ue) if categoria_ue else []
        cualquiera = self.corpus.usos(clave)

        if not cualquiera:
            # El Anexo II es una lista positiva, así que no estar es un dato...
            # pero no se puede distinguir de un fallo de nuestra ingesta, y
            # confundir «no autorizado» con «no lo tenemos» es el error caro.
            return self._sin_dato(
                nombre, f"{clave} no aparece en el Anexo II ingerido")

        if categoria_ue and not en_categoria:
            uso = cualquiera[0]
            return self._celda(
                uso, "NO_CONDICIONADO", clave,
                nota=(f"Autorizado en la UE en otras categorías "
                      f"({len(cualquiera)}), pero no en la {categoria_ue}. "
                      f"Confirmar la clasificación exacta del producto."),
                cita=uso.restricciones or uso.denominacion)

        candidatos = en_categoria or cualquiera
        vistos = terminos(matriz)

        # Se prefiere la fila que resuelve la pregunta: primero una exclusión
        # literal, luego una inclusión literal, luego la de restricción vacía.
        # Sin este orden, un aditivo con veinte filas en la categoría devolvería
        # la primera que salga, que puede ser la que menos dice.
        ordenados = sorted(
            candidatos,
            key=lambda u: {"excluido": 0, "incluido": 1,
                           "sin_restriccion": 2, "indeterminado": 3}[
                analizar_restriccion(u.restricciones, vistos)[0]])
        uso = ordenados[0]
        situacion, motivo = analizar_restriccion(uso.restricciones, vistos)

        if situacion == "excluido":
            return self._celda(uso, "NO_CONDICIONADO", clave,
                               nota=f"{motivo}. Confirmar la clasificación del producto.",
                               cita=uso.restricciones)

        if situacion == "sin_restriccion":
            veredicto = "SI" if categoria_ue else "SI_CONDICIONADO"
            nota = None if categoria_ue else (
                "Autorizado en la UE. No se ha podido mapear la categoría de "
                "alimento de este producto, así que el límite aplicable depende "
                "de su clasificación exacta.")
            # La fila tal cual la escribe el Anexo II, no un resumen montado con
            # puntuación propia. Ver `UsoUE.texto_fila`: la versión compuesta
            # («E 440 — Pectinas: quantum satis») no aparecía en el documento y
            # P-ADI-2 la rechazaba, con razón.
            return self._celda(uso, veredicto, clave, nota=nota,
                               cita=uso.texto_fila or uso.denominacion)

        if situacion == "incluido":
            return self._celda(uso, "SI" if categoria_ue else "SI_CONDICIONADO",
                               clave, nota=motivo, cita=uso.restricciones)

        # Indeterminado: hay restricción y no se puede resolver leyendo. Es el
        # caso de la pulpa frente a «excepto el puré», y sale con el texto
        # entero para que decida quien sabe. Ver el docstring del módulo.
        return self._celda(
            uso, "SI_CONDICIONADO", clave,
            nota=("El uso está restringido por tipo de alimento y no se ha "
                  "podido determinar si este producto queda dentro. Leer la "
                  "restricción completa antes de asumir cobertura."),
            cita=uso.restricciones)

    # -- construcción de la celda ------------------------------------------

    @staticmethod
    def _celda(uso: UsoUE, veredicto: str, e_number: str,
               nota: str | None, cita: str) -> EvaluacionMercado:
        return EvaluacionMercado(
            mercado="EU",
            autorizado=veredicto,
            limite_valor=uso.dosis_valor,
            limite_unidad=uso.dosis_unidad,
            categoria_alimento=f"{uso.categoria.rstrip('.')} {uso.categoria_nombre}",
            referencia_texto=uso.cita,
            referencia_url=URL_CITA,
            cita_literal=cita or uso.denominacion,
            origen="ANEXO_II",
            nota=_matiz_de_via(uso, nota),
        )

    @staticmethod
    def _sin_dato(nombre: str, motivo: str) -> EvaluacionMercado:
        logger.info("EU/%s -> SIN_DATO (%s)", nombre, motivo)
        return EvaluacionMercado(
            mercado="EU",
            autorizado="SIN_DATO",
            referencia_texto="Reglamento (CE) 1333/2008, Anexo II",
            referencia_url=URL_CITA,
            cita_literal="",
            origen="ANEXO_II",
            nota=f"No se pudo verificar contra el Anexo II: {motivo}",
        )


def _matiz_de_via(uso: UsoUE, nota: str | None) -> str | None:
    """Añade de dónde sale la cobertura cuando no es una fila con su número E.

    Importa: `E 200-203` y `Grupo I` cubren al aditivo por **designación
    colectiva**, y esa derivación la hace este sistema leyendo la Parte B, no la
    norma escribiéndola. Quien lea la celda tiene derecho a saberlo.
    """
    if uso.via == "directo":
        return nota
    origen = (f"la fila del Anexo II es «{uso.entrada} — {uso.denominacion}», "
              f"que cubre a este aditivo por designación colectiva")
    return f"{nota} ({origen})." if nota else f"Cobertura indirecta: {origen}."
