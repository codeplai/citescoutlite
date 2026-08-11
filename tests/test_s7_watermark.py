"""
S7.1 - Watermark binario.

DoD: determinista y con un 80 % de acierto verificable.
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from dominio.watermark import (
    PORCENTAJE_AUTOMATICO,
    cubo_de,
    debe_promoverse,
    lunes_de_la_semana,
    semilla_semanal,
)


class TestDeterminismo:
    def test_misma_oferta_y_semilla_dan_siempre_lo_mismo(self):
        offer = str(uuid4())
        decisiones = {debe_promoverse(offer, "2026-W33") for _ in range(50)}
        assert len(decisiones) == 1

    def test_es_estable_entre_procesos(self):
        """El valor no depende del PYTHONHASHSEED: sha256, no hash().

        Se fija contra el calculo hecho a mano. Comparar la funcion consigo
        misma pasaria igual con hash(), que cambia en cada proceso y romperia
        el determinismo entre el job y el panel.
        """
        esperado = int(hashlib.sha256(b"oferta-fija|2026-W33").hexdigest(), 16) % 100
        assert cubo_de("oferta-fija", "2026-W33") == esperado

    def test_cambiar_la_semilla_puede_cambiar_el_lado(self):
        """Si la semilla no moviera nada, el 20 % manual seria siempre el mismo."""
        ofertas = [str(uuid4()) for _ in range(200)]
        con_una = {o: debe_promoverse(o, "2026-W33") for o in ofertas}
        con_otra = {o: debe_promoverse(o, "2026-W34") for o in ofertas}
        assert con_una != con_otra

    def test_la_clave_lleva_separador(self):
        """Sin el, ('ab','1') y ('a','b1') serian la misma clave 'ab1'."""
        assert cubo_de("ab", "1") == int(
            hashlib.sha256(b"ab|1").hexdigest(), 16) % 100
        assert cubo_de("a", "b1") == int(
            hashlib.sha256(b"a|b1").hexdigest(), 16) % 100


class TestDistribucion:
    def test_reparto_cercano_al_80_20(self):
        """DoD: 80 % verificable. Con 5000 ofertas la desviacion es pequeña."""
        ofertas = [str(uuid4()) for _ in range(5000)]
        promovidas = sum(debe_promoverse(o, "2026-W33") for o in ofertas)
        porcentaje = promovidas / len(ofertas) * 100
        assert 77 <= porcentaje <= 83, f"{porcentaje:.1f}% fuera de rango"

    def test_los_cubos_cubren_el_rango(self):
        cubos = {cubo_de(str(uuid4()), "2026-W33") for _ in range(3000)}
        assert min(cubos) < 5 and max(cubos) > 94
        assert all(0 <= c <= 99 for c in cubos)

    def test_porcentaje_cero_no_promueve_nada(self):
        ofertas = [str(uuid4()) for _ in range(300)]
        assert not any(debe_promoverse(o, "s", porcentaje=0) for o in ofertas)

    def test_porcentaje_cien_promueve_todo(self):
        ofertas = [str(uuid4()) for _ in range(300)]
        assert all(debe_promoverse(o, "s", porcentaje=100) for o in ofertas)

    @pytest.mark.parametrize("invalido", [-1, 101, 200])
    def test_porcentaje_fuera_de_rango_es_error(self, invalido):
        with pytest.raises(ValueError, match="entre 0 y 100"):
            debe_promoverse("x", "s", porcentaje=invalido)


class TestSemillaSemanal:
    def test_formato_año_semana_iso(self):
        assert semilla_semanal(datetime(2026, 8, 11, tzinfo=timezone.utc)) == "2026-W33"

    def test_toda_la_semana_comparte_semilla(self):
        lunes = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
        semillas = {semilla_semanal(lunes + timedelta(days=d, hours=h))
                    for d in range(7) for h in (0, 12, 23)}
        assert len(semillas) == 1

    def test_el_lunes_a_las_cero_utc_cambia(self):
        domingo = datetime(2026, 8, 9, 23, 59, 59, tzinfo=timezone.utc)
        lunes = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
        assert semilla_semanal(domingo) != semilla_semanal(lunes)

    def test_sin_zona_se_interpreta_utc(self):
        ingenuo = datetime(2026, 8, 11, 12, 0)
        con_zona = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        assert semilla_semanal(ingenuo) == semilla_semanal(con_zona)

    def test_otra_zona_se_convierte_a_utc(self):
        """Las 21:00 del domingo en Lima son ya lunes en UTC."""
        lima = timezone(timedelta(hours=-5))
        domingo_lima = datetime(2026, 8, 9, 20, 0, tzinfo=lima)  # lunes 01:00 UTC
        assert semilla_semanal(domingo_lima) == "2026-W33"

    def test_lunes_de_la_semana(self):
        assert lunes_de_la_semana(datetime(2026, 8, 13, tzinfo=timezone.utc)).isoformat() == "2026-08-10"

    def test_por_defecto_usa_el_momento_actual(self):
        assert semilla_semanal() == semilla_semanal(datetime.now(timezone.utc))


def test_el_umbral_por_defecto_es_el_del_plan():
    assert PORCENTAJE_AUTOMATICO == 80
