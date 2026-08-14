"""
T7.2 — P-ADI: el validador que impide que este subsistema mienta en silencio.

## Por qué hace falta un validador y no basta con los tests

Los tests de T1 a T6 comprueban que el código hace lo que se le pidió **con las
entradas que se le dieron**. P-ADI comprueba otra cosa: que una respuesta
concreta, la que se le va a enseñar a una persona, **cumple las promesas del
sistema**. Son promesas que ningún test unitario puede vigilar porque dependen
del dato, no del código:

    P-ADI-1  Todo veredicto distinto de SIN_DATO trae URL y cita literal (D-5).
    P-ADI-2  Esa cita aparece de verdad en la fuente que dice citar (D-2).
    P-ADI-3  Cada aditivo trae exactamente los tres mercados, en orden.
    P-ADI-4  SIN_DATO no arrastra cifras: sin dato es sin dato, no «sin límite».
    P-ADI-5  Un límite interno nunca sale de un mercado que no autoriza.

La 2 es la que de verdad importa y la que ningún otro sitio puede comprobar. El
grounding de T1 valida la cita **en el momento de extraerla**; P-ADI la valida
otra vez **contra el corpus de hoy**, que es lo que detecta que una celda de
caché de hace ochenta días cite un texto que la FDA ya cambió.

## Qué se puede verificar y qué no, dicho sin disimulo

- **EE. UU.** — verificable. La sección está en el corpus local del título 21.
- **UE** — verificable. El uso está en el Anexo II ingerido.
- **Codex** — **no verificable por máquina.** Su fuente es una tabla que rellenó
  una persona, y el GSFA no se puede consultar automáticamente (ver
  `corpus_codex`). P-ADI comprueba su estructura pero no puede comprobar su
  contenido, y eso se declara en el resultado en vez de dejarlo pasar como si
  hubiera pasado un control que no existe.

Un validador que dijera «todo correcto» sobre una celda que no ha podido mirar
sería peor que no tener validador: daría por auditado lo que nadie auditó.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from dominio.analisis_aditivos import MERCADOS, AnalisisIngredientes

logger = logging.getLogger(__name__)

Regla = Literal["P-ADI-1", "P-ADI-2", "P-ADI-3", "P-ADI-4", "P-ADI-5"]

# Cuanto de la cita tiene que aparecer en la fuente para darla por buena.
#
# No se exige la cita entera: el texto que se guarda pasa por normalizaciones
# distintas segun el mercado —el XML del CFR aplana tablas, el HTML del Anexo II
# colapsa espacios— y exigir identidad literal produciria falsos positivos por
# un guion. Se comprueba un fragmento largo, que es imposible de acertar por
# casualidad y sobrevive a esas diferencias.
LONGITUD_FRAGMENTO = 40

_ESPACIOS = re.compile(r"\s+")


def _plegar(texto: str) -> str:
    texto = (texto or "").lower()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    return _ESPACIOS.sub(" ", re.sub(r"[^a-z0-9 ]", " ", texto)).strip()


@dataclass(frozen=True)
class Fallo:
    """Una promesa incumplida, con dónde y por qué."""

    regla: Regla
    aditivo: str
    mercado: str
    detalle: str

    def __str__(self) -> str:
        return f"[{self.regla}] {self.aditivo} / {self.mercado}: {self.detalle}"


@dataclass
class Resultado:
    """Lo que P-ADI encontró, y lo que no llegó a mirar."""

    fallos: list[Fallo]
    celdas: int
    verificadas: int
    #: Celdas cuya fuente no se puede consultar por máquina. Hoy, las del Codex.
    no_verificables: int

    @property
    def pasa(self) -> bool:
        return not self.fallos

    def resumen(self) -> str:
        return (f"{self.celdas} celdas · {self.verificadas} con cita comprobada "
                f"contra la fuente · {self.no_verificables} no verificables por "
                f"máquina · {len(self.fallos)} fallos")


def validar(analisis: AnalisisIngredientes, *, corpus_ecfr=None,
            corpus_anexo=None) -> Resultado:
    """Pasa P-ADI sobre un análisis. Sin red: todo sale de corpus locales.

    Los corpus se inyectan porque son de 21 MB y de 6 MB: quien valide muchos
    análisis seguidos debe cargarlos una vez, no una por análisis. Si no se
    pasan, la regla 2 no se comprueba y las celdas cuentan como no verificables
    — que es lo honesto, no lo cómodo.
    """
    fallos: list[Fallo] = []
    celdas = verificadas = no_verificables = 0

    for aditivo in analisis.aditivos:
        # P-ADI-3: los tres mercados, en su orden. El contrato ya lo impone al
        # construir, pero un análisis puede llegar deserializado de una caché o
        # de una API, y entonces nadie ha pasado por el validador de pydantic.
        vistos = [e.mercado for e in aditivo.evaluaciones]
        if vistos != list(MERCADOS):
            fallos.append(Fallo(
                "P-ADI-3", aditivo.nombre, ",".join(vistos) or "(vacío)",
                f"se esperaban {list(MERCADOS)} y llegaron {vistos}"))

        for evaluacion in aditivo.evaluaciones:
            celdas += 1
            mercado = evaluacion.mercado

            if evaluacion.autorizado == "SIN_DATO":
                # P-ADI-4: sin dato es sin dato. Una cifra aquí haría creer que
                # se sabe algo que no se sabe.
                if evaluacion.limite_valor is not None:
                    fallos.append(Fallo(
                        "P-ADI-4", aditivo.nombre, mercado,
                        f"SIN_DATO con límite {evaluacion.limite_valor}"))
                no_verificables += 1
                continue

            # P-ADI-1: sin URL y sin cita no hay veredicto publicable.
            if not evaluacion.referencia_url:
                fallos.append(Fallo("P-ADI-1", aditivo.nombre, mercado,
                                    "veredicto sin URL de referencia"))
            if not evaluacion.cita_literal.strip():
                fallos.append(Fallo("P-ADI-1", aditivo.nombre, mercado,
                                    "veredicto sin cita literal"))
                continue

            # P-ADI-2: la cita, contra la fuente de hoy.
            comprobada = _comprobar_cita(evaluacion, corpus_ecfr, corpus_anexo)
            if comprobada is None:
                no_verificables += 1
            elif comprobada is True:
                verificadas += 1
            else:
                fallos.append(Fallo(
                    "P-ADI-2", aditivo.nombre, mercado,
                    f"la cita no aparece en {evaluacion.referencia_texto}: "
                    f"{evaluacion.cita_literal[:70]!r}"))

        # P-ADI-5: el límite interno solo puede venir de quien autoriza.
        interno = aditivo.limite_interno
        if interno is not None:
            validos = {e.limite_valor for e in aditivo.evaluaciones
                       if e.autoriza and e.limite_valor is not None}
            if interno not in validos:
                fallos.append(Fallo(
                    "P-ADI-5", aditivo.nombre, "-",
                    f"límite interno {interno} no sale de ningún mercado que "
                    f"autorice (candidatos: {sorted(validos) or 'ninguno'})"))

    return Resultado(fallos, celdas, verificadas, no_verificables)


def _comprobar_cita(evaluacion, corpus_ecfr, corpus_anexo) -> bool | None:
    """`True` si la cita está en su fuente, `False` si no, `None` si no se sabe.

    Los tres valores son distintos y el tercero es el que hay que respetar: una
    celda del Codex no se puede comprobar contra nada, y devolver `True` por no
    tener con qué llevarle la contraria la daría por auditada.
    """
    fragmento = _plegar(evaluacion.cita_literal)[:LONGITUD_FRAGMENTO]
    if len(fragmento) < 10:
        # Una cita de menos de diez caracteres no distingue nada; se trata como
        # no comprobable en vez de darla por buena porque "cabe" en cualquier
        # sitio.
        return None

    if evaluacion.mercado == "US":
        if corpus_ecfr is None:
            return None
        seccion = corpus_ecfr.seccion(evaluacion.referencia_texto)
        return fragmento in _plegar(seccion.texto) if seccion else False

    if evaluacion.mercado == "EU":
        if corpus_anexo is None:
            return None
        # La cita de la UE es la restricción o la denominación de alguna de las
        # filas de uso de ese aditivo; se busca en todas porque la celda no
        # guarda cuál fue.
        numero = re.search(r"\bE\s?\d+[a-z]?\b", evaluacion.cita_literal or "")
        codigo = re.search(r"categoría\s+([\d.]+)",
                           evaluacion.referencia_texto or "")
        usos = corpus_anexo.usos(numero.group(0) if numero else "",
                                 codigo.group(1) if codigo else None)
        if not usos and codigo:
            # La cita puede venir de una fila de otra categoría (el caso
            # «autorizado en otras categorías»). Se amplía la búsqueda.
            usos = [u for us in corpus_anexo._por_e.values() for u in us
                    if u.categoria.rstrip(".") == codigo.group(1)]
        return any(fragmento in _plegar(f"{u.texto_fila} {u.restricciones}")
                   for u in usos) if usos else False

    # Codex: su fuente es una persona. Ver el docstring del módulo.
    return None
