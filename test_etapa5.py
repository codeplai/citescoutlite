import asyncio
from adaptadores.verificador_openfda import VerificadorOpenFDA
from adaptadores.verificador_rag import VerificadorRAG

def test_verificadores():
    fda = VerificadorOpenFDA()
    rag = VerificadorRAG()
    
    insumo_es = "cáscara de mango"
    insumo_en = "mango peel"
    
    print(f"Probando Etapa 5 con insumo: {insumo_es} ({insumo_en})")
    
    print("\n--- 1. openFDA (EE.UU.) ---")
    res_fda = fda.verificar(insumo_en, insumo_es)
    print(res_fda)
    
    print("\n--- 2. Base Documental Propia (RAG) ---")
    res_rag = rag.verificar(insumo_en, insumo_es)
    print(res_rag)

if __name__ == "__main__":
    test_verificadores()
