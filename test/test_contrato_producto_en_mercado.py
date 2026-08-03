"""
TIER 1 · T1.3 (S4): el contrato `ProductoEnMercado`, congelado.

DoD del plan §T1.3: "`ProductoEnMercado` congelado; `contratos/` regenerado".

"Congelado" solo significa algo si algo lo comprueba. Contra este esquema se
escribe la tabla del informe (T4.3), el validador P04 (T5.1) y el adaptador de
nivel 3 en F4: cambiarlo en silencio rompe a los tres a la vez, y el sitio donde
se nota es la demo.

Se ejecuta con pytest o directamente: python test/test_contrato_producto_en_mercado.py
"""
import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from dominio.producto_en_mercado import ProductoEnMercado

SCHEMAS = Path("contratos/schemas.json")

CAMPOS = {"insumo", "producto_id", "nombre", "marca", "paises_iso",
          # Formulación: todo se lee del texto de ingredientes del snapshot,
          # que está al 100 % y no cuesta ni una llamada de red.
          "ingredientes", "lista_ingredientes", "n_ingredientes",
          "aditivos", "alergenos",
          "presentacion", "precio_rango", "canal", "fuente", "url", "fecha_dato"}

REQUERIDOS = {"insumo", "producto_id", "nombre", "fuente", "url", "fecha_dato"}

# Los tres que son siempre None en el MVP. Están en el modelo a propósito: son
# lo que la tabla enseña como "sin dato" y el gancho del nivel 3 en F4.
EL_HUECO = {"presentacion", "precio_rango", "canal"}


def _valido(**cambios) -> dict:
    base = dict(insumo="arándano", producto_id="OFF:00000036",
                nombre="Mermelada de arándano", fuente="OFF",
                url="https://world.openfoodfacts.org/product/00000036",
                fecha_dato=date(2026, 3, 14))
    base.update(cambios)
    return base


def test_contratos_regenerado_y_al_dia():
    """`contratos/schemas.json` refleja el modelo actual, no uno anterior."""
    almacenado = json.loads(SCHEMAS.read_text(encoding="utf-8"))
    assert "ProductoEnMercado" in almacenado, \
        "Falta en contratos/: correr scripts/generar_contratos.py"
    assert almacenado["ProductoEnMercado"] == ProductoEnMercado.model_json_schema(), \
        "contratos/ está desfasado: correr scripts/generar_contratos.py"
    print("PASS: contratos/schemas.json al día")


def test_forma_del_contrato():
    esquema = ProductoEnMercado.model_json_schema()
    assert set(esquema["properties"]) == CAMPOS
    assert set(esquema["required"]) == REQUERIDOS
    print(f"PASS: {len(CAMPOS)} campos, {len(REQUERIDOS)} requeridos")


def test_alergenos_vacio_no_significa_sin_alergenos():
    """El campo admite `[]`, y `[]` es "la etiqueta no lo declara".

    Se fija aquí porque es una distinción de seguridad alimentaria: si alguien
    la convierte en un `bool` o en un "ninguno", el informe pasa a afirmar algo
    que el dato no dice.
    """
    p = ProductoEnMercado(**_valido())
    assert p.alergenos == [] and p.aditivos == []
    assert p.ingredientes is None and p.n_ingredientes is None
    print("PASS: alergenos y aditivos nacen vacíos, sin afirmar nada")


def test_el_hueco_es_opcional_y_nace_en_none():
    """Que sean opcionales es lo que permite declararlos sin inventarlos."""
    p = ProductoEnMercado(**_valido())
    for campo in EL_HUECO:
        assert getattr(p, campo) is None, campo
        assert campo not in REQUERIDOS
    print(f"PASS: {sorted(EL_HUECO)} son None por defecto")


def test_una_sola_fuente_por_fila():
    """`fuente` es un Literal cerrado: no entra una fuente inventada."""
    assert ProductoEnMercado(**_valido(fuente="USDA")).fuente == "USDA"
    for mala in ("OpenPrices", "DEMO", "off", ""):
        with pytest.raises(ValidationError):
            ProductoEnMercado(**_valido(fuente=mala))
    print("PASS: fuente solo admite OFF | USDA")


def test_marca_ausente_es_none_no_cadena_vacia():
    assert ProductoEnMercado(**_valido()).marca is None
    assert ProductoEnMercado(**_valido(marca="Acme")).marca == "Acme"
    print("PASS: marca ausente -> None")


def test_paises_iso_nace_vacia_y_no_se_comparte():
    """`default_factory`, no `[]` compartido entre instancias."""
    a = ProductoEnMercado(**_valido())
    b = ProductoEnMercado(**_valido())
    assert a.paises_iso == [] and b.paises_iso == []
    a.paises_iso.append("PE")
    assert b.paises_iso == [], "las instancias comparten la lista"
    print("PASS: paises_iso por instancia")


def test_url_y_fecha_son_obligatorias_y_validadas():
    """Son la procedencia: sin ellas la fila no es auditable."""
    for mala in ("no-es-una-url", "", "ftp://x/y"):
        with pytest.raises(ValidationError):
            ProductoEnMercado(**_valido(url=mala))
    with pytest.raises(ValidationError):
        ProductoEnMercado(**_valido(fecha_dato="ayer"))
    print("PASS: url y fecha_dato validadas")


def test_serializa_a_json_para_salida_json_de_la_etapa():
    """La etapa 2b escribe esto en `etapas_ejecucion.salida_json`."""
    p = ProductoEnMercado(**_valido(marca="Acme", paises_iso=["ES", "FR"]))
    d = json.loads(p.model_dump_json())
    assert d["paises_iso"] == ["ES", "FR"]
    assert d["fecha_dato"] == "2026-03-14"
    assert d["presentacion"] is None and d["precio_rango"] is None
    assert ProductoEnMercado(**d) == p, "no sobrevive el viaje de ida y vuelta"
    print("PASS: serializa y vuelve idéntico")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
