"""
S7.6 - Endpoints de promoción manual.

Lo que más importa aquí es el control de acceso: promover cambia lo que ve
todo el mundo, así que un operador no debe poder. El repositorio se sustituye
por un doble; su SQL se prueba aparte.
"""

from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api.promociones as promociones
from api.auth import get_current_user, requiere_admin


# Con las dos claves: `sub` es lo que usa la rama Supabase y `user_id` la de
# sqlite. Los tests no cargan .env, asi que el modo depende del entorno y el
# usuario tiene que servir en ambos.
_ID_ADMIN = str(uuid4())
_ID_OPERADOR = str(uuid4())
ADMIN = {"sub": _ID_ADMIN, "user_id": _ID_ADMIN, "email": "admin@cite.gob.pe"}
OPERADOR = {"sub": _ID_OPERADOR, "user_id": _ID_OPERADOR,
            "email": "operador@cite.gob.pe"}


class RepoFalso:
    def __init__(self, ofertas=None):
        self._ofertas = ofertas or []
        self.promovidas = []
        self.rechazos = []
        self.validaciones = []
        self.promover_devuelve = True

    def cola_manual(self, semilla, limite=100, solo_con_errores=False):
        return [{
            "staging_id": str(o["staging_id"]),
            "insumo": "quinua", "pais": "PE",
            "producto": {"nombre": "Quinua 500g", "precio": 24.9},
            "fuente_url": "https://t.example/p",
            "creado_en": None, "grounding": None,
            "automatica": False, "cubo": 91,
            "errores": [], "validacion_passed": None,
            "validado_en": None, "horas_en_cuarentena": 3.0,
        } for o in self._ofertas]

    def ofertas_en_cuarentena(self, limite=1000):
        return self._ofertas

    def leer_reglas(self, solo_activas=True):
        return []

    def registrar_validacion(self, staging_id, passed, errores, reglas):
        self.validaciones.append(staging_id)

    def promover(self, staging_id, promotion_source, reglas, promoted_by=None):
        if not self.promover_devuelve:
            return False
        self.promovidas.append({"staging_id": staging_id, "source": promotion_source,
                                "por": promoted_by})
        return True

    def registrar_rechazo(self, staging_id, errores, reglas, promoted_by=None):
        self.rechazos.append(staging_id)

    def historial(self, dias=7, limite=200):
        return []

    def resumen_del_dia(self):
        return {"promovidos_auto": 3, "promovidos_manual": 1, "rechazados": 2,
                "motivos_de_rechazo": {}}


def montar(repo, usuario=ADMIN, es_admin=True) -> TestClient:
    app = FastAPI()
    app.include_router(promociones.router)
    promociones._repo = repo

    app.dependency_overrides[get_current_user] = lambda: usuario

    def _admin():
        if not es_admin:
            raise HTTPException(status_code=403, detail="Requiere rol de administrador")
        return usuario

    app.dependency_overrides[requiere_admin] = _admin
    return TestClient(app)


@pytest.fixture
def oferta():
    return {"staging_id": uuid4(), "fuente_url": "https://t.example/p",
            "producto_json": {"nombre": "Quinua"}, "creado_en": None,
            "grounding_check_status": {"passed": True, "errores": []}}


class TestControlDeAcceso:
    def test_un_operador_no_puede_promover(self, oferta):
        cliente = montar(RepoFalso([oferta]), usuario=OPERADOR, es_admin=False)
        r = cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")
        assert r.status_code == 403

    def test_un_operador_no_puede_rechazar(self, oferta):
        cliente = montar(RepoFalso([oferta]), usuario=OPERADOR, es_admin=False)
        r = cliente.post(f"/api/promociones/{oferta['staging_id']}/rechazar")
        assert r.status_code == 403

    def test_un_operador_no_puede_promover_en_lote(self, oferta):
        cliente = montar(RepoFalso([oferta]), usuario=OPERADOR, es_admin=False)
        r = cliente.post("/api/promociones/promover-lote",
                         json={"staging_ids": [str(oferta["staging_id"])]})
        assert r.status_code == 403

    def test_un_operador_si_puede_ver_la_cola(self, oferta):
        """Mirar la cola de revision puede hacerlo cualquiera del equipo."""
        cliente = montar(RepoFalso([oferta]), usuario=OPERADOR, es_admin=False)
        r = cliente.get("/api/promociones/pendientes")
        assert r.status_code == 200
        assert r.json()["total"] == 1

    def test_un_operador_no_promueve_ni_por_accidente(self, oferta):
        """El 403 tiene que cortar ANTES de tocar nada."""
        repo = RepoFalso([oferta])
        cliente = montar(repo, usuario=OPERADOR, es_admin=False)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")
        assert repo.promovidas == []


class TestPromocion:
    def test_promueve_con_la_procedencia_de_d1(self, oferta):
        repo = RepoFalso([oferta])
        cliente = montar(repo)
        r = cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")
        assert r.status_code == 200 and r.json()["ok"]
        assert repo.promovidas[0]["source"] == "manual_human"

    def test_registra_quien_promovio(self, oferta):
        repo = RepoFalso([oferta])
        cliente = montar(repo)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")
        assert str(repo.promovidas[0]["por"]) == _ID_ADMIN

    def test_revalida_antes_de_promover(self, oferta):
        """Entre pintar la lista y pulsar el boton puede haber caducado."""
        repo = RepoFalso([oferta])
        cliente = montar(repo)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")
        assert len(repo.validaciones) == 1

    def test_una_oferta_que_ya_no_esta_da_motivo(self):
        repo = RepoFalso([])
        cliente = montar(repo)
        r = cliente.post(f"/api/promociones/{uuid4()}/promover")
        assert r.json()["ok"] is False
        assert "cuarentena" in r.json()["motivo"]

    def test_carrera_con_el_job_no_cuenta_como_promovida(self, oferta):
        repo = RepoFalso([oferta])
        repo.promover_devuelve = False
        cliente = montar(repo)
        r = cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")
        assert r.json()["ok"] is False
        assert "antes" in r.json()["motivo"]

    def test_uuid_invalido_no_revienta(self):
        cliente = montar(RepoFalso([]))
        r = cliente.post("/api/promociones/no-es-uuid/promover")
        assert r.status_code == 200
        assert r.json()["ok"] is False


class TestLote:
    def test_una_que_falla_no_cancela_el_resto(self, oferta):
        buena, mala = oferta, {"staging_id": uuid4()}
        repo = RepoFalso([buena])  # `mala` no esta en cuarentena
        cliente = montar(repo)

        r = cliente.post("/api/promociones/promover-lote", json={
            "staging_ids": [str(buena["staging_id"]), str(mala["staging_id"])]})

        resultados = r.json()
        assert [x["ok"] for x in resultados] == [True, False]
        assert len(repo.promovidas) == 1

    def test_lote_vacio_se_rechaza(self):
        cliente = montar(RepoFalso([]))
        assert cliente.post("/api/promociones/promover-lote",
                            json={"staging_ids": []}).status_code == 422


class TestRechazo:
    def test_rechazar_registra_pero_no_borra(self, oferta):
        repo = RepoFalso([oferta])
        cliente = montar(repo)
        r = cliente.post(f"/api/promociones/{oferta['staging_id']}/rechazar")
        assert r.json()["ok"]
        assert len(repo.rechazos) == 1
        assert repo.promovidas == []


class TestLecturas:
    def test_resumen(self):
        cliente = montar(RepoFalso([]))
        assert cliente.get("/api/promociones/resumen").json()["promovidos_auto"] == 3

    def test_historial(self):
        cliente = montar(RepoFalso([]))
        r = cliente.get("/api/promociones/historial?dias=30")
        assert r.status_code == 200 and r.json()["dias"] == 30
