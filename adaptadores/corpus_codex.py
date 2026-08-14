"""
T3 — La celda del Codex: curación manual, y por qué no puede ser otra cosa.

## Las cuatro puertas cerradas

El GSFA (Norma General para los Aditivos Alimentarios, CXS 192-1995) es lo que
responde la columna del Codex. No hay forma automática y legítima de leerlo.
Sondeado el 2026-08-13 y de nuevo el 2026-08-14:

| Ruta | Resultado |
|---|---|
| `fao.org/gsfaonline/*` | **403** de Cloudflare. Y las fichas de detalle usan `?id=`, que el `robots.txt` de la FAO veta con `Disallow: /*?id=*` |
| Web Unlocker de Bright Data | **rechaza la petición**: «Requested site is not available for immediate residential (no KYC) access mode in accordance with robots.txt» |
| Enlace `sh-proxy` al PDF de la norma | **403** |
| `workspace.fao.org/.../CXS_192e.pdf` directo | **200, pero es una página de login de SharePoint**, no el PDF |

La segunda es la que zanja el asunto: hay un proveedor **de pago** negándose a
saltarse el `robots.txt` de la FAO. Es la decisión D-6 del plan, y vale aquí
igual que valió para no rastrear lo que el sitio pide que no se rastree.

## Lo que hace este módulo, entonces

Carga una tabla curada **por una persona**, y se toma en serio que esté curada.
Cada fila declara su `estado`:

- `VERIFICADO` — alguien abrió el GSFA, leyó la categoría y el límite, y anotó
  la URL y la fecha. Es la única que puede dar un `SI` limpio.
- `SECUNDARIA` — el dato viene de un documento interno (los PPTX de referencia),
  no del GSFA. **Nunca da `SI` a secas**: como mucho `SI_CONDICIONADO`, y la
  nota dice de dónde salió. Un dato de segunda mano no puede parecer de primera.
- `PENDIENTE` — nadie lo ha mirado todavía. Devuelve `SIN_DATO`.

`PENDIENTE` es el estado inicial de las 32 filas, y es lo correcto: una tabla
regulatoria vacía que lo dice es infinitamente mejor que una rellenada de
memoria. Rellenarla «porque el modelo se lo sabe» produciría 96 valores
plausibles, no verificables y con aspecto de curados — exactamente la clase de
dato contra la que se construyó el grounding de T1.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from dominio.analisis_aditivos import EvaluacionMercado

logger = logging.getLogger(__name__)

RUTA_CSV = Path("data/codex/gsfa_aditivos.csv")

# Donde una persona empieza a buscar. No es una cita: es el punto de entrada.
URL_GSFA = "https://www.fao.org/gsfaonline/index.html"
CITA_GENERICA = "Codex Alimentarius, GSFA (CXS 192-1995)"

Estado = Literal["VERIFICADO", "SECUNDARIA", "PENDIENTE"]
ESTADOS: frozenset[str] = frozenset({"VERIFICADO", "SECUNDARIA", "PENDIENTE"})

# Columnas que una fila resuelta tiene que traer sí o sí. Sin ellas no hay
# veredicto publicable (D-5): la URL es lo que separa esto de una opinión.
OBLIGATORIAS_SI_RESUELTA = (
    "autorizado", "referencia_texto", "referencia_url", "cita_literal",
    "verificado_por", "fecha_verificacion",
)


class FilaCodexInvalida(ValueError):
    """Una fila dice estar resuelta y le falta con qué demostrarlo."""


@dataclass(frozen=True)
class FilaCodex:
    """Una celda curada del GSFA para un aditivo."""

    e_number: str
    ins: str
    nombre: str
    estado: str
    categoria_gsfa: str | None = None
    categoria_nombre: str | None = None
    limite_valor: float | None = None
    limite_unidad: str | None = None
    autorizado: str | None = None
    referencia_texto: str | None = None
    referencia_url: str | None = None
    cita_literal: str | None = None
    nota: str | None = None
    verificado_por: str | None = None
    fecha_verificacion: str | None = None

    @property
    def resuelta(self) -> bool:
        return self.estado in ("VERIFICADO", "SECUNDARIA")


def _texto(valor: str | None) -> str | None:
    valor = (valor or "").strip()
    return valor or None


def _numero(valor: str | None) -> float | None:
    valor = (valor or "").strip().replace(" ", "").replace(",", ".")
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


def cargar(ruta: Path | str = RUTA_CSV) -> dict[str, FilaCodex]:
    """El CSV curado, validado. Falla ruidosamente si una fila miente.

    Validar al cargar y no al consultar es deliberado: el fallo aparece cuando
    alguien edita la tabla, que es cuando se puede arreglar, y no seis pantallas
    más adelante en forma de celda rara.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No está la tabla del Codex en {ruta}")

    filas: dict[str, FilaCodex] = {}
    with ruta.open(encoding="utf-8", newline="") as f:
        for n, cruda in enumerate(csv.DictReader(f), start=2):
            estado = (cruda.get("estado") or "PENDIENTE").strip().upper()
            if estado not in ESTADOS:
                raise FilaCodexInvalida(
                    f"{ruta}:{n}: estado {estado!r} desconocido. "
                    f"Esperado uno de {sorted(ESTADOS)}.")

            if estado != "PENDIENTE":
                faltan = [c for c in OBLIGATORIAS_SI_RESUELTA
                          if not (cruda.get(c) or "").strip()]
                if faltan:
                    raise FilaCodexInvalida(
                        f"{ruta}:{n}: la fila {cruda.get('e_number')} dice "
                        f"{estado} pero le faltan {faltan}. Una celda sin URL y "
                        f"sin cita no se puede publicar como veredicto (D-5).")

            fila = FilaCodex(
                e_number=(cruda["e_number"] or "").strip(),
                ins=(cruda.get("ins") or "").strip(),
                nombre=(cruda.get("nombre") or "").strip(),
                estado=estado,
                categoria_gsfa=_texto(cruda.get("categoria_gsfa")),
                categoria_nombre=_texto(cruda.get("categoria_nombre")),
                limite_valor=_numero(cruda.get("limite_valor")),
                limite_unidad=_texto(cruda.get("limite_unidad")),
                autorizado=_texto(cruda.get("autorizado")),
                referencia_texto=_texto(cruda.get("referencia_texto")),
                referencia_url=_texto(cruda.get("referencia_url")),
                cita_literal=_texto(cruda.get("cita_literal")),
                nota=_texto(cruda.get("nota")),
                verificado_por=_texto(cruda.get("verificado_por")),
                fecha_verificacion=_texto(cruda.get("fecha_verificacion")),
            )
            filas[fila.e_number] = fila

    resueltas = sum(1 for f in filas.values() if f.resuelta)
    logger.info("Codex: %d filas, %d resueltas, %d pendientes",
                len(filas), resueltas, len(filas) - resueltas)
    return filas


class EvaluadorCodex:
    """La celda del Codex. Sin red: es una tabla de 32 filas en memoria."""

    def __init__(self, filas: dict[str, FilaCodex] | None = None,
                 ruta: Path | str = RUTA_CSV):
        self._filas = filas if filas is not None else cargar(ruta)

    @property
    def filas(self) -> dict[str, FilaCodex]:
        return self._filas

    def cobertura(self) -> tuple[int, int]:
        """(resueltas, totales). Lo que la pantalla enseña como honestidad."""
        return sum(1 for f in self._filas.values() if f.resuelta), len(self._filas)

    def evaluar(self, e_number: str | None, nombre: str = "",
                matriz: str | None = None) -> EvaluacionMercado:
        fila = self._filas.get((e_number or "").strip()) if e_number else None

        if fila is None:
            return self._sin_dato(
                nombre, f"{e_number or nombre} no está en la tabla curada del GSFA")

        if not fila.resuelta:
            return self._sin_dato(
                fila.nombre,
                "pendiente de consultar en el GSFA. El sitio de la FAO no "
                "permite consulta automática, así que esta celda la rellena una "
                "persona")

        veredicto = fila.autorizado or "SIN_DATO"
        nota = fila.nota

        if fila.estado == "SECUNDARIA":
            # Un dato de segunda mano no puede parecer de primera. Se degrada
            # el veredicto limpio y se dice de dónde viene.
            if veredicto == "SI":
                veredicto = "SI_CONDICIONADO"
            procedencia = (f"Dato tomado de {fila.verificado_por}, un documento "
                           f"interno; no se ha verificado contra el GSFA.")
            nota = f"{nota} {procedencia}" if nota else procedencia

        return EvaluacionMercado(
            mercado="CODEX",
            autorizado=veredicto,
            limite_valor=fila.limite_valor,
            limite_unidad=fila.limite_unidad,
            categoria_alimento=(
                f"{fila.categoria_gsfa} {fila.categoria_nombre or ''}".strip()
                if fila.categoria_gsfa else None),
            referencia_texto=fila.referencia_texto or CITA_GENERICA,
            referencia_url=fila.referencia_url or URL_GSFA,
            cita_literal=fila.cita_literal or "",
            origen="CURADO_CODEX",
            nota=nota,
            verificado_en=_fecha(fila.fecha_verificacion),
        )

    @staticmethod
    def _sin_dato(nombre: str, motivo: str) -> EvaluacionMercado:
        logger.info("CODEX/%s -> SIN_DATO (%s)", nombre, motivo)
        return EvaluacionMercado(
            mercado="CODEX",
            autorizado="SIN_DATO",
            referencia_texto=CITA_GENERICA,
            referencia_url=URL_GSFA,
            cita_literal="",
            origen="CURADO_CODEX",
            nota=f"Sin dato del Codex: {motivo}.",
        )


def _fecha(texto: str | None):
    """La fecha de verificación, o ahora si la fila no la trae."""
    from datetime import datetime, timezone
    if not texto:
        return datetime.now(timezone.utc)
    try:
        return datetime.combine(date.fromisoformat(texto),
                                datetime.min.time(), tzinfo=timezone.utc)
    except ValueError:
        return datetime.now(timezone.utc)
