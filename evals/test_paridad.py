import pytest
from dominio.insumo import InsumoInterpretado
from dominio.producto_existente import ProductoExistente
from dominio.insight_mercado import InsightDeMercado
from dominio.informe_scout import InformeScout

def test_contrato_insumo_interpretado():
    schema = InsumoInterpretado.model_json_schema()
    assert "insumo_normalizado" in schema["properties"]
    assert "reconocible" in schema["properties"]
    assert "sinonimos_busqueda" in schema["properties"]

def test_contrato_informe_scout():
    schema = InformeScout.model_json_schema()
    assert "parcial" in schema["properties"]
    assert "snapshot_version" in schema["properties"]
