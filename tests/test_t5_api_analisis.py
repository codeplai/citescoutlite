"""
Gate T5 — el endpoint del análisis de aditivos.

Se prueba contra la rama SQLite, que es la del plan B de la demo y la única que
se puede montar en un test sin una base remota. La rama de Postgres comparte
todo menos la consulta, y esa lleva su filtro por dueño en el `where` — cosa
que este fichero comprueba por lectura, no por ejecución, y así se dice.

Los tres comportamientos que aquí importan no son de camino feliz:

- que un producto **sin aditivos** devuelva 200 y no 404 (es el 49,8 % del
  snapshot),
- que un producto que no está en el informe devuelva 404,
- y que **lo que se analiza salga del informe, no de lo que mande el cliente**.
"""

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api import analisis as modulo
from api.auth import get_current_user

MAPA = {
    "insumo": "fresa",
    "productos": [
        {"producto_id": "OFF:1", "nombre": "Mermelada de fresa",
         "categoria": "Groceries, Jams",
         "ingredientes": "Fresas, azucar, pectina, acido citrico"},
        {"producto_id": "OFF:2", "nombre": "Agua mineral",
         "categoria": "Beverages, Waters", "ingredientes": "Agua mineral natural"},
        {"producto_id": "OFF:3", "nombre": "Sin etiqueta",
         "categoria": None, "ingredientes": None},
    ],
}


class AnalizadorFalso:
    """El motor de T4 ya está probado; aquí solo se prueba el transporte."""

    def __init__(self):
        self.visto = []
        # Parte de la interfaz que el router consume: sin este contador no se
        # puede atribuir el gasto del agente a esta pantalla.
        self.llamadas_agente = 0

    async def analizar(self, producto_id, nombre, ingredientes, categoria=None):
        from casos_de_uso.analizar_aditivos_mercados import AnalizadorAditivos
        self.visto.append(
            {"producto_id": producto_id, "nombre": nombre,
             "ingredientes": ingredientes, "categoria": categoria})
        return await AnalizadorAditivos().analizar(
            producto_id, nombre, ingredientes, categoria)


@pytest.fixture
def db(tmp_path, monkeypatch):
    ruta = tmp_path / "agroscout.db"
    with sqlite3.connect(ruta) as c:
        c.execute("CREATE TABLE etapas_ejecucion (id INTEGER PRIMARY KEY, "
                  "ejecucion_id TEXT, etapa TEXT, salida_json TEXT)")
        c.execute("INSERT INTO etapas_ejecucion (ejecucion_id, etapa, salida_json)"
                  " VALUES (?,?,?)", ("run-1", "2b", json.dumps(MAPA)))
    monkeypatch.setattr(modulo, "USA_SUPABASE", False)
    monkeypatch.setattr(modulo, "ruta_db_sqlite", lambda: str(ruta))
    return ruta


@pytest.fixture
def cliente(db, monkeypatch):
    falso = AnalizadorFalso()
    monkeypatch.setattr(modulo, "_analizador", lambda: falso)

    app = FastAPI()
    app.include_router(modulo.router)
    app.dependency_overrides[get_current_user] = lambda: {"sub": "u1"}
    cliente = TestClient(app)
    cliente.analizador = falso
    return cliente


class TestRespuestas:
    def test_un_producto_con_aditivos_devuelve_su_analisis(self, cliente):
        r = cliente.get("/api/analisis-aditivos/run-1/OFF:1")
        assert r.status_code == 200
        cuerpo = r.json()
        assert cuerpo["producto_nombre"] == "Mermelada de fresa"
        assert {a["nombre"] for a in cuerpo["aditivos"]} == {"Pectina", "Ácido cítrico"}

    def test_sin_aditivos_es_200_y_no_404(self, cliente):
        """El 49,8 % del snapshot. Etiqueta limpia, no error."""
        r = cliente.get("/api/analisis-aditivos/run-1/OFF:2")
        assert r.status_code == 200
        assert r.json()["aditivos"] == []

    def test_sin_etiqueta_tampoco_es_error(self, cliente):
        r = cliente.get("/api/analisis-aditivos/run-1/OFF:3")
        assert r.status_code == 200
        assert r.json()["aditivos"] == [] and r.json()["no_reconocidos"] == []

    def test_un_producto_que_no_esta_en_el_informe_es_404(self, cliente):
        r = cliente.get("/api/analisis-aditivos/run-1/OFF:999")
        assert r.status_code == 404

    def test_un_informe_que_no_existe_es_404(self, cliente):
        r = cliente.get("/api/analisis-aditivos/run-inventado/OFF:1")
        assert r.status_code == 404

    def test_el_id_con_dos_puntos_no_rompe_el_enrutado(self, cliente):
        """Los ids del snapshot son `OFF:00000036`."""
        assert cliente.get("/api/analisis-aditivos/run-1/OFF:1").status_code == 200


class TestFuenteDeVerdad:
    def test_lo_analizado_sale_del_informe_no_del_cliente(self, cliente):
        """El endpoint recibe dos ids; los aditivos los relee del run.

        Si el cliente pudiera mandar la lista, el informe dejaría de decir lo
        que dice el snapshot para decir lo que le mandaron.
        """
        cliente.get("/api/analisis-aditivos/run-1/OFF:1")
        visto = cliente.analizador.visto[0]
        assert visto["ingredientes"] == "Fresas, azucar, pectina, acido citrico"
        assert visto["categoria"] == "Groceries, Jams"

    def test_no_acepta_ingredientes_por_parametro(self, cliente):
        """Aunque alguien lo intente, se ignora: no hay tal parámetro."""
        cliente.get("/api/analisis-aditivos/run-1/OFF:1",
                    params={"ingredientes": "cianuro", "aditivos": "E999"})
        assert cliente.analizador.visto[0]["ingredientes"] == \
               "Fresas, azucar, pectina, acido citrico"


class TestResumen:
    def test_la_pantalla_recibe_las_cuentas_ya_hechas(self, cliente):
        """Si la interfaz las recalcula, acabará contando distinto."""
        cuerpo = cliente.get("/api/analisis-aditivos/run-1/OFF:1").json()
        resumen = cuerpo["resumen"]
        assert resumen["aditivos"] == 2
        assert resumen["celdas"] == 6, "3 mercados × 2 aditivos, siempre"
        assert resumen["categoria_deducida"] is True

    def test_un_producto_sin_categoria_lo_declara(self, cliente):
        cuerpo = cliente.get("/api/analisis-aditivos/run-1/OFF:3").json()
        assert cuerpo["resumen"]["categoria_deducida"] is False

    def test_p_adi_corre_en_cada_respuesta(self, cliente):
        """No solo en los tests: cada celda que se enseña ha pasado el control."""
        p_adi = cliente.get("/api/analisis-aditivos/run-1/OFF:1").json()["resumen"]["p_adi"]
        assert p_adi["ejecutado"] is True
        assert p_adi["fallos"] == []

    def test_informa_de_cuantas_llamadas_al_agente_costo(self, cliente):
        """Es lo único de esta pantalla que cuesta dinero al ocurrir.

        El cost-meter no puede atribuir gasto contando consultas: la mayoría
        sale de caché y no paga nada. Lo que hay que contar son las llamadas.
        """
        cuerpo = cliente.get("/api/analisis-aditivos/run-1/OFF:1").json()
        assert "llamadas_agente" in cuerpo["resumen"]


class TestFiltroPorDueno:
    def test_la_consulta_de_postgres_filtra_por_usuario(self):
        """Se comprueba por lectura: montar Postgres en un test no compensa.

        Lo que se vigila es que el filtro esté **en el `where`** y no después en
        Python: comprobarlo fuera obliga a traerse el mapa de un run ajeno para
        tirarlo, y basta olvidar una rama para que se escape.
        """
        import inspect
        fuente = inspect.getsource(modulo._mapa_del_run)
        consulta = fuente[fuente.index("select x.salida_json"):]
        assert "e.usuario_id = %s" in consulta
        assert "join public.ejecuciones" in consulta
