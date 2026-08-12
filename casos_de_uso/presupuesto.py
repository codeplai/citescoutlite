"""
T6.3 - Tres presupuestos y un kill-switch.

Se consulta **antes de cada etapa LLM**, no despues: el objetivo es no gastar,
no enterarse de lo gastado.

| Nivel        | Variable                      | Al superarse                       |
|--------------|-------------------------------|------------------------------------|
| Manual (S8.5)| `sistema_config.kill_switch`  | un admin lo acciono: nadie gasta   |
| Run          | PRESUPUESTO_RUN_USD           | se saltan las etapas restantes     |
| Usuario/mes  | PRESUPUESTO_USUARIO_MES_USD   | idem, desde `uso_mensual`          |
| Global/mes   | PRESUPUESTO_GLOBAL_MES_USD    | tope de gasto: nadie ejecuta LLM   |

El de arriba es de S8.5 y es de otra naturaleza que los otros tres: no se
deduce de ninguna cifra, lo acciona una persona. Por eso llega como un dato
—`parada_manual`— y no se calcula aqui: este modulo es aritmetica sobre topes y
no sabe leer una tabla. Quien lo lee es `atender_consulta`, que ya es la
frontera donde se resuelven el entitlement y el contexto.

Al degradar, la etapa devuelve su contrato con `sin_dato=True`, el run cierra en
`parcial` con `motivo_parcial='presupuesto'` y **la respuesta es 200**. Sin
reintento automatico. El principio del ADR es degradar a "sin dato", nunca a
error: un tope de gasto es una decision de negocio, no un fallo del sistema, y
un 500 se lo contaria al usuario como si lo fuera.

El gasto del mes se lee una vez al empezar el run y se lleva en memoria. No hace
falta releerlo: la auditoria escribe el run entero al cerrar (ver
adaptadores/auditoria_postgres), asi que durante el run los totales del mes no
se mueven.
"""

import os
from dataclasses import dataclass

from puertos.suscripciones import ContextoSuscripcion

MOTIVO = "presupuesto"


def _tope(variable: str, defecto: float) -> float:
    """Un tope ilegible no puede valer 'sin limite': se cae al defecto."""
    try:
        return float(os.getenv(variable, defecto))
    except (TypeError, ValueError):
        return defecto


@dataclass
class Presupuesto:
    """Contador de un solo run. **No se comparte entre peticiones**: se crea uno
    por run y se inyecta en una copia de Dependencias."""

    tope_run_usd: float
    tope_usuario_mes_usd: float
    tope_global_mes_usd: float
    gasto_usuario_mes_usd: float = 0.0
    gasto_global_mes_usd: float = 0.0
    gasto_run_usd: float = 0.0
    # S8.5. Por defecto False: quien construya un Presupuesto sin saber que
    # existe el interruptor obtiene el comportamiento de antes, y ningun run se
    # para por un dato que nadie le paso.
    parada_manual: bool = False

    @classmethod
    def desde_entorno(cls, contexto: ContextoSuscripcion,
                      tope_usuario_mes_usd: float | None = None,
                      parada_manual: bool = False) -> "Presupuesto":
        return cls(
            parada_manual=parada_manual,
            tope_run_usd=_tope("PRESUPUESTO_RUN_USD", 0.25),
            # El tope mensual del usuario lo fija su plan (T6.1); la variable de
            # entorno es solo el valor por defecto del plan gratuito.
            tope_usuario_mes_usd=(tope_usuario_mes_usd
                                  if tope_usuario_mes_usd is not None
                                  else _tope("PRESUPUESTO_USUARIO_MES_USD", 2.0)),
            tope_global_mes_usd=_tope("PRESUPUESTO_GLOBAL_MES_USD", 10.0),
            gasto_usuario_mes_usd=contexto.gasto_usuario_mes_usd,
            gasto_global_mes_usd=contexto.gasto_global_mes_usd,
        )

    # -- consulta -----------------------------------------------------------

    def nivel_agotado(self) -> str | None:
        """Que corta el gasto, o None si se puede gastar.

        Se comparan los gastos del mes **mas lo que lleve el run**: si no, un
        run largo podria pasarse del tope mensual dentro de si mismo sin que
        ningun nivel se diera por enterado.
        """
        # Primero, y con nombre propio. Va delante porque una decision humana
        # no la discute ninguna cifra: si un administrador ha parado el gasto,
        # da igual cuanto quede de presupuesto.
        #
        # Y con nombre propio —'manual' y no 'global_mes'— porque el motivo se
        # le enseña a quien recibe el informe degradado: "se paro el gasto" y
        # "se acabo el presupuesto del mes" no son la misma noticia, ni llevan
        # a la misma accion.
        if self.parada_manual:
            return "manual"
        if self.gasto_global_mes_usd + self.gasto_run_usd >= self.tope_global_mes_usd:
            return "global_mes"
        if self.gasto_usuario_mes_usd + self.gasto_run_usd >= self.tope_usuario_mes_usd:
            return "usuario_mes"
        if self.gasto_run_usd >= self.tope_run_usd:
            return "run"
        return None

    @property
    def agotado(self) -> bool:
        return self.nivel_agotado() is not None

    # -- registro -----------------------------------------------------------

    def anotar(self, costo_usd: float) -> None:
        """Suma lo que acaba de costar una etapa. Un cache hit cuesta 0 y por
        tanto no acerca el run a ningun tope: es exactamente lo que se quiere."""
        self.gasto_run_usd += max(0.0, float(costo_usd or 0.0))

    def resumen(self) -> dict:
        return {
            "nivel_agotado": self.nivel_agotado(),
            "parada_manual": self.parada_manual,
            "gasto_run_usd": round(self.gasto_run_usd, 6),
            "tope_run_usd": self.tope_run_usd,
            "gasto_usuario_mes_usd": round(self.gasto_usuario_mes_usd, 6),
            "tope_usuario_mes_usd": self.tope_usuario_mes_usd,
            "gasto_global_mes_usd": round(self.gasto_global_mes_usd, 6),
            "tope_global_mes_usd": self.tope_global_mes_usd,
        }
