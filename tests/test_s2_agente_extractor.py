"""
S2.1 - Extractor de producto del AgenteInvestigadorComercial.

El extractor era un stub que ni llegaba a llamar al modelo, asi que N3 nunca
devolvio un producto. Estos tests fijan el contrato de la implementacion real
sin depender del proveedor: se sustituye el cliente LLM por un doble, porque lo
que hay que comprobar aqui es como se pide y que se hace con la respuesta, no
que ModelArts este de pie.

La llamada real contra glm-5.2 se cubre aparte; hoy la credencial de ModelArts
responde 403 (ModelArts.81004) para todos los modelos del proyecto.
"""

import pytest

from casos_de_uso.agente.agente import (
    AgenteInvestigadorComercial,
    MAX_CARACTERES_HTML,
    MODELO_EXTRACCION,
)
from casos_de_uso.agente.grounding_check import grounding_check
from casos_de_uso.agente.schemas import ProductoSchema


FICHA = """Quinua Organica Real Blanca - Bolsa 500 g
Marca: Andes Gold
Precio: S/ 24.90
Presentacion: bolsa de 500 g
Origen: Puno, Peru
Categoria: Granos andinos"""


class LLMFalso:
    """Doble del cliente de instructor. Registra la llamada y devuelve lo dado."""

    def __init__(self, respuesta):
        self.respuesta = respuesta
        self.llamada = None
        self.chat = self  # instructor expone client.chat.completions.create
        self.completions = self

    async def create(self, **kwargs):
        self.llamada = kwargs
        return self.respuesta


def _agente_con(respuesta) -> tuple[AgenteInvestigadorComercial, LLMFalso]:
    agente = AgenteInvestigadorComercial()
    doble = LLMFalso(respuesta)
    agente.llm = doble
    return agente, doble


@pytest.mark.asyncio
async def test_devuelve_una_instancia_no_la_clase(monkeypatch):
    """El stub devolvia la clase ProductoSchema; debe ser una instancia."""
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "clave-de-prueba")
    esperado = ProductoSchema(nombre="Quinua Organica Real Blanca", precio=24.90,
                              marca="Andes Gold", unidad="500 g")
    agente, _ = _agente_con(esperado)

    producto = await agente.extraer_producto(FICHA)

    assert isinstance(producto, ProductoSchema)
    assert producto is not ProductoSchema
    assert producto.nombre == "Quinua Organica Real Blanca"
    assert producto.precio == 24.90


@pytest.mark.asyncio
async def test_pide_el_schema_al_modelo_correcto(monkeypatch):
    """response_model es lo que hace que vuelva validado, y el modelo es glm-5.2."""
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "clave-de-prueba")
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_BASE_URL", "https://maas.example/v1")
    agente, doble = _agente_con(ProductoSchema(nombre="X"))

    await agente.extraer_producto(FICHA)

    assert doble.llamada["model"] == MODELO_EXTRACCION
    assert doble.llamada["response_model"] is ProductoSchema
    assert doble.llamada["api_key"] == "clave-de-prueba"
    assert doble.llamada["api_base"] == "https://maas.example/v1"


@pytest.mark.asyncio
async def test_recorta_el_html_a_la_ventana(monkeypatch):
    """No se le manda la pagina entera al modelo."""
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "clave-de-prueba")
    agente, doble = _agente_con(ProductoSchema(nombre="X"))

    await agente.extraer_producto("a" * (MAX_CARACTERES_HTML * 3))

    enviado = doble.llamada["messages"][1]["content"]
    assert enviado.count("a") == MAX_CARACTERES_HTML


@pytest.mark.asyncio
async def test_el_prompt_prohibe_inventar(monkeypatch):
    """La instruccion anti-invencion es lo que sostiene el grounding check."""
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "clave-de-prueba")
    agente, doble = _agente_con(ProductoSchema(nombre="X"))

    await agente.extraer_producto(FICHA)

    sistema = doble.llamada["messages"][0]["content"].lower()
    assert "null" in sistema
    assert "grounding" in sistema


@pytest.mark.asyncio
async def test_sin_credencial_falla_sin_llamar(monkeypatch):
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "")
    agente, doble = _agente_con(ProductoSchema(nombre="X"))

    with pytest.raises(ValueError, match="HUAWEI_MAAS_API_KEY"):
        await agente.extraer_producto(FICHA)

    assert doble.llamada is None


@pytest.mark.asyncio
async def test_lo_extraido_pasa_el_grounding_check(monkeypatch):
    """Un producto fiel a la ficha sobrevive a la verificacion de S2.4."""
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "clave-de-prueba")
    agente, _ = _agente_con(ProductoSchema(
        nombre="Quinua Organica Real Blanca", precio=24.90, marca="Andes Gold"))

    producto = await agente.extraer_producto(FICHA)
    resultado = grounding_check(FICHA, producto.model_dump())

    assert resultado.passed, [e.razon for e in resultado.errores]


@pytest.mark.asyncio
async def test_el_grounding_check_tumba_lo_inventado(monkeypatch):
    """Si el modelo se inventa el precio, no pasa. Es el punto del checkeo."""
    monkeypatch.setattr("casos_de_uso.agente.agente.HUAWEI_MAAS_API_KEY", "clave-de-prueba")
    agente, _ = _agente_con(ProductoSchema(
        nombre="Quinua Organica Real Blanca", precio=999.99, marca="Marca Inventada"))

    producto = await agente.extraer_producto(FICHA)
    resultado = grounding_check(FICHA, producto.model_dump())

    assert not resultado.passed
    assert "precio" in [e.campo for e in resultado.errores]
