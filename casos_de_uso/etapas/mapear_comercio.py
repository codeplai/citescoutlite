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

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as TiempoAgotado

from casos_de_uso.dependencias import Dependencias
from dominio.insumo import InsumoInterpretado
from dominio.mapa_comercial import MapaComercial
from puertos.descubrimiento_comercial import NivelDescubrimiento

logger = logging.getLogger(__name__)

# S2 INTEG.1: Cascada N1→N2→N3 con agente investigador comercial.
# Nivel pedido = AGENTE_WEB para ejecutar cascada completa si hay gaps.
NIVEL_PEDIDO = NivelDescubrimiento.AGENTE_WEB

# Ambito del MVP. Ver la nota en mapear_comercio() sobre por que no sale de
# `InsumoInterpretado`.
PAIS_POR_DEFECTO = "Perú"

# Cuanto se le concede EN TOTAL a las dos gondolas por agente.
#
# Es un tope de la pareja, no de cada una: lo que hay que acotar es lo que
# tarda /consultas, y esa cifra es el reloj de pared, no la suma de los dos
# trabajos. Alemania y Suiza arrancan a la vez y comparten este presupuesto;
# la que no haya terminado cuando se agota entrega [] y el informe sigue, que
# es como ya degrada cuando el agente falla (ADR-001).
#
# 90 s sale de lo medido: 'galletas de quinua' gastaba 199,8 s en la etapa 2b
# (~10 s de Peru, ~190 s de las dos europeas EN SERIE) y devolvia cero ofertas
# en ambas. En paralelo el reloj pasa a ser el de la mas lenta, y el tope
# convierte el peor caso en una cifra conocida en vez de en "los minutos que
# haga falta".
TOPE_GONDOLAS_AGENTE_S = 90.0

VARIABLE_TOPE = "AGROSCOUT_GONDOLA_TOPE_S"


def _tope_segundos() -> float:
    """El tope vigente, leido en cada consulta y no al importar el modulo.

    No es una preferencia de estilo. `api/main.py` importa
    `casos_de_uso.evaluar_insumo` —y con el este modulo— en su bloque de
    imports, y llama a `load_dotenv()` despues: un `os.getenv` en el cuerpo del
    modulo correria con el entorno todavia sin el `.env` cargado y el valor
    escrito ahi no tendria ningun efecto. Los interruptores
    `AGROSCOUT_GONDOLA_DE`/`_CH` no tienen el problema porque viven en
    api/main.py, ya despues de esa llamada.

    Un valor ilegible no tumba la consulta: se avisa y se usa el de siempre.
    """
    crudo = os.getenv(VARIABLE_TOPE)
    if not crudo:
        return TOPE_GONDOLAS_AGENTE_S
    try:
        return float(crudo)
    except ValueError:
        logger.warning("%s=%r no es un numero; se usan %.0f s",
                       VARIABLE_TOPE, crudo, TOPE_GONDOLAS_AGENTE_S)
        return TOPE_GONDOLAS_AGENTE_S


def _gondolas_por_agente(d: Dependencias, insumo: str,
                         termino_de: str) -> tuple[list, list]:
    """Alemania y Suiza a la vez, con un tope de tiempo para las dos.

    Hasta aqui iban en serie —primero Alemania, despues Suiza— y una consulta
    pagaba los dos runs de agente uno detras de otro dentro de una peticion
    sincrona. Como no comparten nada, ponerlas en paralelo deja el coste en
    dinero igual y la espera en la mas lenta de las dos.

    Se llama a `d.ofertas.de_alemania` y `d.ofertas.de_suiza` y no a un metodo
    nuevo del adaptador a proposito: los interruptores de api/main.py
    (`AGROSCOUT_GONDOLA_DE`, `AGROSCOUT_GONDOLA_CH`) sustituyen justo esos dos
    atributos de la instancia, y un metodo que no pasara por ellos apagaria el
    freno de mano sin que se notara.

    **El hilo que se pasa del tope no muere.** Python no sabe matar un hilo, y
    el agente esta dentro de un `asyncio.run` en otro. Lo que se corta es la
    espera, no el trabajo: la peticion responde y el run huerfano termina solo
    y tira su resultado. Se acepta porque la alternativa —esperarlo— es
    exactamente el problema que este tope viene a resolver; por eso el
    ejecutor se cierra con `wait=False`, que si no `shutdown()` volveria a
    bloquear lo que acabamos de dejar de esperar.
    """
    if d.ofertas is None:
        return [], []

    ejecutor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gondola")
    try:
        # El reloj arranca antes de lanzar nada: el tope cuenta desde que
        # empieza el trabajo, no desde que terminamos de encargarlo.
        tope = _tope_segundos()
        vence = time.monotonic() + tope
        futuros = [
            ("alemana", ejecutor.submit(d.ofertas.de_alemania, insumo, termino_de)),
            ("suiza", ejecutor.submit(d.ofertas.de_suiza, insumo, termino_de)),
        ]
        recogidas = []
        for nombre, futuro in futuros:
            try:
                recogidas.append(futuro.result(
                    timeout=max(0.0, vence - time.monotonic())))
            except TiempoAgotado:
                logger.warning(
                    "Gondola %s: se agoto el tope de %.0f s de las gondolas por "
                    "agente; el informe sale sin esa tabla",
                    nombre, tope)
                recogidas.append([])
            except Exception as e:
                # El adaptador ya captura lo suyo y devuelve []; esto cubre lo
                # que se escape de ahi, para que una gondola rota no tumbe la
                # etapa entera y con ella /consultas.
                logger.error("Gondola %s: %s: %s", nombre, type(e).__name__, e)
                recogidas.append([])
        return recogidas[0], recogidas[1]
    finally:
        ejecutor.shutdown(wait=False)


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
    # `InsumoInterpretado` no tiene campo `pais` y nunca lo ha tuvo: es el
    # esquema que rellena el LLM en la etapa 1 (adaptadores/redactor_glm.py) y
    # sus campos son insumo_normalizado, reconocible, sinonimos_busqueda y
    # terminos_ingles.
    #
    # La linea que habia aqui, `interpretado.pais or "Perú"`, llego en S2
    # INTEG.1-3 apuntando a un campo inexistente. Pydantic lanza AttributeError
    # ante un atributo que no declara, asi que **la etapa 2b reventaba en cada
    # llamada** y con ella /consultas entero, que devolvia 500. Lleva asi desde
    # S2; los 9 tests de test_etapa_2b.py y los 5 de test_e2e_s3.py que fallan
    # por 'InsumoInterpretado object has no attribute pais' son eso.
    #
    # El pais no se anade al modelo porque hoy no es parte de la
    # interpretacion: el MVP es de ambito peruano (ver el snapshot de
    # datasets/ y la normalizacion de etl/normalizar_paises.py). Cuando la
    # consulta admita pais, entra aqui como parametro del contexto de busqueda,
    # no como algo que el LLM tenga que adivinar del texto libre.
    pais = PAIS_POR_DEFECTO

    # Precio de materia prima: lectura local, sin red y sin coste. Va aunque no
    # haya adaptador de descubrimiento, porque son fuentes independientes.
    precios = d.precios.para_insumo(insumo) if d.precios is not None else []

    # Precio de gondola en las cadenas peruanas. Tambien es una fuente
    # independiente: no pasa por la cascada ni por ningun modelo, son cuatro
    # peticiones a un API publico. Por eso se lee aunque no haya adaptador de
    # descubrimiento, igual que los precios de materia prima.
    #
    # Sin adaptador de ofertas la etapa corre igual y la tabla sale vacia; es
    # el modo en que corren los tests deterministas de S2.
    # Se busca por la forma de producto si la consulta pidio una —«barras de
    # quinua»— y se filtra por el insumo. `insumo_normalizado` reduce a la
    # materia prima, que es lo correcto para el resto del informe pero llenaba
    # esta tabla de grano suelto cuando lo que se pedia eran barras.
    ofertas_peru = (d.ofertas.de_peru(insumo, interpretado.forma_producto)
                    if d.ofertas is not None else [])

    # Gondola alemana. Misma etapa y mismo patron defensivo, pero **no es la
    # misma clase de fuente**: ninguna cadena alemana publica precio sin
    # credencial (sondeadas las cinco), asi que esto va por agente y cuesta
    # minutos y dinero, frente a los ~2 s gratis de Peru.
    #
    # Se busca con el termino aleman que dio la etapa 1, no con el insumo
    # normalizado: 'arandano' no encuentra 'Heidelbeeren 200g' ni en el buscador
    # ni en el filtro posterior. Sin termino, `de_alemania` devuelve [] sin
    # gastar la busqueda, que es lo correcto: una consulta que garantiza cero
    # resultados no merece pagarse.
    #
    # La gondola suiza usa el **mismo termino aleman**: las tiendas suizas que
    # importan —Migros, Coop, Piccantino— publican en aleman, y es la region
    # linguistica mas grande del pais. Lo que queda fuera son las fichas en
    # frances e italiano de Migros y Coop, que pediran un
    # `terminos_frances`/`terminos_italiano` en la etapa 1; es una decision
    # aparte y esta escrita en `adaptadores/catalogo_suiza.py`.
    #
    # Las dos salen **a la vez y con un tope comun**; el porque, en
    # `_gondolas_por_agente`. Cada una conserva su interruptor propio en
    # api/main.py, que es lo que permite apagar un mercado sin apagar el otro.
    termino_de = (interpretado.terminos_aleman or [""])[0]
    ofertas_alemania, ofertas_suiza = _gondolas_por_agente(d, insumo, termino_de)

    if d.descubrimiento is None:
        return MapaComercial(
            insumo=insumo,
            nivel_alcanzado=0,
            niveles_no_disponibles=[int(n) for n in NivelDescubrimiento],
            precios_materia_prima=precios,
            ofertas_peru=ofertas_peru,
            ofertas_alemania=ofertas_alemania,
            ofertas_suiza=ofertas_suiza,
        )

    # Ejecutar cascada
    cascada_metadata = None
    if hasattr(d.descubrimiento, 'descubrir_sync'):
        # DescubrimientoCascada: retorna (productos, metadata)
        productos, cascada_metadata = d.descubrimiento.descubrir_sync(
            insumo, pais, NIVEL_PEDIDO
        )
    else:
        # Fallback: adaptador antiguo (DescubrimientoSnapshot).
        #
        # Se le pasa la forma de producto por el mismo motivo que a la gondola
        # peruana unas lineas mas arriba: `insumo_normalizado` reduce a la
        # materia prima, y esta tabla salia llena de grano suelto cuando lo que
        # se pedia eran barras. Medido: de 200 filas devueltas por «quinua»,
        # 11 eran barras y ninguna entraba entre las diez primeras.
        productos = d.descubrimiento.descubrir(
            insumo, NIVEL_PEDIDO, interpretado.forma_producto)

    # Construir mapa comercial con metadata de cascada si disponible
    mapa = MapaComercial(
        insumo=insumo,
        productos=productos,
        nivel_alcanzado=int(NivelDescubrimiento.SNAPSHOT),
        niveles_no_disponibles=d.descubrimiento.niveles_no_disponibles(NIVEL_PEDIDO),
        descartadas=dict(getattr(d.descubrimiento, "descartadas", {}) or {}),
        precios_materia_prima=precios,
        ofertas_peru=ofertas_peru,
        ofertas_alemania=ofertas_alemania,
        ofertas_suiza=ofertas_suiza,
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
