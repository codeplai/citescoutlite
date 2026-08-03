import json

import instructor
from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential

from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.insight_mercado import InsightDeMercado
from dominio.insumo import InsumoInterpretado
from dominio.resultado_busqueda import ResultadoBusqueda
from puertos.redactor_llm import RedactorLLM

_REINTENTOS = dict(stop=stop_after_attempt(3),
                   wait=wait_exponential(multiplier=1, min=2, max=10))


class RedactorGLM(RedactorLLM):
    def __init__(self, api_key: str, base_url: str | None = None):
        self.client = instructor.from_litellm(acompletion)
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
        self.modelo_por_etapa = {
            "1": "openai/deepseek-v4-flash",
            "2a": "openai/deepseek-v4-flash",
            "3": "openai/glm-5.2",
            "4": "openai/glm-5.2",
            "5": "openai/glm-5.2",
        }

    async def _pedir(self, etapa: str, modelo_respuesta, sistema: str, usuario: str):
        modelo = self.modelo_por_etapa.get(etapa, "openai/glm-5.2")
        return await self.client.chat.completions.create(
            model=modelo,
            response_model=modelo_respuesta,
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            api_key=self.api_key,
            api_base=self.base_url,
        )

    @retry(**_REINTENTOS)
    async def interpretar(self, texto: str) -> InsumoInterpretado:
        return await self._pedir(
            "1", InsumoInterpretado,
            "Eres un experto tecnólogo de alimentos. Tu objetivo es interpretar un "
            "insumo agrícola y devolver variaciones y traducciones precisas al inglés, "
            "listas para buscar en bases de datos como USDA FoodData Central y Open "
            "Food Facts. Identifica claramente la materia prima.",
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
