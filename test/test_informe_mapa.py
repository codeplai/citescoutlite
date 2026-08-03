"""
TIER 4 · T4.3a (S4): la tabla del mapa comercial en el informe.

DoD del plan §T4.3: "Tabla en el PDF y en Result.vue: país · marca ·
presentación · precio · URL · fecha. Las celdas vacías se pintan **"sin dato"**,
no se ocultan ni se rellenan con guiones."

Lo que estos tests protegen no es el formato, es la afirmación: el informe tiene
que **enseñar** los tres campos vacíos. Ocultar la columna o poner un guion
serían las dos maneras fáciles de que el hueco desaparezca sin que nadie decida
que desaparezca.

Se ejecuta con pytest o directamente: python test/test_informe_mapa.py
"""
import uuid
from datetime import date
from pathlib import Path

from adaptadores.informe_weasyprint import InformeWeasyPrint
from dominio.insight_mercado import InsightDeMercado
from dominio.mapa_comercial import MapaComercial
from dominio.producto_en_mercado import ProductoEnMercado

SIN_DATO = "_sin dato_"

# Contrato con Result.vue: la SPA corta por aquí para pintar su propia tabla
# paginada en vez de las 25 filas que caben en el PDF.
INICIO = InformeWeasyPrint.MARCA_MAPA_INICIO
FIN = InformeWeasyPrint.MARCA_MAPA_FIN


class _Ejecucion:
    def __init__(self):
        self.id = f"test-{uuid.uuid4()}"
        self.snapshot_version = "2026-07"
        self.insumo_texto = "arándano"
        self.usuario_id = None


def _producto(i: int, **cambios) -> ProductoEnMercado:
    base = dict(insumo="arándano", producto_id=f"OFF:{i:08d}",
                nombre=f"Mermelada de arándano {i}", marca=f"Marca {i}",
                paises_iso=["PE"], fuente="OFF",
                url=f"https://world.openfoodfacts.org/product/{i:08d}",
                fecha_dato=date(2026, 3, 14))
    base.update(cambios)
    return ProductoEnMercado(**base)


def _mapa(n: int = 3, **cambios) -> MapaComercial:
    base = dict(insumo="arándano", productos=[_producto(i) for i in range(n)],
                nivel_alcanzado=1, niveles_no_disponibles=[2, 3])
    base.update(cambios)
    return MapaComercial(**base)


def _insight() -> InsightDeMercado:
    return InsightDeMercado(cobertura="alta", resumen="r",
                            formatos_comunes=["polvo"], citas=["OFF:00000000"])


def _emitir(tmp_path, mapa, insight=None):
    repo = InformeWeasyPrint(output_dir=str(tmp_path))
    return repo.emitir(_Ejecucion(), insight, parcial=False, mapa=mapa)


# --- la tabla --------------------------------------------------------------

def test_la_tabla_tiene_las_seis_columnas(tmp_path):
    """Columnas pensadas desde quien lee: un tecnólogo de alimentos.

    Fuera `Fecha` (es la última modificación del registro en OFF, no el
    lanzamiento) y fuera `Presentación`, para dejarle sitio a los ingredientes.
    `Precio` se queda: es el hueco que hay que enseñar.
    """
    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    for columna in ("Producto", "País", "Marca", "Precio", "Aditivos", "Ingredientes"):
        assert f"| {columna} " in md or f"{columna} |" in md, columna
    assert "| Fecha |" not in md
    print("PASS: la tabla trae las 6 columnas útiles")


def test_el_hueco_se_pinta_sin_dato_en_cada_fila(tmp_path):
    """presentacion, precio_rango y canal son None en el MVP: 3 por producto."""
    md = _emitir(tmp_path, _mapa(n=3), _insight()).markdown_content
    # 2 celdas visibles por fila (presentación y precio) x 3 filas.
    assert md.count(SIN_DATO) >= 6, md.count(SIN_DATO)
    print(f"PASS: {md.count(SIN_DATO)} celdas 'sin dato' en 3 filas")


def test_no_se_rellena_con_guiones_ni_se_oculta(tmp_path):
    """Las dos maneras faciles de que el hueco desaparezca.

    `Precio` es la columna que sostiene el bloque 2 del guion: si desaparece de
    la tabla, la afirmación "el precio no lo tenemos" deja de ser comprobable a
    simple vista y pasa a ser algo que hay que creerse.
    """
    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    assert "Precio" in md, "la columna vacía se ocultó"
    assert "| - |" not in md and "| — |" not in md, "hueco rellenado con guion"
    assert "| N/A |" not in md and "|  |" not in md
    print("PASS: ni columna oculta ni guion de relleno")


def test_marca_ausente_tambien_es_sin_dato(tmp_path):
    """Una fila sin nada: las cinco columnas de dato salen declaradas."""
    mapa = MapaComercial(insumo="arándano", nivel_alcanzado=1,
                         productos=[_producto(0, marca=None, paises_iso=[])])
    md = _emitir(tmp_path, mapa, _insight()).markdown_content
    fila = next(l for l in md.splitlines() if "Mermelada" in l)
    # país, marca, precio, aditivos, ingredientes
    assert fila.count(SIN_DATO) == 5, fila
    print("PASS: las cinco columnas vacías salen como 'sin dato'")


def test_los_ingredientes_van_en_texto_plano_y_completos(tmp_path):
    """En el PDF la columna se lee; recortarla la volvería decorativa."""
    texto = ("organic rolled oats, organic blueberry filling, organic tapioca "
             "syrup, organic cane sugar, water, pectin, citric acid, sea salt")
    mapa = MapaComercial(
        insumo="arándano", nivel_alcanzado=1,
        productos=[_producto(0, ingredientes=texto, n_ingredientes=8,
                             aditivos=["Pectina (E440)", "Ácido cítrico (E330)"])])
    md = _emitir(tmp_path, mapa, _insight()).markdown_content
    fila = next(l for l in md.splitlines() if "Mermelada" in l)
    assert texto in fila, "los ingredientes salen recortados"
    assert "Pectina (E440)" in fila
    print("PASS: ingredientes completos y aditivos con número E en la tabla")


def test_el_informe_matiza_que_vacio_no_es_sin_alergenos(tmp_path):
    """La frase que impide leer una celda vacía como 'no tiene alérgenos'."""
    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    assert "no que el producto no los tenga" in md
    print("PASS: el informe matiza el vacío de alérgenos")


def test_la_afirmacion_del_hueco_esta_escrita(tmp_path):
    """No basta con enseñar celdas vacías: hay que decir por qué lo están."""
    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    assert "no existen en el snapshot" in md
    assert "nivel 3" in md
    print("PASS: el informe explica por qué esos campos están vacíos")


def test_declara_los_niveles_no_consultados(tmp_path):
    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    assert "Fuentes no consultadas" in md
    assert "nivel 2" in md and "nivel 3" in md
    print("PASS: el informe declara los niveles 2 y 3")


def test_la_url_de_procedencia_viaja_en_la_tabla(tmp_path):
    """El DoD pide abrir 10 URLs a mano: tienen que estar y ser correctas."""
    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    assert "https://world.openfoodfacts.org/product/00000000" in md
    print("PASS: las URLs de origen están en la tabla")


def test_tabla_larga_se_recorta_diciendolo(tmp_path):
    """Recortar en silencio sería mentir sobre cuántos productos hay.

    El PDF enseña 12 porque con los ingredientes completos cada fila ocupa casi
    media página. Lo que se recorta no se pierde: el objeto `mapa` conserva los
    200 y la SPA los pagina, y el informe dice las dos cosas.
    """
    informe = _emitir(tmp_path, _mapa(n=60), _insight())
    md = informe.markdown_content
    assert "Se muestran 12 de 60 productos" in md
    assert "en la aplicación" in md, "no se dice dónde está el resto"
    assert len(informe.mapa.productos) == 60, "el informe conserva los 60"
    print("PASS: recorte declarado, mapa completo conservado")


def test_pipes_del_nombre_no_rompen_la_tabla(tmp_path):
    """Un `|` en el nombre partiría la fila en dos celdas de más."""
    import markdown as md_lib

    mapa = MapaComercial(insumo="arándano", nivel_alcanzado=1,
                         productos=[_producto(0, nombre="Jam | Extra")])
    md = _emitir(tmp_path, mapa, _insight()).markdown_content
    fila = next(l for l in md.splitlines() if "Jam" in l)
    assert "Jam \\| Extra" in fila, fila

    # La prueba de verdad es el HTML: da igual cuántos `|` haya en el texto
    # mientras la fila renderizada tenga exactamente 6 celdas.
    html = md_lib.markdown(md, extensions=["tables", "sane_lists"])
    fila_html = next(f for f in html.split("<tr>") if "Jam" in f)
    assert fila_html.count("<td>") == 6, fila_html
    print("PASS: el pipe se escapa y la fila renderiza 6 celdas")


# --- integración con el resto del informe ---------------------------------

def test_el_mapa_sobrevive_a_un_run_sin_presupuesto(tmp_path):
    """2b no gasta presupuesto: sin insight, el mapa sigue ahí."""
    informe = _emitir(tmp_path, _mapa(), insight=None)
    assert "Mapa comercial" in informe.markdown_content
    assert "el presupuesto asignado se agotó" in informe.markdown_content
    assert informe.mapa is not None
    print("PASS: sin insight, el informe conserva el mapa")


def test_sin_mapa_el_informe_sigue_saliendo(tmp_path):
    """Ningún llamador antiguo se rompe por no pasar mapa."""
    informe = _emitir(tmp_path, None, _insight())
    assert "Mapa comercial" not in informe.markdown_content
    assert informe.mapa is None
    print("PASS: sin mapa el informe se emite igual")


def test_mapa_vacio_lo_dice_en_vez_de_una_tabla_vacia(tmp_path):
    mapa = MapaComercial(insumo="zzz", nivel_alcanzado=1, niveles_no_disponibles=[2, 3])
    md = _emitir(tmp_path, mapa, _insight()).markdown_content
    assert "no se encontró ningún producto" in md
    assert "| Producto |" not in md
    print("PASS: mapa vacío se declara, no se pinta una tabla sin filas")


def test_las_marcas_delimitan_el_mapa_para_la_spa(tmp_path):
    """`Result.vue` corta por estas marcas para no duplicar la tabla.

    La SPA pinta su propia tabla paginada con los 200 productos; si estas marcas
    desaparecen o se descolocan, el usuario ve dos tablas del mismo mapa, una
    completa y otra recortada a 25 filas.
    """
    md = _emitir(tmp_path, _mapa(n=60), _insight()).markdown_content
    ini, fin = md.index(INICIO), md.index(FIN)
    assert ini < fin, "las marcas están invertidas"

    dentro, fuera = md[ini:fin], md[:ini] + md[fin:]
    assert "| Producto |" in dentro, "la tabla quedó fuera de las marcas"
    assert "Se muestran 12 de 60" in dentro, "el aviso de recorte quedó fuera"
    assert "| Producto |" not in fuera, "quedó una tabla suelta fuera"
    # Lo que la SPA se queda tiene que seguir siendo un informe.
    assert "Insight de Mercado" in fuera
    print("PASS: la sección del mapa está delimitada y es recortable")


def test_las_marcas_no_se_imprimen_en_el_pdf(tmp_path):
    """Son comentarios HTML: el lector del PDF no debe verlas."""
    import markdown as md_lib

    md = _emitir(tmp_path, _mapa(), _insight()).markdown_content
    html = md_lib.markdown(md, extensions=["tables", "sane_lists"])
    assert INICIO in html, "el comentario debe sobrevivir al markdown"
    # Un comentario HTML no pinta texto: lo que no puede pasar es que el lector
    # lea la palabra "MAPA" suelta en mitad del informe.
    import re
    visible = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert "MAPA" not in visible
    print("PASS: las marcas no son texto visible")


def test_mapa_vacio_tambien_queda_delimitado(tmp_path):
    """Si no, la SPA cortaría mal el informe de un insumo sin productos."""
    mapa = MapaComercial(insumo="zzz", nivel_alcanzado=1, niveles_no_disponibles=[2, 3])
    md = _emitir(tmp_path, mapa, _insight()).markdown_content
    assert md.index(INICIO) < md.index(FIN)
    print("PASS: mapa vacío también delimitado")


def test_el_pdf_se_genera_de_verdad(tmp_path):
    """La tabla pasa por markdown -> HTML -> xhtml2pdf sin romper la composición."""
    informe = _emitir(tmp_path, _mapa(n=30), _insight())
    pdf = Path(informe.ruta_pdf)
    assert pdf.exists() and pdf.stat().st_size > 2000, pdf.stat().st_size
    assert pdf.read_bytes()[:4] == b"%PDF"
    print(f"PASS: PDF de {pdf.stat().st_size:,} bytes con la tabla dentro")


if __name__ == "__main__":
    import tempfile
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as tmp:
                fn(Path(tmp))
