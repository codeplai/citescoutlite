"""
Gate T3 — la celda del Codex.

Este tier no tiene capa de integración y **no puede tenerla**: el GSFA no es
consultable por máquina (403 de Cloudflare, `robots.txt` que veta las fichas con
`?id=`, y el Web Unlocker de Bright Data negándose a saltárselo). La tabla la
rellena una persona; lo que aquí se prueba es que el código **no deje colar** una
fila que no esté respaldada.

Por eso la mayoría de estos tests comprueban rechazos, no aciertos. Con 33 filas
de las que hoy solo 2 están resueltas, el riesgo real no es equivocarse en un
límite: es que una fila a medias se publique como si fuera un veredicto.
"""

import csv

import pytest

from adaptadores.corpus_codex import (
    RUTA_CSV,
    EvaluadorCodex,
    FilaCodexInvalida,
    cargar,
)

CAMPOS = [
    "e_number", "ins", "nombre", "frecuencia_snapshot", "categoria_gsfa",
    "categoria_nombre", "limite_valor", "limite_unidad", "autorizado",
    "referencia_texto", "referencia_url", "cita_literal", "nota", "estado",
    "verificado_por", "fecha_verificacion",
]


def _csv(tmp_path, *filas):
    ruta = tmp_path / "codex.csv"
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        for fila in filas:
            w.writerow({c: fila.get(c, "") for c in CAMPOS})
    return ruta


def _resuelta(**cambios):
    base = dict(
        e_number="E200", ins="200", nombre="Ácido sórbico",
        categoria_gsfa="04.1.2.8", limite_valor="1000", limite_unidad="mg/kg",
        autorizado="SI", referencia_texto="CXS 192-1995, cat. 04.1.2.8",
        referencia_url="https://www.fao.org/gsfaonline/groups/details.html?id=10",
        cita_literal="1 000 mg/kg", estado="VERIFICADO",
        verificado_por="QA", fecha_verificacion="2026-08-14")
    return {**base, **cambios}


class TestCarga:
    """Validar al cargar, no al consultar: el fallo sale cuando se puede arreglar."""

    def test_una_fila_verificada_completa_carga(self, tmp_path):
        filas = cargar(_csv(tmp_path, _resuelta()))
        assert filas["E200"].resuelta

    @pytest.mark.parametrize("falta", ["referencia_url", "cita_literal",
                                       "verificado_por", "fecha_verificacion"])
    def test_verificada_sin_su_respaldo_no_carga(self, tmp_path, falta):
        """D-5: sin URL y sin cita no hay veredicto publicable."""
        with pytest.raises(FilaCodexInvalida, match=falta):
            cargar(_csv(tmp_path, _resuelta(**{falta: ""})))

    def test_estado_desconocido_no_carga(self, tmp_path):
        with pytest.raises(FilaCodexInvalida, match="desconocido"):
            cargar(_csv(tmp_path, _resuelta(estado="MAS O MENOS")))

    def test_pendiente_no_necesita_respaldo(self, tmp_path):
        """Es el estado inicial de 31 de las 33 filas; no puede ser un error."""
        filas = cargar(_csv(tmp_path, {"e_number": "E330", "nombre": "Ácido cítrico",
                                       "estado": "PENDIENTE"}))
        assert not filas["E330"].resuelta

    def test_sin_estado_se_asume_pendiente(self, tmp_path):
        """Quien añada una fila a mano y olvide el estado no publica nada."""
        filas = cargar(_csv(tmp_path, {"e_number": "E415", "nombre": "Goma xantana"}))
        assert filas["E415"].estado == "PENDIENTE"


class TestEvaluador:
    def test_pendiente_es_sin_dato_no_prohibido(self, tmp_path):
        """El error que no se puede cometer: «no lo hemos mirado» ≠ «no»."""
        ev = EvaluadorCodex(cargar(_csv(tmp_path, {
            "e_number": "E330", "nombre": "Ácido cítrico", "estado": "PENDIENTE"})))
        e = ev.evaluar("E330", "Ácido cítrico")
        assert e.autorizado == "SIN_DATO"
        assert e.limite_valor is None

    def test_un_aditivo_que_no_esta_en_la_tabla_es_sin_dato(self, tmp_path):
        ev = EvaluadorCodex(cargar(_csv(tmp_path, _resuelta())))
        assert ev.evaluar("E999", "Inventadina").autorizado == "SIN_DATO"

    def test_verificada_da_el_veredicto_tal_cual(self, tmp_path):
        ev = EvaluadorCodex(cargar(_csv(tmp_path, _resuelta())))
        e = ev.evaluar("E200", "Ácido sórbico")
        assert e.autorizado == "SI"
        assert e.limite_valor == 1000.0
        assert e.origen == "CURADO_CODEX"

    def test_secundaria_nunca_da_un_si_limpio(self, tmp_path):
        """Un dato de segunda mano no puede parecer de primera.

        La fila dice `SI`; como su procedencia es un documento interno y no el
        GSFA, sale `SI_CONDICIONADO`. La cifra es la misma; lo que cambia es
        cuánto se puede apoyar uno en ella.
        """
        ev = EvaluadorCodex(cargar(_csv(tmp_path, _resuelta(
            estado="SECUNDARIA", verificado_por="acido1.pptx"))))
        e = ev.evaluar("E200", "Ácido sórbico")
        assert e.autorizado == "SI_CONDICIONADO"
        assert "acido1.pptx" in e.nota
        assert "no se ha verificado contra el GSFA" in e.nota

    def test_secundaria_conserva_la_nota_propia_de_la_fila(self, tmp_path):
        ev = EvaluadorCodex(cargar(_csv(tmp_path, _resuelta(
            estado="SECUNDARIA", autorizado="SI_CONDICIONADO",
            verificado_por="acido2.pptx", nota="Cobertura por categoría general."))))
        nota = ev.evaluar("E200", "x").nota
        assert "categoría general" in nota and "acido2.pptx" in nota

    def test_la_cobertura_se_cuenta_para_poder_ensenarla(self, tmp_path):
        ev = EvaluadorCodex(cargar(_csv(
            tmp_path, _resuelta(),
            {"e_number": "E330", "nombre": "Cítrico", "estado": "PENDIENTE"})))
        assert ev.cobertura() == (1, 2)


# --- La tabla real del repo ----------------------------------------------

tabla_presente = pytest.mark.skipif(
    not RUTA_CSV.exists(), reason="Falta data/codex/gsfa_aditivos.csv")


@pytest.fixture(scope="module")
def filas():
    return cargar()


@tabla_presente
class TestTablaDelRepo:
    def test_carga_sin_errores(self, filas):
        """Si esto falla, alguien editó el CSV y dejó una fila a medias."""
        assert len(filas) >= 32

    def test_estan_los_aditivos_del_snapshot(self, filas):
        """Los que de verdad aparecen en las 29.054 filas del índice."""
        del_snapshot = {"E330", "E300", "E322", "E415", "E440", "E412", "E202",
                        "E296", "E331", "E306", "E955", "E270", "E500", "E170",
                        "E211", "E410", "E407", "E466", "E950", "E220", "E339"}
        assert del_snapshot <= set(filas)

    def test_los_dos_casos_de_referencia_estan_como_secundarios(self, filas):
        """Vienen de los PPTX, no del GSFA, y la tabla lo dice."""
        assert filas["E200"].estado == "SECUNDARIA"
        assert filas["E200"].verificado_por == "acido1.pptx"
        assert filas["E385"].estado == "SECUNDARIA"
        assert filas["E385"].verificado_por == "acido2.pptx"

    def test_el_caso_1_trae_su_categoria_y_su_limite(self, filas):
        fila = filas["E200"]
        assert fila.categoria_gsfa == "04.1.2.8"
        assert fila.limite_valor == 1000.0

    def test_el_caso_2_trae_su_categoria_y_su_limite(self, filas):
        fila = filas["E385"]
        assert fila.categoria_gsfa == "04.2.2.4"
        assert fila.limite_valor == 365.0
        assert fila.autorizado == "SI_CONDICIONADO", "el asterisco del PPTX"

    def test_ninguna_fila_resuelta_se_queda_sin_url(self, filas):
        """Barrido de D-5 sobre la tabla entera."""
        sin_url = [f.e_number for f in filas.values()
                   if f.resuelta and not f.referencia_url]
        assert not sin_url

    def test_lo_pendiente_esta_declarado_como_pendiente(self, filas):
        """Y no disfrazado de dato. Hoy son 31 de 33."""
        pendientes = [f for f in filas.values() if f.estado == "PENDIENTE"]
        assert all(f.autorizado is None for f in pendientes)
