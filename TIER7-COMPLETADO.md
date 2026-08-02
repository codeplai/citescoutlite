# TIER 7 COMPLETADO - Cierre y auditoría

**Fecha:** 2026-08-02
**Status:** ✅ COMPLETADO — 5/5 criterios de DoD · **Semana 2 cerrada**

---

## Resultado

| Gate | Obtenido |
|---|---|
| Golden set | **5/5** |
| Manifest con SHA256 | **6 fuentes**, verificadas por test |
| E2E workflow | **7/7 PASSED** |
| URLs navegables | 29.054 productos, **0 sin url** |
| README reproducible | reescrito con el pipeline real |

Suite completa: **18/18**.

---

## USDA: se cerró la deuda de TIER 2

TIER 2 se ejecutó sin `USDA_API_KEY` y `usda_productos.json` quedó como un
marcador `{"estado": "SALTADO"}`. Con la clave ya en `.env`, se completó.

`etl/cargar_usda.py` estaba **inservible para cerrar S2** y se reescribió:

| Problema | Corrección |
|---|---|
| Ante cualquier fallo de la API escribía un producto **inventado** (`USDA:123456 — Mango Peel Functional Drink`) con URL que no resuelve | Un fallo devuelve lista vacía y queda registrado. Sin clave no descarga nada y **no genera respaldo** |
| No filtraba `dataType`, admitía cualquiera | Filtra a `Branded`, como pide el plan |
| No traía `fecha_dato` | `modifiedDate`/`publicationDate` → Unix. Si no viene, `None`; nunca la fecha de hoy |
| Solo consultaba `"mango peel"` | Los 5 insumos piloto en inglés |
| Escribía en `data/` | Escribe en `datasets/2026-07/` |

**Resultado:** 990 productos únicos, **990/990 con fecha real**.

### Impacto en el snapshot

```
OFF          28.236
USDA            990  ->  818 tras deduplicar (172 duplicados)
                         ────────
productos_merged.json    29.054
```

El dedup de `merge_datasets.py` era O(n×m) — 28.236 × 990 = **28 millones de
comparaciones** en bucle anidado. Se indexó por `(marca, nombre[:20])`
conservando las mismas reglas: el merge pasó a **0,8 s**.

### Indexación incremental

Reindexar los 29.054 productos habría costado las horas de cómputo de TIER 4.
Se añadió `etl/indexar_incremental.py`, que compara por `id` y embebe solo lo
que falta: **818 productos en 10,2 s**, y reconstruye el índice IVF-PQ.

USDA queda plenamente recuperable: el mejor producto USDA para *blueberry*
puntúa 0,456 y ocupa la **posición 11** del ranking global. En consultas con
varios sinónimos concatenados OFF domina el top-30, lo que es esperable con
28.236 filas frente a 818, no un fallo de índice.

---

## El bug que bloqueó la indexación

`tabla.add()` fallaba con un error sin relación aparente con la causa:

```
ImportError: cannot import name 'Dataset' from 'datasets' (unknown location)
```

**Cadena real:** `sentence_transformers` hace un `import datasets` protegido
para soportar HuggingFace Datasets. Como este repo tiene una carpeta
`datasets/` en la raíz y el directorio de trabajo está en `sys.path`, Python la
resuelve como *namespace package* vacío. El import "funciona",
sentence-transformers captura el `ImportError` posterior y sigue — **pero deja
la entrada envenenada en `sys.modules`**. Después LanceDB comprueba
`if "datasets" in sys.modules` para registrar sus conversores opcionales, da por
hecho que es HuggingFace, y hace `from datasets import Dataset`, que revienta
sin captura.

`adaptadores/modelo_embeddings.limpiar_datasets_fantasma()` elimina esa entrada.
El primer intento de arreglo —limpiar al cargar el modelo— **no funcionó**:
`encode()` vuelve a disparar el import. Hay que limpiar **inmediatamente antes
de cada escritura en LanceDB**, que es donde está la llamada.

---

## T7.1 · Golden set 5/5

`evals/set_dorado.yaml` tenía 2 casos y **ningún código lo leía**. Se amplió a
los 5 insumos piloto y se escribió `evals/runner_s2.py`.

**Se evalúa sin LLM.** `interpretar_insumo` y `generar_insight` dependen de una
API externa que haría el set caro, lento y no reproducible; los sinónimos se
fijan en el YAML —son los que produce esa etapa— y se ejercita el resto del
flujo, incluida la derivación de `n_directos` y la regla
`n_directos <= 2 => informe_parcial` de `evaluar_insumo.py:26`.

```
[PASS] S2-arandano    Arándano                30 resultados, 30 directos (OFF 22 + USDA 8)
[PASS] S2-palta       Palta                   30 resultados, 30 directos
[PASS] S2-esparrago   Descarte de espárrago   30 resultados, 30 directos
[PASS] S2-mango       Cáscara de mango        30 resultados, 30 directos (OFF 29 + USDA 1)
[PASS] S2-quinua      Quinua                  30 resultados, 30 directos
Resultado: 5/5 casos pasan
```

Los mínimos se fijaron en 3 (no en 30) para que el set detecte una regresión
real de cobertura sin romperse ante variaciones normales del ranking.

---

## T7.2 · Manifest con SHA256

`etl/finalizar_manifest.py` calcula SHA256 y tamaño de las 6 fuentes **y
regenera `fuentes`/`estadisticas` leyendo los archivos reales**.

Esto salda la deuda arrastrada desde TIER 5: el manifest seguía declarando
**89 productos y `espárrago: 0`** mientras el índice tenía 29.054. Un manifest
desincronizado hace que cualquier auditoría se contradiga con los datos.

```
total_productos: 29.054   {OFF: 28.236, USDA: 818}
cobertura: arándano 5.877 · palta 3.218 · espárrago 902 · mango 11.124 · quinua 9.127
productos sin fecha_dato: 0
productos sin url: 0
regulatorio: eCFR 702 docs / 99.333 palabras · DIGESA 32 docs / 6.602 palabras
```

---

## T7.3 · E2E workflow

`test/test_e2e_s2.py` — **7/7 PASSED**

| Test | Verifica |
|---|---|
| `test_e2e_datos_en_disco` | Archivos del snapshot presentes y no vacíos |
| `test_e2e_indice_vectorial` | Filas indexadas **== filas del JSON**; 1024-dim; OFF y USDA presentes |
| `test_e2e_busqueda_los_5_insumos` | Los 5 devuelven resultados con id, url y fecha reales |
| `test_e2e_corpus_regulatorio` | Tabla `regulatorio` con 734 pasajes |
| `test_e2e_manifest_sha256_coincide` | **Recalcula** los SHA256 y exige que coincidan |
| `test_e2e_estadisticas_coinciden_con_los_datos` | Regresión del manifest de 89 productos |
| `test_e2e_golden_set_5_de_5` | Ejecuta el runner de T7.1 |

El test de SHA256 los recalcula en vez de comprobar que el campo exista: un
manifest con hashes obsoletos es peor que no tenerlos, porque promete una
reproducibilidad que no cumple.

---

## Latencia tras añadir USDA

Reverificado el gate P03 con 29.054 filas (antes 28.236):

```
GPU:  media 48,4ms | p50 42,9ms | p95 66,3ms  (antes 45,2ms)
CPU:  media 150,3ms | p50 151,5ms | p95 176,2ms  (antes 173,0ms)
```

**P03 sigue verde con 30x de margen** en el peor caso (CPU).

---

## DoD de TIER 7

- [x] Golden set 5/5
- [x] `manifest.json` con SHA256 de todos los archivos
- [x] E2E test pasa (7/7)
- [x] URLs navegables verificadas (0 productos sin url, formato validado en test)
- [x] README con procedimiento reproducible completo

---

## Estado final de Semana 2

| TIER | Estado | Evidencia |
|---|---|---|
| 1 · Preparación | ✅ | Decisiones documentadas en el manifest |
| 2 · Descargas | ✅ | 28.236 OFF + 990 USDA |
| 3 · Limpieza | ✅ | 29.054 mergeados, 172 duplicados |
| 4 · Embeddings | ✅ | bge-m3 1024-dim, 29.054 filas |
| 5 · Búsqueda | ✅ | **P03: p95 66ms GPU / 176ms CPU** |
| 6 · Corpus regulatorio | ✅ | 734 pasajes eCFR + DIGESA |
| 7 · Cierre | ✅ | Golden set 5/5, SHA256, E2E 7/7 |

---

## Deuda que queda abierta

1. **`usa_insumo_directo` sigue sin derivarse en el snapshot** (`False` en las
   29.054 filas). El dominio lo recalcula en cada búsqueda contra los sinónimos,
   así que el pipeline es correcto, pero el JSON no es fuente de verdad para ese
   campo.
2. **Dos defectos cosméticos en la extracción DIGESA** (glifos duplicados en el
   Decálogo; un pasaje que arranca con la cola de una resolución de PRODUCE).
   No se tocaron por riesgo de dañar texto legítimo.
3. **5 PDFs de DIGESA fuera del corpus** por ser escaneos. La vía es OCR, no más
   scraping: el sitio devuelve 403 si se le piden páginas muy seguidas.
4. **El eCFR no cubre los insumos piloto.** Para normativa específica de
   arándano/palta/espárrago/mango/quinua la fuente son las NTS peruanas y el
   Codex, no el Title 21.
5. **La tabla `normativas` de S1 sigue en `vectores/`** con 4 filas de demo.
   `verificador_rag` solo cae a ella si `regulatorio` no existe; puede
   eliminarse en S3.
6. **`venv/` no tiene `fastapi`**: es el entorno de embeddings/búsqueda. La API
   corre con `uv`. El E2E cubre el pipeline de datos, no los endpoints HTTP.
