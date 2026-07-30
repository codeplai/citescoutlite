import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import sqlite3

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    snapshot_version="2026-07",
    offline_mode=offline_mode
)

class ConsultaRequest(BaseModel):
    texto: str

class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/token")
async def login(req: LoginRequest):
    with sqlite3.connect("agroscout.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE email = ? AND password_hash = ?", (req.email, req.password))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")
        # In a real app we would sign a JWT here. 
        # For this MVP, we just return a fixed token string indicating success.
        return {"access_token": "mvp-real-db-token-123", "token_type": "bearer", "user": req.email}

@app.post("/consultas")
async def consultar_insumo(req: ConsultaRequest):
    try:
        informe = await evaluar_insumo(req.texto, dependencias)
        return informe.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import FileResponse

@app.get("/informes/{id}")
async def descargar_informe(id: str):
    file_path = f"informes/{id}.pdf"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/pdf", filename=f"Informe_AgroScout_{id}.pdf")
    raise HTTPException(status_code=404, detail="Informe no encontrado")

@app.get("/ejecucion/{id}/tokens")
async def obtener_tokens(id: str):
    with sqlite3.connect("agroscout.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT SUM(tokens), SUM(tokens_entrada), SUM(tokens_salida) FROM etapas_ejecucion WHERE ejecucion_id = ?", (id,))
        row = cur.fetchone()
        tokens = row[0] if row and row[0] is not None else 0
        entrada = row[1] if row and row[1] is not None else 0
        salida = row[2] if row and row[2] is not None else 0
        return {
            "ejecucion_id": id, 
            "total_tokens": tokens,
            "tokens_entrada": entrada,
            "tokens_salida": salida
        }

def start():
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
