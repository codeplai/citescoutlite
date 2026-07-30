import instructor
from litellm import acompletion
from puertos.redactor_llm import RedactorLLM
from dominio.insumo import InsumoInterpretado
from dominio.insight_mercado import InsightDeMercado
from dominio.resultado_busqueda import ResultadoBusqueda
from tenacity import retry, stop_after_attempt, wait_exponential

class RedactorGLM(RedactorLLM):
    def __init__(self, api_key: str, base_url: str | None = None):
        self.client = instructor.from_litellm(acompletion)
        self.api_key = api_key
        self.base_url = base_url
        self.modelo_por_etapa = {
            1: "openai/deepseek-v4-flash",
            2: "openai/deepseek-v4-flash",
            3: "openai/glm-5.0",
            4: "openai/glm-5.2",
            5: "openai/glm-5.2",
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def interpretar(self, texto: str) -> InsumoInterpretado:
        modelo = self.modelo_por_etapa.get(1, "openai/glm-5.2")
        resp = await self.client.chat.completions.create(
            model=modelo,
            response_model=InsumoInterpretado,
            messages=[
                {"role": "system", "content": "Eres un experto tecnólogo de alimentos. Tu objetivo es interpretar un insumo agrícola y devolver variaciones y traducciones precisas al inglés, listas para buscar en bases de datos como USDA FoodData Central y Open Food Facts. Identifica claramente la materia prima."},
                {"role": "user", "content": texto},
            ],
            api_key=self.api_key,
            api_base=self.base_url
        )
        return resp

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def redactar_insight(self, productos: ResultadoBusqueda, contexto_regulatorio: str = "") -> InsightDeMercado:
        modelo = self.modelo_por_etapa.get(3, "openai/glm-5.2")
        productos_str = productos.model_dump_json()

        system_prompt = (
            "Eres un analista de desarrollo de productos del CITEagroindustrial. Basado en los resultados de búsqueda proporcionados, genera un Insight de Mercado detallado para asesorar a mipymes y cooperativas.\n\n"
            "1. Define la 'cobertura' según la cantidad de resultados encontrados (baja/media/alta).\n"
            "2. Escribe un 'resumen' orientativo sobre cómo se usa este insumo en la industria hoy.\n"
            "3. Extrae los 'formatos_comunes' (polvo, extracto, mermelada, etc.).\n"
            "4. Formula una 'hipotesis_formulacion' detallada, haciendo ingeniería inversa de ingredientes si es posible.\n"
            "5. Añade una 'verificacion_regulatoria' orientativa, indicando requisitos o restricciones sanitarias. BASA tu respuesta en el 'Contexto Regulatorio Extraído' que se te proporcione y MENCIONA EXPLÍCITAMENTE LAS FUENTES LOCALIZADAS.\n"
            "6. REGLA DE FORMATO: Cuando enumeres elementos con (1), (2), (3) o 1), 2), 3), cada uno DEBE ir en una línea separada (usa saltos de línea).\n"
            "7. REGLA DE FORMATO: En la 'verificacion_regulatoria', pon el nombre de la fuente/regulación en negrita antes de los dos puntos (ej: **openFDA (EE.UU.)**:), e incluye una URL de referencia para cada regulación.\n\n"
            "IMPORTANTE: Tu respuesta DEBE ser un JSON válido que contenga EXACTAMENTE las siguientes claves: cobertura, resumen, formatos_comunes, hipotesis_formulacion, verificacion_regulatoria, citas."
        )
        
        user_content = f"PRODUCTOS ENCONTRADOS:\n{productos_str}"
        if contexto_regulatorio:
            user_content += f"\n\nCONTEXTO REGULATORIO EXTRAIDO DESDE BASES OFICIALES (Úsalo para la verificacion_regulatoria):\n{contexto_regulatorio}"

        resp = await self.client.chat.completions.create(
            model=modelo,
            response_model=InsightDeMercado,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            api_key=self.api_key,
            api_base=self.base_url
        )
        return resp
