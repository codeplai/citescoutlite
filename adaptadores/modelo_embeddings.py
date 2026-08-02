"""
Singleton compartido del modelo de embeddings (bge-m3).

Lo usan `busqueda_lancedb` (catálogo de productos) y `verificador_rag` (corpus
regulatorio). Sin esto cada adaptador cargaría su propia copia: bge-m3 son
~568M parámetros, así que serían ~2.3 GB duplicados y ~8 s extra de arranque.
"""
import os
import sys

MODELO = "BAAI/bge-m3"
DIMENSIONES = 1024

_modelo = None


def limpiar_datasets_fantasma():
    """
    Quita de `sys.modules` el paquete `datasets` falso que crea este repo.

    **Llamar justo antes de cada escritura en LanceDB que venga después de un
    `encode()`.** No basta con hacerlo una vez al cargar el modelo: `encode()`
    vuelve a disparar el import.

    `sentence_transformers` hace un `import datasets` protegido para soportar
    HuggingFace Datasets. Como el proyecto tiene una carpeta `datasets/` en la
    raíz y el directorio de trabajo está en `sys.path`, Python la resuelve como
    *namespace package* vacío: el import "funciona", sentence-transformers
    captura el ImportError posterior y sigue... pero deja la entrada en
    `sys.modules`.

    Después, LanceDB comprueba `if "datasets" in sys.modules` para registrar sus
    conversores opcionales, da por hecho que es HuggingFace y hace
    `from datasets import Dataset`, que revienta sin captura. El síntoma es un
    `ImportError: cannot import name 'Dataset' from 'datasets' (unknown
    location)` al llamar a `table.add()`, sin relación aparente con la causa.
    """
    modulo = sys.modules.get("datasets")
    if modulo is not None and getattr(modulo, "__file__", None) is None:
        rutas = list(getattr(modulo, "__path__", []))
        if any(os.path.basename(r.rstrip("\\/")) == "datasets" for r in rutas):
            del sys.modules["datasets"]


def dispositivo() -> str:
    """cuda si está disponible; `AGROSCOUT_DEVICE` lo fuerza."""
    forzado = os.getenv("AGROSCOUT_DEVICE")
    if forzado:
        return forzado
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def get_modelo():
    """Carga bge-m3 una sola vez por proceso."""
    global _modelo
    if _modelo is None:
        from sentence_transformers import SentenceTransformer
        _modelo = SentenceTransformer(MODELO, device=dispositivo())
        # Mismo recorte que en la indexación (etl/tier4_gpu.py): las consultas
        # son cortas y 512 tokens evita reservar memoria para 8192.
        _modelo.max_seq_length = 512
    return _modelo


def reset():
    """Libera el singleton. Solo para tests."""
    global _modelo
    _modelo = None
