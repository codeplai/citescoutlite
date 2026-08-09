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

# S2 INTEG.1: Cascada N1→N2→N3 con agente investigador comercial.
# Nivel pedido = AGENTE_WEB para ejecutar cascada completa si hay gaps.
NIVEL_PEDIDO = NivelDescubrimiento.AGENTE_WEB


def mapear_comercio(d: Dependencias,
                    interpretado: InsumoInterpretado) -> MapaComercial:
    """
    Productos reales en el mercado para el insumo ya normalizado.

    S2 INTEG.3: Ejecuta cascada N1→N2→N3 si el adaptador lo soporta:
      - N1: Snapshot LanceDB (siempre)
      - N2: Bright Data (si adaptador lo implementa)
      - N3: Agente investigador web (si hay gaps)

    N3 guarda datos en staging_agente (cuarentena) sin promoción automática.
    Auditoría registra niveles_ejecutados y cobertura en salida_json.
    """
    insumo = interpretado.insumo_normalizado
    pais = interpretado.pais or "Perú"  # País del contexto de búsqueda

    # Precio de materia prima: lectura local, sin red y sin coste. Va aunque no
    # haya adaptador de descubrimiento, porque son fuentes independientes.
    precios = d.precios.para_insumo(insumo) if d.precios is not None else []

    if d.descubrimiento is None:
        return MapaComercial(
            insumo=insumo,
            nivel_alcanzado=0,
            niveles_no_disponibles=[int(n) for n in NivelDescubrimiento],
            precios_materia_prima=precios,
        )

    # Ejecutar cascada
    cascada_metadata = None
    if hasattr(d.descubrimiento, 'descubrir_sync'):
        # DescubrimientoCascada: retorna (productos, metadata)
        productos, cascada_metadata = d.descubrimiento.descubrir_sync(
            insumo, pais, NIVEL_PEDIDO
        )
    else:
        # Fallback: adaptador antiguo (DescubrimientoSnapshot)
        productos = d.descubrimiento.descubrir(insumo, NIVEL_PEDIDO)

    # Construir mapa comercial con metadata de cascada si disponible
    mapa = MapaComercial(
        insumo=insumo,
        productos=productos,
        nivel_alcanzado=int(NivelDescubrimiento.SNAPSHOT),
        niveles_no_disponibles=d.descubrimiento.niveles_no_disponibles(NIVEL_PEDIDO),
        descartadas=dict(getattr(d.descubrimiento, "descartadas", {}) or {}),
        precios_materia_prima=precios,
    )

    # Agregar metadata de cascada si está disponible
    if cascada_metadata:
        mapa.niveles_ejecutados = cascada_metadata.niveles_ejecutados
        mapa.has_gaps = cascada_metadata.has_gaps
        mapa.productos_n3_staging = cascada_metadata.productos_n3_staging
        # Actualizar nivel_alcanzado al máximo ejecutado
        if cascada_metadata.niveles_ejecutados:
            mapa.nivel_alcanzado = max(cascada_metadata.niveles_ejecutados)

    return mapa
