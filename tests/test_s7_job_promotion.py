"""
S7.5 - Job de promoción automática.

Con un repositorio doble: lo que se comprueba aquí es el reparto 80/20, que se
valide antes de promover y que todo quede registrado. El SQL se prueba aparte.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from casos_de_uso.promocion import Regla
from config.job_promotion_auto import job_promotion_auto


FRESCURA = Regla("dato_fresco", {"tipo": "date_freshness", "max_dias": 7})
URL = Regla("url_presente", {"tipo": "url_presente"})
SEMANA = datetime(2026, 8, 11, 4, 0, tzinfo=timezone.utc)


class RepositorioFalso:
    """Doble en memoria del RepositorioPromocion."""

    def __init__(self, ofertas, reglas=None, ya_promovidas=()):
        self._ofertas = ofertas
        self._reglas = reglas if reglas is not None else [FRESCURA, URL]
        self._ya_promovidas = set(ya_promovidas)
        self.watermarks = []
        self.validaciones = []
        self.promovidas = []
        self.rechazos = []

    def leer_reglas(self, solo_activas=True):
        return [r for r in self._reglas if r.activo or not solo_activas]

    def ofertas_en_cuarentena(self, limite=1000):
        return self._ofertas[:limite]

    def registrar_watermark(self, staging_id, semilla, lunes, cubo, porcentaje, automatica):
        self.watermarks.append({"staging_id": staging_id, "semilla": semilla,
                                "cubo": cubo, "automatica": automatica})

    def registrar_validacion(self, staging_id, passed, errores, reglas):
        self.validaciones.append({"staging_id": staging_id, "passed": passed,
                                  "errores": errores, "reglas": reglas})

    def promover(self, staging_id, promotion_source, reglas, promoted_by=None):
        if staging_id in self._ya_promovidas:
            return False
        self.promovidas.append({"staging_id": staging_id,
                                "source": promotion_source, "reglas": reglas})
        return True

    def registrar_rechazo(self, staging_id, errores, reglas, promoted_by=None):
        self.rechazos.append({"staging_id": staging_id, "errores": errores})


def _oferta(**cambios):
    base = {
        "staging_id": uuid4(),
        "creado_en": datetime.now(timezone.utc) - timedelta(hours=1),
        "fuente_url": "https://tienda.example/p/1",
        "producto_json": {"nombre": "Quinua 500g", "precio": 24.9},
        "grounding_check_status": {"passed": True, "errores": []},
    }
    base.update(cambios)
    return base


@pytest.mark.asyncio
async def test_reparte_ochenta_veinte():
    ofertas = [_oferta() for _ in range(400)]
    repo = RepositorioFalso(ofertas)

    r = await job_promotion_auto(momento=SEMANA, repositorio=repo)

    assert r["ofertas_revisadas"] == 400
    # Todas son válidas, así que las automáticas acaban promovidas.
    porcentaje_auto = r["promovidas"] / 400 * 100
    assert 74 <= porcentaje_auto <= 86, f"{porcentaje_auto:.1f}%"
    assert r["promovidas"] + r["manuales"] == 400
    assert r["rechazadas"] == 0


@pytest.mark.asyncio
async def test_las_manuales_no_se_tocan():
    """El 20 % se queda en cuarentena, sin validar ni promover."""
    ofertas = [_oferta() for _ in range(200)]
    repo = RepositorioFalso(ofertas)

    r = await job_promotion_auto(momento=SEMANA, repositorio=repo)

    assert r["manuales"] > 0
    # Se valida solo lo automático.
    assert len(repo.validaciones) == r["promovidas"] + r["rechazadas"]
    assert len(repo.promovidas) == r["promovidas"]
    # Pero el watermark se registra para TODAS: es la trazabilidad del reparto.
    assert len(repo.watermarks) == 200


@pytest.mark.asyncio
async def test_no_promueve_lo_que_no_pasa_las_reglas():
    vieja = _oferta(creado_en=datetime.now(timezone.utc) - timedelta(days=30))
    repo = RepositorioFalso([vieja])

    r = await job_promotion_auto(momento=SEMANA, porcentaje=100, repositorio=repo)

    assert r["promovidas"] == 0
    assert r["rechazadas"] == 1
    assert repo.promovidas == []
    assert repo.rechazos[0]["errores"][0]["regla"] == "dato_fresco"
    assert r["motivos_de_rechazo"] == {"dato_fresco": 1}


@pytest.mark.asyncio
async def test_promueve_con_la_procedencia_de_d1():
    repo = RepositorioFalso([_oferta()])

    await job_promotion_auto(momento=SEMANA, porcentaje=100, repositorio=repo)

    assert repo.promovidas[0]["source"] == "auto_watermark"


@pytest.mark.asyncio
async def test_registra_validacion_de_todo_lo_automatico():
    repo = RepositorioFalso([_oferta() for _ in range(50)])

    r = await job_promotion_auto(momento=SEMANA, porcentaje=100, repositorio=repo)

    assert len(repo.validaciones) == 50
    assert all(v["passed"] for v in repo.validaciones)
    assert r["estado"] == "success"


@pytest.mark.asyncio
async def test_una_oferta_ya_promovida_no_se_cuenta_dos_veces():
    """Si el panel se adelantó, el job no la vuelve a contar como promovida."""
    oferta = _oferta()
    repo = RepositorioFalso([oferta], ya_promovidas=[oferta["staging_id"]])

    r = await job_promotion_auto(momento=SEMANA, porcentaje=100, repositorio=repo)

    assert r["promovidas"] == 0
    assert r["ya_promovidas"] == 1


@pytest.mark.asyncio
async def test_es_estable_entre_pasadas_de_la_misma_semana():
    """Reintentar el job no debe cambiar quién fue automático."""
    ofertas = [_oferta() for _ in range(150)]

    primera = RepositorioFalso(ofertas)
    await job_promotion_auto(momento=SEMANA, repositorio=primera)
    segunda = RepositorioFalso(ofertas)
    await job_promotion_auto(momento=SEMANA + timedelta(hours=6), repositorio=segunda)

    assert ([w["automatica"] for w in primera.watermarks]
            == [w["automatica"] for w in segunda.watermarks])


@pytest.mark.asyncio
async def test_sin_ofertas_no_falla():
    r = await job_promotion_auto(momento=SEMANA, repositorio=RepositorioFalso([]))

    assert r["estado"] == "success"
    assert r["ofertas_revisadas"] == 0
    assert r["sla_ok"]


@pytest.mark.asyncio
async def test_un_error_en_una_oferta_no_tumba_la_pasada():
    class RepoQueFalla(RepositorioFalso):
        """Falla en la segunda oferta y solo en esa."""
        llamadas = 0

        def registrar_validacion(self, staging_id, passed, errores, reglas):
            RepoQueFalla.llamadas += 1
            if RepoQueFalla.llamadas == 2:
                raise RuntimeError("caída simulada")
            super().registrar_validacion(staging_id, passed, errores, reglas)

    repo = RepoQueFalla([_oferta() for _ in range(10)])
    r = await job_promotion_auto(momento=SEMANA, porcentaje=100, repositorio=repo)

    assert r["errores"] == 1
    assert r["estado"] == "partial"
    assert r["promovidas"] == 9


@pytest.mark.asyncio
async def test_sin_reglas_activas_promueve_pero_se_nota(caplog):
    repo = RepositorioFalso([_oferta()], reglas=[])

    with caplog.at_level("WARNING"):
        r = await job_promotion_auto(momento=SEMANA, porcentaje=100, repositorio=repo)

    assert r["promovidas"] == 1
    assert "Sin reglas activas" in caplog.text


@pytest.mark.asyncio
async def test_informa_del_sla():
    r = await job_promotion_auto(momento=SEMANA, repositorio=RepositorioFalso([]))
    assert r["sla_ok"] is True
    assert r["duracion_segundos"] < 15 * 60
