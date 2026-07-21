import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from casos_de_uso.dependencias import Dependencias
from casos_de_uso.evaluar_insumo import evaluar_insumo
from adaptadores.redactor_glm import RedactorGLM
from adaptadores.busqueda_lancedb import BusquedaLanceDB
from adaptadores.cache_sqlite import CacheSQLite
from adaptadores.auditoria_sqlite import AuditoriaSQLite
from adaptadores.informe_weasyprint import InformeWeasyPrint

from adaptadores.verificador_openfda import VerificadorOpenFDA
from adaptadores.verificador_rag import VerificadorRAG

load_dotenv()

app = FastAPI(title="AgroScout IA Lite MVP")

zai_api_key = os.getenv("HUAWEI_MAAS_API_KEY", "")
zai_base_url = os.getenv("HUAWEI_MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
offline_mode = os.getenv("AGROSCOUT_OFFLINE", "0") == "1"

redactor = RedactorGLM(api_key=zai_api_key, base_url=zai_base_url)
catalogo = BusquedaLanceDB()
cache_llm = CacheSQLite()
auditoria = AuditoriaSQLite()
informes = InformeWeasyPrint()
fda = VerificadorOpenFDA()
rag = VerificadorRAG()

dependencias = Dependencias(
    redactor=redactor,
    catalogo=catalogo,
    cache=cache_llm,
    informes=informes,
    auditoria=auditoria,
    verificador_fda=fda,
    verificador_rag=rag,
    snapshot_version="2026-07"
)

class ConsultaRequest(BaseModel):
    texto: str

@app.post("/consultas")
async def consultar_insumo(req: ConsultaRequest):
    try:
        informe = await evaluar_insumo(req.texto, dependencias)
        return informe.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/informes/{id}")
async def descargar_informe(id: str):
    return {"id": id, "status": "mock download"}

def start():
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
