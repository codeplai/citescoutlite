"""
S8.5 y S8.9 - El kill-switch y los planes.

Lo que decide si esta fase sirve no es que el botón guarde un booleano, sino
**qué hace el sistema cuando está encendido**: los runs tienen que seguir
respondiendo 200 y cerrar en parcial, no fallar. Degradar, nunca error
(ADR-001). Eso es lo primero que se prueba.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api.admin as admin
from adaptadores.configuracion_postgres import ConfiguracionPostgres
from api.auth import requiere_admin
from casos_de_uso.presupuesto import Presupuesto
from puertos.suscripciones import ContextoSuscripcion

_ID = str(uuid4())
ADMIN = {"sub": _ID, "user_id": _ID, "email": "admin@cite.gob.pe"}

HOLGADO = ContextoSuscripcion(plan="premium", gasto_usuario_mes_usd=0.0,
                              gasto_global_mes_usd=0.0)


def _presupuesto(**extra) -> Presupuesto:
    base = dict(tope_run_usd=1.0, tope_usuario_mes_usd=10.0,
                tope_global_mes_usd=100.0)
    return Presupuesto(**{**base, **extra})


# ---------------------------------------------------------------------------
# El interruptor corta el gasto
# ---------------------------------------------------------------------------

class TestParadaManual:
    def test_con_el_switch_encendido_no_se_gasta(self):
        assert _presupuesto(parada_manual=True).agotado

    def test_y_con_nombre_propio(self):
        """'manual' y no 'global_mes': "se paró el gasto" y "se acabó el
        presupuesto del mes" no son la misma noticia ni llevan a la misma
        acción."""
        assert _presupuesto(parada_manual=True).nivel_agotado() == "manual"

    def test_manda_sobre_cualquier_cifra(self):
        """Una decisión humana no la discute un tope: da igual cuánto quede."""
        p = _presupuesto(parada_manual=True, gasto_run_usd=0.0,
                         gasto_usuario_mes_usd=0.0, gasto_global_mes_usd=0.0)
        assert p.nivel_agotado() == "manual"

    def test_apagado_no_cambia_nada(self):
        assert _presupuesto(parada_manual=False).nivel_agotado() is None

    def test_por_defecto_esta_apagado(self):
        """Quien construya un Presupuesto sin saber que existe el interruptor
        tiene que obtener el comportamiento de antes."""
        assert _presupuesto().parada_manual is False
        assert Presupuesto.desde_entorno(HOLGADO).parada_manual is False

    def test_desde_entorno_lo_propaga(self):
        assert Presupuesto.desde_entorno(HOLGADO, parada_manual=True).parada_manual

    def test_el_resumen_lo_expone(self):
        """El informe degradado tiene que poder decir por qué lo está."""
        assert _presupuesto(parada_manual=True).resumen()["parada_manual"] is True

    def test_los_topes_siguen_funcionando_sin_el(self):
        p = _presupuesto(parada_manual=False, gasto_global_mes_usd=999.0)
        assert p.nivel_agotado() == "global_mes"


# ---------------------------------------------------------------------------
# Leer el interruptor falla hacia el lado seguro
# ---------------------------------------------------------------------------

class TestLecturaSegura:
    def test_si_la_base_falla_se_asume_apagado(self, monkeypatch):
        """Un error de lectura que dejara el sistema parado convertiría una
        incidencia de base de datos en una caída del servicio."""
        monkeypatch.setattr(
            "adaptadores.configuracion_postgres.pool",
            lambda: (_ for _ in ()).throw(RuntimeError("sin base")))

        assert ConfiguracionPostgres().kill_switch().activo is False

    def test_un_valor_que_no_es_booleano_no_para_el_sistema(self, monkeypatch):
        """La columna es jsonb sin esquema: un `{"activo": "si"}` escrito a
        mano contra la base no puede parar a todo el mundo."""
        class CursorFalso:
            def execute(self, *a, **k): return self
            def fetchone(self): return ({"activo": "si", "motivo": None}, None, None)
            def __enter__(self): return self
            def __exit__(self, *a): return False

        class ConexionFalsa:
            def cursor(self): return CursorFalso()
            def __enter__(self): return self
            def __exit__(self, *a): return False

        class PoolFalso:
            def connection(self): return ConexionFalsa()

        monkeypatch.setattr("adaptadores.configuracion_postgres.pool",
                            lambda: PoolFalso())

        assert ConfiguracionPostgres().kill_switch().activo is False


# ---------------------------------------------------------------------------
# Los endpoints
# ---------------------------------------------------------------------------

class ConfigFalsa:
    def __init__(self, activo=False, motivo=None, revienta_al_escribir=False):
        self._activo = activo
        self._motivo = motivo
        self.revienta = revienta_al_escribir
        self.escrituras = []

    def kill_switch(self):
        from puertos.configuracion_sistema import EstadoKillSwitch
        return EstadoKillSwitch(activo=self._activo, motivo=self._motivo)

    def fijar_kill_switch(self, activo, *, motivo=None, por=None):
        if self.revienta:
            raise RuntimeError("no se pudo escribir")
        self.escrituras.append({"activo": activo, "motivo": motivo, "por": por})
        self._activo, self._motivo = activo, motivo
        return self.kill_switch()


class PerfilesFalso:
    def __init__(self, plan_actual="gratuito", existe=True):
        self._plan = plan_actual
        self._existe = existe

    def listar(self, limite=200):
        return [{"id": _ID, "email": "a@cite.gob.pe", "plan": self._plan,
                 "rol": "operador", "creado_en": None, "runs_mes": 3,
                 "costo_mes_usd": 0.01}]

    def cambiar_plan(self, usuario_id, plan):
        if not self._existe:
            return None
        antes, self._plan = self._plan, plan
        return {"antes": antes, "despues": plan}


class AuditoriaFalsa:
    def __init__(self):
        self.registros = []

    def registrar(self, evento, **kwargs):
        self.registros.append({"evento": evento, **kwargs})
        return len(self.registros)


def montar(config=None, perfiles=None, auditoria=None, es_admin=True):
    app = FastAPI()
    app.include_router(admin.router)
    admin._config = config or ConfigFalsa()
    admin._perfiles = perfiles or PerfilesFalso()
    admin._auditoria = auditoria or AuditoriaFalsa()

    def _admin():
        if not es_admin:
            raise HTTPException(status_code=403, detail="Requiere rol de administrador")
        return ADMIN

    app.dependency_overrides[requiere_admin] = _admin
    return TestClient(app)


class TestControlDeAcceso:
    @pytest.mark.parametrize("metodo,ruta,cuerpo", [
        ("get", "/api/admin/kill-switch", None),
        ("put", "/api/admin/kill-switch", {"activo": True}),
        ("get", "/api/admin/usuarios", None),
        ("put", f"/api/admin/usuarios/{_ID}/plan", {"plan": "premium"}),
    ])
    def test_un_operador_no_entra(self, metodo, ruta, cuerpo):
        cliente = montar(es_admin=False)
        respuesta = getattr(cliente, metodo)(ruta, **({"json": cuerpo} if cuerpo else {}))
        assert respuesta.status_code == 403

    def test_un_operador_no_para_el_sistema_ni_por_accidente(self):
        config = ConfigFalsa()
        montar(config, es_admin=False).put("/api/admin/kill-switch",
                                           json={"activo": True})
        assert config.escrituras == []


class TestKillSwitch:
    def test_lo_enciende(self):
        config = ConfigFalsa(activo=False)
        datos = montar(config).put("/api/admin/kill-switch",
                                   json={"activo": True, "motivo": "incidente"}).json()

        assert datos["activo"] is True
        assert datos["motivo"] == "incidente"
        assert config.escrituras[0]["por"] == _ID

    def test_cambiarlo_se_audita_con_antes_y_despues(self):
        auditoria = AuditoriaFalsa()
        montar(ConfigFalsa(activo=False), auditoria=auditoria).put(
            "/api/admin/kill-switch", json={"activo": True, "motivo": "x"})

        registro = auditoria.registros[0]
        assert registro["evento"] == "kill_switch_toggled"
        assert registro["antes"]["activo"] is False
        assert registro["despues"]["activo"] is True
        assert registro["usuario_email"] == "admin@cite.gob.pe"

    def test_reenviar_el_mismo_estado_no_ensucia_la_auditoria(self):
        """El panel refresca; si cada refresco dejara una entrada, entre ellas
        se perdería la única que importa: la vez que alguien lo apagó."""
        auditoria = AuditoriaFalsa()
        cliente = montar(ConfigFalsa(activo=True), auditoria=auditoria)
        respuesta = cliente.put("/api/admin/kill-switch", json={"activo": True})

        assert respuesta.status_code == 200
        assert respuesta.json()["cambio"] is False
        assert auditoria.registros == []

    def test_si_no_se_puede_guardar_se_dice(self):
        """Un botón que dice que ha parado el gasto sin haberlo parado es peor
        que uno que da error."""
        cliente = montar(ConfigFalsa(revienta_al_escribir=True))
        assert cliente.put("/api/admin/kill-switch",
                           json={"activo": True}).status_code == 500

    def test_un_fallo_al_escribir_no_deja_rastro_de_exito(self):
        auditoria = AuditoriaFalsa()
        montar(ConfigFalsa(revienta_al_escribir=True), auditoria=auditoria).put(
            "/api/admin/kill-switch", json={"activo": True})
        assert auditoria.registros == []

    def test_el_motivo_no_puede_ser_un_parte_entero(self):
        cliente = montar(ConfigFalsa())
        respuesta = cliente.put("/api/admin/kill-switch",
                                json={"activo": True, "motivo": "x" * 500})
        assert respuesta.status_code == 422


class TestElRunLoRespeta:
    """El DoD de la fase: el interruptor tiene que llegar hasta el run.

    Se comprueba en la frontera —`atender_consulta`— porque es donde se lee la
    tabla y se construye el Presupuesto. Que un Presupuesto con
    `parada_manual` corte el gasto ya está probado arriba; lo que falta es que
    alguien se lo pase.
    """

    @pytest.fixture
    def capturar(self, monkeypatch):
        capturado = {}

        async def falsa(texto, d, usuario_id=None):
            capturado["presupuesto"] = d.presupuesto
            return "informe"

        import casos_de_uso.evaluar_insumo as ei
        monkeypatch.setattr(ei, "generar_dossier", falsa)
        monkeypatch.setattr(ei, "generar_mapa_comercial", falsa)
        return capturado

    def _dependencias(self, configuracion):
        from casos_de_uso.dependencias import Dependencias

        class Suscripciones:
            def contexto_de(self, _usuario_id):
                return HOLGADO

        return Dependencias(
            redactor=None, catalogo=None, cache=None, informes=None,
            auditoria=None, suscripciones=Suscripciones(),
            configuracion=configuracion,
        )

    @pytest.mark.asyncio
    async def test_el_switch_encendido_llega_al_presupuesto(self, capturar):
        from casos_de_uso.evaluar_insumo import atender_consulta

        await atender_consulta("quinua", self._dependencias(ConfigFalsa(activo=True)))

        assert capturar["presupuesto"].parada_manual is True
        assert capturar["presupuesto"].nivel_agotado() == "manual"

    @pytest.mark.asyncio
    async def test_apagado_el_run_corre_como_siempre(self, capturar):
        from casos_de_uso.evaluar_insumo import atender_consulta

        await atender_consulta("quinua", self._dependencias(ConfigFalsa(activo=False)))

        assert capturar["presupuesto"].parada_manual is False
        assert capturar["presupuesto"].nivel_agotado() is None

    @pytest.mark.asyncio
    async def test_sin_adaptador_de_configuracion_no_hay_interruptor(self, capturar):
        """El plan B de sqlite y los tests deterministas de S2 arman
        Dependencias sin tocar la base: no pueden quedarse parados."""
        from casos_de_uso.evaluar_insumo import atender_consulta

        await atender_consulta("quinua", self._dependencias(None))

        assert capturar["presupuesto"].parada_manual is False


class TestPlanes:
    def test_cambia_el_plan(self):
        datos = montar(perfiles=PerfilesFalso("gratuito")).put(
            f"/api/admin/usuarios/{_ID}/plan", json={"plan": "premium"}).json()

        assert datos["antes"] == "gratuito"
        assert datos["despues"] == "premium"

    def test_se_audita_con_antes_y_despues(self):
        auditoria = AuditoriaFalsa()
        montar(perfiles=PerfilesFalso("gratuito"), auditoria=auditoria).put(
            f"/api/admin/usuarios/{_ID}/plan", json={"plan": "premium"})

        registro = auditoria.registros[0]
        assert registro["evento"] == "plan_changed"
        assert registro["entidad"] == "perfiles"
        assert registro["entidad_id"] == _ID
        assert registro["antes"] == {"plan": "gratuito"}
        assert registro["despues"] == {"plan": "premium"}

    def test_poner_el_mismo_plan_no_se_audita(self):
        auditoria = AuditoriaFalsa()
        montar(perfiles=PerfilesFalso("premium"), auditoria=auditoria).put(
            f"/api/admin/usuarios/{_ID}/plan", json={"plan": "premium"})
        assert auditoria.registros == []

    def test_un_plan_inventado_se_rechaza(self):
        """Y con 400, no con el 500 que daría el check de la tabla."""
        cliente = montar()
        assert cliente.put(f"/api/admin/usuarios/{_ID}/plan",
                           json={"plan": "oro"}).status_code == 400

    def test_un_plan_inventado_no_se_audita(self):
        auditoria = AuditoriaFalsa()
        montar(auditoria=auditoria).put(f"/api/admin/usuarios/{_ID}/plan",
                                        json={"plan": "oro"})
        assert auditoria.registros == []

    def test_un_usuario_que_no_existe_da_404(self):
        cliente = montar(perfiles=PerfilesFalso(existe=False))
        assert cliente.put(f"/api/admin/usuarios/{_ID}/plan",
                           json={"plan": "premium"}).status_code == 404

    def test_el_listado_trae_el_gasto_del_mes(self):
        """Cambiar el plan de alguien sin ver lo que consume es decidir a
        ciegas."""
        datos = montar().get("/api/admin/usuarios").json()
        assert datos["usuarios"][0]["costo_mes_usd"] == 0.01
        assert datos["planes"] == ["gratuito", "premium"]
