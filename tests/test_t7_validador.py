"""
Gate T7 — P-ADI y la sonda de URLs.

Los objetos se construyen con `model_construct`, que **salta los validadores de
pydantic**, y es a propósito: P-ADI existe para vigilar respuestas que nadie ha
validado —las que llegan deserializadas de una caché, de una API o de un JSON en
disco—. Probarlo con objetos que ya pasaron por el constructor sería probar el
constructor.

El test que más importa de este fichero es
`test_una_cita_montada_no_pasa_por_literal`: es el fallo que P-ADI encontró en
producción, en el código propio, y en el mercado que se presumía más verificable.
"""

import pytest

from casos_de_uso.validar_analisis import Resultado, validar
from dominio.analisis_aditivos import (
    AditivoEvaluado,
    AnalisisIngredientes,
    EvaluacionMercado,
)
from etl.sondar_urls_regulatorias import MUERTA, OPACA, VIVA, _sondar

URL = "https://www.ecfr.gov/current/title-21"
CITA_US = "This substance is generally recognized as safe when used in accordance"


def celda(mercado="US", veredicto="SI", **cambios):
    """Sin validar, que es de donde vienen los datos que P-ADI vigila."""
    base = dict(
        mercado=mercado, autorizado=veredicto, limite_valor=None,
        limite_unidad=None, categoria_alimento=None,
        referencia_texto="21 CFR § 182.3089", referencia_url=URL,
        cita_literal=CITA_US, nota=None,
        origen={"US": "AGENTE_ECFR", "EU": "ANEXO_II",
                "CODEX": "CURADO_CODEX"}[mercado],
        verificado_en=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc))
    return EvaluacionMercado.model_construct(**{**base, **cambios})


def aditivo(*evaluaciones, nombre="Ácido sórbico"):
    if not evaluaciones:
        evaluaciones = (celda("US"), celda("CODEX"), celda("EU"))
    return AditivoEvaluado.model_construct(
        nombre=nombre, ins="200", e_number="E200", funcion=None,
        evaluaciones=list(evaluaciones))


def analisis(*aditivos):
    return AnalisisIngredientes.model_construct(
        producto_id="OFF:1", producto_nombre="X", matriz=None, matriz_ue=None,
        aditivos=list(aditivos or (aditivo(),)), no_reconocidos=[],
        generado_en=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc))


class CorpusFalso:
    """El mínimo que P-ADI consulta de un corpus del eCFR."""

    def __init__(self, texto=CITA_US + " with good manufacturing practice."):
        self._texto = texto

    def seccion(self, _identificador):
        return type("S", (), {"texto": self._texto})()


class TestP_ADI_1:
    """Sin URL y sin cita no hay veredicto publicable."""

    def test_sin_url_falla(self):
        r = validar(analisis(aditivo(celda("US", referencia_url=""),
                                     celda("CODEX"), celda("EU"))))
        assert any(f.regla == "P-ADI-1" and "URL" in f.detalle for f in r.fallos)

    def test_sin_cita_falla(self):
        r = validar(analisis(aditivo(celda("US", cita_literal=""),
                                     celda("CODEX"), celda("EU"))))
        assert any(f.regla == "P-ADI-1" and "cita" in f.detalle for f in r.fallos)

    def test_sin_dato_no_necesita_ni_url_ni_cita(self):
        """`SIN_DATO` es el estado honesto; exigirle pruebas no tiene sentido."""
        r = validar(analisis(aditivo(
            celda("US", veredicto="SIN_DATO", cita_literal=""),
            celda("CODEX"), celda("EU"))))
        assert not [f for f in r.fallos if f.regla == "P-ADI-1"]


class TestP_ADI_2:
    """La regla que ningún otro sitio puede comprobar."""

    def test_una_cita_que_esta_en_la_norma_pasa(self):
        r = validar(analisis(), corpus_ecfr=CorpusFalso())
        assert r.pasa, [str(f) for f in r.fallos]
        assert r.verificadas == 1

    def test_una_cita_montada_no_pasa_por_literal(self):
        """El fallo que P-ADI encontró en el código propio.

        `EvaluadorUE` componía la cita como `f"{entrada} — {denominacion}:
        {dosis}"`, que produce «E 440 — Pectinas: quantum satis»: una cadena con
        puntuación propia que no aparece en ninguna parte del Anexo II. Tenía
        aspecto de cita y era un resumen.
        """
        r = validar(
            analisis(aditivo(celda("US", cita_literal="E 440 — Pectinas: quantum satis"),
                             celda("CODEX"), celda("EU"))),
            corpus_ecfr=CorpusFalso())
        assert any(f.regla == "P-ADI-2" for f in r.fallos)

    def test_sin_corpus_no_se_da_por_buena(self):
        """No poder comprobar no es comprobar. Cuenta como no verificable."""
        r = validar(analisis())
        assert r.pasa
        assert r.verificadas == 0
        assert r.no_verificables == 3

    def test_una_seccion_que_ya_no_existe_falla(self):
        class SinSeccion:
            def seccion(self, _):
                return None

        r = validar(analisis(), corpus_ecfr=SinSeccion())
        assert any(f.regla == "P-ADI-2" for f in r.fallos)

    def test_el_codex_nunca_cuenta_como_verificado(self):
        """Su fuente es una persona; darlo por auditado sería mentir."""
        r = validar(analisis(aditivo(celda("US"), celda("CODEX"), celda("EU"))),
                    corpus_ecfr=CorpusFalso())
        assert r.verificadas == 1, "solo la de EE. UU."
        assert r.no_verificables >= 1

    def test_una_cita_demasiado_corta_no_se_da_por_buena(self):
        """Diez caracteres caben en cualquier sitio: no distinguen nada."""
        r = validar(analisis(aditivo(celda("US", cita_literal="sí"),
                                     celda("CODEX"), celda("EU"))),
                    corpus_ecfr=CorpusFalso())
        assert not [f for f in r.fallos if f.regla == "P-ADI-2"]
        assert r.verificadas == 0


class TestP_ADI_3:
    def test_faltar_un_mercado_falla(self):
        r = validar(analisis(aditivo(celda("US"), celda("EU"))))
        assert any(f.regla == "P-ADI-3" for f in r.fallos)

    def test_el_orden_importa(self):
        """La pantalla pinta las tarjetas en el orden en que llegan."""
        r = validar(analisis(aditivo(celda("EU"), celda("US"), celda("CODEX"))))
        assert any(f.regla == "P-ADI-3" for f in r.fallos)


class TestP_ADI_4:
    def test_sin_dato_con_cifra_falla(self):
        """«No lo sé» no puede venir con un número al lado."""
        r = validar(analisis(aditivo(
            celda("US", veredicto="SIN_DATO", cita_literal="", limite_valor=220.0),
            celda("CODEX"), celda("EU"))))
        assert any(f.regla == "P-ADI-4" for f in r.fallos)


class TestP_ADI_5:
    def test_un_limite_interno_inventado_falla(self):
        ad = aditivo(celda("US", limite_valor=1000.0, limite_unidad="mg/kg"),
                     celda("CODEX"), celda("EU"))
        # `limite_interno` es una propiedad calculada; se fuerza el caso que
        # P-ADI vigila sustituyéndola por uno que no sale de ningún mercado.
        class Trucado(type(ad)):
            @property
            def limite_interno(self):
                return 7.0

        r = validar(analisis(Trucado.model_construct(**ad.__dict__)))
        assert any(f.regla == "P-ADI-5" for f in r.fallos)

    def test_el_minimo_de_los_que_autorizan_pasa(self):
        r = validar(analisis(aditivo(
            celda("US", limite_valor=1000.0, limite_unidad="mg/kg"),
            celda("CODEX", limite_valor=365.0, limite_unidad="mg/kg"),
            celda("EU"))), corpus_ecfr=CorpusFalso())
        assert not [f for f in r.fallos if f.regla == "P-ADI-5"]


class TestResultado:
    def test_un_analisis_sin_aditivos_pasa(self):
        """Etiqueta limpia: no hay nada que validar y eso no es un fallo."""
        r = validar(AnalisisIngredientes(producto_id="OFF:1", producto_nombre="Agua"))
        assert r.pasa and r.celdas == 0

    def test_el_resumen_dice_lo_que_no_se_miro(self):
        r = validar(analisis(), corpus_ecfr=CorpusFalso())
        assert "no verificables" in r.resumen()


class ClienteFalso:
    def __init__(self, codigo):
        self._codigo = codigo

    def head(self, url, **kwargs):
        return type("R", (), {"status_code": self._codigo})()

    get = head


class TestSondaDeUrls:
    """Tres estados, no dos. El tercero es el que evita borrar citas buenas."""

    def test_una_url_que_responde_esta_viva(self):
        assert _sondar(ClienteFalso(200), URL)[0] == VIVA

    def test_un_404_esta_muerto(self):
        assert _sondar(ClienteFalso(404), URL)[0] == MUERTA

    def test_un_403_de_la_fao_es_opaco_no_muerto(self):
        """La página existe y una persona la abre; es Cloudflare, no un 404.

        Marcarla «muerta» haría borrar una cita correcta del Codex.
        """
        estado, motivo = _sondar(
            ClienteFalso(403), "https://www.fao.org/gsfaonline/groups/details.html?id=10")
        assert estado == OPACA
        assert "anti-bot" in motivo

    def test_un_403_de_otro_sitio_si_es_muerte(self):
        """La excepción es para hosts conocidos, no para cualquier 403."""
        assert _sondar(ClienteFalso(403), "https://ejemplo.com/x")[0] == MUERTA

    def test_un_fallo_de_red_no_lanza(self):
        class Roto:
            def head(self, *a, **k):
                raise ConnectionError("sin red")

        assert _sondar(Roto(), URL)[0] == MUERTA
