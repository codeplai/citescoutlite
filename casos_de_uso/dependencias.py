from dataclasses import dataclass
from typing import Dict, Any
from puertos.redactor_llm import RedactorLLM
from puertos.catalogo_productos import CatalogoProductos
from puertos.cache_llm import CacheLLM
from puertos.repositorio_informes import RepositorioInformes
from puertos.auditoria import Auditoria
from puertos.descubrimiento_comercial import DescubrimientoComercial
from puertos.verificador_regulatorio import VerificadorRegulatorio
from puertos.repositorio_regulaciones import RepositorioRegulaciones

@dataclass
class Dependencias:
    redactor: RedactorLLM
    catalogo: CatalogoProductos
    cache: CacheLLM
    informes: RepositorioInformes
    auditoria: Auditoria
    verificador_fda: VerificadorRegulatorio = None
    verificador_rag: VerificadorRegulatorio = None
    suscripciones: Any = None
    # Etapa 2b (S4). Sin el, la etapa corre igual y devuelve un mapa vacio que
    # declara los tres niveles como no disponibles: degrada a "sin dato", nunca
    # error. Es lo que permite que los tests deterministas de S2 sigan armando
    # Dependencias sin tocar LanceDB.
    descubrimiento: DescubrimientoComercial = None
    # Precio de MATERIA PRIMA (MIDAGRI). Sin el, la etapa 2b devuelve el mapa
    # igual y la lista de precios vacia: nada de esto es bloqueante.
    precios: Any = None
    # Precio de GONDOLA del producto terminado, tienda por tienda. Es otra
    # fuente independiente: no pasa por la cascada ni por ningun modelo, son
    # peticiones a un API publico de catalogo. Sin el, la tabla de ofertas sale
    # vacia y el resto del informe no se entera.
    ofertas: Any = None
    # Corpus regulatorio (S4). Sin el, etapa 5 degrada a sin_dato.
    # Permite búsquedas de regulaciones: eCFR, EFSA, Codex, INACAL, DIGESA.
    # Con él, citas en dossier regulatorio son verificables (URLs vivas).
    repositorio_regulaciones: RepositorioRegulaciones = None
    # Contador del run en curso (T6.3). Es lo unico mutable de este objeto, y
    # por eso cada run trabaja sobre una copia hecha con dataclasses.replace:
    # Dependencias se construye una sola vez al arrancar y se comparte entre
    # peticiones concurrentes.
    presupuesto: Any = None
    # Kill-switch de S8.5. Sin el no hay interruptor y el run corre como
    # siempre: los tests deterministas de S2 arman Dependencias sin tocar la
    # base, y el plan B de sqlite no tiene sistema_config.
    configuracion: Any = None
    snapshot_version: str = "2026-07"
    tarifas_modelos: Dict[str, Dict[str, float]] = None
    offline_mode: bool = False

    def __post_init__(self):
        if self.tarifas_modelos is None:
            # Claves SIN el prefijo 'openai/' del enrutado de litellm; el
            # ejecutor lo normaliza antes de buscar aqui.
            #
            # Servidos por el endpoint de ModelArts (verificado 2026-08-02):
            # deepseek-v4-flash, deepseek-v3 y glm-5.2. glm-5.0 y glm-4.7
            # devuelven 404 y se conservan solo para poder valorar el historico
            # que los referencia.
            self.tarifas_modelos = {
                "deepseek-v4-flash": {"entrada_por_1k": 0.000135, "salida_por_1k": 0.000539},
                "glm-5.0": {"entrada_por_1k": 0.000539, "salida_por_1k": 0.002965},
                "glm-4.7": {"entrada_por_1k": 0.003, "salida_por_1k": 0.006},
                "glm-5.2": {"entrada_por_1k": 0.010, "salida_por_1k": 0.020},
            }
