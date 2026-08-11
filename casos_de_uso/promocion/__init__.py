"""S7 - Promoción de ofertas desde la cuarentena."""

from .validador import (
    ErrorValidacion,
    Regla,
    ResultadoValidacion,
    validar_oferta,
)

__all__ = [
    "ErrorValidacion",
    "Regla",
    "ResultadoValidacion",
    "validar_oferta",
]
