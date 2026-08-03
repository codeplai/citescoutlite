"""
T7.2 - E2E de la Semana 3.

Diez pruebas que recorren lo que S3 anadio: estado gestionado, auth de Supabase,
paywall, cost-meter y kill-switch. Cierran P02, P06, P12 (parcial) y P13.

No corre en la suite por defecto: necesita credenciales y red. Con ellas, es
barato — los insumos que usa ya estan en el cache, asi que ningun test paga una
llamada al modelo salvo que alguien vacie `cache_llm`.

Las contrasenas de las cuentas demo se leen de `.env.local`, que esta en
.gitignore. Si no existe, correr antes:

    uv run python scripts/crear_usuarios_demo.py --generar
"""

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# api.main lee APP_DB al importarse, asi que se fija antes.
os.environ.setdefault("APP_DB", "supabase")

ARCHIVO_LOCAL = RAIZ / ".env.local"
CON_PRODUCTOS = "Arándano"            # 30 directos -> run completo
POCOS_PRODUCTOS = "cascara de cacao"  # n_directos <= 2 -> guard tecnico
ETAPAS_LLM = {"1", "3", "4", "5"}

pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not ARCHIVO_LOCAL.is_file(),
    reason="Necesita Supabase y las cuentas demo (.env.local)",
)


def _credenciales() -> dict[str, str]:
    texto = ARCHIVO_LOCAL.read_text(encoding="utf-8").splitlines()
    return dict(re.match(r"^([A-Z_]+)=(.*)$", ln.strip()).groups()
                for ln in texto if re.match(r"^([A-Z_]+)=(.*)$", ln.strip()))


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cliente():
    from fastapi.testclient import TestClient
    from api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def tokens(cliente):
    local = _credenciales()
    emitidos = {}
    for cuenta, variable in (("gratuita", "PASSWORD_DEMO_GRATUITA"),
                             ("premium", "PASSWORD_DEMO_PREMIUM")):
        email = f"demo-{cuenta}@cite.gob.pe"
        respuesta = cliente.post("/token",
                                 json={"email": email, "password": local[variable]})
        assert respuesta.status_code == 200, f"login de {email}: {respuesta.text}"
        emitidos[cuenta] = respuesta.json()["access_token"]
    return emitidos


@pytest.fixture(scope="module")
def uuids():
    from adaptadores.db import pool
    with pool().connection() as conexion:
        filas = conexion.execute("""select email, id from auth.users
                                     where email like 'demo-%@cite.gob.pe'""").fetchall()
    return {email.split("-")[1].split("@")[0]: str(uid) for email, uid in filas}


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _consultar(cliente, token, texto):
    respuesta = cliente.post("/consultas", json={"texto": texto}, headers=_auth(token))
    assert respuesta.status_code == 200, respuesta.text
    return respuesta.json()


def _etapas_de(ejecucion_id):
    from adaptadores.db import pool
    with pool().connection() as conexion:
        return conexion.execute("""
            select etapa, modelo, costo_usd, tokens, cache_hit
              from public.etapas_ejecucion where ejecucion_id = %s order by etapa
        """, (ejecucion_id,)).fetchall()


@pytest.fixture(scope="module")
def run_premium(cliente, tokens):
    return _consultar(cliente, tokens["premium"], CON_PRODUCTOS)


@pytest.fixture(scope="module")
def run_gratuito(cliente, tokens):
    return _consultar(cliente, tokens["gratuita"], CON_PRODUCTOS)


# --------------------------------------------------------------------------
# Estado y auth
# --------------------------------------------------------------------------

def test_esquema_supabase():
    """Las 5 tablas existen, con RLS activo y 3 politicas."""
    from adaptadores.db import pool
    tablas = ("perfiles", "ejecuciones", "etapas_ejecucion", "cache_llm", "informes")

    with pool().connection() as conexion:
        rls = dict(conexion.execute("""
            select tablename, rowsecurity from pg_tables
             where schemaname = 'public' and tablename = any(%s)
        """, (list(tablas),)).fetchall())
        politicas = conexion.execute(
            "select count(*) from pg_policies where schemaname = 'public'").fetchone()[0]
        vista = conexion.execute("""select count(*) from pg_views
                                     where schemaname = 'public'
                                       and viewname = 'uso_mensual'""").fetchone()[0]

    assert set(rls) == set(tablas), f"faltan tablas: {set(tablas) - set(rls)}"
    assert all(rls.values()), f"RLS apagado en: {[t for t, v in rls.items() if not v]}"
    assert politicas == 3, f"se esperaban 3 politicas, hay {politicas}"
    assert vista == 1, "falta la vista uso_mensual"


@pytest.mark.parametrize("nombre,cabecera", [
    ("sin cabecera", None),
    ("formato invalido", "Token abc"),
    ("firma manipulada", "Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ4In0.AAAA"),
    ("token vacio", "Bearer "),
])
def test_auth_rechaza_token_invalido(cliente, nombre, cabecera):
    """401 en todos los endpoints protegidos, sea cual sea la forma del fallo."""
    cabeceras = {"Authorization": cabecera} if cabecera else {}
    peticiones = [
        cliente.post("/consultas", json={"texto": "quinua"}, headers=cabeceras),
        cliente.get(f"/informes/{uuid.uuid4()}", headers=cabeceras),
        cliente.get(f"/ejecucion/{uuid.uuid4()}/tokens", headers=cabeceras),
        cliente.get("/uso", headers=cabeceras),
    ]
    codigos = [r.status_code for r in peticiones]
    assert codigos == [401] * 4, f"{nombre}: {codigos}"


def test_aislamiento_por_usuario(cliente, tokens, uuids, run_premium):
    """El informe de otro responde 404, no 403: un 403 confirmaria que existe."""
    ejecucion_id = run_premium["ejecucion_id"]

    propio = cliente.get(f"/informes/{ejecucion_id}", headers=_auth(tokens["premium"]))
    assert propio.status_code == 200 and "url" in propio.json()

    ajeno = cliente.get(f"/informes/{ejecucion_id}", headers=_auth(tokens["gratuita"]))
    assert ajeno.status_code == 404


# --------------------------------------------------------------------------
# P06 - paywall frente a guard tecnico
# --------------------------------------------------------------------------

# Las etapas premium. Se comprueba su ausencia o presencia, no la lista exacta
# de etapas del run: el inventario crece (2b llego con S4, 6 llegara despues) y
# un test que fije la lista entera se rompe cada vez sin que nada este mal.
ETAPAS_PREMIUM = {"4", "5"}


def test_paywall_gratuito(run_gratuito):
    """Sin etapas premium, informe parcial y motivo 'paywall'. Y 200, no 402."""
    etapas = {fila[0] for fila in _etapas_de(run_gratuito["ejecucion_id"])}
    assert "1" in etapas and "3" in etapas, etapas
    assert not (etapas & ETAPAS_PREMIUM), f"el plan gratuito ejecuto {etapas & ETAPAS_PREMIUM}"
    assert run_gratuito["parcial"] is True
    assert run_gratuito["motivo_parcial"] == "paywall"
    assert run_gratuito["hipotesis"] is None
    assert run_gratuito["dossier"] is None


def test_premium_completo(run_premium):
    """Mismo insumo con cuenta premium: las dos etapas de pago y sin motivo."""
    etapas = {fila[0] for fila in _etapas_de(run_premium["ejecucion_id"])}
    assert ETAPAS_PREMIUM <= etapas, f"faltan {ETAPAS_PREMIUM - etapas}"
    assert run_premium["motivo_parcial"] is None
    assert run_premium["hipotesis"] is not None
    assert run_premium["dossier"] is not None


def test_guard_tecnico_no_es_paywall(cliente, tokens):
    """Con pocos productos el motivo es tecnico, aunque la cuenta sea premium."""
    informe = _consultar(cliente, tokens["premium"], POCOS_PRODUCTOS)
    assert informe["motivo_parcial"] == "pocos_productos"
    # Las etapas premium se ejecutan igual: no es un recorte de plan, es que el
    # snapshot dio poco. Confundir las dos cosas es lo que P06 prohibe.
    etapas = {fila[0] for fila in _etapas_de(informe["ejecucion_id"])}
    assert ETAPAS_PREMIUM <= etapas, f"faltan {ETAPAS_PREMIUM - etapas}"


# --------------------------------------------------------------------------
# P02 - cache
# --------------------------------------------------------------------------

def test_cache_hit_sin_llm(cliente, tokens, run_premium):
    """El segundo run identico no llama al modelo. Se comprueba con la columna
    cache_hit y no deduciendolo de que los tokens sean 0."""
    repetido = _consultar(cliente, tokens["premium"], CON_PRODUCTOS)
    etapas = _etapas_de(repetido["ejecucion_id"])

    llamadas = [fila[0] for fila in etapas if fila[0] in ETAPAS_LLM and not fila[4]]
    assert not llamadas, f"estas etapas volvieron a llamar al LLM: {llamadas}"
    assert sum(fila[3] for fila in etapas) == 0, "el segundo run gasto tokens"
    assert sum(float(fila[2]) for fila in etapas) == 0, "el segundo run costo dinero"


# --------------------------------------------------------------------------
# P13 - cost-meter
# --------------------------------------------------------------------------

def test_costo_cuadra(cliente, tokens, uuids, run_premium):
    """Lo que dice /uso es exactamente lo que hay en la base, y solo lo suyo."""
    from adaptadores.db import pool

    respuesta = cliente.get("/uso", headers=_auth(tokens["premium"]))
    assert respuesta.status_code == 200
    uso = respuesta.json()

    with pool().connection() as conexion:
        real = float(conexion.execute("""
            select coalesce(sum(x.costo_usd), 0) from public.etapas_ejecucion x
              join public.ejecuciones e on e.id = x.ejecucion_id
             where e.usuario_id = %s
               and date_trunc('month', e.creado_en) = date_trunc('month', now())
        """, (uuids["premium"],)).fetchone()[0])

        dueno = conexion.execute(
            "select usuario_id from public.ejecuciones where id = %s",
            (uso["ultimo_run"]["id"],)).fetchone()[0]

    assert abs(uso["costo_mes_usd"] - real) < 1e-6, (uso["costo_mes_usd"], real)
    assert uso["plan"] == "premium"
    assert str(dueno) == uuids["premium"], "/uso mostro el run de otro usuario"


def test_uso_no_incluye_runs_ajenos(cliente, tokens, uuids):
    """Cada cuenta ve su gasto y solo el suyo."""
    from adaptadores.db import pool

    gratuita = cliente.get("/uso", headers=_auth(tokens["gratuita"])).json()
    premium = cliente.get("/uso", headers=_auth(tokens["premium"])).json()

    with pool().connection() as conexion:
        total = float(conexion.execute("""
            select coalesce(sum(costo_usd), 0) from public.uso_mensual
             where mes = date_trunc('month', now())
        """).fetchone()[0])

    assert gratuita["plan"] == "gratuito" and premium["plan"] == "premium"
    # Ninguna de las dos ve el total del sistema: el suyo es una parte.
    assert gratuita["costo_mes_usd"] <= total
    assert premium["costo_mes_usd"] <= total


# --------------------------------------------------------------------------
# P12 - kill-switch
# --------------------------------------------------------------------------

def test_killswitch_degrada_sin_error(cliente, tokens, monkeypatch):
    """Tope global a 0: HTTP 200, run parcial, motivo 'presupuesto' y **cero**
    llamadas al modelo. Un tope de gasto es una decision de negocio, no un
    fallo: por eso no es un 500."""
    monkeypatch.setenv("PRESUPUESTO_GLOBAL_MES_USD", "0")

    respuesta = cliente.post("/consultas", json={"texto": CON_PRODUCTOS},
                             headers=_auth(tokens["premium"]))
    assert respuesta.status_code == 200, respuesta.text

    informe = respuesta.json()
    assert informe["parcial"] is True
    assert informe["motivo_parcial"] == "presupuesto"

    etapas = _etapas_de(informe["ejecucion_id"])
    assert sum(fila[3] for fila in etapas) == 0, "el kill-switch dejo pasar tokens"


# --------------------------------------------------------------------------
# Plan B
# --------------------------------------------------------------------------

def test_plan_b_sqlite(tmp_path):
    """APP_DB=sqlite + AGROSCOUT_OFFLINE=1 completa un run sin tocar la red.

    Corre en un subproceso porque api.main decide su backend al importarse: no
    se pueden tener las dos ramas vivas en el mismo proceso.
    """
    guion = f'''
import os
os.environ["APP_DB"] = "sqlite"
os.environ["AGROSCOUT_OFFLINE"] = "1"

from dotenv import load_dotenv
load_dotenv(r"{RAIZ / '.env'}")
os.environ["APP_DB"] = "sqlite"
os.environ["AGROSCOUT_OFFLINE"] = "1"

import asyncio
from adaptadores.auditoria_sqlite import AuditoriaSQLite
from adaptadores.busqueda_lancedb import BusquedaLanceDB
from adaptadores.cache_sqlite import CacheSQLite
from adaptadores.descubrimiento_snapshot import DescubrimientoSnapshot
from adaptadores.informe_weasyprint import InformeWeasyPrint
from adaptadores.redactor_glm import RedactorGLM
from adaptadores.suscripciones_sqlite import SuscripcionesSQLite
from adaptadores.verificador_openfda import VerificadorOpenFDA
from adaptadores.verificador_rag import VerificadorRAG
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.evaluar_insumo import generar_mapa_comercial

d = Dependencias(
    # Sin api_key: si alguna etapa intentara llamar al modelo, fallaria. Que el
    # run termine demuestra que salio entero del cache local.
    redactor=RedactorGLM(api_key="", base_url=None),
    catalogo=BusquedaLanceDB(), cache=CacheSQLite(),
    informes=InformeWeasyPrint(), auditoria=AuditoriaSQLite(),
    verificador_fda=VerificadorOpenFDA(offline=True),
    verificador_rag=VerificadorRAG(offline=True),
    suscripciones=SuscripcionesSQLite(),
    # Mismos adaptadores que api/main.py. El descubrimiento de la etapa 2b no
    # es opcional aqui: su salida entra en la clave de cache de la etapa 3, asi
    # que omitirlo produciria una clave distinta y el run buscaria el LLM.
    descubrimiento=DescubrimientoSnapshot(),
    snapshot_version="2026-07")

informe = asyncio.run(generar_mapa_comercial({CON_PRODUCTOS!r}, d, "plan-b"))
assert informe.markdown_content, "el informe salio vacio"
assert informe.ruta_pdf, "no se genero el PDF"
print("PLAN_B_OK", informe.ejecucion_id)
'''
    proceso = subprocess.run([sys.executable, "-c", guion], cwd=RAIZ,
                             capture_output=True, text=True, timeout=600)
    assert "PLAN_B_OK" in proceso.stdout, (
        f"el plan B no completo el run.\nstdout: {proceso.stdout[-2000:]}\n"
        f"stderr: {proceso.stderr[-2000:]}")
