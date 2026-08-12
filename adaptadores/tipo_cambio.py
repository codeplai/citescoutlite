"""
S8 - Tipo de cambio del dia, para expresar toda oferta en soles.

## Por que

El agente N3 trae ofertas de tiendas de fuera: en una pasada real aparecieron
maca a EUR 8,90 (terzaluna.com) y a USD 7,64 (walmart.com) junto a precios
peruanos en soles. Un mapa comercial que mezcla monedas no se puede leer: 8,90
no es comparable con 14,99 si uno es euro y el otro sol.

## La fuente es el BCRP, y eso importa

El Banco Central de Reserva del Peru publica el tipo de cambio oficial por API
abierta. Para un entregable de CITE es la fuente citable: la misma logica por
la que las regulaciones de S4 se citan contra eCFR o DIGESA y no contra un
resumen de terceros.

Las series se identificaron **consultando la API**, no de memoria: un barrido
por los codigos PD04637PD-PD04648PD devuelve el nombre de cada serie, y asi se
vio que el codigo que parecia el del euro (PD04645PD) es en realidad
"TC Cierre Compra - 01:30 PM (S/ por US$)", o sea dolar otra vez.

| Serie | Nombre que devuelve la API |
|---|---|
| `PD04640PD` | TC Sistema bancario SBS (S/ por US$) - Venta |
| `PD04648PD` | TC Euro (S/ por Euro) - Venta |

**Se usa el tipo de VENTA.** Es el que pagaria quien tuviera que comprar esa
moneda para adquirir el producto, y es el criterio conservador: sobrestima
ligeramente el precio en soles antes que subestimarlo. Mezclar compra y venta
segun la moneda daria cifras que no se pueden comparar entre si.

## Lo que se guarda

Nunca se pisa el precio original. La conversion viaja aparte y con su
procedencia —tasa, fecha de la tasa y fuente—, porque una cifra convertida sin
la tasa con la que se convirtio no es auditable, y dentro de un mes nadie
podria reconstruir de donde salio.

Ojo con la fecha: el BCRP no publica sabados, domingos ni feriados; esos dias
la serie trae "n.d.". Se toma el ultimo valor publicado y **se registra la
fecha de ese valor**, que puede no ser hoy. Decir "tipo de cambio del dia"
cuando es el del viernes seria mentir en un informe.
"""

import logging
import threading
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

_BASE_BCRP = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"

# Solo tipos de VENTA. Ver el docstring.
SERIES_BCRP = {
    "USD": "PD04640PD",   # TC Sistema bancario SBS (S/ por US$) - Venta
    "EUR": "PD04648PD",   # TC Euro (S/ por Euro) - Venta
}

MONEDA_LOCAL = "PEN"

# La serie devuelve los periodos como '03.Aug.26' cuando se pide en /ing.
_MESES = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}

# Cuantos dias hacia atras se pide. Cubre un puente largo sin traerse un
# historico entero en cada consulta.
DIAS_VENTANA = 12


@dataclass(frozen=True)
class Conversion:
    """Una cifra en soles y de donde sale."""
    precio_pen: float
    moneda_origen: str
    tasa: float
    fecha_tasa: str      # la del valor publicado, no necesariamente hoy
    fuente: str

    def to_json(self) -> dict:
        return asdict(self)


class TipoCambioNoDisponible(Exception):
    """No se pudo obtener una tasa fiable. Quien llama decide si degrada."""


def _fecha_de(nombre: str) -> str:
    """'03.Aug.26' -> '2026-08-03'. Devuelve el original si no encaja."""
    try:
        dia, mes, anio = nombre.split(".")
        return date(2000 + int(anio), _MESES[mes], int(dia)).isoformat()
    except (ValueError, KeyError):
        return nombre


class TipoCambio:
    """Tasas a soles, cacheadas por moneda y dia."""

    def __init__(self, timeout: float = 20.0):
        self._timeout = timeout
        self._cache: dict[tuple[str, str], tuple[float, str, str]] = {}
        self._cerrojo = threading.Lock()

    # -- consulta -----------------------------------------------------------

    def tasa(self, moneda: str) -> tuple[float, str, str]:
        """`(tasa, fecha_de_la_tasa, fuente)` para pasar `moneda` a soles."""
        moneda = (moneda or "").strip().upper()
        if not moneda:
            raise TipoCambioNoDisponible("Sin moneda de origen")

        if moneda == MONEDA_LOCAL:
            return 1.0, date.today().isoformat(), "n/a (ya esta en soles)"

        clave = (moneda, date.today().isoformat())
        with self._cerrojo:
            if clave in self._cache:
                return self._cache[clave]

        if moneda in SERIES_BCRP:
            resultado = self._desde_bcrp(moneda)
        else:
            resultado = self._desde_respaldo(moneda)

        with self._cerrojo:
            self._cache[clave] = resultado
        return resultado

    def a_soles(self, monto: float | None, moneda: str | None) -> Conversion | None:
        """Convierte, o None si no hay monto o no se pudo obtener la tasa.

        Devolver None y no lanzar es deliberado: una oferta sin conversion
        sigue siendo una oferta valida en su moneda, y tumbar la ingesta entera
        porque el BCRP no responde seria desproporcionado.
        """
        if monto is None:
            return None
        try:
            tasa, fecha, fuente = self.tasa(moneda or "")
        except TipoCambioNoDisponible as e:
            logger.warning(f"Sin tipo de cambio para {moneda!r}: {e}")
            return None

        return Conversion(
            # Dos decimales: es dinero, y arrastrar los seis del float solo
            # sugiere una precision que la tasa no tiene.
            precio_pen=round(float(monto) * tasa, 2),
            moneda_origen=(moneda or "").upper(),
            tasa=tasa,
            fecha_tasa=fecha,
            fuente=fuente,
        )

    # -- fuentes ------------------------------------------------------------

    def _desde_bcrp(self, moneda: str) -> tuple[float, str, str]:
        serie = SERIES_BCRP[moneda]
        hasta = date.today()
        desde = hasta - timedelta(days=DIAS_VENTANA)
        url = (f"{_BASE_BCRP}/{serie}/json/"
               f"{desde.isoformat()}/{hasta.isoformat()}/ing")

        try:
            respuesta = httpx.get(url, timeout=self._timeout,
                                  headers={"User-Agent": "AgroScoutIA/1.0"})
            respuesta.raise_for_status()
            datos = respuesta.json()
        except Exception as e:
            raise TipoCambioNoDisponible(
                f"BCRP no respondio para {moneda}: {type(e).__name__}") from e

        # Del mas reciente hacia atras, saltando los dias sin publicacion.
        for periodo in reversed(datos.get("periods", [])):
            crudo = (periodo.get("values") or [None])[0]
            if crudo in (None, "", "n.d."):
                continue
            try:
                tasa = float(crudo)
            except ValueError:
                continue
            nombre = datos["config"]["series"][0]["name"]
            return tasa, _fecha_de(periodo["name"]), f"BCRP · {nombre}"

        raise TipoCambioNoDisponible(
            f"La serie {serie} no trae ningun valor publicado en {DIAS_VENTANA} dias")

    def _desde_respaldo(self, moneda: str) -> tuple[float, str, str]:
        """Para monedas que el BCRP no publica (ni USD ni EUR).

        No es oficial y se etiqueta como tal en la procedencia: quien lea el
        informe tiene que poder distinguir una cifra respaldada por el banco
        central de una que viene de un agregador.
        """
        url = f"https://open.er-api.com/v6/latest/{moneda}"
        try:
            respuesta = httpx.get(url, timeout=self._timeout,
                                  headers={"User-Agent": "AgroScoutIA/1.0"})
            respuesta.raise_for_status()
            datos = respuesta.json()
        except Exception as e:
            raise TipoCambioNoDisponible(
                f"El respaldo no respondio para {moneda}: {type(e).__name__}") from e

        if datos.get("result") != "success":
            raise TipoCambioNoDisponible(f"El respaldo rechazo {moneda}")

        tasa = (datos.get("rates") or {}).get(MONEDA_LOCAL)
        if not tasa:
            raise TipoCambioNoDisponible(f"El respaldo no da {moneda}->PEN")

        actualizado = datos.get("time_last_update_utc", "")
        try:
            fecha = datetime.strptime(
                actualizado[:16], "%a, %d %b %Y").date().isoformat()
        except ValueError:
            fecha = date.today().isoformat()

        return float(tasa), fecha, "exchangerate-api.com (no oficial)"


_instancia: TipoCambio | None = None


def tipo_cambio() -> TipoCambio:
    """Instancia unica del proceso, para que la cache sirva de algo."""
    global _instancia
    if _instancia is None:
        _instancia = TipoCambio()
    return _instancia
