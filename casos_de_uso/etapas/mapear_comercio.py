"""
TIER 4 · T4.1 (S4): etapa 2b, el mapa comercial.

Entre la búsqueda (2a) y el insight (3). **Sin LLM**: su `costo_usd` es 0 y su
duración se mide en milisegundos.

Va por `etapa_sync`, no por `etapa()`, y merece explicación porque el plan §T4.1
dice lo contrario. `etapa()` resuelve el modelo con
`d.redactor.modelo_por_etapa.get(num_etapa, "glm-5.2")` (ejecutor.py:47), y '2b'
no está en ese diccionario: la fila de auditoría quedaría con
`modelo='glm-5.2'` para una etapa que **no llama a ningún modelo**. En un
proyecto cuyo argumento entero es "el dato o es real o dice que no está", una
fila que nombra un LLM que nunca corrió es justo lo que el CITE puede pinchar
mirando `etapas_ejecucion`.

`etapa_sync` escribe `modelo='sync'` y `costo_usd=0.0` explícitos, y es lo que
ya usa la otra etapa sin LLM, la búsqueda 2a. Lo que se pierde es la caché; a
19 ms por consulta local, el viaje a la caché cuesta más que rehacer el trabajo.

Sin adaptador de descubrimiento la etapa **no falla**: devuelve un mapa vacío
que declara los tres niveles como no disponibles. Es el principio del ADR-001
que ya sigue el resto del DAG: degrada a "sin dato", nunca error.
"""

from casos_de_uso.dependencias import Dependencias
from dominio.insumo import InsumoInterpretado
from dominio.mapa_comercial import MapaComercial
from puertos.descubrimiento_comercial import NivelDescubrimiento

# El MVP solo tiene adaptador de nivel 1, pero se pide la cascada entera: así el
# mapa declara [2, 3] y el día que exista el agente de F4 esta línea no cambia.
NIVEL_PEDIDO = NivelDescubrimiento.AGENTE_WEB


def mapear_comercio(d: Dependencias,
                    interpretado: InsumoInterpretado) -> MapaComercial:
    """Productos reales en el mercado para el insumo ya normalizado."""
    insumo = interpretado.insumo_normalizado

    if d.descubrimiento is None:
        return MapaComercial(
            insumo=insumo,
            nivel_alcanzado=0,
            niveles_no_disponibles=[int(n) for n in NivelDescubrimiento],
        )

    productos = d.descubrimiento.descubrir(insumo, NIVEL_PEDIDO)

    return MapaComercial(
        insumo=insumo,
        productos=productos,
        nivel_alcanzado=int(NivelDescubrimiento.SNAPSHOT),
        niveles_no_disponibles=d.descubrimiento.niveles_no_disponibles(NIVEL_PEDIDO),
        descartadas=dict(getattr(d.descubrimiento, "descartadas", {}) or {}),
    )
