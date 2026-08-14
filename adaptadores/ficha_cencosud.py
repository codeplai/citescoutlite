"""
Ingredientes y tabla nutricional de Wong y Metro, por codigo de barras.

## Como se encontro, porque no fue evidente

El API de catalogo de VTEX no los trae, ni el HTML de la ficha, ni el JSON-LD,
ni Intelligent Search, ni las especificaciones del SKU. Se comprobaron las
siete vias. El dato aparece en la pagina, pero **solo despues de ejecutar
JavaScript**, que es la diferencia entre el DOM que ve el inspector y el HTML
que envia el servidor.

Se capturo con un navegador headless registrando **todas** las respuestas de
red —el primer intento filtro por 'graphql' y no lo encontro, porque no va por
ahi— y aparecio un API propio de Cencosud, fuera de VTEX:

    GET https://www.wong.pe/v1/api/productinformations/{EAN}

Sin credencial, sin anti-bot y **con el codigo de barras como clave**, que es
justo lo que el catalogo ya nos da. Devuelve mas de lo que se buscaba:

    ingredients         lista completa, en texto
    nutritional_tables  por 100 g Y por porcion, con unidad
    traces              trazas de alergenos
    num_portions        porciones por envase
    certificates        apto para APLV, sin lactosa, vegetariano...

Playwright sirvio para descubrirlo y **no hace falta en produccion**: esto es
un GET normal.

## Solo Wong y Metro

Son del grupo Cencosud y comparten plataforma. Plaza Vea y Makro son de
Intercorp y responden 400 a esta ruta; sus datos nutricionales salen de
`allSpecifications` (ver `catalogo_vtex.py`) y **no publican ingredientes en
ninguna via conocida**.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# host -> nombre de tienda. Solo las de Cencosud.
FICHA_CENCOSUD = {
    "Wong": "www.wong.pe",
    "Metro": "www.metro.pe",
}

_RUTA = "/v1/api/productinformations/{ean}"

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

TIEMPO_ESPERA = 12.0

# Cuantas fichas se piden a la vez. Son 20 ofertas por consulta y en serie
# serian ~4 s; en paralelo, medio segundo. Seis es prudente: no es un API
# documentado y no conviene tratarlo como propio.
CONCURRENCIA = 6

# `code` del API -> campo de EspecificacionNutricional. El API los nombra en
# ingles y con codigos estables, que es mejor que las etiquetas en castellano
# de Plaza Vea: no dependen de como escriba cada cadena.
NUTRIENTES = {
    "portion": "porcion",
    "energy": "calorias",
    "protein": "proteinas",
    "carbohydrate": "carbohidratos",
    "carbohydrates": "carbohidratos",
    "sugar": "azucares",
    "sugars": "azucares",
    "fat_total": "grasas",
    "sodium": "sodio",
}


def _texto_nutriente(fila: dict) -> Optional[str]:
    """El valor con su unidad, tal como lo publica la ficha.

    Se prefiere **por porcion**, para que la columna sea comparable con la de
    Plaza Vea y Makro, que solo publican por porcion. Si no hay valor por
    porcion se usa el de 100 g y se dice en la etiqueta, porque una cifra sin
    su base no se puede comparar con nada.

    `portion` es la excepcion y hay que tratarla aparte: su `value` es el
    TAMAÑO de la racion —34 g— y su `value_per_portion` viene a 0. Pasarla por
    la regla general la etiquetaba «34 g (por 100 g)», que es exactamente al
    reves de lo que dice, y arriba de la ficha, que es donde se lee primero.
    """
    unidad = (fila.get("unit_name") or "").strip()
    valor = fila.get("value")

    if (fila.get("code") or "").strip() == "portion":
        return f"{valor:g} {unidad}".strip() if isinstance(valor, (int, float)) else None

    por_porcion = fila.get("value_per_portion")
    if isinstance(por_porcion, (int, float)) and por_porcion:
        return f"{por_porcion:g} {unidad}".strip()

    if isinstance(valor, (int, float)) and valor:
        # Se marca la base: sin eso, 437 kCal por 100 g se leeria como la
        # racion y multiplicaria por tres el aporte real.
        return f"{valor:g} {unidad} (por 100 g)".strip()

    return (fila.get("text") or "").strip() or None


class FichaCencosud:
    """Ingredientes y nutricion por EAN, para Wong y Metro."""

    def __init__(self, timeout: float = TIEMPO_ESPERA):
        self._timeout = timeout
        # Cache de proceso, por (tienda, ean). Lo que hay dentro de un envase
        # no cambia de un dia para otro, y sin esto dos consultas seguidas del
        # mismo insumo repetirian las veinte peticiones.
        #
        # No persiste entre reinicios: eso pide una tabla y es el paso
        # siguiente, no este.
        self._cache: dict[tuple[str, str], Optional[dict]] = {}

    def de(self, tienda: str, ean: Optional[str]) -> Optional[dict]:
        """La ficha de un producto, o None si no la hay."""
        host = FICHA_CENCOSUD.get(tienda)
        if not host or not ean:
            return None

        clave = (tienda, ean)
        if clave in self._cache:
            return self._cache[clave]

        with httpx.Client(timeout=self._timeout, follow_redirects=True,
                          headers={"User-Agent": _UA,
                                   "Accept-Language": "es-PE,es;q=0.9"}) as cliente:
            ficha = self._pedir(cliente, host, ean)

        self._cache[clave] = ficha
        return ficha

    def de_varias(self, pares: list[tuple[str, Optional[str]]]) -> dict[tuple, dict]:
        """Varias fichas a la vez. Devuelve solo las que respondieron.

        En paralelo porque son una peticion por oferta: en serie, veinte
        ofertas son ~4 s añadidos a una consulta que hoy tarda 2.
        """
        pendientes = [(t, e) for t, e in pares
                      if e and t in FICHA_CENCOSUD and (t, e) not in self._cache]

        if pendientes:
            with httpx.Client(timeout=self._timeout, follow_redirects=True,
                              headers={"User-Agent": _UA,
                                       "Accept-Language": "es-PE,es;q=0.9"}) as cliente:
                with ThreadPoolExecutor(max_workers=CONCURRENCIA) as ejecutor:
                    resultados = list(ejecutor.map(
                        lambda p: self._pedir(cliente, FICHA_CENCOSUD[p[0]], p[1]),
                        pendientes))
            for par, ficha in zip(pendientes, resultados):
                self._cache[par] = ficha

        return {p: self._cache[p] for p in pares
                if p in self._cache and self._cache[p]}

    def _pedir(self, cliente: httpx.Client, host: str,
               ean: str) -> Optional[dict]:
        """Una ficha. Ante cualquier fallo, None.

        Nunca lanza: esto enriquece una tabla que ya tiene precio y stock, y
        que una ficha no responda no puede tumbar la consulta (ADR-001).
        """
        try:
            respuesta = cliente.get(f"https://{host}{_RUTA.format(ean=ean)}")
            if respuesta.status_code != 200:
                return None
            if "json" not in respuesta.headers.get("content-type", ""):
                return None
            datos = (respuesta.json() or {}).get("response") or {}
        except Exception as e:
            logger.info(f"Ficha de {host} para EAN {ean}: "
                        f"{type(e).__name__}: {e}")
            return None

        return self._a_dominio(datos)

    @staticmethod
    def _a_dominio(datos: dict) -> Optional[dict]:
        ingredientes = (datos.get("ingredients") or "").strip() or None

        nutricion: dict[str, Any] = {}
        for fila in (datos.get("nutritional_tables") or []):
            campo = NUTRIENTES.get((fila.get("code") or "").strip())
            if not campo:
                continue
            valor = _texto_nutriente(fila)
            if valor:
                nutricion[campo] = valor

        porciones = datos.get("num_portions")
        if porciones:
            nutricion["porciones_envase"] = str(porciones)

        trazas = (datos.get("traces") or "").strip() or None

        # Sin ingredientes ni nutricion no hay ficha que devolver: un
        # diccionario con solo las trazas haria que la columna prometiera algo
        # que al abrirlo esta vacio.
        if not ingredientes and not any(
                k for k in nutricion if k not in ("porcion", "porciones_envase")):
            return None

        return {"ingredientes": ingredientes,
                "nutricion": nutricion or None,
                "trazas": trazas}
