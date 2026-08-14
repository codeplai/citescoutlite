"""
Etapa 2b - Afinar el mapa comercial por la forma de producto pedida.

`insumo_normalizado` reduce a la materia prima, que es lo correcto para el
resto del informe. Pero quien escribe «barra de quinua» quiere barras, y la
tabla salía llena de grano suelto: de las 200 filas que devolvía «quinua», 11
eran barras y ninguna entraba en las diez primeras.

Los tests de las funciones puras no tocan el snapshot. Los de integración sí,
y se saltan si el índice no está montado.
"""

import pytest

from adaptadores.descubrimiento_snapshot import (
    DescubrimientoSnapshot,
    _casa_forma,
    _get_tabla,
    _reset_cache,
    _terminos_de_forma,
)


class TestTerminosDeForma:
    def test_traduce_la_forma_a_terminos_de_gondola(self):
        """El snapshot es anglosajon: 'barras' no encuentra 'Quinoa Bars'."""
        assert "bar" in _terminos_de_forma("barras de quinua")

    def test_el_plural_no_necesita_lista_de_plurales(self):
        assert _terminos_de_forma("barra de quinua") == _terminos_de_forma("barras de quinua")

    def test_sin_forma_no_hay_terminos(self):
        """None es el caso normal: se pregunto por el insumo a secas."""
        assert _terminos_de_forma(None) == []
        assert _terminos_de_forma("") == []

    def test_una_forma_que_no_conocemos_no_inventa_nada(self):
        """Cae al comportamiento de siempre en vez de buscar un termino falso."""
        assert _terminos_de_forma("sopa de quinua") == []

    def test_ignora_acentos_y_mayusculas(self):
        assert _terminos_de_forma("INFUSIÓN de manzanilla")

    @pytest.mark.parametrize("forma,esperado", [
        ("harina de maca", "flour"),
        ("aceite de palta", "oil"),
        ("galletas de quinua", "cookie"),
        ("leche de almendras", "milk"),
    ])
    def test_formas_frecuentes(self, forma, esperado):
        assert esperado in _terminos_de_forma(forma)


class TestCasaForma:
    def test_exige_palabra_completa(self):
        """'Barley' es cebada, no una barra. El LIKE de LanceDB no distingue."""
        assert not _casa_forma("White Quinoa & Barley", ["bar"])
        assert _casa_forma("Quinoa Chocolate Bar", ["bar"])

    def test_acepta_plural(self):
        assert _casa_forma("Crunchy 7 Grain with Quinoa Bars", ["bar"])

    def test_nombre_vacio_no_casa(self):
        assert not _casa_forma(None, ["bar"])
        assert not _casa_forma("", ["bar"])

    def test_ignora_acentos(self):
        assert _casa_forma("Barrita de Quinua", ["barra"]) is False
        assert _casa_forma("Barra de Quinua", ["barra"])


@pytest.fixture
def snapshot():
    """El snapshot real, devolviendo el singleton como estaba.

    `_tabla` es global al proceso. Abrirlo aquí y dejarlo abierto hace que los
    tests que corran después —los de la cascada N1→N2→N3— encuentren un
    snapshot donde esperaban ninguno, den por buena la primera pasada y sigan a
    N2, que sale a Bright Data de verdad. Se manifestaba como seis fallos en
    test_s5_puerto_async.py que solo aparecían al correr la suite entera.
    """
    d = DescubrimientoSnapshot()
    if _get_tabla(d.db_path) is None:
        _reset_cache()
        pytest.skip("índice LanceDB no montado")
    yield d
    _reset_cache()


class TestSobreElSnapshot:
    def test_las_barras_suben_al_principio(self, snapshot):
        import re
        es_barra = re.compile(r"\bbars?\b", re.I)

        sin = snapshot.descubrir("quinua")
        con = snapshot.descubrir("quinua", forma_producto="barras de quinua")

        barras_sin = sum(1 for p in sin[:10] if es_barra.search(p.nombre))
        barras_con = sum(1 for p in con[:10] if es_barra.search(p.nombre))

        assert barras_sin == 0, "el caso que motivo el arreglo ha cambiado"
        assert barras_con >= 8

    def test_no_deja_la_tabla_en_tres_filas(self, snapshot):
        """Detras de la forma va el resto del insumo, no un corte seco."""
        con = snapshot.descubrir("quinua", forma_producto="barras de quinua")
        sin = snapshot.descubrir("quinua")
        assert len(con) == len(sin)

    def test_sin_forma_se_comporta_como_siempre(self, snapshot):
        assert [p.producto_id for p in snapshot.descubrir("quinua")] \
            == [p.producto_id for p in snapshot.descubrir("quinua", forma_producto=None)]

    def test_una_forma_desconocida_no_altera_el_resultado(self, snapshot):
        assert [p.producto_id for p in snapshot.descubrir("quinua")] \
            == [p.producto_id for p in snapshot.descubrir("quinua", forma_producto="sopa de quinua")]

    def test_no_cuela_cebada_por_parecerse_a_barra(self, snapshot):
        con = snapshot.descubrir("quinua", forma_producto="barras de quinua")
        assert "barley" not in con[0].nombre.lower()
