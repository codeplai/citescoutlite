from dataclasses import dataclass
from typing import Dict, Any
from puertos.redactor_llm import RedactorLLM
from puertos.catalogo_productos import CatalogoProductos
from puertos.cache_llm import CacheLLM
from puertos.repositorio_informes import RepositorioInformes
from puertos.auditoria import Auditoria
from puertos.verificador_regulatorio import VerificadorRegulatorio

@dataclass
class Dependencias:
    redactor: RedactorLLM
    catalogo: CatalogoProductos
    cache: CacheLLM
    informes: RepositorioInformes
    auditoria: Auditoria
    verificador_fda: VerificadorRegulatorio = None
    verificador_rag: VerificadorRegulatorio = None
    snapshot_version: str = "2026-07"
    tarifas_modelos: Dict[str, Dict[str, float]] = None
    offline_mode: bool = False

    def __post_init__(self):
        if self.tarifas_modelos is None:
            self.tarifas_modelos = {
                "deepseek-v4-flash": {"entrada_por_1k": 0.000135, "salida_por_1k": 0.000539},
                "glm-4.7": {"entrada_por_1k": 0.003, "salida_por_1k": 0.006},
                "glm-5.2": {"entrada_por_1k": 0.010, "salida_por_1k": 0.020},
            }
