# Dataset Semana 2: 5 Insumos Piloto

**Snapshot:** 2026-07 · **Taxonomía:** 0.1
**Cerrado:** 2026-08-02 (TIER 7)

| | |
|---|---|
| Productos | **29.460** (28.236 OFF + 818 USDA + 406 terminados) |
| Embeddings | BAAI/bge-m3, 1024-dim, LanceDB métrica cosine |
| Corpus regulatorio | **734 pasajes** (702 eCFR + 32 DIGESA) |
| Sin `fecha_dato` | 0 |
| Sin `url` | 0 |

---

## Procedimiento de reproducibilidad

Los comandos se ejecutan desde la raíz del repo con el intérprete de `venv/`
(el entorno que tiene `lancedb`, `sentence-transformers` y `torch`):

```bash
./venv/Scripts/python.exe -m <modulo>     # Windows
```

### 1. Descarga OFF

**Estrategia: OPCIÓN B (export offline).** Decidida en TIER 1 porque la API
live devolvía 503.

```bash
python -m etl.cargar_off_bulk
```

Descarga el export masivo, lo filtra a los 5 insumos piloto y escribe
`off_productos.json`. **Esperado:** 28.236 productos.

### 2. Descarga USDA

Requiere `USDA_API_KEY` en `.env` (se obtiene gratis en
<https://fdc.nal.usda.gov/api-key-signup>).

```bash
python -m etl.cargar_usda
```

Descarga `dataType=Branded` para los 5 insumos en inglés. **Esperado:** 990
productos únicos, todos con `fecha_dato` real.

Sin clave el módulo **no descarga nada y no genera datos de respaldo**: se
prefiere un dataset vacío a uno inventado.

### 2b. Productos terminados (S8, 2026-08-24)

```bash
./venv/Scripts/python.exe -m etl.cargar_off_terminados --dry-run   # solo cuenta
./venv/Scripts/python.exe -m etl.cargar_off_terminados
```

Trae la FORMA DE PRODUCTO de 20 insumos en Perú, Suiza y Alemania: néctar,
mermelada, muesli, chips. El snapshot original se filtró a cinco insumos, así
que la góndola encontraba materia prima suelta pero no lo que se compra en una
tienda. **Esperado:** 482 productos de 1.434 códigos.

No usa el export masivo ni `cgi/search.pl` (sigue en 503, decisión D-A): va por
search-a-licious para los códigos y por la API v2 para cada ficha, porque el
índice de búsqueda no guarda ingredientes ni marca.

Se reanuda solo. El avance queda en `off_terminados_codigos.json` y en
`off_terminados_fichas.jsonl`, que se escribe línea a línea: relanzar el mismo
comando continúa donde se quedó. Hace falta porque OFF limita a ~16 fichas por
minuto efectivas y la corrida entera son ~90 min. Para rehacer el
descubrimiento, borrar el JSON de códigos.

Rendimiento de la fuente, medido: **765 de 1.434 códigos (53 %) vienen sin
lista de ingredientes** y se descartan —el catálogo peruano de OFF está muy
incompleto—, y 175 más no nombran ningún insumo. Aceptados por mercado:
Alemania 270, Suiza 154, Perú 70.

### 3. Merge y deduplicación

```bash
python -m etl.merge_datasets
```

Deduplica por marca + primeros 20 caracteres del nombre, y los terminados
además por `id_fuente`: salen de la misma fuente que `off_productos.json`, de
modo que 71 de ellos ya estaban en el snapshot con su código de barras idéntico.
**Esperado:** 29.460 productos (172 duplicados OFF/USDA, 406 terminados nuevos).

### 4. Embeddings

Primera vez (genera los ~29.000 embeddings, 15-30 min en GPU):

```bash
python -m etl.tier4_gpu
```

Después de añadir productos nuevos — indexa **solo los que faltan**:

```bash
python -m etl.indexar_incremental --dry-run   # muestra cuántos faltan
python -m etl.indexar_incremental
```

**Esperado:** `vectores/productos.lance` con 29.460 filas de 1024 dimensiones.

### 5. Corpus regulatorio

```bash
python -m etl.procesar_ecfr          # eCFR Title 21: partes 182/184/145/146/150
python -m etl.procesar_digesa        # PDFs de DIGESA (descarta escaneos)
python -m etl.procesar_regulatorio   # embeddings -> tabla `regulatorio`
```

**Esperado:** 702 pasajes eCFR (99.333 palabras) + 32 pasajes DIGESA (6.602
palabras).

### 6. Cierre del manifest

```bash
python -m etl.finalizar_manifest
```

Calcula SHA256 y tamaño de cada fuente y **regenera las estadísticas leyendo
los archivos reales**, para que el manifest no se desincronice del snapshot.

---

## Validación

```bash
python -m evals.runner_s2      # golden set: 5/5
python -m pytest test/ -v      # 18 tests
```

| Comprobación | Gate | Estado |
|---|---|---|
| Productos indexados | ≥ 250 | 29.460 ✓ |
| Dimensiones | 1024 | ✓ |
| p95 de búsqueda | < 2 s | 45 ms GPU / 173 ms CPU ✓ |
| Documentos eCFR | ≥ 5 | 702 ✓ |
| Palabras DIGESA | ≥ 2000 | 6.602 ✓ |
| Golden set | 5/5 | ✓ |
| SHA256 del manifest | coincide | ✓ |

---

## Verificar integridad del snapshot

```bash
sha256sum productos_merged.json   # debe coincidir con fuentes[].sha256 del manifest
```

`test_e2e_s2.py::test_e2e_manifest_sha256_coincide` lo recalcula automáticamente.

---

## Insumos piloto y cobertura

| Insumo | Inglés | Productos |
|---|---|---|
| Arándano | blueberry | 5.877 |
| Palta | avocado | 3.218 |
| Espárrago | asparagus | 902 |
| Mango | mango | 11.124 |
| Quinua | quinoa | 9.127 |

Un producto puede contar en más de un insumo (contiene varios).

---

## Decisiones de S2

| Decisión | Valor | Razón |
|---|---|---|
| **D-A: Estrategia OFF** | Opción B (offline) | La API live devolvía 503 |
| **D-B: USDA** | Sí (desde TIER 7) | La clave se configuró al cerrar S2; en TIER 2 no estaba |
| **D-C: Motor PDF** | xhtml2pdf | Funciona; WeasyPrint queda para S4+ |
| **D-E: Endpoint eCFR** | `versioner` | El `renderer` que proponía el plan devuelve 404 |
| **D-F: OCR de DIGESA** | No | 5 de 10 PDFs son escaneos; se descartan antes que inventar texto |

---

## Estructura

```
datasets/2026-07/
  ├── README.md                     (este archivo)
  ├── manifest.json                 (SHA256 + estadísticas, TIER 7)
  ├── off_productos.json            (TIER 2 · 28.236)
  ├── off_terminados.json           (S8 · 482 terminados PE/CH/DE)
  ├── usda_productos.json           (TIER 2/7 · 990)
  ├── productos_merged.json         (TIER 3 · 29.460)
  ├── ecfr_aditivos.json            (TIER 6 · 702 pasajes)
  ├── digesa_normas.json            (TIER 6 · 32 pasajes)
  ├── digesa_normas_reporte.json    (TIER 6 · qué PDFs se descartaron y por qué)
  └── normativas_codex.json         (S1 · demo, sustituido por el corpus TIER 6)

vectores/
  ├── productos.lance/              (29.460 filas)
  ├── regulatorio.lance/            (734 pasajes)
  └── normativas.lance/             (S1 · demo, con fallback desde verificador_rag)
```
