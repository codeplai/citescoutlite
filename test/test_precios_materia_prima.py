"""
Precio de materia prima (MIDAGRI · SISAP).

Lo que estos tests protegen, por encima del formato, es **que no se confunda con
el precio de góndola**. Son dos preguntas distintas:

  - a cuánto está el kilo de palta en el mayorista  -> esto, y sí lo sabemos;
  - a cuánto vende su guacamole una marca           -> `precio_rango`, y no.

Si alguien los junta en la misma tabla, el informe pasa a dar a entender que el
precio de góndola existe y está detrás del plan de pago. No existe.

Se ejecuta con pytest o directamente: python test/test_precios_materia_prima.py
"""
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from adaptadores.precios_sisap import PreciosSISAP
from dominio.precio_materia_prima import PrecioMateriaPrima
from etl.cargar_precios_sisap import interpretar, unificar_nombres

SNAPSHOT = Path("datasets/precios-sisap/precios.json")


def _valido(**cambios):
    base = dict(insumo="palta", producto="PALTA FUERTE COSTA", mercado="MMF2",
                mercado_nombre="Mercado Mayorista de Frutas Nº 2",
                precio_soles_kg=3.85, variacion_pct=5.1, fecha=date(2026, 7, 24),
                url_boletin="https://cdn.www.gob.pe/uploads/document/file/1/x.pdf")
    base.update(cambios)
    return base


# --- el contrato ----------------------------------------------------------

def test_un_precio_de_cero_no_es_un_precio():
    """Cero soles el kilo no es un dato barato: es un dato que falta."""
    for malo in (0, -1.5):
        with pytest.raises(ValidationError):
            PrecioMateriaPrima(**_valido(precio_soles_kg=malo))
    print("PASS: precio <= 0 rechazado por el contrato")


def test_la_procedencia_es_obligatoria():
    """Sin fecha y sin PDF de origen, el número no es verificable."""
    for campo in ("fecha", "url_boletin"):
        datos = _valido()
        del datos[campo]
        with pytest.raises(ValidationError):
            PrecioMateriaPrima(**datos)
    print("PASS: fecha y url_boletin obligatorias")


def test_variacion_ausente_es_none_no_cero():
    p = PrecioMateriaPrima(**_valido(variacion_pct=None))
    assert p.variacion_pct is None
    print("PASS: variación ausente es None, no 0 %")


# --- el parseo del boletín ------------------------------------------------

def test_interpretar_una_fila_del_boletin():
    fila = ["01311", "PALTA FUERTE COSTA", "", "MMF2", "3.66", "3.85", "5.1%",
            "3.78", "3.73"]
    r = interpretar(fila)
    assert r["producto"] == "PALTA FUERTE COSTA"
    assert r["mercado"] == "MMF2"
    assert r["precio_semana_anterior"] == 3.66
    assert r["precio_soles_kg"] == 3.85
    assert r["variacion_pct"] == 5.1
    print("PASS: fila del boletín interpretada")


def test_filas_que_no_son_precio_se_descartan():
    for fila in (["012", "HORTALIZAS", "", "", "", ""],      # cabecera de grupo
                 ["01311", "PALTA", "MMF2"],                  # sin números
                 ["texto", "suelto", "sin", "codigo", "x"]):
        assert interpretar(fila) is None, fila
    print("PASS: cabeceras y filas incompletas descartadas")


def test_reconstruccion_de_nombres_partidos_por_el_pdf():
    """El corte por columnas parte palabras, y por sitios distintos cada día.

    Un espacio que aparece en TODAS las muestras es real; uno que falta en
    alguna es del corte. Nunca se inventa un espacio que no se haya visto.
    """
    registros = [{"producto": "PALTA LINDA (COSTA/SE LVA)"},
                 {"producto": "PALTA LINDA (CO STA/SELVA)"},
                 {"producto": "PALTA LINDA (COSTA/SELVA)"}]
    unificar_nombres(registros)
    assert all(r["producto"] == "PALTA LINDA (COSTA/SELVA)" for r in registros)
    print("PASS: nombre reconstruido por intersección")


def test_con_una_sola_muestra_no_se_inventa_nada():
    """Sin con qué comparar, el nombre se queda como vino."""
    registros = [{"producto": "MANGO EDWARD PLANT A"}]
    unificar_nombres(registros)
    assert registros[0]["producto"] == "MANGO EDWARD PLANT A"
    print("PASS: sin muestras que comparar, no se toca el nombre")


# --- el adaptador ---------------------------------------------------------

def test_insumo_sin_precio_devuelve_lista_vacia():
    """`[]` significa "no se publica", no "vale cero"."""
    a = PreciosSISAP()
    assert a.para_insumo("arándano") == []
    assert a.para_insumo("quinua") == []
    assert a.para_insumo("zzz-no-existe") == []
    print("PASS: insumo sin precio -> [] sin lanzar")


def test_el_insumo_casa_sin_importar_mayusculas_ni_tildes():
    """La etapa 1 devuelve `'Palta'`; el snapshot guarda `'palta'`.

    Sin plegar, la comparación no casa nunca **y no avisa**: el bloque sale
    vacío como si MIDAGRI no publicara el precio, que es la conclusión
    contraria. Fue un fallo real, detectado ejercitando la API.
    """
    a = PreciosSISAP()
    esperado = len(a.para_insumo("palta"))
    assert esperado > 0, "el snapshot no trae palta"
    for variante in ("Palta", "PALTA", " palta "):
        assert len(a.para_insumo(variante)) == esperado, variante
    # Y con tilde, que es como llega el espárrago.
    assert len(a.para_insumo("Espárrago")) == len(a.para_insumo("esparrago"))
    print("PASS: el insumo casa plegando mayúsculas y tildes")


def test_sin_snapshot_no_revienta():
    """Degrada a sin dato, nunca a error."""
    a = PreciosSISAP(ruta="no/existe/precios.json")
    assert a.para_insumo("palta") == [] and a.insumos_cubiertos() == []
    print("PASS: sin snapshot, lista vacía")


def test_precios_reales_del_snapshot():
    productos = PreciosSISAP().para_insumo("palta")
    assert productos, "el snapshot no trae palta"
    assert all(p.precio_soles_kg > 0 for p in productos)
    assert all(p.insumo == "palta" for p in productos)
    # Ordenados de mayor a menor: la variedad cara primero.
    assert productos == sorted(productos, key=lambda p: -p.precio_soles_kg)
    # Una sola observación por variedad y mercado: la más reciente.
    claves = [(p.producto, p.mercado) for p in productos]
    assert len(claves) == len(set(claves))
    print(f"PASS: {len(productos)} variedades de palta · "
          f"S/ {productos[0].precio_soles_kg:.2f}/kg la más cara")


def test_el_snapshot_declara_lo_que_no_cubre():
    datos = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(datos["insumos_sin_precio"]) == {"quinua", "arándano"}
    alcance = datos["alcance"].lower()
    assert "materia prima" in alcance
    assert "no es el precio de góndola" in alcance
    print("PASS: el snapshot declara su alcance y sus huecos")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
