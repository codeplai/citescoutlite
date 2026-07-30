import hashlib
import json
import time
from typing import TypeVar, Callable, Awaitable, Any, get_type_hints
from pydantic import BaseModel
from casos_de_uso.dependencias import Dependencias
from puertos.auditoria import Ejecucion

T = TypeVar("T", bound=BaseModel)

def _generar_clave_cache(entrada: Any, etapa: int, snapshot_version: str, modelo: str = "", kwargs: dict = None) -> str:
    entrada_str = entrada.model_dump_json() if isinstance(entrada, BaseModel) else json.dumps(entrada)
    kwargs_str = json.dumps(kwargs or {}, sort_keys=True)
    base = f"{entrada_str}|{modelo}|{kwargs_str}|{etapa}|{snapshot_version}".encode('utf-8')
    return hashlib.sha256(base).hexdigest()

async def etapa(d: Dependencias, ejecucion: Ejecucion, num_etapa: int, func: Callable[..., Awaitable[T]], entrada: Any, **kwargs) -> T:
    modelo = d.redactor.modelo_por_etapa.get(num_etapa, "glm-5.2") if hasattr(d.redactor, 'modelo_por_etapa') else ""
    clave = _generar_clave_cache(entrada, num_etapa, ejecucion.snapshot_version, modelo, kwargs)
    cacheado = d.cache.obtener(clave)
    
    tipo_retorno = get_type_hints(func).get('return')
    
    if cacheado and tipo_retorno:
        return tipo_retorno.model_validate(cacheado)
        
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

    tarifa = d.tarifas_modelos.get(modelo, {})
    costo_usd = (tokens_entrada * tarifa.get("entrada_por_1k", 0) / 1000) + \
                (tokens_salida * tarifa.get("salida_por_1k", 0) / 1000)

    d.cache.guardar(clave, salida_dict)
    d.auditoria.registrar_etapa(ejecucion, num_etapa, entrada_dict, salida_dict, duracion_ms, costo_usd=costo_usd, tokens=tokens_usados, tokens_entrada=tokens_entrada, tokens_salida=tokens_salida, modelo=modelo)
    return resultado

def etapa_sync(d: Dependencias, ejecucion: Ejecucion, num_etapa: int, func: Callable[[Dependencias, Any], T], entrada: Any) -> T:
    start_time = time.time()
    resultado = func(d, entrada)
    duracion_ms = int((time.time() - start_time) * 1000)

    entrada_dict = entrada.model_dump(mode='json') if isinstance(entrada, BaseModel) else {"valor": entrada}
    salida_dict = resultado.model_dump(mode='json')

    d.auditoria.registrar_etapa(ejecucion, num_etapa, entrada_dict, salida_dict, duracion_ms, costo_usd=0.0, modelo="sync")
    return resultado
