"""
S8.2 - Cost-meter.

Lo que más importa aquí no es que sume: es que **las cuatro vistas del mismo
periodo cuadren entre sí**. Una tabla de costes que no cuadra consigo misma no
la usa nadie, y con cuatro agregaciones distintas del mismo dato es fácil que
dejen de hacerlo sin que nadie se entere.

La consulta SQL se prueba contra la base real al construirla; aquí se sustituye
el repositorio por un doble.
"""

import csv
import io
from datetime import date
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api.costos as costos
from adaptadores.repositorio_costos import MAXIMO_DIAS, _proyeccion
from api.auth import requiere_admin

_ID = str(uuid4())
ADMIN = {"sub": _ID, "user_id": _ID, "email": "admin@cite.gob.pe"}


def _datos(**extra):
    base = {
        "dias": 30,
        "serie": [
            {"dia": "2026-08-11", "runs": 2, "costo_usd": 0.01, "tokens": 100},
            {"dia": "2026-08-12", "runs": 3, "costo_usd": 0.02, "tokens": 200},
        ],
        "por_etapa": [
            {"etapa": "3", "costo_usd": 0.03, "tokens": 300, "veces": 5, "cache_hits": 2},
        ],
        "por_usuario": [
            {"usuario_id": _ID, "email": "quien@cite.gob.pe", "plan": "premium",
             "runs": 5, "costo_usd": 0.03, "tokens": 300},
        ],
        "por_estado": [{"motivo": "ok", "runs": 5}],
        "mes": {"costo_usd": 0.03, "runs": 5, "tope_global_usd": 10.0,
                "pct_del_tope": 0.3, "proyeccion_cierre_usd": 0.06},
    }
    return {**base, **extra}


class RepoFalso:
    def __init__(self, datos=None, revienta=False):
        self._datos = datos if datos is not None else _datos()
        self.revienta = revienta
        self.llamadas = []

    def resumen(self, dias=30):
        self.llamadas.append(dias)
        if self.revienta:
            raise RuntimeError("la base no responde")
        return self._datos


def montar(repo=None, es_admin=True) -> TestClient:
    app = FastAPI()
    app.include_router(costos.router)
    costos._repo = repo or RepoFalso()

    def _admin():
        if not es_admin:
            raise HTTPException(status_code=403, detail="Requiere rol de administrador")
        return ADMIN

    app.dependency_overrides[requiere_admin] = _admin
    return TestClient(app)


# ---------------------------------------------------------------------------
# La proyección
# ---------------------------------------------------------------------------

class TestProyeccion:
    def test_a_mitad_de_mes_proyecta_el_doble(self):
        # Agosto tiene 31 días; el día 15 se lleva 15/31 del mes.
        assert _proyeccion(15.0, date(2026, 8, 15)) == pytest.approx(31.0)

    def test_el_ultimo_dia_ya_no_proyecta_nada(self):
        assert _proyeccion(31.0, date(2026, 8, 31)) == pytest.approx(31.0)

    def test_el_primer_dia_no_divide_por_cero(self):
        """`hoy.day` vale 1, no 0: el mes no empieza en el día cero."""
        assert _proyeccion(2.0, date(2026, 8, 1)) == pytest.approx(62.0)

    def test_sin_gasto_no_proyecta_gasto(self):
        assert _proyeccion(0.0, date(2026, 8, 15)) == 0.0

    def test_febrero_no_tiene_31_dias(self):
        assert _proyeccion(10.0, date(2026, 2, 10)) == pytest.approx(28.0)


# ---------------------------------------------------------------------------
# Control de acceso
# ---------------------------------------------------------------------------

class TestControlDeAcceso:
    def test_un_operador_no_ve_lo_que_gasta_cada_uno(self):
        """El desglose habla de las personas del equipo. Cada usuario ve lo
        suyo en /uso, que filtra por su propia identidad."""
        assert montar(es_admin=False).get("/api/costos").status_code == 403

    def test_ni_lo_exporta(self):
        cliente = montar(es_admin=False)
        assert cliente.get("/api/costos/export.csv").status_code == 403

    def test_un_admin_si(self):
        assert montar().get("/api/costos").status_code == 200


# ---------------------------------------------------------------------------
# El endpoint
# ---------------------------------------------------------------------------

class TestResumen:
    def test_las_cuatro_vistas_cuadran(self):
        """Serie, etapas, usuarios y estados son cuatro cortes del mismo
        periodo: si dejan de sumar lo mismo, la pantalla miente."""
        datos = montar().get("/api/costos").json()

        por_serie = sum(d["costo_usd"] for d in datos["serie"])
        por_etapa = sum(e["costo_usd"] for e in datos["por_etapa"])
        por_usuario = sum(u["costo_usd"] for u in datos["por_usuario"])
        assert por_serie == pytest.approx(por_etapa) == pytest.approx(por_usuario)

        runs_serie = sum(d["runs"] for d in datos["serie"])
        runs_estado = sum(e["runs"] for e in datos["por_estado"])
        assert runs_serie == runs_estado

    def test_los_dias_llegan_al_repositorio(self):
        repo = RepoFalso()
        montar(repo).get("/api/costos?dias=7")
        assert repo.llamadas == [7]

    def test_el_rango_de_dias_esta_acotado(self):
        cliente = montar()
        assert cliente.get(f"/api/costos?dias={MAXIMO_DIAS + 1}").status_code == 422
        assert cliente.get("/api/costos?dias=0").status_code == 422

    def test_un_fallo_de_base_no_filtra_el_sql(self):
        """El mensaje de psycopg lleva la consulta entera; no va al navegador."""
        respuesta = montar(RepoFalso(revienta=True)).get("/api/costos")
        assert respuesta.status_code == 500
        assert "select" not in respuesta.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    @pytest.mark.parametrize("detalle,filas", [
        ("serie", 2), ("etapa", 1), ("usuario", 1), ("estado", 1),
    ])
    def test_las_cuatro_vistas_se_exportan(self, detalle, filas):
        r = montar().get(f"/api/costos/export.csv?detalle={detalle}")
        leidas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))

        assert r.status_code == 200
        assert tuple(leidas[0]) == costos.COLUMNAS[detalle]
        assert len(leidas) - 1 == filas

    def test_el_nombre_del_fichero_dice_que_lleva(self):
        """Cuatro descargas llamadas 'costos.csv' en la carpeta de descargas no
        se distinguen entre sí."""
        r = montar().get("/api/costos/export.csv?detalle=usuario&dias=7")
        assert 'filename="costos-usuario-7d.csv"' in r.headers["content-disposition"]

    def test_lleva_bom_y_crlf(self):
        r = montar().get("/api/costos/export.csv")
        assert r.content.startswith(b"\xef\xbb\xbf")
        assert b"\r\n" in r.content

    def test_un_detalle_inventado_se_rechaza(self):
        assert montar().get("/api/costos/export.csv?detalle=x").status_code == 400

    def test_el_export_usa_el_mismo_periodo_que_la_pantalla(self):
        repo = RepoFalso()
        montar(repo).get("/api/costos/export.csv?detalle=serie&dias=90")
        assert repo.llamadas == [90]


# ---------------------------------------------------------------------------
# El CSV compartido con la auditoría
# ---------------------------------------------------------------------------

class TestExportacionCompartida:
    def test_una_celda_vacia_no_dice_none(self):
        """`None` en una celda de Excel se lee como el texto 'None', y luego
        alguien lo suma."""
        from api.exportacion import texto_de
        assert texto_de(None) == ""

    def test_los_dicts_van_legibles(self):
        from api.exportacion import texto_de
        assert "Perú" in texto_de({"pais": "Perú"})
        assert "\\u" not in texto_de({"pais": "Perú"})
