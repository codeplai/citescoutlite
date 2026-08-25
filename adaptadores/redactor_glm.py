import json
import logging
import os
import time

import instructor
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential

from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.insight_mercado import InsightDeMercado
from dominio.insumo import InsumoInterpretado
from dominio.resultado_busqueda import ResultadoBusqueda
from puertos.redactor_llm import RedactorLLM

_log = logging.getLogger(__name__)

# Cuanto se espera a UNA llamada al modelo antes de darla por perdida.
#
# No habia ninguno, y eso significa que una llamada que no vuelve no vuelve
# nunca: la peticion de /consultas se queda esperando indefinidamente y, como
# el reintento solo entra si la llamada FALLA, tenacity ni se entera. Un
# proveedor que cuelga la conexion sin cerrarla bloqueaba el run entero.
#
# El numero es DELIBERADAMENTE generoso, y conviene entender por que antes de
# bajarlo. Medido el 2026-08-24 contra ModelArts: glm-5.2 genera a ~24
# tokens/s, y las etapas grandes producen miles de tokens. En
# `etapas_ejecucion` hay etapas 4 y 5 reales de 214 s y 237 s.
#
# O sea que un tope "razonable" de 60 o 120 s no cortaria llamadas colgadas:
# cortaria generaciones que iban bien, y encima las reintentaria enteras. El
# resultado seria una consulta MAS lenta y un informe peor.
#
# 300 s deja margen sobre el maximo observado y sigue acotando lo que este
# tope existe para acotar: la llamada que no vuelve nunca. Para saber si algun
# dia se puede bajar hace falta el dato que hasta ahora no habia —cuanto tarda
# UNA llamada, no la etapa con sus reintentos—, y por eso `_pedir` ahora lo
# registra.
TIEMPO_MAXIMO_S = float(os.getenv("AGROSCOUT_LLM_TIMEOUT_S", "300"))

# `reraise` para ver la causa. Sin el, al agotar los tres intentos tenacity
# lanza un RetryError que esconde el error de verdad y arriba solo se lee
# 'RetryError[Future...]'. Es la misma correccion que ya lleva el agente en
# casos_de_uso/agente/agente.py.
_REINTENTOS = dict(stop=stop_after_attempt(3),
                   wait=wait_exponential(multiplier=1, min=2, max=10),
                   reraise=True)


class RedactorGLM(RedactorLLM):
    def __init__(self, api_key: str, base_url: str | None = None):
        # MD_JSON y no el TOOLS por defecto de instructor, y esto no es una
        # preferencia: con TOOLS **se perdian respuestas correctas enteras**.
        #
        # instructor pedia el esquema por function calling, y los modelos de
        # ModelArts a veces contestan en texto plano con el JSON dentro de un
        # bloque ```json. Cuando eso pasa `tool_calls` viene a None, instructor
        # levanta "No tool calls or function call found in response (mode:
        # TOOLS)" y la respuesta se tira. Comprobado sobre una de esas
        # respuestas descartadas: traia 14 ingredientes, 8 procesos y 14 citas,
        # todas con ids validos. El contenido estaba perfecto; llego por el
        # canal equivocado.
        #
        # Medido el 2026-08-24 sobre la misma entrada (etapa 4, 'salsa de soya'):
        #
        #   modelo     modo      exito    media
        #   flash      TOOLS      2/4     27,7 s
        #   flash      MD_JSON    4/4     14,5 s
        #   glm-5.2    TOOLS      2/2    136,5 s
        #   glm-5.2    MD_JSON    2/2    100,7 s
        #
        # O sea que MD_JSON arregla los descartes Y es mas rapido en los dos
        # modelos: TOOLS obliga a emitir el andamiaje de la llamada de funcion,
        # y eso son tokens que se generan a la misma velocidad que el informe.
        # De las 6 respuestas con MD_JSON, ninguna invento una cita; de las 6
        # con TOOLS, una si.
        #
        # El modo NO entra en la clave de cache (ver ejecutor.py), asi que este
        # cambio no invalida nada de lo ya cacheado.
        self.client = instructor.from_litellm(acompletion, mode=instructor.Mode.MD_JSON)
        self.api_key = api_key
        self.base_url = base_url
        # Verificado contra el endpoint el 2026-08-02: ModelArts sirve
        # deepseek-v4-flash, deepseek-v3 y glm-5.2. glm-5.0 y glm-4.7 devuelven
        # 404 'ModelArts.81009 Invalid model'. La etapa 3 apuntaba a glm-5.0 y
        # por eso fallaba en vivo; el golden set de S2 no lo detectaba porque
        # corria sobre cache.
        #
        # Claves de tipo str: la numeracion de etapas es '1','2a','2b','3','4','5','6'
        # desde el esquema de S3 (D6). Con claves int el ejecutor no encontraba
        # el modelo y caia al de por defecto, corrompiendo la clave de cache.
        # La etapa 4 va con flash y las otras dos no. No es una inconsistencia:
        # es la unica de las tres cuyo contenido es DECLARADAMENTE especulativo
        # —una hipotesis de formulacion— mientras que la 3 y la 5 escriben citas
        # verificables (ids de producto y referencias regulatorias), que es
        # justo donde un modelo mas pequeno inventa.
        #
        # Y es la que mas se nota. Medido sobre 'salsa de soya' (2026-08-24):
        #
        #   etapa   tokens salida   glm-5.2 a ~15 tok/s   flash a ~57 tok/s
        #     3          1.411           96,2 s                ~25 s
        #     4          2.404          160,2 s                ~42 s
        #     5          1.301           90,0 s                ~23 s
        #
        # Las tres salen a la vez, asi que la consulta dura la MAS LENTA. Con
        # la 4 en glm-5.2 esa era ella con 160 s; pasandola a flash el listero
        # baja a la etapa 3, y la consulta de ~177 s a ~113 s.
        #
        # De propina, flash cuesta ~50 veces menos: esa etapa 4 costo 0,099 US$
        # y con flash sale por 0,002 US$.
        #
        # OJO: el modelo entra en la clave de cache (ejecutor.py), asi que este
        # cambio invalida lo cacheado de la etapa 4 y cada insumo la paga una
        # vez mas. Es peaje unico, no un coste nuevo.
        self.modelo_por_etapa = {
            "1": "openai/deepseek-v4-flash",
            "2a": "openai/deepseek-v4-flash",
            "3": "openai/glm-5.2",
            "4": "openai/deepseek-v4-flash",
            "5": "openai/glm-5.2",
        }

    async def _pedir(self, etapa: str, modelo_respuesta, sistema: str, usuario: str):
        modelo = self.modelo_por_etapa.get(etapa, "openai/glm-5.2")
        inicio = time.perf_counter()
        try:
            respuesta = await self.client.chat.completions.create(
                model=modelo,
                response_model=modelo_respuesta,
                messages=[
                    {"role": "system", "content": sistema},
                    {"role": "user", "content": usuario},
                ],
                api_key=self.api_key,
                api_base=self.base_url,
                # Sin esto una llamada colgada se lleva la peticion por delante.
                # Ver la nota de TIEMPO_MAXIMO_S.
                timeout=TIEMPO_MAXIMO_S,
            )
        except Exception as e:
            _log.warning("Etapa %s con %s: %s tras %.1f s",
                         etapa, modelo, type(e).__name__, time.perf_counter() - inicio)
            raise
        # A nivel INFO porque es el dato que faltaba para saber por que una
        # consulta tarda: la duracion de la etapa se registra en
        # etapas_ejecucion, pero incluye los reintentos, asi que no distingue
        # 'una llamada lenta' de 'tres llamadas'.
        _log.info("Etapa %s con %s: %.1f s", etapa, modelo,
                  time.perf_counter() - inicio)
        return respuesta

    @retry(**_REINTENTOS)
    async def interpretar(self, texto: str) -> InsumoInterpretado:
        return await self._pedir(
            "1", InsumoInterpretado,
            "Eres un experto tecnólogo de alimentos. Tu objetivo es interpretar un "
            "insumo agrícola y devolver variaciones y traducciones precisas al inglés, "
            "listas para buscar en bases de datos como USDA FoodData Central y Open "
            "Food Facts. Identifica claramente la materia prima.\n\n"
            # El término alemán no es una traducción de diccionario: es la
            # palabra con la que la etiqueta del producto sale en el lineal, y
            # con ella se filtran después los resultados de la tienda. 'Beere'
            # (baya) encontraría media frutería; 'Heidelbeeren' encuentra
            # arándanos. Y se pide explícitamente poder dejarlo vacío porque un
            # término inventado no da cero resultados: da los equivocados, y
            # esos sí llegan al informe.
            "Para 'terminos_aleman', da el nombre con el que ese insumo aparece "
            "etiquetado en un supermercado alemán (REWE, Edeka, Alnatura), no una "
            "traducción literal ni una categoría amplia. Si no lo sabes con "
            "certeza, devuelve la lista vacía: es preferible a inventarlo.\n\n"
            # `insumo_normalizado` reduce a la materia prima, y eso es correcto
            # para el resto del informe. Pero la tabla de góndola busca con lo
            # que se le dé, y con 'quinua' devuelve grano a granel a quien
            # preguntó por barras. Medido: 'barras de quinua' salía como
            # 'quinua' y la tabla se llenaba de bolsas de 500 g.
            #
            # Se pide explícitamente que se deje vacío en el caso normal: si el
            # modelo rellena 'forma_producto' con 'quinua en grano' cuando se
            # preguntó 'quinua', la búsqueda se estrecha sin que nadie lo haya
            # pedido y desaparecen ofertas buenas.
            # 'forma_producto' NO se pide aquí, aunque esté en el esquema: lo
            # calcula `casos_de_uso/etapas/interpretar_insumo.py` comparando el
            # texto con el insumo normalizado, y sobrescribe lo que devuelva el
            # modelo.
            #
            # Se intentó pedirlo, primero con la regla en abstracto y luego con
            # seis ejemplos literales: 1 de 4 y 4 de 6, fallando en casos
            # distintos cada vez. Una comparación de cadenas responde siempre
            # igual y no cuesta tokens.
            "",
            texto)

    @retry(**_REINTENTOS)
    async def redactar_insight(self, productos: ResultadoBusqueda,
                               mapa: dict | None = None) -> InsightDeMercado:
        sistema = (
            "Eres un analista de desarrollo de productos del CITEagroindustrial. "
            "Basado en los resultados de búsqueda proporcionados, genera un Insight de "
            "Mercado para asesorar a mipymes y cooperativas.\n\n"
            "1. Define la 'cobertura' según la cantidad de resultados encontrados "
            "(baja/media/alta).\n"
            "2. Escribe un 'resumen' orientativo sobre cómo se usa este insumo en la "
            "industria hoy.\n"
            "3. Extrae los 'formatos_comunes' (polvo, extracto, mermelada, etc.).\n"
            "4. Rellena 'citas' con los IDs de los productos que sustentan lo anterior.\n"
            "   Usa SOLO ids que aparezcan en los datos que se te dan, tal cual. "
            "Un id que no esté ahí es un invento y se rechaza (P05).\n"
            "5. Escribe una 'nota_regulatoria' BREVE (2-3 frases) y ORIENTATIVA sobre "
            "qué tipo de requisitos suelen aplicar a esta categoría de alimento.\n\n"
            "REGLA CRÍTICA sobre 'nota_regulatoria': NO cites normas concretas, ni "
            "números de artículo, ni URLs. No dispones de corpus normativo en esta "
            "etapa y una cita inventada es peor que ninguna. Limítate a orientar y di "
            "explícitamente que se requiere verificación con la norma vigente.\n\n"
            "REGLA DE FORMATO: cuando enumeres con (1), (2), (3), cada elemento va en "
            "una línea separada.\n\n"
            "IMPORTANTE: responde un JSON válido con EXACTAMENTE estas claves: "
            "cobertura, resumen, formatos_comunes, citas, nota_regulatoria."
        )
        usuario = f"PRODUCTOS ENCONTRADOS:\n{productos.model_dump_json()}"
        if mapa:
            # El mapa de la etapa 2b (S4). Los paises y marcas son reales y
            # medidos, asi que son material de cita; los tres campos de
            # `sin_dato` van a proposito para que el modelo no los rellene.
            usuario += (
                "\n\nMAPA COMERCIAL (etapa 2b, datos reales del snapshot):\n"
                f"{json.dumps(mapa, ensure_ascii=False)}\n\n"
                "Sobre el mapa: 'paises' y 'marcas' son recuentos reales, "
                "puedes afirmarlos. Los campos de 'sin_dato' NO se conocen: "
                "no inventes presentaciones, precios ni canales de venta. "
                "'niveles_no_disponibles' son fuentes que no se consultaron."
            )
        return await self._pedir("3", InsightDeMercado, sistema, usuario)

    @retry(**_REINTENTOS)
    async def formular_hipotesis(self, productos: ResultadoBusqueda) -> HipotesisFormulacion:
        sistema = (
            "Eres un tecnólogo de alimentos del CITEagroindustrial haciendo ingeniería "
            "inversa de formulaciones. A partir de los productos comparables que se te "
            "dan, deduce cómo se elabora un producto equivalente.\n\n"
            "1. 'hipotesis': explica la formulación probable y en qué te basas.\n"
            "2. 'ingredientes_probables': lista deducida de los ingredientes que "
            "aparecen en los productos comparables.\n"
            "3. 'procesos_sugeridos': procesos industriales plausibles (secado, "
            "extracción, molienda, pasteurización...).\n"
            "4. 'citas': IDs de los productos concretos que sostienen la hipótesis.\n\n"
            "REGLA CRÍTICA: cada afirmación debe apoyarse en los productos aportados. "
            "Si los datos no bastan para deducir algo, dilo en la hipótesis en vez de "
            "rellenar con conocimiento general.\n\n"
            "IMPORTANTE: responde un JSON válido con EXACTAMENTE estas claves: "
            "hipotesis, ingredientes_probables, procesos_sugeridos, citas."
        )
        return await self._pedir(
            "4", HipotesisFormulacion, sistema,
            f"PRODUCTOS COMPARABLES:\n{productos.model_dump_json()}")

    @retry(**_REINTENTOS)
    async def verificar_regulacion(self, insumo: str, contexto: str) -> DossierRegulatorio:
        sistema = (
            "Eres un especialista en regulación alimentaria. Se te entrega el resultado "
            "de una búsqueda en un corpus normativo oficial (21 CFR de la FDA y normas "
            "de DIGESA Perú). Tu tarea es convertirlo en un dossier accionable.\n\n"
            "1. 'restricciones': requisitos o límites concretos que aplican al insumo.\n"
            "2. 'citas': una por cada norma REALMENTE presente en el contexto, con "
            "'texto' (el fragmento), 'fuente' (norma y organismo), 'url' (si el "
            "contexto la trae) y 'fecha' (si consta; null si no).\n"
            "3. 'sin_dato': true SOLO si el contexto no contiene ninguna norma "
            "aplicable.\n\n"
            "REGLA CRÍTICA: no inventes normas, números de sección ni URLs. Usa "
            "EXCLUSIVAMENTE lo que aparezca en el contexto. Si el contexto dice que no "
            "encontró normas aplicables, devuelve sin_dato=true, restricciones vacías y "
            "citas vacías. Un dossier con una cita inventada no vale nada: lo que se "
            "vende aquí es que la cita se pueda comprobar.\n\n"
            "IMPORTANTE: responde un JSON válido con EXACTAMENTE estas claves: "
            "restricciones, citas, sin_dato."
        )
        return await self._pedir(
            "5", DossierRegulatorio, sistema,
            f"INSUMO: {insumo}\n\nCONTEXTO NORMATIVO RECUPERADO:\n{contexto}")
