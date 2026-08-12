import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from adaptadores.auditoria_panel import AuditoriaPanel
from adaptadores.autenticacion import Autenticacion
# Antes de que uvicorn cree su bucle. En Windows el policy por defecto es el
# Proactor y psycopg en asincrono no puede usarlo, de modo que sin esto el
# WebSocket de jobs y todo lo que escriba eventos_job falla en desarrollo.
from adaptadores.bucle_asincrono import asegurar_bucle_compatible
from adaptadores.busqueda_lancedb import BusquedaLanceDB
from adaptadores.descubrimiento_snapshot import DescubrimientoSnapshot
from adaptadores.entorno import ruta_db_sqlite
from adaptadores.precios_sisap import PreciosSISAP
from adaptadores.informe_weasyprint import InformeWeasyPrint
from adaptadores.redactor_glm import RedactorGLM
from adaptadores.verificador_openfda import VerificadorOpenFDA
from adaptadores.verificador_rag import VerificadorRAG
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.evaluar_insumo import atender_consulta
from casos_de_uso.politica_suscripcion import entitlement_de
from api.health import router as health_router
from api.websocket_jobs import router as websocket_router
from api.webhooks import router as webhooks_router
from api.discovery import router as discovery_router
from api.admin import router as admin_router
from api.alertas import router as alertas_router
from api.auditoria import router as auditoria_router
from api.costos import router as costos_router
from api.promociones import router as promociones_router

load_dotenv()
asegurar_bucle_compatible()

# ---------------------------------------------------------------------------
# T3.4 - Conmutador de backend de estado y autenticacion. Ambos viven ahora en
# api/auth.py, porque los routers tambien los necesitan y este modulo es el que
# los monta: importarlos desde aqui seria un ciclo. Se reexportan para no
# cambiar los endpoints de mas abajo.
# ---------------------------------------------------------------------------
from api.auth import (APP_DB, USA_SUPABASE, autenticacion, get_current_user,
                      rol_de, usuario_actual_id)

app = FastAPI(title="AgroScout IA Lite MVP")

_auditoria = AuditoriaPanel()

# Incluir routers
app.include_router(health_router)
app.include_router(websocket_router)
app.include_router(webhooks_router)
app.include_router(discovery_router)
# S6.7. Solo tiene sentido contra Postgres: las tablas de alertas no existen en
# el SQLite del plan B, y sus consultas usan el pool de adaptadores/db.py.
if USA_SUPABASE:
    app.include_router(alertas_router)
    # S7.6. Igual que alertas: staging_agente y las tablas de promocion solo
    # existen en Postgres.
    app.include_router(promociones_router)
    # S8.3. `auditoria_panel` esta particionada por mes: es de Postgres y no
    # tiene equivalente en el SQLite del plan B.
    app.include_router(auditoria_router)
    # S8.5 y S8.9. Igual: `sistema_config` y `perfiles` solo existen aqui.
    app.include_router(admin_router)
    # S8.2. Agrega sobre `etapas_ejecucion` con CTE y generate_series.
    app.include_router(costos_router)

# Origenes desde los que se puede abrir la SPA. Los de localhost cubren el
# desarrollo en la propia maquina.
#
# CORS_ORIGINS anade los demas, separados por coma. Existe porque la maquina de
# la demo se usa tambien en remoto: abierta desde otro equipo, el origen del
# navegador es la IP de la maquina y no 'localhost', asi que sin esto todas las
# llamadas mueren en el preflight. Va por entorno y no en esta lista para que
# una direccion de red concreta no acabe en el repositorio.
_ORIGENES = ["http://localhost:3000", "http://localhost:8001",
             "http://127.0.0.1:3000", "http://127.0.0.1:8001"]
_ORIGENES += [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ORIGENES,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

zai_api_key = os.getenv("HUAWEI_MAAS_API_KEY", "")
zai_base_url = os.getenv("HUAWEI_MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
offline_mode = os.getenv("AGROSCOUT_OFFLINE", "0") == "1"


DIRECTORIO_SNAPSHOT = Path("datasets/2026-07")


def cargar_snapshot_version() -> str:
    """Version del snapshot de datos.

    Es el nombre del directorio del dataset, no `version_taxonomia` del
    manifest. Se leia ese campo y devolvia '0.1', mientras que las 54
    ejecuciones del historico, las 47 entradas de cache y el valor por defecto
    de Dependencias dicen '2026-07'. Como el snapshot entra en la clave de
    cache, la API corria con una version que **no coincidia con ninguna entrada
    cacheada**: cada consulta pagaba el LLM entero aunque la respuesta ya
    estuviera guardada.

    `version_taxonomia` es otra cosa —la version del esquema del manifest— y se
    expone aparte para quien la necesite.
    """
    return DIRECTORIO_SNAPSHOT.name


def cargar_version_taxonomia() -> str:
    manifest = DIRECTORIO_SNAPSHOT / "manifest.json"
    if manifest.exists():
        try:
            with open(manifest, encoding="utf-8") as f:
                return json.load(f).get("version_taxonomia", "0.1")
        except Exception:
            pass
    return "0.1"


snapshot_version = cargar_snapshot_version()

redactor = RedactorGLM(api_key=zai_api_key, base_url=zai_base_url)
catalogo = BusquedaLanceDB()
# Etapa 2b (S4). Nivel 1 de la cascada del ADR-001: el snapshot local. Sin red
# y sin LLM, asi que tambien funciona con AGROSCOUT_OFFLINE=1.
descubrimiento = DescubrimientoSnapshot()
# Precio de materia prima (MIDAGRI). Lee un snapshot local: sin red.
precios = PreciosSISAP()

if USA_SUPABASE:
    from adaptadores.auditoria_postgres import AuditoriaPostgres
    from adaptadores.cache_postgres import CachePostgres
    from adaptadores.entorno import clave_publica, url_supabase
    from adaptadores.repositorio_informes_supabase import RepositorioInformesSupabase

    from adaptadores.suscripciones_postgres import SuscripcionesPostgres

    from adaptadores.configuracion_postgres import ConfiguracionPostgres

    cache_llm = CachePostgres()
    auditoria = AuditoriaPostgres()
    informes = RepositorioInformesSupabase()
    suscripciones = SuscripcionesPostgres()
    configuracion = ConfiguracionPostgres()
else:
    from adaptadores.auditoria_sqlite import AuditoriaSQLite
    from adaptadores.cache_sqlite import CacheSQLite
    from adaptadores.suscripciones_sqlite import SuscripcionesSQLite

    cache_llm = CacheSQLite()
    auditoria = AuditoriaSQLite()
    informes = InformeWeasyPrint()
    suscripciones = SuscripcionesSQLite()
    # El plan B no tiene `sistema_config`: sin interruptor, y los runs corren
    # como siempre. Es coherente con el resto de la rama sqlite, que tampoco
    # monta los routers de alertas ni de promociones.
    configuracion = None

fda = VerificadorOpenFDA(offline=offline_mode)
rag = VerificadorRAG(offline=offline_mode)

dependencias = Dependencias(
    redactor=redactor,
    catalogo=catalogo,
    cache=cache_llm,
    informes=informes,
    auditoria=auditoria,
    verificador_fda=fda,
    verificador_rag=rag,
    suscripciones=suscripciones,
    configuracion=configuracion,
    descubrimiento=descubrimiento,
    precios=precios,
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
    """Proxy del password grant de Supabase.

    Conserva la firma de request y response de S1 (`access_token` y `user`), asi
    que Login.vue no cambia y la SPA no necesita ninguna clave de Supabase: el
    login pasa entero por el backend.
    """
    if not USA_SUPABASE:
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

    respuesta = httpx.post(
        f"{url_supabase()}/auth/v1/token",
        params={"grant_type": "password"},
        headers={"apikey": clave_publica(), "Content-Type": "application/json"},
        json={"email": req.email, "password": req.password},
        timeout=30,
    )

    if respuesta.status_code >= 400:
        # Supabase distingue 'credenciales invalidas' de 'email sin confirmar';
        # hacia fuera son lo mismo, para no filtrar que cuentas existen.
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    datos = respuesta.json()

    # S8.3 - `login` es una de las seis acciones que 8.3 quiere ver, y hasta
    # ahora no se anotaba en ninguna parte: el login pasa por Supabase Auth,
    # que lleva su propio registro al que el panel de CITE no tiene acceso.
    #
    # Solo se registran las entradas que salieron bien. Los intentos fallidos
    # son otra cosa —vigilancia de accesos, no auditoria de cambios— y
    # anotarlos aqui llenaria la tabla de correos tecleados a medias, que
    # ademas pueden ser de personas que no existen.
    _auditoria.registrar(
        "login",
        usuario_id=(datos.get("user") or {}).get("id"),
        usuario_email=req.email,
        entidad="auth.users",
        entidad_id=(datos.get("user") or {}).get("id"),
    )

    return {
        "access_token": datos["access_token"],
        "token_type": "bearer",
        "user": req.email,
        # Se devuelve aunque la SPA todavia no lo use: el token de Supabase vive
        # ~1 h, suficiente para la demo, pero no cerramos la puerta a renovarlo.
        "refresh_token": datos.get("refresh_token"),
        "expires_in": datos.get("expires_in"),
    }


@app.post("/consultas")
async def consultar_insumo(req: ConsultaRequest, current_user: dict = Depends(get_current_user)):
    """El plan del usuario decide que composicion se ejecuta (T6.2).

    Un usuario gratuito recibe **200 con informe parcial** y
    `motivo_parcial='paywall'`; no un 402 ni un error. Lo mismo cuando salta un
    presupuesto: degradar a "sin dato", nunca a error.
    """
    try:
        informe = await atender_consulta(req.texto, dependencias,
                                         usuario_actual_id(current_user))
        # mode="json" y no model_dump() a secas: desde S4 el informe lleva el
        # mapa, con HttpUrl y date dentro. Sin esto la serializacion recae en
        # el jsonable_encoder de FastAPI, que funciona pero recorre el arbol
        # entero otra vez para arreglar tipos que pydantic ya sabe convertir.
        return informe.model_dump(mode="json")
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
    # T6.4 lo reemplaza por GET /uso, con el desglose por etapa y el tope del plan.
    usuario_id = usuario_actual_id(current_user)

    if USA_SUPABASE:
        from adaptadores.db import pool
        with pool().connection() as conexion:
            # El join con ejecuciones no es decorativo: sin el, cualquiera con
            # un id ajeno veia el consumo de otro.
            fila = conexion.execute("""
                select coalesce(sum(x.tokens), 0), coalesce(sum(x.tokens_entrada), 0),
                       coalesce(sum(x.tokens_salida), 0), coalesce(sum(x.costo_usd), 0)
                  from public.etapas_ejecucion x
                  join public.ejecuciones e on e.id = x.ejecucion_id
                 where x.ejecucion_id = %s and e.usuario_id = %s
            """, (id, usuario_id)).fetchone()
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


@app.get("/api/sesion")
async def sesion(current_user: dict = Depends(get_current_user)):
    """S8.1 - Quién es quien está mirando el panel.

    Hasta ahora el frontend no tenía forma de saberlo: `/token` devuelve el
    token y el correo, y `/uso` devuelve el plan, pero el **rol** no salía por
    ningún sitio. Sin este dato no se puede decidir qué entradas del panel
    enseñar, y el panel de S8 tiene pantallas que solo son de administrador.

    Es de lectura y no decide nada. **Quien autoriza sigue siendo
    `requiere_admin` en cada endpoint**: lo que devuelve esto viaja al
    navegador, y allí cualquiera puede reescribirlo desde las herramientas de
    desarrollo. Sirve para no enseñar una puerta que se va a cerrar en la
    cara, no para abrirla.
    """
    usuario_id = usuario_actual_id(current_user)
    return {
        "usuario_id": usuario_id,
        "email": current_user.get("email"),
        "rol": rol_de(usuario_id),
    }


@app.get("/uso")
async def uso_mensual(current_user: dict = Depends(get_current_user)):
    """T6.4 - Cost-meter del usuario. Reemplaza a /ejecucion/{id}/tokens.

    Todo sale filtrado por `usuario_id`; no hay parametro que permita mirar el
    consumo de otro. El endpoint viejo no filtraba: cualquiera con un id ajeno
    veia su gasto.
    """
    usuario_id = usuario_actual_id(current_user)
    contexto = suscripciones.contexto_de(usuario_id)
    entitlement = entitlement_de(contexto)

    ultimo = None
    if USA_SUPABASE:
        from adaptadores.db import pool
        with pool().connection() as conexion:
            fila = conexion.execute("""
                select coalesce(sum(runs), 0), coalesce(sum(costo_usd), 0)
                  from public.uso_mensual
                 where usuario_id = %s and mes = date_trunc('month', now())
            """, (usuario_id,)).fetchone()
            runs, costo_mes = int(fila[0]), float(fila[1])

            cabecera = conexion.execute("""
                select id, estado, motivo_parcial from public.ejecuciones
                 where usuario_id = %s order by creado_en desc limit 1
            """, (usuario_id,)).fetchone()

            if cabecera:
                etapas = conexion.execute("""
                    select etapa, modelo, costo_usd, tokens, cache_hit
                      from public.etapas_ejecucion
                     where ejecucion_id = %s order by etapa
                """, (cabecera[0],)).fetchall()
                ultimo = {
                    "id": str(cabecera[0]),
                    "estado": cabecera[1],
                    "motivo_parcial": cabecera[2],
                    "costo_usd": round(sum(float(e[2]) for e in etapas), 6),
                    "etapas": [{"etapa": e[0], "modelo": e[1],
                                "costo_usd": float(e[2]), "tokens": e[3],
                                "cache_hit": e[4]} for e in etapas],
                }
    else:
        with sqlite3.connect(ruta_db_sqlite()) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(DISTINCT e.id), COALESCE(SUM(x.costo_usd), 0)
                  FROM ejecuciones e LEFT JOIN etapas_ejecucion x ON x.ejecucion_id = e.id
                 WHERE e.usuario_id = ?
                   AND strftime('%Y-%m', e.creado_en) = strftime('%Y-%m', 'now')
            """, (usuario_id,))
            runs, costo_mes = cur.fetchone()
            runs, costo_mes = int(runs or 0), float(costo_mes or 0)

            cur.execute("""SELECT id, estado, motivo_parcial FROM ejecuciones
                            WHERE usuario_id = ? ORDER BY creado_en DESC LIMIT 1""",
                        (usuario_id,))
            cabecera = cur.fetchone()
            if cabecera:
                cur.execute("""SELECT etapa, modelo, costo_usd, tokens, cache_hit
                                 FROM etapas_ejecucion WHERE ejecucion_id = ? ORDER BY etapa""",
                            (cabecera[0],))
                etapas = cur.fetchall()
                ultimo = {
                    "id": cabecera[0], "estado": cabecera[1],
                    "motivo_parcial": cabecera[2],
                    "costo_usd": round(sum(float(e[2] or 0) for e in etapas), 6),
                    "etapas": [{"etapa": e[0], "modelo": e[1],
                                "costo_usd": float(e[2] or 0), "tokens": e[3],
                                "cache_hit": bool(e[4])} for e in etapas],
                }

    return {
        "mes": datetime.now(timezone.utc).strftime("%Y-%m"),
        "plan": entitlement.plan,
        "costo_mes_usd": round(costo_mes, 6),
        "tope_usd": entitlement.tope_mes_usd,
        "runs": runs,
        # El tope global es del sistema, no del usuario, pero se expone porque
        # el kill-switch le afecta: si salta, sus runs degradan sin que su
        # propia cuota tenga nada que ver.
        #
        # S8.5: desde que el interruptor existe, este campo tiene DOS causas.
        # Calcularlo solo con el umbral dejaria al usuario viendo verde con el
        # sistema parado a mano, que es exactamente el caso en el que mas falta
        # hace saberlo.
        "kill_switch_activo": (contexto.gasto_global_mes_usd >= _tope_global()
                               or _parada_manual()),
        "ultimo_run": ultimo,
    }


def _parada_manual() -> bool:
    """Si un administrador ha accionado el interruptor de 8.5.

    Sin adaptador de configuracion —el plan B de sqlite— no hay interruptor
    que consultar, y la respuesta es que no.
    """
    return bool(dependencias.configuracion
                and dependencias.configuracion.kill_switch().activo)


def _tope_global() -> float:
    try:
        return float(os.getenv("PRESUPUESTO_GLOBAL_MES_USD", 10.0))
    except (TypeError, ValueError):
        return 10.0


def start():
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)
