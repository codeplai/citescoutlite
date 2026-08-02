"""
Singleton compartido del modelo de embeddings (bge-m3).

Lo usan `busqueda_lancedb` (catálogo de productos) y `verificador_rag` (corpus
regulatorio). Sin esto cada adaptador cargaría su propia copia: bge-m3 son
~568M parámetros, así que serían ~2.3 GB duplicados y ~8 s extra de arranque.
"""
import os

MODELO = "BAAI/bge-m3"
DIMENSIONES = 1024

_modelo = None


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
