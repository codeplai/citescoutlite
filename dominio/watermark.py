"""
S7.1 - Watermark binario: qué ofertas entran en la promoción automática.

La idea de S7 es que el 80 % de lo que el agente deja en cuarentena se
promueva solo y el 20 % restante lo revise una persona. Este módulo decide, de
forma determinista, en qué mitad cae cada oferta.

Determinista y no aleatorio a propósito: la misma oferta debe caer siempre del
mismo lado dentro de una semana. Si se sorteara en cada pasada, un reintento
del job podría promover automáticamente algo que la vez anterior mandó a
revisión manual, y la auditoría dejaría de poder explicar por qué una oferta
concreta salió por donde salió.

La semilla cambia cada lunes a las 00:00 UTC. Así el 20 % que se revisa a mano
no es siempre el mismo conjunto de ofertas: si fuera fijo, las mismas tiendas
caerían eternamente en revisión manual y nadie miraría nunca las otras.
"""

import hashlib
from datetime import date, datetime, timezone

# Porcentaje que se promueve de forma automática. El resto va a revisión.
PORCENTAJE_AUTOMATICO = 80

# Separador entre oferta y semilla al construir la clave del hash. Sin él,
# ("ab", "1") y ("a", "b1") producirian el mismo hash: los identificadores son
# uuid y hoy no colisionarian, pero eso es una propiedad del formato actual,
# no algo en lo que convenga apoyarse.
_SEPARADOR = "|"


def semilla_semanal(momento: datetime | None = None) -> str:
    """Semilla de la semana ISO a la que pertenece `momento` (UTC).

    Devuelve algo como '2026-W33'. Se usa el año-semana ISO y no la fecha del
    lunes porque es la forma canónica de nombrar una semana y se lee de un
    vistazo en los logs.

    `momento` sin zona se interpreta como UTC: la frontera de la semana es
    lunes 00:00 UTC, no la medianoche local de quien corra el job.
    """
    if momento is None:
        momento = datetime.now(timezone.utc)
    elif momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    else:
        momento = momento.astimezone(timezone.utc)

    año_iso, semana_iso, _ = momento.isocalendar()
    return f"{año_iso}-W{semana_iso:02d}"


def lunes_de_la_semana(momento: datetime | None = None) -> date:
    """Fecha del lunes de esa semana ISO, para dejarla escrita en el log."""
    if momento is None:
        momento = datetime.now(timezone.utc)
    elif momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    else:
        momento = momento.astimezone(timezone.utc)

    año_iso, semana_iso, _ = momento.isocalendar()
    return date.fromisocalendar(año_iso, semana_iso, 1)


def cubo_de(offer_id: str, semilla: str) -> int:
    """Cubo 0-99 de una oferta para una semilla. Es el reparto en crudo.

    sha256 reparte de forma uniforme, así que el resto entre 100 da cubos
    equiprobables. Se expone aparte de `debe_promoverse` para poder comprobar
    la distribución sin depender del umbral.
    """
    clave = f"{offer_id}{_SEPARADOR}{semilla}".encode("utf-8")
    return int(hashlib.sha256(clave).hexdigest(), 16) % 100


def debe_promoverse(offer_id: str, semilla: str,
                    porcentaje: int = PORCENTAJE_AUTOMATICO) -> bool:
    """True si la oferta va por la vía automática esta semana.

    `porcentaje` es parametrizable porque CITE puede querer estrechar el
    automático mientras coge confianza en las reglas: con 0 nada se promueve
    solo, con 100 todo.
    """
    if not 0 <= porcentaje <= 100:
        raise ValueError(
            f"porcentaje debe estar entre 0 y 100, no {porcentaje}")

    return cubo_de(offer_id, semilla) < porcentaje
