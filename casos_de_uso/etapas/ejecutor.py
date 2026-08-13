import hashlib
import json
import logging
import time
from typing import TypeVar, Callable, Awaitable, Any, get_type_hints
from pydantic import BaseModel
from casos_de_uso.dependencias import Dependencias
from puertos.auditoria import Ejecucion

T = TypeVar("T", bound=BaseModel)

_log = logging.getLogger(__name__)


def _tarifa_de(d: Dependencias, modelo: str) -> dict:
    """Busca la tarifa del modelo, normalizando el prefijo del proveedor.

    Los modelos se declaran como 'openai/glm-5.2' porque es lo que litellm
    necesita para enrutar, pero la tabla de tarifas los lista sin prefijo. El
    `.get(modelo, {})` de antes no encontraba ninguno y devolvia tarifa vacia,
    de modo que **todo costaba 0 US$ desde S1**: 15.766 tokens registrados y
    0.0 en costo_usd en las 94 filas del historico.

    Un modelo sin tarifa sigue costando 0, porque no hay con que calcularlo,
    pero ahora lo dice en vez de callarselo. Es la diferencia entre "esta
    etapa fue gratis" y "no se cuanto costo esta etapa".
    """
    if not modelo:
        return {}
    clave = modelo.rsplit("/", 1)[-1]
    tarifa = (d.tarifas_modelos or {}).get(clave)
    if tarifa is None:
        _log.warning(
            "Modelo %r sin tarifa declarada: su costo se registrara como 0. "
            "Anadirlo a Dependencias.tarifas_modelos.", clave)
        return {}
    return tarifa

def _huella_de_esquema(tipo_retorno: Any) -> str:
    """Huella de los campos que produce una etapa.

    Entra en la clave de cache porque **la salida de una etapa no depende solo
    de su entrada, sino tambien de la forma que se le pidio al modelo**. Sin
    esto, anadir un campo al esquema no invalida nada: `model_validate` rellena
    el campo nuevo con su valor por defecto y la etapa devuelve para siempre un
    resultado al que le falta justo lo que se acaba de anadir.

    Paso de verdad al anadir `terminos_aleman` a `InsumoInterpretado`: los
    insumos ya consultados —'arandano', 'cascara de cacao'— seguian sirviendo
    una interpretacion sin termino aleman, con lo que la gondola alemana no se
    consultaba nunca. Y en silencio: [] es tambien la respuesta legitima de "no
    hay ofertas", asi que desde fuera no se distinguia de una busqueda vacia.

    Se usan solo los nombres de campo, ordenados. Cambiar una descripcion no
    cambia la forma del dato y no merece tirar la cache; anadir o quitar un
    campo, si.
    """
    if not (isinstance(tipo_retorno, type) and issubclass(tipo_retorno, BaseModel)):
        return ""
    return ",".join(sorted(tipo_retorno.model_fields))


def _generar_clave_cache(entrada: Any, etapa: str, snapshot_version: str, modelo: str = "", kwargs: dict = None, tipo_retorno: Any = None) -> str:
    entrada_str = entrada.model_dump_json() if isinstance(entrada, BaseModel) else json.dumps(entrada)
    kwargs_str = json.dumps(kwargs or {}, sort_keys=True)
    esquema = _huella_de_esquema(tipo_retorno)
    base = (f"{entrada_str}|{modelo}|{kwargs_str}|{etapa}|{snapshot_version}"
            f"|{esquema}").encode('utf-8')
    return hashlib.sha256(base).hexdigest()

async def etapa(d: Dependencias, ejecucion: Ejecucion, num_etapa: str, func: Callable[..., Awaitable[T]], entrada: Any, **kwargs) -> T:
    inicio_total = time.time()
    modelo = d.redactor.modelo_por_etapa.get(num_etapa, "glm-5.2") if hasattr(d.redactor, 'modelo_por_etapa') else ""

    # El tipo de retorno se resuelve ANTES de construir la clave: su lista de
    # campos entra en el hash, para que un cambio de esquema invalide lo
    # cacheado en vez de servirlo con los campos nuevos vacios.
    tipo_retorno = get_type_hints(func).get('return')
    clave = _generar_clave_cache(entrada, num_etapa, ejecucion.snapshot_version,
                                 modelo, kwargs, tipo_retorno)
    cacheado = d.cache.obtener(clave)

    if cacheado and tipo_retorno:
        # Una etapa servida por cache tambien se audita. Antes se devolvia aqui
        # sin registrar nada, asi que un run con cache caliente dejaba menos
        # filas en etapas_ejecucion que etapas ejecuto: el gate de T5 ("5 filas")
        # y test_cache_hit_sin_llm de T7 no se podian comprobar, porque "no hubo
        # llamada al LLM" y "la etapa no ocurrio" eran indistinguibles.
        resultado = tipo_retorno.model_validate(cacheado)
        entrada_dict = entrada.model_dump(mode='json') if isinstance(entrada, BaseModel) else {"valor": entrada}
        d.auditoria.registrar_etapa(
            ejecucion, num_etapa, entrada_dict, cacheado,
            duracion_ms=int((time.time() - inicio_total) * 1000),
            costo_usd=0.0, tokens=0, tokens_entrada=0, tokens_salida=0,
            modelo=modelo, cache_hit=True)
        return resultado

    start_time = time.time()
    resultado = await func(d, entrada, **kwargs)
    duracion_ms = int((time.time() - start_time) * 1000)
    
    entrada_dict = entrada.model_dump(mode='json') if isinstance(entrada, BaseModel) else {"valor": entrada}
    salida_dict = resultado.model_dump(mode='json')
    
    tokens_usados = 0
    tokens_entrada = 0
    tokens_salida = 0
    if hasattr(resultado, '_raw_response') and hasattr(resultado._raw_response, 'usage'):
        usage = resultado._raw_response.usage
        if hasattr(usage, 'total_tokens'):
            tokens_usados = usage.total_tokens
        if hasattr(usage, 'prompt_tokens'):
            tokens_entrada = usage.prompt_tokens
        if hasattr(usage, 'completion_tokens'):
            tokens_salida = usage.completion_tokens

    tarifa = _tarifa_de(d, modelo)
    costo_usd = (tokens_entrada * tarifa.get("entrada_por_1k", 0) / 1000) + \
                (tokens_salida * tarifa.get("salida_por_1k", 0) / 1000)

    # etapa, modelo y snapshot acompanan a la respuesta: sin ellos en la fila,
    # un cache hit no demuestra que la clave sea la correcta (P02).
    d.cache.guardar(clave, salida_dict, etapa=num_etapa, modelo=modelo,
                    snapshot_version=ejecucion.snapshot_version)
    # El contador del run se actualiza aqui, no en la composicion: asi ninguna
    # etapa futura puede gastar sin quedar contada por olvidarse de sumarla.
    if d.presupuesto is not None:
        d.presupuesto.anotar(costo_usd)

    d.auditoria.registrar_etapa(ejecucion, num_etapa, entrada_dict, salida_dict, duracion_ms, costo_usd=costo_usd, tokens=tokens_usados, tokens_entrada=tokens_entrada, tokens_salida=tokens_salida, modelo=modelo, cache_hit=False)
    return resultado

def etapa_sync(d: Dependencias, ejecucion: Ejecucion, num_etapa: str, func: Callable[[Dependencias, Any], T], entrada: Any) -> T:
    start_time = time.time()
    resultado = func(d, entrada)
    duracion_ms = int((time.time() - start_time) * 1000)

    entrada_dict = entrada.model_dump(mode='json') if isinstance(entrada, BaseModel) else {"valor": entrada}
    salida_dict = resultado.model_dump(mode='json')

    d.auditoria.registrar_etapa(ejecucion, num_etapa, entrada_dict, salida_dict, duracion_ms, costo_usd=0.0, modelo="sync")
    return resultado
