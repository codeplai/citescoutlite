"""
S8 - Web Unlocker de Bright Data, como **reserva ante un 403**.

## Por que existe, con la medicion delante

El agente descarga fichas con un `httpx` pelado. Funciona con tiendas
pequenas y falla con las grandes. Medido el 2026-08-13 sobre 'Quinoa', el
agente abrio tres URL y perdio dos:

    1. muddanatur.com                 -> extraida, pero sin precio
    2. idealo.de/preisvergleich/...   -> 403 Forbidden
    3. rewe.de/shop/c/quinoa          -> 403 Forbidden

Resultado: **cero ofertas alemanas** para un insumo que Alemania vende en
todos los supermercados. No es que el dato no exista, es que no se puede
llegar a el.

## Por que NO se usa el cliente que ya habia

`adaptadores/bright_data_api.py` es la **Scraper API**: encola un trabajo,
devuelve un `snapshot_id` y espera a que Bright Data llame a un webhook. Ese
modelo sirve para el barrido de catalogo de N2, que es asincrono y tiene donde
esperar. Aqui hace falta lo contrario: una peticion y una respuesta, dentro del
bucle de descarga del agente, mientras el navegador aguanta.

Web Unlocker es justo eso: un POST que devuelve el HTML ya resuelto.

## Solo cuando el directo falla

Se llama **despues** de un 403, nunca antes. Cada peticion por aqui cuesta, y
la mayoria de las tiendas que el agente encuentra abren sin ayuda: pagar proxy
para todas seria gastar de mas en la mitad de los casos y anadir latencia a la
otra mitad.

## Requiere una zona, y eso se crea en el panel

Comprobado el 2026-08-13 contra la cuenta del proyecto: la clave autentica,
pero `GET /zone/get_active_zones` devuelve `[]` y `GET /status` responde

    {"status":"active", "can_make_requests":false,
     "auth_fail_reason":"zone_not_found"}

o sea, **no hay ninguna zona creada**. Sin ella, cada peticion vuelve con
HTTP 200 y cero bytes, y la cabecera `x-brd-err-code: client_10002` lo explica.

Por eso este modulo **se apaga solo**: si no hay clave, o no hay zona, o la
respuesta viene vacia, devuelve None y el agente sigue como hasta ahora. No
lanza. Encender esto es crear la zona en el panel de Bright Data y, si se llama
distinto de `web_unlocker1`, ponerlo en `BRIGHT_DATA_ZONE`.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

_URL_API = "https://api.brightdata.com/request"

# Nombre por defecto de la zona. Es el que Bright Data propone al crear una
# Web Unlocker, y el unico que en la sonda no dio "zone not found".
ZONA_POR_DEFECTO = "web_unlocker1"

# Generoso a proposito: esto solo corre cuando el directo YA fallo, y resolver
# un anti-bot lleva su tiempo. Un timeout corto aqui convierte la reserva en
# otro fallo.
TIEMPO_ESPERA = 90.0


class DesbloqueoBrightData:
    """Descarga por Web Unlocker. Nunca lanza: o devuelve HTML, o None."""

    def __init__(self, api_key: str | None = None, zona: str | None = None,
                 timeout: float = TIEMPO_ESPERA):
        self._api_key = api_key if api_key is not None else os.getenv("BRIGHT_DATA_KEY", "")
        self._zona = zona or os.getenv("BRIGHT_DATA_ZONE", ZONA_POR_DEFECTO)
        self._timeout = timeout
        # Se avisa una vez por proceso, no por URL: con tres URL por consulta y
        # muchas consultas, un aviso por intento llenaria el log de la misma
        # linea y escondería lo que si hay que leer.
        self._ya_avisado = False

    @property
    def configurado(self) -> bool:
        return bool(self._api_key)

    def _avisar_una_vez(self, mensaje: str) -> None:
        if not self._ya_avisado:
            self._ya_avisado = True
            logger.warning(mensaje)

    async def descargar(self, url: str) -> str | None:
        """El HTML de `url` resuelto por Bright Data, o None si no se pudo.

        None significa "sigue sin esto", no "la pagina no existe". Quien llama
        se queda con el fallo original, que es informacion mas util que un
        error del proxy.
        """
        if not self.configurado:
            self._avisar_una_vez(
                "Sin BRIGHT_DATA_KEY: las paginas con anti-bot se quedan sin leer")
            return None

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as cliente:
                respuesta = await cliente.post(
                    _URL_API,
                    headers={"Authorization": f"Bearer {self._api_key}",
                             "Content-Type": "application/json"},
                    json={"zone": self._zona, "url": url, "format": "raw"},
                )
        except Exception as e:
            logger.warning(f"Bright Data no respondio para {url}: {type(e).__name__}")
            return None

        # El fallo de zona llega con **HTTP 200 y cuerpo vacio**, no con un
        # codigo de error: sin mirar la cabecera parece que la pagina estaba en
        # blanco. Es el estado real de la cuenta hoy, asi que se nombra.
        codigo = respuesta.headers.get("x-brd-err-code")
        if codigo:
            self._avisar_una_vez(
                f"Bright Data rechaza las peticiones ({codigo}: "
                f"{respuesta.headers.get('x-brd-err-msg', '')[:120]}). "
                f"Zona usada: {self._zona!r}. Crea una Web Unlocker en el panel "
                f"o ajusta BRIGHT_DATA_ZONE; hasta entonces las tiendas con "
                f"anti-bot se quedan sin leer.")
            return None

        if respuesta.status_code != 200:
            logger.warning(f"Bright Data: HTTP {respuesta.status_code} para {url}")
            return None

        html = respuesta.text or ""
        if not html.strip():
            self._avisar_una_vez(
                f"Bright Data devuelve vacio para {url} sin dar motivo. "
                f"Comprueba la zona {self._zona!r} en el panel.")
            return None

        logger.info(f"Bright Data resolvio {url} ({len(html):,} B)")
        return html
