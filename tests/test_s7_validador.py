"""
S7.3 + S7.8 - Validador de reglas y sus casos límite.

DoD de 7.8: los seis casos del plan pasan y cada rechazo queda explicado.
"""

from datetime import datetime, timedelta, timezone

import pytest

from casos_de_uso.promocion import ErrorValidacion, Regla, ResultadoValidacion, validar_oferta


FRESCURA = Regla("dato_fresco", {"tipo": "date_freshness", "max_dias": 7})
URL = Regla("url_presente", {"tipo": "url_presente"})
GROUNDING = Regla("grounding_ok", {"tipo": "grounding_ok"})
ACTIVAS = [FRESCURA, URL, GROUNDING]


def oferta(**cambios):
    base = {
        "staging_id": "11111111-1111-1111-1111-111111111111",
        "creado_en": datetime.now(timezone.utc) - timedelta(hours=2),
        "fuente_url": "https://tienda.example/producto/1",
        "producto_json": {"nombre": "Quinua 500g", "precio": 24.9, "stock": 12},
        "grounding_check_status": {"passed": True, "errores": []},
    }
    base.update(cambios)
    return base


class TestCasosDelPlan:
    """Los seis casos que enumera 7.8."""

    def test_todo_valido_acepta(self):
        r = validar_oferta(oferta(), ACTIVAS)
        assert r.passed, r.errores_json()
        assert r.errores == []
        assert set(r.reglas_evaluadas) == {"dato_fresco", "url_presente", "grounding_ok"}

    def test_dato_de_ocho_dias_rechaza(self):
        vieja = oferta(creado_en=datetime.now(timezone.utc) - timedelta(days=8))
        r = validar_oferta(vieja, ACTIVAS)
        assert not r.passed
        assert "dato_fresco" in [e.regla for e in r.errores]
        assert "8 días" in [e.motivo for e in r.errores if e.regla == "dato_fresco"][0]

    def test_url_muerta_rechaza(self):
        r = validar_oferta(oferta(fuente_url=""), ACTIVAS)
        assert not r.passed
        assert "url_presente" in [e.regla for e in r.errores]

    def test_precio_fuera_de_rango_rechaza_si_la_regla_esta_activa(self):
        """La regla de precio esta apagada; encendida, dice que no puede evaluarse."""
        precio = Regla("precio_vs_historico",
                       {"tipo": "price_range", "min_pct_historico": 80,
                        "max_pct_historico": 120}, activo=True)
        r = validar_oferta(oferta(), [precio])
        assert not r.passed
        assert "serie de precios" in r.errores[0].motivo

    def test_stock_cero_rechaza_si_la_regla_esta_activa(self):
        stock = Regla("stock_minimo", {"tipo": "stock", "min_unidades": 1}, activo=True)
        r = validar_oferta(oferta(producto_json={"nombre": "x", "stock": 0}), [stock])
        assert not r.passed

    def test_marketplace_rechaza_si_la_regla_esta_activa(self):
        tienda = Regla("tienda_no_marketplace",
                       {"tipo": "tienda_class", "excluir": ["marketplace"]}, activo=True)
        r = validar_oferta(oferta(), [tienda])
        assert not r.passed
        assert "clasificación de tienda" in r.errores[0].motivo


class TestReglasApagadas:
    def test_una_regla_inactiva_ni_se_evalua(self):
        apagada = Regla("stock_minimo", {"tipo": "stock"}, activo=False)
        r = validar_oferta(oferta(), ACTIVAS + [apagada])
        assert r.passed
        assert "stock_minimo" not in r.reglas_evaluadas

    def test_sin_reglas_activas_todo_pasa(self):
        r = validar_oferta(oferta(), [])
        assert r.passed
        assert r.reglas_evaluadas == []


class TestGrounding:
    def test_grounding_fallido_rechaza_y_nombra_los_campos(self):
        mal = oferta(grounding_check_status={
            "passed": False,
            "errores": [{"campo": "precio", "razon": "No encontrado en HTML"}]})
        r = validar_oferta(mal, ACTIVAS)
        assert not r.passed
        assert "precio" in [e.motivo for e in r.errores if e.regla == "grounding_ok"][0]

    def test_sin_grounding_no_es_lo_mismo_que_aprobado(self):
        """Ausente significa que nadie comprobo, no que estuviera bien."""
        r = validar_oferta(oferta(grounding_check_status=None), ACTIVAS)
        assert not r.passed
        assert "no se verificó" in [
            e.motivo for e in r.errores if e.regla == "grounding_ok"][0]


class TestComportamiento:
    def test_acumula_todos_los_fallos_no_corta_en_el_primero(self):
        """CITE debe ver de una vez todo lo que le falta a la oferta."""
        mala = oferta(creado_en=datetime.now(timezone.utc) - timedelta(days=30),
                      fuente_url="",
                      grounding_check_status={"passed": False, "errores": []})
        r = validar_oferta(mala, ACTIVAS)
        assert len(r.errores) == 3
        assert {e.regla for e in r.errores} == {"dato_fresco", "url_presente", "grounding_ok"}

    def test_tipo_desconocido_no_aprueba_en_silencio(self):
        rara = Regla("inventada", {"tipo": "no_existe"}, activo=True)
        r = validar_oferta(oferta(), [rara])
        assert not r.passed
        assert "desconocido" in r.errores[0].motivo

    def test_usa_el_nombre_de_la_regla_de_la_fila(self):
        """CITE puede renombrar la regla; el log debe usar SU nombre."""
        renombrada = Regla("frescura_cite", {"tipo": "date_freshness", "max_dias": 1})
        vieja = oferta(creado_en=datetime.now(timezone.utc) - timedelta(days=5))
        r = validar_oferta(vieja, [renombrada])
        assert r.errores[0].regla == "frescura_cite"

    def test_url_no_http_rechaza(self):
        r = validar_oferta(oferta(fuente_url="ftp://x.example/f"), ACTIVAS)
        assert not r.passed

    def test_creado_en_sin_zona_se_interpreta_utc(self):
        ingenua = oferta(creado_en=datetime.utcnow() - timedelta(hours=1))
        assert validar_oferta(ingenua, [FRESCURA]).passed

    def test_los_errores_se_serializan_para_el_log(self):
        r = validar_oferta(oferta(fuente_url=""), ACTIVAS)
        json = r.errores_json()
        assert isinstance(json, list)
        assert set(json[0]) == {"regla", "motivo", "valor"}
