"""
La clave de caché tiene que cambiar cuando cambia el ESQUEMA de la etapa.

Porque la salida de una etapa no depende solo de su entrada: depende también de
la forma que se le pidió al modelo. Sin esto, añadir un campo no invalida nada
—`model_validate` lo rellena con su valor por defecto— y la etapa devuelve para
siempre un resultado al que le falta justo lo que se acaba de añadir.

No es hipotético: pasó al añadir `terminos_aleman` a `InsumoInterpretado`. Los
insumos ya consultados seguían sirviendo una interpretación sin término alemán,
y la góndola alemana no se consultaba nunca. **En silencio**, que es lo peor:
`[]` es también la respuesta legítima de «no hay ofertas allí», así que desde
fuera no se distinguía de una búsqueda vacía.
"""

from pydantic import BaseModel

from casos_de_uso.etapas.ejecutor import _generar_clave_cache, _huella_de_esquema
from dominio.insumo import InsumoInterpretado


class EsquemaViejo(BaseModel):
    """`InsumoInterpretado` tal como era antes del término alemán."""
    insumo_normalizado: str = ""
    reconocible: bool = False
    sinonimos_busqueda: list = []
    terminos_ingles: list = []


def _clave(tipo, entrada="arandano"):
    return _generar_clave_cache(entrada, "1", "v1", "glm-5.2", {}, tipo)


class TestHuellaDeEsquema:
    def test_anadir_un_campo_cambia_la_clave(self):
        """El caso real: sin esto, 'arandano' nunca habría traído góndola
        alemana, porque su interpretación cacheada no tiene el término."""
        assert _clave(EsquemaViejo) != _clave(InsumoInterpretado)

    def test_el_mismo_esquema_da_la_misma_clave(self):
        """La caché tiene que seguir sirviendo: invalidar de más es tirar
        dinero en llamadas que ya se pagaron."""
        assert _clave(InsumoInterpretado) == _clave(InsumoInterpretado)

    def test_entradas_distintas_siguen_dando_claves_distintas(self):
        assert _clave(InsumoInterpretado, "quinua") != _clave(InsumoInterpretado, "cacao")

    def test_sin_tipo_de_retorno_no_revienta(self):
        """`get_type_hints` puede no encontrar anotación de retorno; entonces no
        hay huella que añadir, pero la clave se sigue generando."""
        assert _generar_clave_cache("x", "1", "v1")

    def test_un_tipo_que_no_es_modelo_se_ignora(self):
        assert _huella_de_esquema(str) == ""
        assert _huella_de_esquema(None) == ""

    def test_la_huella_no_depende_del_orden_de_declaracion(self):
        """Se ordenan los nombres: reordenar campos no cambia el dato que
        producen, y tirar la caché por eso sería gratuito y caro."""
        class A(BaseModel):
            uno: int = 0
            dos: int = 0

        class B(BaseModel):
            dos: int = 0
            uno: int = 0

        assert _huella_de_esquema(A) == _huella_de_esquema(B)

    def test_el_termino_aleman_esta_en_la_huella_actual(self):
        """Guardia sobre el campo del que dependía la góndola alemana."""
        assert "terminos_aleman" in _huella_de_esquema(InsumoInterpretado)
