import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from adaptadores.autenticacion import Autenticacion
from adaptadores.busqueda_lancedb import BusquedaLanceDB
from adaptadores.entorno import ruta_db_sqlite
from adaptadores.informe_weasyprint import InformeWeasyPrint
from adaptadores.redactor_glm import RedactorGLM
from adaptadores.verificador_openfda import VerificadorOpenFDA
from adaptadores.verificador_rag import VerificadorRAG
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.evaluar_insumo import evaluar_insumo

load_dotenv()

# ---------------------------------------------------------------------------
# T3.4 - Conmutador de backend de estado.
#
# La rama 'sqlite' se conserva funcionando a proposito: es el plan B de la demo
# (D5) y el modo en que corren los tests que no deben depender de la red.
# ---------------------------------------------------------------------------
APP_DB = os.getenv("APP_DB", "sqlite").strip().lower()
USA_SUPABASE = APP_DB == "supabase"

if APP_DB not in ("supabase", "sqlite"):
    raise RuntimeError(
        f"APP_DB={APP_DB!r} no es un valor valido. Usar 'supabase' o 'sqlite'.")


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

if USA_SUPABASE:
    from adaptadores.auditoria_postgres import AuditoriaPostgres
    from adaptadores.cache_postgres import CachePostgres
    from adaptadores.repositorio_informes_supabase import RepositorioInformesSupabase

    cache_llm = CachePostgres()
    auditoria = AuditoriaPostgres()
    informes = RepositorioInformesSupabase()
else:
    from adaptadores.auditoria_sqlite import AuditoriaSQLite
    from adaptadores.cache_sqlite import CacheSQLite

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

# ---------------------------------------------------------------------------
# Puente provisional hasta T4.1.
#
# ejecuciones.usuario_id apunta a auth.users, pero el login de hoy sigue siendo
# el JWT propio de S1, cuyo user_id es un entero de la tabla sqlite 'usuarios'.
# Hasta que T4 sustituya la verificacion por la de Supabase, los runs de la rama
# supabase se cuelgan de la cuenta tecnica que creo la migracion de T2.2.
#
# En cuanto T4.1 este, esto se borra y el uuid sale del 'sub' del JWT.
# ---------------------------------------------------------------------------
EMAIL_USUARIO_PROVISIONAL = os.getenv("USUARIO_PROVISIONAL_EMAIL", "admin@cite.gob.pe")
_uuid_provisional: str | None = None


def usuario_actual_id(current_user: dict) -> str | None:
    if not USA_SUPABASE:
        return str(current_user.get("user_id")) if current_user.get("user_id") else None

    global _uuid_provisional
    if _uuid_provisional is None:
        from adaptadores.db import pool
        with pool().connection() as conexion:
            fila = conexion.execute(
                "select id from auth.users where email = %s",
                (EMAIL_USUARIO_PROVISIONAL,)).fetchone()
        if not fila:
            raise HTTPException(
                status_code=500,
                detail=f"No existe {EMAIL_USUARIO_PROVISIONAL}: correr "
                       "etl/migrar_sqlite_a_supabase.py o T4.3")
        _uuid_provisional = str(fila[0])
    return _uuid_provisional


class ConsultaRequest(BaseModel):
    texto: str


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/token")
async def login(req: LoginRequest):
    # T4.2 lo sustituye por un proxy del password grant de Supabase, con la
    # misma firma de request y response para no tocar el frontend.
    with sqlite3.connect(ruta_db_sqlite()) as conn:
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
        informe = await evaluar_insumo(req.texto, dependencias,
                                       usuario_actual_id(current_user))
        return informe.model_dump()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/informes/{id}")
async def descargar_informe(id: str, current_user: dict = Depends(get_current_user)):
    if not USA_SUPABASE:
        file_path = f"informes/{id}.pdf"
        if os.path.exists(file_path):
            return FileResponse(file_path, media_type="application/pdf", filename=f"Informe_AgroScout_{id}.pdf")
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    from adaptadores.db import pool

    # Filtra por dueno. Un informe ajeno responde 404 y no 403: un 403
    # confirmaria que el id existe.
    with pool().connection() as conexion:
        fila = conexion.execute("""
            select ruta_storage from public.informes
             where ejecucion_id = %s and usuario_id = %s
             order by creado_en desc limit 1
        """, (id, usuario_actual_id(current_user))).fetchone()

    if not fila:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    return {"url": informes.firmar_de_nuevo(fila[0]), "expira_en_segundos": 3600}


@app.get("/ejecucion/{id}/tokens")
async def obtener_tokens(id: str, current_user: dict = Depends(get_current_user)):
    # T6.4 lo reemplaza por GET /uso, que ademas filtra por usuario: hoy
    # cualquiera con un id ajeno ve el consumo de otro.
    if USA_SUPABASE:
        from adaptadores.db import pool
        with pool().connection() as conexion:
            fila = conexion.execute("""
                select coalesce(sum(tokens), 0), coalesce(sum(tokens_entrada), 0),
                       coalesce(sum(tokens_salida), 0), coalesce(sum(costo_usd), 0)
                  from public.etapas_ejecucion where ejecucion_id = %s
            """, (id,)).fetchone()
    else:
        with sqlite3.connect(ruta_db_sqlite()) as conn:
            cur = conn.cursor()
            cur.execute("SELECT SUM(tokens), SUM(tokens_entrada), SUM(tokens_salida), SUM(costo_usd) FROM etapas_ejecucion WHERE ejecucion_id = ?", (id,))
            fila = cur.fetchone()

    tokens = fila[0] or 0
    entrada = fila[1] or 0
    salida = fila[2] or 0
    costo = fila[3] or 0.0
    return {
        "ejecucion_id": id,
        "total_tokens": int(tokens),
        "tokens_entrada": int(entrada),
        "tokens_salida": int(salida),
        "costo_usd": round(float(costo), 6)
    }


def start():
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
