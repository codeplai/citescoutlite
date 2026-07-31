"""Test TIER 1: Verificar que S1 está integrada."""

def test_s1_embeddings_importable():
    """Verificar que bge-m3 se puede importar."""
    from sentence_transformers import SentenceTransformer
    assert SentenceTransformer is not None
    print("PASS: sentence-transformers importable")

def test_s1_lancedb_importable():
    """Verificar que LanceDB está disponible."""
    import lancedb
    assert lancedb is not None
    print("PASS: LanceDB importable")

def test_s1_pydantic_models_available():
    """Verificar que modelos Pydantic están definidos."""
    from dominio.producto_existente import ProductoExistente
    from dominio.resultado_busqueda import ResultadoBusqueda
    assert ProductoExistente is not None
    assert ResultadoBusqueda is not None
    print("PASS: Modelos Pydantic disponibles")

if __name__ == "__main__":
    test_s1_embeddings_importable()
    test_s1_lancedb_importable()
    test_s1_pydantic_models_available()
    print("\nAll S1 integration tests PASSED")
