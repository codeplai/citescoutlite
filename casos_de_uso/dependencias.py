from dataclasses import dataclass
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
