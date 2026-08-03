"""
TIER 3 (S4): puerto `DescubrimientoComercial` y su nivel 1 sobre el snapshot.

DoD del plan §T3:
  - descubrir("arándano", nivel_maximo=1) -> >=50 productos en <300 ms
  - nivel_maximo=3 -> lo mismo, declara [2, 3] y **nunca lanza**
  - un test que fija el contrato del puerto (contra él se escribe el agente en F4)

Se ejecuta con pytest o directamente: python test/test_descubrimiento_comercial.py
"""
import time

from adaptadores.descubrimiento_snapshot import DescubrimientoSnapshot
from dominio.producto_en_mercado import ProductoEnMercado
from etl.limpiar_texto import REEMPLAZO, SIN_DATO
from etl.normalizar_paises import ISO_ALPHA2
from puertos.descubrimiento_comercial import NivelDescubrimiento

MIN_PRODUCTOS = 50
MAX_MS = 300

# La fila que T2.2 excluye: `nombre` = 'P�o integral'.
FILA_EXCLUIDA = "OFF:7896002308762"


def _adaptador() -> DescubrimientoSnapshot:
    return DescubrimientoSnapshot()


def test_nivel_1_devuelve_productos_rapido():
    """DoD: >=50 productos en <300 ms.

    Se cronometra en caliente. Abrir la tabla LanceDB ocurre una vez por
    proceso, no por consulta —igual que en medir_latencia_p95 de S2—, así que
    incluirlo mediría el arranque, no la etapa. El número frío se imprime.
    """
    d = _adaptador()

    t0 = time.perf_counter()
    d.descubrir("arándano")
    frio_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    productos = d.descubrir("arándano", NivelDescubrimiento.SNAPSHOT)
    caliente_ms = (time.perf_counter() - t0) * 1000

    assert len(productos) >= MIN_PRODUCTOS, f"Solo {len(productos)} productos"
    assert caliente_ms < MAX_MS, f"{caliente_ms:.0f} ms >= {MAX_MS} ms"
    assert all(isinstance(p, ProductoEnMercado) for p in productos)
    print(f"PASS: {len(productos)} productos · {caliente_ms:.0f} ms en caliente "
          f"({frio_ms:.0f} ms en frío, incluye abrir la tabla)")


def test_pedir_un_nivel_inexistente_no_lanza_y_lo_declara():
    """DoD: nivel_maximo=3 devuelve lo mismo y declara [2, 3]."""
    d = _adaptador()
    n1 = d.descubrir("arándano", NivelDescubrimiento.SNAPSHOT)
    n3 = d.descubrir("arándano", NivelDescubrimiento.AGENTE_WEB)

    assert [p.producto_id for p in n3] == [p.producto_id for p in n1], \
        "nivel_maximo=3 debe devolver lo mismo que nivel 1"
    assert d.niveles_no_disponibles(NivelDescubrimiento.AGENTE_WEB) == [2, 3]
    assert d.niveles_no_disponibles(NivelDescubrimiento.API_LICENCIADA) == [2]
    assert d.niveles_no_disponibles(NivelDescubrimiento.SNAPSHOT) == []
    print("PASS: nivel 3 no lanza, devuelve lo mismo y declara [2, 3]")


def test_contrato_del_puerto():
    """Fija la forma contra la que se escribirá el agente en F4."""
    d = _adaptador()
    assert callable(d.descubrir) and callable(d.niveles_no_disponibles)
    # La cascada del ADR-001, con sus valores. Cambiarlos rompe `salida_json`.
    assert [int(n) for n in NivelDescubrimiento] == [1, 2, 3]
    assert NivelDescubrimiento.SNAPSHOT < NivelDescubrimiento.AGENTE_WEB
    # El puerto se pide por defecto en su nivel más barato.
    assert d.descubrir("mango") == d.descubrir("mango", NivelDescubrimiento.SNAPSHOT)
    print("PASS: contrato del puerto fijado")


def test_insumo_desconocido_devuelve_lista_vacia_sin_lanzar():
    """No es un error preguntar por algo que no está: es una lista vacía."""
    d = _adaptador()
    assert d.descubrir("zzzz-no-existe-zzzz") == []
    print("PASS: insumo desconocido -> []")


def test_el_filtro_no_se_rompe_con_comillas():
    """`descubrir()` es frontera con texto de usuario."""
    d = _adaptador()
    for hostil in ("arándano'; DROP TABLE productos; --", "a' OR '1'='1", "%%%"):
        assert isinstance(d.descubrir(hostil), list)
    print("PASS: el filtro resiste texto hostil")


def test_los_cinco_insumos_piloto_devuelven_productos():
    d = _adaptador()
    for insumo in ("arándano", "palta", "espárrago", "mango", "quinua"):
        productos = d.descubrir(insumo)
        assert productos, f"{insumo} sin productos"
        assert all(p.insumo == insumo for p in productos)
    print("PASS: los 5 insumos piloto devuelven productos")


def test_paises_normalizados_a_iso():
    """T2.1 aplicado al leer: nada de `en:us` ni `United States, World`."""
    d = _adaptador()
    productos = d.descubrir("arándano")
    for p in productos:
        for iso in p.paises_iso:
            assert iso in ISO_ALPHA2, f"{p.producto_id}: {iso!r} no es ISO"
    distintos = {iso for p in productos for iso in p.paises_iso}
    assert len(distintos) >= 5, f"Solo {len(distintos)} países: {distintos}"
    print(f"PASS: {len(distintos)} países ISO distintos en arándano")


def test_marca_ausente_es_none_nunca_un_no_dato_disfrazado():
    """El adaptador no emite lo que P04 tendrá que castigar en T5.1."""
    d = _adaptador()
    for insumo in ("arándano", "quinua", "mango"):
        for p in d.descubrir(insumo):
            assert p.marca is None or p.marca.strip(), "marca vacía, debería ser None"
            if p.marca is not None:
                assert p.marca.strip().lower() not in SIN_DATO, \
                    f"{p.producto_id}: marca = {p.marca!r}"
    print("PASS: marca es None o un valor real, nunca 'N/A' ni ''")


def test_el_hueco_se_declara_no_se_rellena():
    """presentacion, precio_rango y canal son None en el MVP, a propósito."""
    d = _adaptador()
    for p in d.descubrir("arándano"):
        assert p.presentacion is None
        assert p.precio_rango is None
        assert p.canal is None
    print("PASS: los tres campos del hueco siguen en None")


def test_la_fila_con_mojibake_no_se_publica():
    """T2.2: la fila excluida no entra al mapa por ninguna vía."""
    d = _adaptador()
    for insumo in ("arándano", "palta", "espárrago", "mango", "quinua"):
        for p in d.descubrir(insumo):
            assert p.producto_id != FILA_EXCLUIDA
            assert REEMPLAZO not in p.nombre
            assert REEMPLAZO not in (p.marca or "")
    print("PASS: la fila con U+FFFD no aparece en el mapa")


def test_las_filas_rotas_se_descartan_y_se_cuentan():
    """La proyección tiene cuatro salidas de emergencia y ninguna se ejecuta
    con los datos reales de arándano. Un camino que nunca ha corrido no está
    probado, así que se le pasan filas rotas a mano.

    Descartar no es lo mismo que ignorar: cada motivo queda contado en
    `descartadas`, porque que un producto no llegue a la tabla del informe
    nunca debe ser silencioso.
    """
    d = _adaptador()
    buena = {"id": "OFF:1", "nombre": "Mermelada de arándano", "marca": "Acme",
             "pais": "en:us", "url": "https://example.org/p/1",
             "fecha_dato": 1749514977, "fuente": "OFF"}

    rotas = [
        dict(buena, id="OFF:2", nombre=f"P{REEMPLAZO}o integral"),  # T2.2
        dict(buena, id="OFF:3", fuente="DEMO"),                     # fuera del Literal
        dict(buena, id="OFF:4", fecha_dato=None),                   # sin fecha
        dict(buena, id="OFF:5", url="no-es-una-url"),               # URL inválida
        dict(buena, id="OFF:6", nombre="N/A"),                      # nombre disfrazado
    ]

    salida = d._proyectar([buena] + rotas, "arándano")

    assert [p.producto_id for p in salida] == ["OFF:1"], \
        f"Se coló una fila rota: {[p.producto_id for p in salida]}"
    assert d.descartadas == {
        "mojibake_irreparable": 1,
        "fuente_desconocida": 1,
        "sin_fecha_dato": 1,
        "url_invalida": 1,
        "sin_nombre": 1,
    }, d.descartadas
    # Y la buena sale bien normalizada: `en:us` -> US.
    assert salida[0].paises_iso == ["US"]
    print(f"PASS: 5 filas rotas descartadas y contadas · {d.descartadas}")


def test_sin_duplicados_y_dentro_del_limite():
    d = DescubrimientoSnapshot(limite=75)
    productos = d.descubrir("arándano")
    ids = [p.producto_id for p in productos]
    assert len(ids) == len(set(ids)), "hay productos duplicados"
    assert len(ids) <= 75
    print(f"PASS: {len(ids)} productos, sin duplicados, dentro del límite")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
