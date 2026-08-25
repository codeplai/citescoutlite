"""
Las tres etapas de modelo —3, 4 y 5— dejan de ir en fila india.

Ninguna lee la salida de otra: la 3 sale de `resultado` y el mapa, la 4 de
`resultado`, la 5 de `interpretado`. Iban en serie sin necesitarlo, y eran el
95 % de la consulta.

Medido en `etapas_ejecucion` el 2026-08-24, con la cache vacia:

    consulta            etapa 3   etapa 4   etapa 5   en serie   la mayor
    'salsa de rocoto'      64 s     120 s      93 s      277 s      120 s
    'Pringles Queso'      111 s     172 s     109 s      392 s      172 s
    'papas pringles'      164 s     125 s     101 s      390 s      164 s
"""

import asyncio
import time
from types import SimpleNamespace

import pytest

from casos_de_uso import evaluar_insumo as mod
from dominio.dossier_regulatorio import DossierRegulatorio


def _deps(agotado=False):
    return SimpleNamespace(presupuesto=SimpleNamespace(agotado=agotado))


def _mapa():
    return SimpleNamespace(resumen_para_llm=lambda: {"insumo": "rocoto"})


def _etapa_que_duerme(duraciones, registro, revienta=None):
    """Sustituto de `etapa` que tarda lo que se le diga por numero de etapa."""
    async def etapa_falsa(d, ejecucion, num, func, entrada, **kwargs):
        registro.append((num, "inicio", time.monotonic()))
        await asyncio.sleep(duraciones.get(num, 0.01))
        if num == revienta:
            raise RuntimeError(f"la etapa {num} se cayo")
        registro.append((num, "fin", time.monotonic()))
        return f"salida-{num}"
    return etapa_falsa


async def _correr(monkeypatch, d=None, duraciones=None, con_premium=True,
                  revienta=None):
    registro = []
    monkeypatch.setattr(mod, "etapa",
                        _etapa_que_duerme(duraciones or {}, registro, revienta))
    motivos = set()
    salida = await mod._etapas_de_modelo(
        d or _deps(), "ejec", "resultado", "interpretado", _mapa(), "rocoto",
        motivos, con_premium)
    return salida, motivos, registro


class TestEnParalelo:
    @pytest.mark.asyncio
    async def test_el_reloj_es_el_de_la_mas_lenta_no_la_suma(self, monkeypatch):
        # Las proporciones de 'Pringles Queso': 111 / 172 / 109 s.
        duraciones = {"3": 0.30, "4": 0.45, "5": 0.28}
        inicio = time.monotonic()
        await _correr(monkeypatch, duraciones=duraciones)
        transcurrido = time.monotonic() - inicio
        # En serie serian 1,03 s; la mayor es 0,45 s.
        assert transcurrido < 0.80, f"parece que siguen en serie: {transcurrido:.2f} s"

    @pytest.mark.asyncio
    async def test_las_tres_arrancan_antes_de_que_acabe_ninguna(self, monkeypatch):
        _, _, registro = await _correr(monkeypatch,
                                       duraciones={"3": 0.3, "4": 0.3, "5": 0.3})
        inicios = [t for _, hito, t in registro if hito == "inicio"]
        primer_fin = min(t for _, hito, t in registro if hito == "fin")
        assert len(inicios) == 3
        assert max(inicios) < primer_fin

    @pytest.mark.asyncio
    async def test_cada_salida_va_a_su_sitio(self, monkeypatch):
        """`gather` conserva el orden, y aqui ese orden es insight/hipotesis/dossier.

        Invertirlo pondria el dossier regulatorio en el hueco de la hipotesis y
        no se notaria hasta leer el informe.
        """
        (insight, hipotesis, dossier), _, _ = await _correr(monkeypatch)
        assert insight == "salida-3"
        assert hipotesis == "salida-4"
        assert dossier == "salida-5"


class TestPlanGratuito:
    @pytest.mark.asyncio
    async def test_solo_corre_la_etapa_3_y_se_marca_el_paywall(self, monkeypatch):
        (insight, hipotesis, dossier), motivos, registro = await _correr(
            monkeypatch, con_premium=False)
        assert [num for num, hito, _ in registro if hito == "inicio"] == ["3"]
        assert insight == "salida-3"
        assert hipotesis is None and dossier is None
        assert motivos == {"paywall"}


class TestPresupuesto:
    @pytest.mark.asyncio
    async def test_sin_saldo_no_se_lanza_ninguna(self, monkeypatch):
        """La comprobacion que de verdad protege sigue en pie.

        Es la que evita las TRES. La que se ha perdido es la de en medio, que
        solo evitaba las siguientes una vez empezado el gasto.
        """
        (insight, hipotesis, dossier), motivos, registro = await _correr(
            monkeypatch, d=_deps(agotado=True))
        assert registro == [], "se gasto con el presupuesto agotado"
        assert insight is None and hipotesis is None
        assert isinstance(dossier, DossierRegulatorio) and dossier.sin_dato
        assert "presupuesto" in motivos


class TestRedactorSegunCobertura:
    @pytest.mark.asyncio
    async def test_con_pocos_productos_se_usa_el_insight_parcial(self, monkeypatch):
        """Con poca cobertura el informe no afirma sobre el mercado.

        La eleccion de redactor viajaba con el codigo que se ha movido, asi que
        conviene fijarla: perderla no rompe nada visible, solo hace que un
        informe sin base hable como si la tuviera.
        """
        vistos = []

        async def etapa_falsa(d, ejecucion, num, func, entrada, **kwargs):
            vistos.append((num, func))
            return f"salida-{num}"

        monkeypatch.setattr(mod, "etapa", etapa_falsa)
        await mod._etapas_de_modelo(_deps(), "ejec", "resultado", "interpretado",
                                    _mapa(), "rocoto", {"pocos_productos"}, True)
        assert dict(vistos)["3"] is mod.generar_insight_parcial

    @pytest.mark.asyncio
    async def test_con_cobertura_normal_se_usa_el_insight_completo(self, monkeypatch):
        vistos = []

        async def etapa_falsa(d, ejecucion, num, func, entrada, **kwargs):
            vistos.append((num, func))
            return f"salida-{num}"

        monkeypatch.setattr(mod, "etapa", etapa_falsa)
        await mod._etapas_de_modelo(_deps(), "ejec", "resultado", "interpretado",
                                    _mapa(), "rocoto", set(), True)
        assert dict(vistos)["3"] is mod.generar_insight


class TestFallo:
    @pytest.mark.asyncio
    async def test_si_una_revienta_la_excepcion_sube(self, monkeypatch):
        with pytest.raises(RuntimeError, match="la etapa 4 se cayo"):
            await _correr(monkeypatch, revienta="4")
