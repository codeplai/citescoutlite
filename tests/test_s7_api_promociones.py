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

    def resumen_del_dia(self, horas=24):
        total = 6
        return {"ventana_horas": horas, "promovidos_auto": 3,
                "promovidos_manual": 1, "rechazados": 2, "total": total,
                "pct_auto": 50.0,
                "motivos_de_rechazo": {"dato_fresco": 2}}

    def tendencia(self, dias=7):
        return [{"dia": f"2026-08-{5 + i:02d}", "auto": i, "manual": 0,
                 "rechazadas": 0} for i in range(dias)]


class AuditoriaFalsa:
    """Doble de la auditoría de S8.3.

    Se instala siempre, y no solo cuando un test mira lo que registró. Sin
    esto, `promociones._auditoria` es el objeto real y estos tests escribirían
    en la tabla de auditoría de verdad —con staging_ids inventados— en cuanto
    alguien corra la suite con el entorno cargado. Hoy no pasa solo porque los
    tests no leen `.env` y la conexión falla en silencio, que es una garantía
    por accidente.
    """

    def __init__(self):
        self.registros = []

    def registrar(self, evento, **kwargs):
        self.registros.append({"evento": evento, **kwargs})
        return len(self.registros)


def montar(repo, usuario=ADMIN, es_admin=True,
           auditoria=None) -> TestClient:
    app = FastAPI()
    app.include_router(promociones.router)
    promociones._repo = repo
    promociones._auditoria = auditoria if auditoria is not None else AuditoriaFalsa()

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


class TestAuditoria:
    """S8.3 - promover y rechazar dejan rastro."""

    def test_promover_deja_una_entrada(self, oferta):
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso([oferta]), auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")

        assert len(auditoria.registros) == 1
        registro = auditoria.registros[0]
        assert registro["evento"] == "promotion_manual"
        assert registro["usuario_id"] == _ID_ADMIN
        assert registro["usuario_email"] == "admin@cite.gob.pe"
        assert registro["entidad_id"] == str(oferta["staging_id"])

    def test_lo_que_cambio_va_en_antes_y_despues(self, oferta):
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso([oferta]), auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")

        registro = auditoria.registros[0]
        assert registro["antes"]["promotion_source"] is None
        assert registro["despues"]["promotion_source"] == "manual_human"

    def test_la_entrada_se_entiende_sin_la_oferta_delante(self, oferta):
        """`staging_agente` tiene un TTL de 24 h. Una entrada que solo guardase
        el id sería ilegible mañana, y la auditoría se conserva un año."""
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso([oferta]), auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")

        assert auditoria.registros[0]["detalles"]["nombre"] == "Quinua"

    def test_una_promocion_que_no_ocurrio_no_se_audita(self, oferta):
        """Si otro proceso llegó antes, no hubo cambio: anotarlo sería
        registrar algo que no pasó."""
        repo = RepoFalso([oferta])
        repo.promover_devuelve = False
        auditoria = AuditoriaFalsa()
        cliente = montar(repo, auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")

        assert auditoria.registros == []

    def test_un_403_no_deja_rastro_de_promocion(self, oferta):
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso([oferta]), usuario=OPERADOR, es_admin=False,
                         auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/promover")

        assert auditoria.registros == []

    def test_rechazar_tambien_deja_entrada(self, oferta):
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso([oferta]), auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/rechazar")

        registro = auditoria.registros[0]
        assert registro["evento"] == "promotion_rejected"
        assert registro["detalles"]["nombre"] == "Quinua"

    def test_el_rechazo_no_inventa_un_cambio_de_estado(self, oferta):
        """Rechazar no toca la fila: sigue en cuarentena hasta que el TTL se la
        lleve. Rellenar un `despues` para que la columna no quede vacía sería
        afirmar un cambio que no ha ocurrido."""
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso([oferta]), auditoria=auditoria)
        cliente.post(f"/api/promociones/{oferta['staging_id']}/rechazar")

        registro = auditoria.registros[0]
        assert registro.get("antes") is None
        assert registro.get("despues") is None

    def test_cada_oferta_del_lote_tiene_su_entrada(self, oferta):
        """Dentro de un año la pregunta es "por qué se promovió ESTA oferta", y
        una entrada que diga "se promovieron 3" no la responde."""
        ofertas = [{**oferta, "staging_id": uuid4()} for _ in range(3)]
        auditoria = AuditoriaFalsa()
        cliente = montar(RepoFalso(ofertas), auditoria=auditoria)
        cliente.post("/api/promociones/promover-lote",
                     json={"staging_ids": [str(o["staging_id"]) for o in ofertas]})

        assert len(auditoria.registros) == 3
        assert len({r["entidad_id"] for r in auditoria.registros}) == 3


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


class TestEstadisticas:
    """S7.9 - lo que pinta el widget."""

    def test_resumen_y_tendencia_vienen_juntos(self):
        """En dos llamadas, un refresco a medias mezclaria dos ventanas."""
        cliente = montar(RepoFalso([]))
        d = cliente.get("/api/promociones/estadisticas").json()
        assert set(d) == {"resumen", "tendencia"}

    def test_la_tendencia_trae_un_punto_por_dia(self):
        cliente = montar(RepoFalso([]))
        d = cliente.get("/api/promociones/estadisticas?dias=7").json()
        assert len(d["tendencia"]) == 7

    def test_el_porcentaje_lo_calcula_el_backend(self):
        """Para que el job, la API y el panel no discrepen por redondeo."""
        cliente = montar(RepoFalso([]))
        assert cliente.get("/api/promociones/estadisticas").json()["resumen"]["pct_auto"] == 50.0

    def test_ventana_configurable(self):
        cliente = montar(RepoFalso([]))
        d = cliente.get("/api/promociones/estadisticas?horas=72").json()
        assert d["resumen"]["ventana_horas"] == 72

    def test_ventanas_fuera_de_rango_se_rechazan(self):
        cliente = montar(RepoFalso([]))
        assert cliente.get("/api/promociones/estadisticas?horas=0").status_code == 422
        assert cliente.get("/api/promociones/estadisticas?dias=999").status_code == 422

    def test_requiere_estar_autenticado_pero_no_ser_admin(self):
        cliente = montar(RepoFalso([]), usuario=OPERADOR, es_admin=False)
        assert cliente.get("/api/promociones/estadisticas").status_code == 200
