# TIER 6 COMPLETADO - Corpus regulatorio

**Fecha:** 2026-08-02
**Status:** ✅ COMPLETADO — 4/4 criterios de DoD

---

## Resultado

| Métrica | Gate | Obtenido |
|---|---|---|
| Documentos eCFR | ≥ 5 | **702 pasajes** (336 secciones) |
| Palabras DIGESA | ≥ 2000 | **6.602** |
| Tabla `regulatorio` en LanceDB | con embeddings | **734 filas**, bge-m3 1024-dim, cosine |
| URLs navegables | sí | eCFR y DIGESA, verificadas en test |

Corpus total: **105.935 palabras** de fuentes oficiales.

---

## T6.1 · eCFR (FDA)

**La URL del plan devuelve 404.** `PLAN-TIERS-S2.md` §T6.1 propone
`/api/renderer/versions/title-21/part-182/full.json`, que no existe. El API real
es el `versioner`, que entrega XML:

```
https://www.ecfr.gov/api/versioner/v1/full/{fecha}/title-21.xml?part={parte}
```

La fecha se resuelve contra `/api/versioner/v1/titles.json`, así que el corpus
queda fechado con la **vigencia oficial (2026-07-29)**, no con la fecha de
descarga.

**Partes descargadas** — el plan solo pedía la 182:

| Parte | Contenido | Secciones |
|---|---|---|
| 182 | Substances Generally Recognized As Safe | 85 |
| 184 | Direct Food Substances Affirmed As GRAS | 215 |
| 145 | Canned Fruits | 13 |
| 146 | Canned Fruit Juices | 20 |
| 150 | Fruit Butters, Jellies, Preserves and Jams | 3 |

Se añadieron 145/146/150 porque 182/184 son catálogos de aditivos químicos: no
contienen nada sobre frutas, y consultarlos por los insumos piloto daba
similitud **negativa**.

El parser aplana párrafos **y tablas**: en la Part 182 los pares nombre común /
nombre botánico son la parte sustantiva, y sin ellos las secciones quedaban
reducidas a su frase introductoria.

---

## T6.2 · DIGESA (Perú)

De 10 PDFs oficiales, **5 tenían capa de texto y 5 eran escaneos**. Los escaneos
se descartan y quedan registrados en `digesa_normas_reporte.json`. **No se hace
OCR y no se inventa contenido.**

| Documento | Resultado |
|---|---|
| RM 865-2020-MINSA | 9 pág. → 9 pasajes (1.915 palabras) |
| RM 854-2020-MINSA | 20 pág. → 5 pasajes (1.036 palabras) |
| Guía didáctica de inocuidad | 32 pág. → 9 pasajes (2.085 palabras) |
| Artículos sin autorización sanitaria | 17 pág. → 7 pasajes (1.329 palabras) |
| Decálogo de inocuidad | 1 pág. → 2 pasajes (237 palabras) |
| RD 043-2017, DS 010-2014-SA, RD 192-2017, Directiva 87-2020, Criterios técnicos | escaneados → descartados |

**Problema resuelto: los separados de El Peruano vienen a dos columnas.**
Extraer la página entera intercala ambas columnas línea por línea y produce
texto incoherente ("…el Sector Salud está | Designan Director General de la
Dirección | conformado por el Ministerio…"), que habría generado embeddings
basura.

La primera versión del detector buscaba un canal vacío alrededor de `width/2` y
fallaba: la cabecera "NORMAS LEGALES" cruza la página entera y llena la banda
central. El detector definitivo analiza solo el cuerpo (excluye el 10% superior
y el 7% inferior) y **localiza el canal real**, que no está centrado — aparece
entre x=235 y x=244 según la página.

---

## T6.3 · Indexación y RAG

Tabla `regulatorio` (734 filas, bge-m3, cosine, índice IVF-PQ). Sustituye a la
tabla `normativas` de S1 (4 filas de demo, búsqueda FTS).

`adaptadores/verificador_rag.py` pasa a búsqueda vectorial, con **fallback a
`normativas`** si el ETL de TIER 6 no se ha corrido.

También se extrajo `adaptadores/modelo_embeddings.py`: búsqueda y RAG comparten
ahora un único bge-m3. Sin eso serían ~2,3 GB duplicados y ~8 s extra de
arranque.

---

## El fallo grave que se encontró y corrigió

Con la implementación directa del plan, **el RAG citaba normas sin ninguna
relación con el insumo**:

| Consulta | Norma recuperada | Similitud |
|---|---|---|
| mango | **Manganese sulfate** | +0.281 |
| quinua | **Urea** | +0.191 |
| palta | **Canned apricots** | +0.14 |
| espárrago | **Canned applesauce** | +0.16 |
| arándano | **Bromelain** (de la piña) | −0.086 |

Esto es exactamente el dato inventado que el MVP prohíbe: el redactor habría
recibido la regulación del sulfato de manganeso como contexto normativo del
mango.

Tres correcciones, en este orden:

1. **Troceo de las secciones del CFR** (`etl/troceo.py`). Una sección de 1.000
   palabras no puede casar con una consulta de dos: la señal se diluye y la
   similitud sale negativa aunque el documento mencione el término. Troceado,
   "arándano blueberry" pasó de recuperar *Bromelain* a recuperar *Canned
   berries*.

2. **Consulta contextualizada.** El nombre pelado del insumo es mala consulta.
   Enmarcarla ("normativa sanitaria y aditivos alimentarios aplicables a
   productos elaborados con …") subió *Canned berries* de −0.05 a **+0.25**.
   Pero sube **todas** las similitudes, incluidas las falsas — por sí sola
   empeora el problema, y por eso hace falta la tercera.

3. **Anclaje léxico para el eCFR.** Un umbral de similitud no basta: los falsos
   positivos puntuaban por encima de cualquier umbral razonable. Cada sección
   del Title 21 trata de una sustancia concreta (Parts 182/184) o de un
   commodity concreto (145 "Canned cherries", 146 "Orange juice"); **ninguna es
   una regla genérica**. Si el texto no nombra el insumo, no le aplica.
   Las normas de DIGESA sí son generales (inocuidad, registro sanitario,
   higiene) y aplican a cualquier alimento del mercado peruano, así que no
   exigen anclaje.

**Además, se consulta cada corpus por separado.** En un ranking conjunto, con
702 pasajes eCFR contra 32 de DIGESA, la primera norma peruana aparecía en la
**posición 396** — nunca habría entrado en un top-k global, pese a ser la que
realmente aplica en Perú.

### Comportamiento resultante

```
arándano  -> 21 CFR 150.160 (mermeladas; el texto nombra blueberries) + DIGESA
mango     -> "Sin norma del 21 CFR que nombre 'mango'" + DIGESA general
quinua    -> idem
espárrago -> idem
```

Para 4 de los 5 insumos piloto la respuesta correcta **es** "no hay norma CFR
aplicable": el corpus tiene **cero ocurrencias** de mango, avocado, asparagus y
quinoa. El CFR estadounidense fija estándares de identidad para commodities
americanos (manzana, naranja, piña, cereza), no para cultivos de exportación
peruanos. Que el sistema lo diga explícitamente, en vez de rellenar con la norma
más cercana, es el comportamiento correcto.

---

## Verificación

`test/test_regulatorio.py` — **5/5 PASSED** (suite completa: **11/11**)

| Test | Verifica |
|---|---|
| `test_ecfr_minimo_5_documentos` | ≥5 docs, cita `21 CFR X.Y`, URL de ecfr.gov, fecha de vigencia |
| `test_digesa_minimo_2000_palabras` | ≥2000 palabras, URLs de digesa.minsa.gob.pe |
| `test_tabla_regulatorio_con_embeddings` | Tabla existe, 1024-dim, `fuente_url` no vacía |
| `test_no_cita_normas_de_sustancias_no_relacionadas` | Regresión: mango↛manganese, quinua↛urea, palta↛apricot |
| `test_ecfr_solo_si_nombra_el_insumo` | Arándano sí cita CFR; mango lo declara ausente |

```bash
python -m etl.procesar_ecfr
python -m etl.procesar_digesa
python -m etl.procesar_regulatorio
python -m pytest test/test_regulatorio.py -v
```

---

## DoD de TIER 6

- [x] `datasets/2026-07/ecfr_aditivos.json` ≥5 documentos (702)
- [x] `datasets/2026-07/digesa_normas.json` ≥2000 palabras (6.602)
- [x] Tabla `regulatorio` en LanceDB con embeddings (734 filas, 1024-dim)
- [x] URLs navegables a fuentes oficiales

---

## Notas para TIER 7

1. **Dos defectos cosméticos en la extracción DIGESA**, no corregidos por riesgo
   de dañar texto legítimo:
   - `DECALOGO_ALIMENTOS` tiene glifos duplicados por falsa negrita
     ("AALLIIMMEENNTTAACCIIÓÓNN").
   - Un pasaje de `RM_865` arranca con la cola de una resolución de PRODUCE
     ("Regístrese… Ministro de la Producción") por caer en un límite de troceo.
2. **5 PDFs de DIGESA quedan fuera por ser escaneos.** Si TIER 7 necesita más
   corpus peruano, la vía es OCR (tesseract), no más scraping: el sitio
   devuelve 403 si se le piden páginas muy seguidas.
3. **`pdfplumber`** se instaló en `venv/` y se añadió a `pyproject.toml`
   (`>=0.11.0`); es la única dependencia nueva de TIER 6.
4. El corpus **no cubre los insumos piloto en el CFR**. Si el negocio necesita
   normativa específica de arándano/palta/espárrago/mango/quinua, la fuente son
   las NTS peruanas y el Codex Alimentarius, no el Title 21.
