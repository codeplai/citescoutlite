"""
RAG normativo sobre el corpus regulatorio.

TIER 6 (S2): pasa de FTS sobre `normativas` (4 filas de demo) a búsqueda
vectorial bge-m3 sobre `regulatorio` (eCFR + DIGESA, fuentes oficiales con URL
navegable). Si la tabla `regulatorio` no existe, cae al comportamiento anterior
para no romper entornos que aún no han corrido el ETL de TIER 6.
"""
import lancedb

from adaptadores.modelo_embeddings import get_modelo
from puertos.verificador_regulatorio import VerificadorRegulatorio

TABLA = "regulatorio"
TABLA_LEGACY = "normativas"

# Umbral de similitud coseno por debajo del cual un resultado se descarta.
# La búsqueda vectorial siempre devuelve los k vecinos más cercanos, por lejos
# que estén; sin piso, una consulta sin respuesta en el corpus devuelve ruido.
SIMILITUD_MINIMA = 0.10

# Piso más bajo para DIGESA: son 32 pasajes contra 702 del eCFR, redactados en
# lenguaje administrativo que puntúa peor frente a una consulta por insumo.
SIMILITUD_MINIMA_DIGESA = 0.04

# El eCFR exige ANCLAJE LÉXICO: solo se cita si el texto nombra el insumo.
#
# El umbral por sí solo no basta. Al contextualizar la consulta suben TODAS las
# similitudes, incluidas las falsas; medido en este corpus, "mango" recupera
# **Manganese sulfate** (+0.28) y "quinua" recupera **Urea** (+0.19), por encima
# de cualquier umbral razonable y completamente equivocado.
#
# La razón de fondo es que cada sección del Title 21 trata de una sustancia
# concreta (Parts 182/184) o de un commodity concreto (Part 145 "Canned
# cherries", Part 146 "Orange juice"). Ninguna es una regla genérica: si no
# nombra el insumo, no le aplica. Sin anclaje, "palta" acababa citando
# **Canned apricots** y "espárrago" **Canned applesauce**.
#
# Las normas de DIGESA son distintas: inocuidad, registro sanitario e higiene
# aplican a cualquier alimento comercializado en Perú, nombre o no al insumo.
FUENTE_EXIGE_ANCLAJE = "eCFR"


class VerificadorRAG(VerificadorRegulatorio):
    def __init__(self, db_path: str = "vectores", offline: bool = False,
                 k: int = 3, similitud_minima: float = SIMILITUD_MINIMA,
                 similitud_minima_digesa: float = SIMILITUD_MINIMA_DIGESA):
        self.db_path = db_path
        self.offline = offline
        self.k = k
        self.similitud_minima = similitud_minima
        self.similitud_minima_digesa = similitud_minima_digesa
        self._tabla = None
        self._legacy = None

    def _abrir(self):
        """Abre la tabla una vez por instancia y decide si hay corpus TIER 6."""
        if self._tabla is None and self._legacy is None:
            db = lancedb.connect(self.db_path)
            listado = db.list_tables()
            nombres = getattr(listado, "tables", listado)
            if TABLA in nombres:
                self._tabla = db.open_table(TABLA)
            elif TABLA_LEGACY in nombres:
                self._legacy = db.open_table(TABLA_LEGACY)
        return self._tabla, self._legacy

    def verificar(self, insumo_en: str, insumo_es: str) -> str:
        if self.offline:
            return ("RAG Normativo: [MODO OFFLINE] Base documental no disponible. "
                    "Sin datos de normativas locales.")
        try:
            tabla, legacy = self._abrir()

            if tabla is not None:
                return self._buscar_vectorial(tabla, insumo_en, insumo_es)
            if legacy is not None:
                return self._buscar_fts(legacy, insumo_es)

            return "RAG Normativo: Base documental no inicializada."

        except Exception as e:
            print(f"Error en RAG normativo: {e}")
            return f"RAG Normativo: Error de búsqueda ({e})."

    @staticmethod
    def _anclado_lexicamente(fila: dict, terminos: list[str]) -> bool:
        texto = f"{fila.get('titulo', '')} {fila.get('texto', '')}".lower()
        return any(t in texto for t in terminos)

    def _admisible(self, fila: dict, terminos: list[str]) -> bool:
        """El eCFR solo aplica si nombra el insumo; DIGESA aplica por ser
        normativa sanitaria general del mercado peruano."""
        if fila.get("tipo") != FUENTE_EXIGE_ANCLAJE:
            return True
        return self._anclado_lexicamente(fila, terminos)

    def _buscar_en(self, tabla, vector, tipo: str, limite: int) -> list[dict]:
        return (
            tabla.search(vector, vector_column_name="embedding")
            .metric("cosine")
            .where(f"tipo = '{tipo}'", prefilter=True)
            .select(["id", "titulo", "texto", "cita", "fuente", "fuente_url", "tipo"])
            .limit(limite)
            .to_list()
        )

    def _buscar_vectorial(self, tabla, insumo_en: str, insumo_es: str) -> str:
        # El nombre pelado del insumo es mala consulta: es corto y no describe
        # lo que se busca. Contextualizarlo con el marco regulatorio sube la
        # similitud de las normas correctas (arándano -> "Canned berries" pasa
        # de -0.05 a +0.25). El corpus es bilingüe, así que van ambos términos.
        consulta = (f"normativa sanitaria y aditivos alimentarios aplicables a "
                    f"productos elaborados con {insumo_es} ({insumo_en})")
        vector = get_modelo().encode(consulta).tolist()
        terminos = [t.lower() for t in (insumo_es, insumo_en) if t]

        # Se consulta cada corpus por separado en vez de un top-k global. El
        # eCFR tiene 702 pasajes contra 32 de DIGESA, así que en un ranking
        # conjunto la primera norma peruana aparece recién en la posición ~396:
        # quedaría siempre fuera, pese a ser la que de verdad aplica en Perú.
        ecfr = [r for r in self._buscar_en(tabla, vector, "eCFR", 40)
                if (1 - r["_distance"]) >= self.similitud_minima
                and self._anclado_lexicamente(r, terminos)][:self.k]

        # DIGESA no exige anclaje ni el mismo piso: son reglas de inocuidad,
        # registro sanitario e higiene que rigen para cualquier alimento
        # comercializado en Perú, nombren o no al insumo.
        digesa = [r for r in self._buscar_en(tabla, vector, "DIGESA", 10)
                  if (1 - r["_distance"]) >= self.similitud_minima_digesa][:2]

        relevantes = ecfr + digesa

        if not relevantes:
            return (f"RAG Normativo: El corpus (eCFR + DIGESA) no contiene normas "
                    f"aplicables a '{insumo_es}'. Ninguna sección del 21 CFR "
                    f"nombra el insumo y ninguna norma DIGESA supera el umbral de "
                    f"similitud. No se aporta contexto regulatorio.")

        lineas = []
        if not ecfr:
            lineas.append(f"  (Sin norma del 21 CFR que nombre '{insumo_es}'; "
                          f"solo aplica normativa sanitaria general peruana.)")

        for r in relevantes:
            cita = r.get("cita") or r.get("titulo", "")
            texto = (r.get("texto") or "").strip()
            if len(texto) > 700:
                texto = texto[:700].rsplit(" ", 1)[0] + "..."
            lineas.append(
                f"- **{r.get('fuente', '')}** ({cita}, similitud "
                f"{1 - r['_distance']:.2f}): {texto}\n"
                f"  Fuente: {r.get('fuente_url', '')}"
            )

        return "RAG Normativo (eCFR/DIGESA):\n" + "\n".join(lineas)

    def _buscar_fts(self, tabla, insumo_es: str) -> str:
        """Camino heredado de S1: FTS sobre la tabla `normativas` de demo."""
        resultados = tabla.search(insumo_es, query_type="fts").limit(2).to_list()
        if not resultados:
            return (f"RAG Normativo: No se encontraron normas locales "
                    f"específicas para '{insumo_es}'.")

        normas = [
            f"- {r.get('fuente', 'Desconocida')} ({r.get('titulo', '')}): "
            f"{r.get('texto', '')}"
            for r in resultados
        ]
        return "RAG Normativo (Codex/DIGESA/EFSA):\n" + "\n".join(normas)
