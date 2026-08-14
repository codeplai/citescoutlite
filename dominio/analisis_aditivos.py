"""
T1 (análisis de ingredientes): contrato del veredicto regulatorio por mercado.

Se adelanta desde T4.1 del plan porque T1 no puede devolver nada sin él: el
agente del eCFR produce `EvaluacionMercado`, y sin el tipo no hay dónde
ponerlo.

## La distinción que sostiene este módulo: el veredicto es del PAR

No es del aditivo. Es del par **(aditivo × categoría de alimento)**, y los dos
casos de referencia (`acido1.pptx`, `acido2.pptx`) lo enseñan por partida doble:

- El ácido sórbico **no está prohibido en la UE**. Está autorizado — pero la
  categoría que lo autoriza (04.2.4.1) excluye purés, y el producto era pulpa
  de maracuyá. Veredicto `NO_CONDICIONADO`.
- El EDTA sale limpio en EE. UU. porque 21 CFR §172.120 **nombra los pepinos
  encurtidos** en su tabla, con 220 ppm. En Codex solo hay cobertura por
  categoría general (04.2.2.4), así que ahí es `SI_CONDICIONADO`.

Por eso `autorizado` tiene cinco valores y no dos. **El asterisco de las
diapositivas de referencia es `SI_CONDICIONADO` / `NO_CONDICIONADO`**: no es un
adorno tipográfico, es el estado de "el aditivo sí, pero de tu categoría no
tenemos confirmación". Colapsarlo a SÍ/NO haría más simple la pantalla y
mentiría en los dos casos que la originaron.

## Por qué `cita_literal` es obligatoria

Es la mitad del grounding (D-2 del plan). El agente puede afirmar un límite
solo si consigue copiar el fragmento donde ese límite aparece, y ese fragmento
se comprueba después contra el texto de la norma. Un número sin cita es un
número inventado con buena presentación, que en materia regulatoria es la peor
clase de dato posible.

La otra mitad la da la arquitectura, no una comprobación: **el modelo nunca
produce la referencia**. `referencia_texto` y `referencia_url` se construyen a
partir del identificador de sección con el que se pidió el documento, así que
una cita a una norma que no existe es imposible por construcción.
"""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

Mercado = Literal["US", "CODEX", "EU"]

#: Los tres mercados, en el orden en que se leen: el propio, el internacional y
#: el destino europeo. La pantalla pinta las tarjetas en este orden y el
#: contrato lo fija aquí para que no dependa de cómo itere quien las construya.
MERCADOS: tuple[Mercado, ...] = ("US", "CODEX", "EU")

Veredicto = Literal[
    "SI",                # autorizado y la categoría del producto está nombrada
    "SI_CONDICIONADO",   # autorizado, pero la cobertura de la categoría no consta
    "NO",                # no autorizado para este uso
    "NO_CONDICIONADO",   # autorizado en otras categorías, no en la del producto
    "SIN_DATO",          # no se pudo comprobar. NUNCA equivale a "no autorizado"
]

#: Veredictos que cuentan como "este mercado deja usarlo". Se define una vez
#: aquí porque `limite_interno` y la pantalla tienen que estar de acuerdo sobre
#: qué es autorizar; dos listas separadas acaban discrepando.
AUTORIZAN: frozenset[str] = frozenset({"SI", "SI_CONDICIONADO"})


class EvaluacionMercado(BaseModel):
    """Lo que un mercado dice sobre un aditivo en una matriz concreta."""

    mercado: Mercado
    autorizado: Veredicto

    limite_valor: float | None = Field(
        default=None,
        description="None cuando el límite es BPM (sin cifra) o no hay dato. "
                    "Que sea None NO significa 'sin límite': significa 'sin "
                    "cifra', y cuál de las dos cosas es lo dice limite_unidad",
    )
    limite_unidad: Literal["mg/kg", "ppm", "BPM", "N/A"] | None = Field(
        default=None,
        description="'BPM' es un límite real (buenas prácticas, sin cifra); "
                    "'N/A' es que no aplica; None es que no se sabe",
    )
    categoria_alimento: str | None = Field(
        default=None,
        description="Código GSFA o de Anexo II, o el alimento nombrado en la "
                    "norma ('Cucumbers pickled'). None = no consta",
    )

    # --- La parte verificable. Ver el docstring del módulo. ---
    referencia_texto: str = Field(
        description="Cita corta: '21 CFR § 172.120'. La construye el adaptador "
                    "desde el id de sección, nunca el modelo",
    )
    referencia_url: HttpUrl = Field(
        description="Enlace a la fuente oficial. Sin URL no se pinta veredicto",
    )
    cita_literal: str = Field(
        default="",
        description="Fragmento textual de la norma que sostiene el límite. "
                    "Vacío solo si autorizado == 'SIN_DATO'",
    )

    origen: Literal["AGENTE_ECFR", "ANEXO_II", "CURADO_CODEX", "CACHE"] = Field(
        description="Qué mecanismo produjo esta celda. Va a la pantalla: no es "
                    "lo mismo una cita traída del eCFR hace un minuto que una "
                    "celda curada a mano en agosto",
    )
    verificado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Cuándo se comprobó contra la fuente",
    )
    nota: str | None = Field(
        default=None,
        description="El porqué del asterisco, en una frase que se lee al pie "
                    "de la tarjeta",
    )

    @field_validator("cita_literal")
    @classmethod
    def _sin_espacios_de_mas(cls, v: str) -> str:
        return " ".join(v.split())

    @model_validator(mode="after")
    def _un_veredicto_exige_su_prueba(self) -> "EvaluacionMercado":
        """D-2 y D-5 como invariante del tipo, no como buena intención.

        Se comprueba aquí y no solo en el test porque este objeto lo van a
        construir tres adaptadores distintos (agente, Anexo II, curación) y
        el sitio barato de olvidarse de la cita es el tercero.
        """
        if self.autorizado != "SIN_DATO" and not self.cita_literal:
            raise ValueError(
                f"{self.mercado}: veredicto '{self.autorizado}' sin cita "
                f"literal. Un veredicto sin la frase que lo sostiene no se "
                f"puede publicar (D-2)."
            )
        if self.autorizado == "SIN_DATO" and self.limite_valor is not None:
            raise ValueError(
                f"{self.mercado}: SIN_DATO no puede traer límite numérico."
            )
        return self

    @property
    def autoriza(self) -> bool:
        return self.autorizado in AUTORIZAN

    @property
    def condicionado(self) -> bool:
        """Si la pantalla tiene que pintarle el asterisco."""
        return self.autorizado.endswith("_CONDICIONADO")


class AditivoEvaluado(BaseModel):
    """Un aditivo de la etiqueta, visto por los tres mercados a la vez."""

    nombre: str = Field(description="Nombre canónico en castellano")
    ins: str | None = Field(default=None, description="Código INS del Codex: '200'")
    e_number: str | None = Field(default=None, description="Número E: 'E200'")
    funcion: str | None = Field(
        default=None, description="Función tecnológica: 'Conservante'")

    evaluaciones: list[EvaluacionMercado] = Field(
        description="Exactamente 3, una por mercado, siempre y en el orden de "
                    "MERCADOS",
    )

    @model_validator(mode="after")
    def _siempre_los_tres(self) -> "AditivoEvaluado":
        """Un mercado sin dato es una evaluación SIN_DATO, no una lista corta.

        Es la invariante que más protege al lector: una tarjeta que falta se
        lee como «no aplica», y lo que de verdad pasa es «no lo sabemos». Son
        cosas distintas y la pantalla solo puede distinguirlas si el dato llega
        distinguido.
        """
        vistos = [e.mercado for e in self.evaluaciones]
        if list(MERCADOS) != vistos:
            raise ValueError(
                f"'{self.nombre}': se esperaban los mercados {list(MERCADOS)} "
                f"en ese orden y llegaron {vistos}. Un mercado sin dato va como "
                f"EvaluacionMercado(autorizado='SIN_DATO'), no se omite."
            )
        return self

    def por_mercado(self, mercado: Mercado) -> EvaluacionMercado:
        return next(e for e in self.evaluaciones if e.mercado == mercado)

    @property
    def limite_interno(self) -> float | None:
        """El más estricto entre los mercados que SÍ autorizan, en mg/kg.

        Es el paso 6 de la metodología: adoptarlo permite una sola formulación
        para varios destinos. Tres cosas que la implementación decide y conviene
        no re-decidir en otra parte:

        - **ppm y mg/kg son la misma unidad** en base másica (1 ppm = 1 mg/kg),
          así que se comparan directamente. No se convierte nada.
        - **BPM no participa del mínimo.** Un mercado que dice "buenas prácticas,
          sin cifra" no impone techo numérico; si fuera 0 o infinito el mínimo
          saldría mal en un sentido o en el otro. Simplemente no vota.
        - **Los mercados que NO autorizan tampoco votan.** Su respuesta no es un
          límite bajo, es una reformulación obligatoria, y mezclarlas
          convertiría una prohibición en un número.
        """
        cifras = [
            e.limite_valor for e in self.evaluaciones
            if e.autoriza and e.limite_valor is not None
            and e.limite_unidad in ("mg/kg", "ppm")
        ]
        return min(cifras) if cifras else None

    @property
    def limite_interno_unidad(self) -> str | None:
        return "mg/kg" if self.limite_interno is not None else None

    @property
    def exige_reformular(self) -> bool:
        """Algún mercado lo prohíbe: no es un límite, es rediseñar el producto."""
        return any(
            e.autorizado in ("NO", "NO_CONDICIONADO") for e in self.evaluaciones
        )


class AnalisisIngredientes(BaseModel):
    """Lo que la pestaña de análisis enseña para una fila del mapa comercial."""

    producto_id: str = Field(description="Id con prefijo de fuente: 'OFF:00000036'")
    producto_nombre: str

    matriz: str | None = Field(
        default=None,
        description="La categoría tal cual la trae la etiqueta. 8.322 valores "
                    "distintos en el snapshot: es texto libre, no un código",
    )
    matriz_ue: str | None = Field(
        default=None,
        description="Código de categoría del Anexo II (04.2.4.1), deducido de "
                    "la etiqueta por `etl.mapear_categoria`. None = no se pudo",
    )
    # Se llamaba `matriz_gsfa` y era un nombre equivocado: el Codex y la UE
    # **comparten la raíz de la numeración y divergen en la hoja**. El 04.1.2.8
    # que cita `acido1.pptx` es un código del GSFA y no existe entre las 116
    # categorías del Anexo II. Son dos vocabularios, y aquí solo se deriva el
    # europeo, que es el único que hoy consume alguien (`EvaluadorUE`). Cuando
    # el Codex necesite el suyo irá en un campo propio, no reutilizando este.

    aditivos: list[AditivoEvaluado] = Field(
        default_factory=list,
        description="Vacío es un resultado válido y frecuente: el 49,8 % de las "
                    "filas del snapshot no lleva ningún aditivo reconocido. No "
                    "es un error ni un hueco, es una etiqueta limpia",
    )
    no_reconocidos: list[str] = Field(
        default_factory=list,
        description="Ingredientes que no se supieron clasificar. Se enseñan "
                    "para que se vea hasta dónde llega la lectura",
    )

    generado_en: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc))

    @property
    def hay_prohibiciones(self) -> bool:
        return any(a.exige_reformular for a in self.aditivos)

    def mercados_que_prohiben(self) -> list[Mercado]:
        """Para el bloque de conclusiones: dónde hay que reformular."""
        return [
            m for m in MERCADOS
            if any(a.por_mercado(m).autorizado in ("NO", "NO_CONDICIONADO")
                   for a in self.aditivos)
        ]
