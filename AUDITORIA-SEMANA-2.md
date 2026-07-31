# Auditoría Semana 2 · Datos reales de los 5 insumos

**Fecha:** 2026-07-30  
**Período:** Semana 2 del plan de 4 semanas (post-Semana 1)  
**Objetivo de salida:** P03 en verde + 5 insumos respondiendo de punta a punta con datos verificables  

---

## 1. Dependencias críticas de Semana 1

**Si Semana 1 NO entrega esto, Semana 2 está bloqueada.**

| Ítem | Estado requerido | Impacto si falta |
|---|---|---|
| **Cost-meter real** (§7 S1) | `costo_usd` = tokens × tarifa por modelo, por etapa | P03 cae; costo visible en informes es falso; argumentación inservible |
| **`fecha_dato` real** | Timestamp desde OFF (not invented `date.today()`) | P04 y P05 muestran dato inventado; guion bloquea en vivo |
| **`usa_insumo_directo` derivado** | Parsing de ingredientes (`texto → bool`), no hardcode | Guard clause es falso; demo principal no ejecuta |
| **Etapas 4 y 5 separadas** | Dentro de `etapa()` como etapas independientes | Paywall no es posible; cost-meter no puede auditar por etapa; P06 imposible |
| **Modelo por etapa (E1 ≠ E3)** | flashx en E1, 4.7 en E3; modelo en clave de cache | Costo incorrecto; hits de cache cruzados; P02 falla |
| **Huawei MaaS verificado** (D2) | ✓ Modelos GLM accesibles con costo < US$0.02/run | Si modelo barato no existe, pitch se cae; presupuesto recomendado sube |
| **Auth + JWT real** | bcrypt, JWT con exp, CORS cerrado, todos endpoints autorizados | RLS no protege nada; P01 imposible; datos de otras orgs visibles |
| **`contratos/` generado** | `.json` Schema con `model_json_schema()` por entidad | P04 no es verificable (sin definición canónica del formato) |

**Acción preventiva:** Semana 1 debe terminar con test que verifique:
```python
# pseudocode para test de cierre de S1
assert cost_usd > 0  # no es fijo
assert fecha_dato != today()
assert usa_insumo_directo in (True, False)  # derivado, no const
assert len(etapas) == 6  # no fusionadas
assert cache.modelo in ("glm-4.7-flashx", "glm-4.7", ...)
```

---

## 2. Estado actual del código vs necesidades de S2

### 2.1 ETL y carga de datos

| Componente | Estado hoy | Necesario S2 | Hueco |
|---|---|---|---|
| **`cargar_off_masivo()`** | ✅ Existe, descarga 5 insumos por búsqueda API | ✅ Reutilizable | Timeout/fallback a DEMO data; con OFF lento, falla |
| **Filtrado a 50-200 productos** | ❌ No existe | ✅ Crítico: `off_productos.json` → indexación | Sin filtrado, indexación toma horas; dataset crece a GB |
| **USDA Branded subset** | ❌ Falta clave propia | ✅ Crítico: 10-50 productos | DEMO_KEY tiene límite; datos no son reales |
| **Embeddings bge-m3** | ✅ `sentence-transformers` en `pyproject.toml` | ✅ Llamada real en ETL | No se llama: [indexar_vectores.py:40-43](etl/indexar_vectores.py#L40) usa FTS, no `from sentence_transformers import SentenceTransformer` |
| **Índice vectorial en LanceDB** | ✅ Estructura existe | ✅ Con embeddings reales | Hoy: FTS only; [busqueda_lancedb.py:22](adaptadores/busqueda_lancedb.py#L22) `query_type="fts"` |
| **DuckDB para datos** | ✅ Dependencia en `pyproject.toml` | ✅ Para tendencias (S2 preparación) | 0 usos en código; tablas no diseñadas |
| **`datasets/2026-07/` + manifest** | ❌ No existe | ✅ Crítico: versioning + reproducibilidad | Semana 2 debe crear la estructura |
| **Corpus regulatorio mínimo** | ⚠️ RAG con openFDA existe ([adaptadores/](adaptadores/)) | ✅ Expandir con eCFR + DIGESA | openFDA está; aditivos eCFR no; DIGESA no tiene OCR |

### 2.2 Búsqueda y vectorización

**Código actual:** `busqueda_lancedb.py`
```python
# Línea 22:
results = table.search(query).where(f"ingredients LIKE '%{insumo}%'").limit(5).to_list()
```
→ **FTS pura, sin embeddings.**

**Necesario S2:**
```python
# Pseudocode de destino
embedding = model.encode(query)  # bge-m3
results = table.search(embedding).metric("cosine").limit(5).to_list()
assert len(results) >= 3, "cobertura insuficiente"
measure_p95(search_time_per_query)  # P03 exige p95 < 2s
```

### 2.3 Set dorado de pruebas

| Estado | Tamaño | Cobertura |
|---|---|---|
| Hoy (`evals/set_dorado.yaml`) | 2 casos | Mango + 1 genérico |
| Necesario S2 | 5+ casos | 1 por insumo piloto (arándano, palta, espárrago, mango, quinua) |
| Verificación | Manual en PDF | ✅ Datos reales en OFF navegables |

---

## 3. Desglose de tareas de Semana 2

### Semana 2, Día 1 · Setup y verificación de E2E

**Inputs:** Semana 1 entregó todas las dependencias.

- [ ] Checkout código de S1, verificar test de cierre
- [ ] `USDA_API_KEY` disponible en `.env.local`; test de acceso a API
- [ ] Configurar `datasets/2026-07/` con estructura:
  ```
  datasets/2026-07/
    ├── manifest.json          # {fecha_descarga, hash, filas_por_fuente, version_taxonomia}
    ├── off_productos.json     # salida de cargar_off_masivo()
    ├── usda_productos.json    # salida de cargar_usda()
    └── README.md              # procedimiento reproducible
  ```
- [ ] `manifest.json` schema:
  ```json
  {
    "fecha_descarga": "2026-07-30T14:30:00Z",
    "snapshot_version": "2026-07",
    "version_taxonomia": "0.1",
    "fuentes": {
      "OFF": {"filas": 245, "hash": "sha256:abc123", "fecha_ingesta": "..."},
      "USDA": {"filas": 32, "hash": "...", "fecha_ingesta": "..."}
    }
  }
  ```
- [ ] Verificar que `indexar_vectores.py` puede ejecutarse sin error (sin embeddings aún)

**Salida esperada:** Estructura lista; ambas APIs accesibles; baseline de tiempo de descarga medido.

---

### Semana 2, Día 2-3 · Descarga y filtrado OFF + USDA

**Parallelizable:** OFF y USDA pueden ejecutarse en paralelo.

#### OFF (Día 2)
- [ ] Ejecutar `python -m etl.cargar_off_masivo` → `data/off_productos.json`
  - Insumos: `["arándano", "palta", "espárrago", "mango", "quinua"]`
  - Esperado: 50-200 productos por insumo (250-1000 total)
  - Timeout/fallback a DEMO data → logs claramente etiquetados
- [ ] Validación de estructura:
  ```python
  assert all(p.get("fecha_dato") for p in productos if p["id_fuente"].startswith("OFF"))
  assert all(p.get("url") for p in productos if p["id_fuente"].startswith("OFF"))
  assert len(productos) >= 250  # mínimo garantizado
  ```
- [ ] Copiar a `datasets/2026-07/off_productos.json`
- [ ] Log de métricas: filas por insumo, % con ingredientes, fecha más antigua/reciente

#### USDA (Día 2-3)
- [ ] Script nuevo: `etl/cargar_usda.py` (no existe aún)
  - Endpoint: `https://fdc.nal.usda.gov/api/foods/search`
  - Param: `USDA_API_KEY`, `pageSize=100`, filtro por `insumos` piloto
  - Salida: `lista[{id, nombre, marca, ingredientes, url, fecha_dato}]`
- [ ] Copiar a `datasets/2026-07/usda_productos.json`
- [ ] Deduplicación vs OFF (por nombre + marca + insumo)

**Salida esperada:**
```
datasets/2026-07/
├── off_productos.json      (300-1000 filas)
└── usda_productos.json     (10-50 filas, sin duplicados con OFF)
```

---

### Semana 2, Día 4 · Embeddings reales + indexación

**Secuencial:** depende de Día 2-3.

- [ ] Reescribir `etl/indexar_vectores.py`:
  ```python
  from sentence_transformers import SentenceTransformer
  
  model = SentenceTransformer("BAAI/bge-m3")
  
  # 1. Cargar productos desde datasets/2026-07/off_productos.json + usda
  productos = load_products("datasets/2026-07/")
  
  # 2. Generar embeddings
  texts = [f"{p['nombre']} {p['ingredientes']}" for p in productos]
  embeddings = model.encode(texts, batch_size=32)  # ~2-5 min para 500 productos
  
  # 3. Indexar en LanceDB
  data = [
    {
      "id": p["id_fuente"],
      "nombre": p["nombre"],
      "ingredientes": p["ingredientes"],
      "embedding": embedding,
      "fuente": p["id_fuente"].split(":")[0],
      "fecha_dato": p["fecha_dato"],
      "url": p["url"]
    }
    for p, embedding in zip(productos, embeddings)
  ]
  
  db = lancedb.connect("vectores/")
  table = db.create_table("productos", data=data, mode="overwrite")
  table.create_index(...)  # LanceDB índice vectorial automático
  ```
- [ ] Fix entry point en `pyproject.toml`: `etl = "etl.indexar_vectores:main"` → el módulo debe tener `def main():`
- [ ] Medir tiempo de indexación y espacio en disco
- [ ] Crear entrada en `manifest.json`: `"vectores": {"hash": "...", "dimensiones": 1024, "modelo": "bge-m3"}`

**Validación:**
```python
# test/test_embeddings.py
def test_embeddings_loaded():
    db = lancedb.connect("vectores/")
    table = db.open_table("productos")
    assert table.count_rows() >= 250
    assert all("embedding" in r for r in table.to_pandas().to_dict("records"))
```

**Salida esperada:** `vectores/productos.lance/` con embeddings reales.

---

### Semana 2, Día 5 · Búsqueda con p95 + golden set

**Secuencial:** depende de Día 4.

- [ ] Reescribir `adaptadores/busqueda_lancedb.py` para usar embeddings:
  ```python
  def buscar_productos(query: str, insumo: str, limit: int = 5) -> List[ResultadoBusqueda]:
      embedding = model.encode(query)  # caché de modelo a nivel de módulo
      
      results = table.search(embedding)
          .metric("cosine")
          .where(f"fuente = 'OFF' OR fuente = 'USDA'")  # excluir DEMO si OFF tuvo éxito
          .limit(limit)
          .to_list()
      
      return [
          ResultadoBusqueda(
              id=r["id"],
              nombre=r["nombre"],
              ingredientes=r["ingredientes"],
              fuente_url=r["url"],
              fecha_dato=r["fecha_dato"],  # ← NO inventada
              similitud=r["_distance"]  # cosine distance
          )
          for r in results
      ]
  ```
- [ ] Medir latencia p95:
  ```python
  import time
  latencies = []
  for _ in range(100):
      t0 = time.time()
      buscar_productos("arándano", limit=5)
      latencies.append(time.time() - t0)
  
  p95 = np.percentile(latencies, 95)
  assert p95 < 2.0, f"P95 latency {p95}s exceeds 2s SLA (P03 requirement)"
  ```
- [ ] Ampliar `evals/set_dorado.yaml` a 5 casos (1 por insumo):
  ```yaml
  - insumo: "arándano"
    esperado_minimo_coincidencias: 3
    verificacion: "productos con arándano en OFF navegables en el URL"
  - insumo: "palta"
    esperado_minimo_coincidencias: 2
  - ...
  ```
- [ ] Ejecutar `uv run evals` y verificar P03 en verde:
  ```
  P03 · Búsqueda vectorial < 2s, 30+ productos, verificable en OFF navegador
  [ ✅ PASS ]
  ```

**Salida esperada:** P03 en verde; benchmark de latencia documentado.

---

### Semana 2, Día 5-6 · Corpus regulatorio mínimo + integración final

**Parallelizable con Día 5** (un dev en búsqueda, otro en regulación).

- [ ] Corpus eCFR (aditivos alimentarios):
  - [ ] Descargar subset de eCFR aditivos relevantes a los 5 insumos (eCFR Title 21, Part 182 = GRAS list)
  - [ ] Fuente: https://www.eCFR.gov/api/ o descarga manual PDF + OCR
  - [ ] Normalizar a JSON: `{id, titulo, texto, fuente_url, fecha_publicacion}`
  - [ ] Guardar en `datasets/2026-07/ecfr_aditivos.json`
- [ ] Corpus DIGESA:
  - [ ] Identificar 2-3 normas DIGESA relevantes (ej: Resolución Sanitaria sobre colorantes)
  - [ ] Descargar PDF desde `digesa.minsa.gob.pe`
  - [ ] OCR simple (Tesseract o similar) → texto
  - [ ] Guardar en `datasets/2026-07/digesa_normas.txt`
  - **Nota:** OCR completo es para F5; S2 puede ser manual si es <3 normas
- [ ] Integrar corpus a LanceDB (mismo índice `productos`):
  ```python
  regulatory_docs = load_regulatory_docs("datasets/2026-07/")
  regulatory_embeddings = model.encode([d["texto"] for d in regulatory_docs])
  # Insertar en tabla `regulatorio` o campo adicional en `productos`
  ```
- [ ] Prueba negativa: buscar "aditivo 500" → encuentra norma con referencia verificable

**Salida esperada:** Corpus indexado; base para P08.

---

### Semana 2, Día 6-7 · Integración punta-a-punta + E2E

- [ ] Prueba E2E: insumo `arándano` → etapa 1-3 → informe con datos reales
  ```bash
  curl -H "Authorization: Bearer $JWT" \
    http://localhost:8000/consultas \
    -d '{"insumo": "arándano"}' \
    -o test_output.pdf
  ```
  - Verificar PDF:
    - [ ] Producto 1 con nombre real de OFF
    - [ ] Fecha dato es timestamp de OFF (no `today()`)
    - [ ] URL verificable en navegador
    - [ ] Costo en USD > 0
    - [ ] Sin valores literales inventados
- [ ] Verificar `manifest.json` actualizado con hashes de descarga
- [ ] Golden set de 5 casos pasa (`uv run evals`)
- [ ] Estadísticas finales de S2:
  ```markdown
  ## Salida Semana 2
  
  - ✅ OFF: 287 productos, 5 insumos
  - ✅ USDA: 34 productos, 2 duplicados removidos
  - ✅ Embeddings: bge-m3, 1024 dim, p95 = 1.2s
  - ✅ Corpus regulatorio: 5 documentos, 8400 palabras
  - ✅ P03: 5/5 golden set pasa
  - ✅ Datos verificables en vivo (URLs navegables)
  ```

---

## 4. Matriz de pruebas (P03 + P08)

### P03 · Búsqueda < 2s, 30+ productos, sin inventar datos

| Aspecto | Criterio | Test |
|---|---|---|
| **Latencia** | p95 < 2s | `pytest test/test_latency.py::test_p95_latency` |
| **Cobertura** | ≥30 productos indexados | `len(table.count_rows()) >= 30` |
| **Fecha real** | No es `date.today()` | `all(p["fecha_dato"] != str(date.today()) for p in results)` |
| **URL navegable** | Abre en navegador, producto existe | Manual: click en URL, verificar en OFF |
| **Sin DEMO data** | Si OFF tuvo éxito, DEMO excluido | `assert "DEMO:" not in [r["id"] for r in results]` |

**DoD:** Todos criterios verde; P03 levanta en CI.

### P08 · Corpus regulatorio con citas verificables (preparación)

**S2 construye la base; P08 completo es F5.**

| Aspecto | S2 Preparación | Criterio final (F5) |
|---|---|---|
| **Corpus eCFR** | 5-10 documentos de aditivos | ≥50 normas, indexadas, meta con URL |
| **Corpus DIGESA** | 2-3 normas, OCR manual | ≥5 normas, OCR automático |
| **Indexación** | En LanceDB regulatorio | Búsqueda de citas devuelve norma + párrafo |
| **Cita verificable** | URL a fuente oficial | URL + línea exacta + hash de PDF |

---

## 5. Riesgos y mitigaciones

### R1 · ETL masivo de OFF lento o incompleto

**Riesgo:** OFF API timeout, fallback a DEMO data, productos inventados.

**Probabilidad:** Media (OFF a veces lenta, inestable).

**Impacto:** P03 y P04 fallan; demo muestra datos inventados; CITE lo ve en vivo.

**Mitigación:**
- [ ] Día 1: medir tiempo real de descarga. Si > 5 min por insumo, plan B: usar **descarga offline de export masivo** (https://world.openfoodfacts.org/data/ → `.gz` de 2GB, tardar ~1 hora en descargar y descomprimir, pero ETL es local después).
- [ ] Implementar reintentos exponenciales en `cargar_off_masivo()` (3x con backoff).
- [ ] Logging claro: `[OFF OK] 245 productos` vs `[OFF FALLBACK] usando DEMO data`.
- [ ] Si DEMO data se usa: **prohibir mostrar en demo**; swapear a búsqueda viva de 1-2 productos reales en vivo.

---

### R2 · bge-m3 no cabe en memoria o es lento

**Riesgo:** Modelo grande (438MB), 100+ productos → indexación toma horas.

**Probabilidad:** Baja (sentence-transformers está optimizado).

**Impacto:** Indexación no termina en el día; P03 falla.

**Mitigación:**
- [ ] Día 4: medir en máquina real: `time python -m etl.indexar_vectores`. Si > 30 min, reducir batch_size o usar modelo más pequeño (`bge-small-en-v1.5`, 33MB).
- [ ] Baseline: 500 productos + 100 lineas documento = ≈5 min en CPU.
- [ ] Si GPU disponible (CUDA), usar `model.cuda()` → ~30 seg.

---

### R3 · USDA_API_KEY no disponible o tiene límite

**Riesgo:** DEMO_KEY corre solo en desarrollo; en producción, datos reducidos.

**Probabilidad:** Media (depende de aprobación externa).

**Impacto:** USDA datos incompletos; P03 cubre 80% con OFF.

**Mitigación:**
- [ ] Día 2: test acceso `curl "https://api.nal.usda.gov/fdc/v1/foods/search?query=blueberry&pageSize=1&api_key=$USDA_API_KEY"`. Si falla, proceder solo con OFF.
- [ ] Documentar en `manifest.json`: `"usda_clave_estado": "disponible" | "ausente"`.
- [ ] P03 no requiere USDA; OFF solo alcanza.

---

### R4 · Corpus eCFR/DIGESA no se consigue en tiempo

**Riesgo:** OCR lento; PDFs de DIGESA no accesibles; formato inconsistente.

**Probabilidad:** Media (regulación es siempre frágil).

**Impacto:** P08 base débil; demo regulatoria sin sustancia.

**Mitigación:**
- [ ] Día 5, mañana: identificar 3 normas eCFR + 2 DIGESA específicas por insumo **antes** de intentar descargar.
- [ ] Plan B (Día 6 tarde): usar corpus mínimo **conocido** (ej: `Color Additives Status List` ya disponible en TXT), copiar a `datasets/2026-07/`, documentar como "base de referencia".
- [ ] P08 en S2 es preparación; citas verificables son F5.

---

### R5 · Manifest.json no refleja realidad

**Riesgo:** Hash de archivo falso, fecha de descarga perdida, snapshot_version desincronizado.

**Probabilidad:** Media (fácil olvidar actualizar después de cargar datos).

**Impacto:** Auditoría falla; reproducibilidad rota; CITE no confía en datos.

**Mitigación:**
- [ ] Automatizar: script que calcula hashes y escribe `manifest.json` después de cada descarga:
  ```python
  def update_manifest(datasets_dir="datasets/2026-07/"):
      manifest = {
          "fecha_descarga": datetime.utcnow().isoformat(),
          "snapshot_version": "2026-07",
          "version_taxonomia": "0.1",
          "fuentes": {}
      }
      for file in ["off_productos.json", "usda_productos.json"]:
          path = f"{datasets_dir}/{file}"
          with open(path, "rb") as f:
              manifest["fuentes"][file] = {
                  "filas": len(json.load(open(path))),
                  "hash": hashlib.sha256(f.read()).hexdigest(),
                  "fecha_ingesta": datetime.utcnow().isoformat()
              }
      with open(f"{datasets_dir}/manifest.json", "w") as f:
          json.dump(manifest, f, indent=2)
  ```
- [ ] Llamar al final de cada ETL.

---

## 6. Hitos diarios recomendados

| Día | Hito | Verificación |
|---|---|---|
| **Lunes 5 ago** | Setup + estructura `datasets/2026-07/` | `ls datasets/2026-07/manifest.json` ✓ |
| **Martes 6 ago** | OFF + USDA descargados | `wc -l datasets/2026-07/*.json` → >250 filas |
| **Miércoles 7 ago** | Embeddings indexados | `vectores/productos.lance/` existe; `table.count_rows()` ≥ 250 |
| **Jueves 8 ago** | P95 latencia < 2s | `pytest test/test_latency.py` pasa |
| **Viernes 9 ago** | E2E + golden set | `uv run evals` → 5/5 pasa; PDF con datos reales generado |
| **Viernes 9 ago EOD** | Corpus regulatorio básico | `datasets/2026-07/ecfr_*.json` + `digesa_*.txt` ≥ 5 docs |

---

## 7. Checklist de cierre de Semana 2

- [ ] **Datos:**
  - [ ] `off_productos.json`: 250-1000 filas, no hay DEMO data (o logs claramente etiquetados)
  - [ ] `usda_productos.json`: 10-50 filas, deduplicado vs OFF
  - [ ] `manifest.json` actualizado con hashes, fecha, conteos
  - [ ] Todos los campos `fecha_dato` son timestamps reales, no `date.today()`

- [ ] **Embeddings:**
  - [ ] `vectores/productos.lance/` con tabla `productos` indexada
  - [ ] ≥250 filas con embedding vectorial (dimensión 1024, modelo bge-m3)
  - [ ] p95 latencia medida y documentada (< 2s)

- [ ] **Búsqueda:**
  - [ ] `adaptadores/busqueda_lancedb.py` usa embeddings, no FTS
  - [ ] Retorna `fecha_dato` real desde tabla, no inventado
  - [ ] URL navegable verificable en OFF

- [ ] **Regulación:**
  - [ ] Corpus eCFR: 5-10 documentos, indexados
  - [ ] Corpus DIGESA: 2-3 normas, accesibles
  - [ ] Ambos en LanceDB o tabla separada `regulatorio`

- [ ] **Pruebas:**
  - [ ] `evals/set_dorado.yaml` ampliado a 5 casos (1 por insumo)
  - [ ] `uv run evals` → P03 en verde ✓
  - [ ] E2E workflow: login → consulta arándano → PDF con datos reales
  - [ ] `pytest test/test_embeddings.py` → todos pasan

- [ ] **Documentación:**
  - [ ] `datasets/2026-07/README.md`: procedimiento reproducible de descarga
  - [ ] `manifest.json` con metadatos completos
  - [ ] Benchmarks: tiempo de descarga, indexación, latencia p95

- [ ] **Integración con S3:**
  - [ ] Verificar que S3 (etapas 4 y 5 separadas) entrega costo por etapa real
  - [ ] Etapa 2b (MapaComercial) lista para recibir datos del snapshot
  - [ ] Cache de modelo funciona (modelo en clave es diferente por etapa)

---

## 8. Riesgos de NO hacer esto en S2

Si S2 no termina con datos reales:

1. **Semana 3 será caos:** Auth + RLS a mano + paywall + datos falsos = no es demostrable.
2. **Semana 4 es imposible:** 2b MapaComercial no tiene qué mostrar.
3. **Demo del CDR cae:** Muestran datos inventados en vivo; CITE cierra carpeta.
4. **Argumentación de "cero valores inventados" se desmorona.**

**Acción: S2 debe terminar con:** "Aquí están los datos verificables en el navegador. Prueben el link."

---

## 9. Próximos pasos (Semana 3)

S3 toma de S2:
- `datasets/2026-07/` con datos reales
- `vectores/productos.lance/` con embeddings
- P03 en verde

S3 construye sobre eso:
- Multi-tenant Postgres con RLS
- Paywall
- Cost-meter por tenant
- 2 cuentas demo

Si S2 no termina a tiempo, S3 comienza con datos inventados o incompletos → plan se rompe.

---

**Autor:** Auditoría para semana 2  
**Estado:** Requiere confirmación de S1 entregado + permisos API (USDA, Huawei)  
**Actualización:** Revisar Martes 6 ago PM si hay desviaciones en velocidad
