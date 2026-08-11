"""
S7.3 - Validador de reglas (anti-garbage).

Comprueba una oferta de `staging_agente` contra las reglas que CITE tenga
encendidas en `promotion_rules`. Funciones puras: las reglas y la oferta
entran como argumentos, y no se toca la base aquí.

Sobre las reglas que no se pueden evaluar
-----------------------------------------
Tres de las seis reglas base describen datos que el sistema todavía no tiene
(precio histórico por producto, stock en unidades, clasificación de tienda).
Vienen apagadas de fábrica, pero CITE puede encenderlas desde el panel.

Cuando eso pasa, la oferta **no pasa** y el motivo lo dice. La alternativa
—dar la regla por cumplida— seria peor de lo que parece: la promoción
automática seguiria corriendo y el informe diria que se valido el precio
contra el histórico cuando nadie lo miro. Rechazar es recuperable (queda el
20 % manual y el log dice exactamente qué regla sobra); aprobar en falso, no.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(frozen=True)
class Regla:
    """Una fila de promotion_rules."""
    nombre: str
    expresion: dict[str, Any]
    activo: bool = True


@dataclass(frozen=True)
class ErrorValidacion:
    """Por qué una regla rechazó la oferta."""
    regla: str
    motivo: str
    valor: str | None = None

    def to_json(self) -> dict:
        return {"regla": self.regla, "motivo": self.motivo, "valor": self.valor}


@dataclass
class ResultadoValidacion:
    passed: bool = False
    errores: list[ErrorValidacion] = field(default_factory=list)
    reglas_evaluadas: list[str] = field(default_factory=list)

    def errores_json(self) -> list[dict]:
        return [e.to_json() for e in self.errores]


# --- Evaluadores por tipo de regla ------------------------------------------
#
# Cada uno recibe (oferta, expresion) y devuelve un ErrorValidacion o None.
# La oferta es una fila de staging_agente ya en dict.


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _evaluar_frescura(oferta: dict, expresion: dict) -> ErrorValidacion | None:
    max_dias = expresion.get("max_dias", 7)
    creado_en = oferta.get("creado_en")

    if creado_en is None:
        return ErrorValidacion("dato_fresco", "La oferta no tiene fecha de captura")

    if creado_en.tzinfo is None:
        creado_en = creado_en.replace(tzinfo=timezone.utc)

    dias = (_ahora() - creado_en).days
    if dias > max_dias:
        return ErrorValidacion(
            "dato_fresco", f"Dato de hace {dias} días (máximo {max_dias})", str(dias))
    return None


def _evaluar_url(oferta: dict, expresion: dict) -> ErrorValidacion | None:
    url = (oferta.get("fuente_url") or "").strip()
    if not url:
        return ErrorValidacion("url_presente", "Sin URL de origen")
    if not url.startswith(("http://", "https://")):
        return ErrorValidacion("url_presente", "La URL no es http(s)", url[:80])
    return None


def _evaluar_grounding(oferta: dict, expresion: dict) -> ErrorValidacion | None:
    estado = oferta.get("grounding_check_status")

    # Ausente no es lo mismo que fallido, pero tampoco es aprobado: significa
    # que nadie comprobó que los valores estuvieran en el HTML.
    if not estado:
        return ErrorValidacion(
            "grounding_ok", "Sin grounding check: no se verificó contra el HTML")

    if not estado.get("passed"):
        campos = [e.get("campo") for e in (estado.get("errores") or [])]
        detalle = ", ".join(c for c in campos if c) or "sin detalle"
        return ErrorValidacion(
            "grounding_ok", f"Grounding check falló en: {detalle}")
    return None


def _no_evaluable(motivo: str) -> Callable[[dict, dict], ErrorValidacion | None]:
    """Evaluador para reglas cuyo dato no existe todavía en el sistema."""
    def evaluador(oferta: dict, expresion: dict) -> ErrorValidacion | None:
        return ErrorValidacion("regla_no_evaluable", motivo)
    return evaluador


EVALUADORES: dict[str, Callable[[dict, dict], ErrorValidacion | None]] = {
    "date_freshness": _evaluar_frescura,
    "url_presente": _evaluar_url,
    "grounding_ok": _evaluar_grounding,
    # Las tres de abajo estan escritas y apagadas en promotion_rules. Si
    # alguien las enciende, esto explica por que no se puede cumplir en vez de
    # dejar pasar la oferta como si se hubiera comprobado.
    "price_range": _no_evaluable(
        "No hay serie de precios por producto: tendencias_insumo es por insumo "
        "y trimestre, no por oferta"),
    "stock": _no_evaluable(
        "El stock en unidades casi nunca aparece en la ficha, y el extractor "
        "deja null cuando no lo ve"),
    "tienda_class": _no_evaluable(
        "No hay clasificación de tienda; habría que derivarla del dominio de "
        "fuente_url"),
}


def validar_oferta(oferta: dict, reglas: list[Regla]) -> ResultadoValidacion:
    """Comprueba una oferta contra las reglas activas.

    Args:
        oferta: fila de staging_agente como dict (creado_en, fuente_url,
            producto_json, grounding_check_status...).
        reglas: las de promotion_rules. Las inactivas se ignoran.

    Returns:
        ResultadoValidacion con el veredicto y un error por cada regla que no
        se cumplio. Se evaluan TODAS las reglas activas, no se corta en la
        primera: si se cortara, CITE tendria que promover y fallar una y otra
        vez para descubrir todo lo que le falta a una oferta.
    """
    resultado = ResultadoValidacion()

    for regla in reglas:
        if not regla.activo:
            continue

        resultado.reglas_evaluadas.append(regla.nombre)
        tipo = regla.expresion.get("tipo")
        evaluador = EVALUADORES.get(tipo)

        if evaluador is None:
            resultado.errores.append(ErrorValidacion(
                regla.nombre,
                f"Tipo de regla desconocido: {tipo!r}. Revisar la expresión."))
            continue

        error = evaluador(oferta, regla.expresion)
        if error is not None:
            # El evaluador nombra la regla generica ('dato_fresco'); se
            # sustituye por el nombre real de la fila, que es el que CITE ve en
            # el panel y puede haber renombrado.
            resultado.errores.append(ErrorValidacion(
                regla.nombre, error.motivo, error.valor))

    resultado.passed = not resultado.errores
    return resultado
