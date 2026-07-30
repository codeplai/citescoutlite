import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import sqlite3
from pathlib import Path

from casos_de_uso.dependencias import Dependencias
from casos_de_uso.evaluar_insumo import evaluar_insumo
from adaptadores.redactor_glm import RedactorGLM
from adaptadores.busqueda_lancedb import BusquedaLanceDB
from adaptadores.cache_sqlite import CacheSQLite
from adaptadores.auditoria_sqlite import AuditoriaSQLite
from adaptadores.informe_weasyprint import InformeWeasyPrint

from adaptadores.verificador_openfda import VerificadorOpenFDA
from adaptadores.verificador_rag import VerificadorRAG
from adaptadores.autenticacion import Autenticacion
from typing import Optional
from fastapi import Header, Depends

load_dotenv()

async def get_current_user(authorization: Optional[str] = Header(None)):
    """Extrae y verifica el JWT del header Authorization."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Token no proporcionado")

    token = autenticacion.extraer_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Formato de token inválido")

    payload = autenticacion.verificar_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    return payload

app = FastAPI(title="AgroScout IA Lite MVP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8001", "http://127.0.0.1:3000", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

zai_api_key = os.getenv("HUAWEI_MAAS_API_KEY", "")
zai_base_url = os.getenv("HUAWEI_MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
offline_mode = os.getenv("AGROSCOUT_OFFLINE", "0") == "1"

def cargar_snapshot_version() -> str:
    """Carga versión del snapshot desde manifest.json."""
    manifest_path = Path("datasets/2026-07/manifest.json")
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            return manifest.get("version_taxonomia", "0.1")
        except Exception:
            pass
    return "0.1"

snapshot_version = cargar_snapshot_version()

redactor = RedactorGLM(api_key=zai_api_key, base_url=zai_base_url)
catalogo = BusquedaLanceDB()
cache_llm = CacheSQLite()
auditoria = AuditoriaSQLite()
informes = InformeWeasyPrint()
fda = VerificadorOpenFDA(offline=offline_mode)
rag = VerificadorRAG(offline=offline_mode)
autenticacion = Autenticacion(secret_key=os.getenv("JWT_SECRET_KEY", "agroscout-secret-key-change-in-production"))

dependencias = Dependencias(
    redactor=redactor,
    catalogo=catalogo,
    cache=cache_llm,
    informes=informes,
    auditoria=auditoria,
    verificador_fda=fda,
    verificador_rag=rag,
    snapshot_version=snapshot_version,
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
        cur.execute("SELECT id, password_hash, org_id FROM usuarios WHERE email = ?", (req.email,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        user_id, password_hash, org_id = row
        if not autenticacion.verificar_password(req.password, password_hash):
            raise HTTPException(status_code=401, detail="Credenciales inválidas")

        token = autenticacion.generar_token(user_id, req.email, org_id)
        return {"access_token": token, "token_type": "bearer", "user": req.email}

@app.post("/consultas")
async def consultar_insumo(req: ConsultaRequest, current_user: dict = Depends(get_current_user)):
    try:
        informe = await evaluar_insumo(req.texto, dependencias)
        return informe.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import FileResponse

@app.get("/informes/{id}")
async def descargar_informe(id: str, current_user: dict = Depends(get_current_user)):
    file_path = f"informes/{id}.pdf"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/pdf", filename=f"Informe_AgroScout_{id}.pdf")
    raise HTTPException(status_code=404, detail="Informe no encontrado")

@app.get("/ejecucion/{id}/tokens")
async def obtener_tokens(id: str, current_user: dict = Depends(get_current_user)):
    with sqlite3.connect("agroscout.db") as conn:
        cur = conn.cursor()
        cur.execute("SELECT SUM(tokens), SUM(tokens_entrada), SUM(tokens_salida), SUM(costo_usd) FROM etapas_ejecucion WHERE ejecucion_id = ?", (id,))
        row = cur.fetchone()
        tokens = row[0] if row and row[0] is not None else 0
        entrada = row[1] if row and row[1] is not None else 0
        salida = row[2] if row and row[2] is not None else 0
        costo = row[3] if row and row[3] is not None else 0.0
        return {
            "ejecucion_id": id,
            "total_tokens": tokens,
            "tokens_entrada": entrada,
            "tokens_salida": salida,
            "costo_usd": round(costo, 6)
        }

def start():
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
