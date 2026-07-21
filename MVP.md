# MVP.md — Blueprint técnico de construcción

**AgroScout IA Lite · MVP en Python** · Julio 2026
Documento para desarrollar: complementa `MVP_AgroScout_Arquitectura.md` (propuesta/demo) y hereda la persistencia local de `../Arquitectura_AgroScout_IA_Lite.md` (v6).

---

## 1. Qué se construye

Caso de uso `EvaluarInsumo` recortado a **etapas 1-3 + informe simple**, con auditoría y cache en SQLite desde el día uno (no es opcional: el modo `--offline` de la demo depende del cache).

Regla de dependencia: `dominio` no importa nada externo; `casos_de_uso` solo importa `dominio` y `puertos`; los `adaptadores` implementan puertos; `api/` (FastAPI) solo llama casos de uso; `frontend/` (Vue) solo consume la API por HTTP — nunca importa Python.

## 2. Estructura del repositorio

Archivos ≤200 líneas, funciones ≤50, sin `utils/` ni `helpers/`:

```
agroscout-mvp/
├── dominio/
│   ├── insumo.py                # Insumo, InsumoInterpretado
│   ├── producto_existente.py    # ProductoExistente (id_fuente, fecha_dato, ingredientes)
│   ├── insight_mercado.py       # InsightDeMercado (cobertura, citas)
│   └── informe_scout.py         # InformeScout (parcial: bool, snapshot_version)
├── casos_de_uso/
│   ├── evaluar_insumo.py        # orquestador (guard clauses, ver §5)
│   └── etapas/
│       ├── interpretar_insumo.py
│       ├── buscar_productos.py
│       ├── generar_insight.py
│       ├── formular_hipotesis.py   # Etapa 4: Análisis avanzado
│       ├── verificar_regulacion.py # Etapa 5: RAG y openFDA
│       └── emitir_informe.py
├── puertos/
│   ├── catalogo_productos.py    # Protocol
│   ├── redactor_llm.py          # Protocol
│   ├── cache_llm.py             # Protocol
│   ├── verificador_regulatorio.py # Protocol para Stage 5
│   └── repositorio_informes.py  # Protocol
├── adaptadores/
│   ├── busqueda_lancedb.py      # CatalogoProductos → LanceDB + DuckDB
│   ├── redactor_glm.py          # RedactorLLM → litellm/Z.ai (instructor)
│   ├── verificador_openfda.py   # VerificadorRegulatorio → openFDA API
│   ├── verificador_rag.py       # VerificadorRegulatorio → Documentos Propios
│   ├── cache_sqlite.py          # CacheLLM → SQLite WAL
│   ├── auditoria_sqlite.py      # registro de ejecuciones/etapas
│   └── informe_weasyprint.py    # RepositorioInformes → Jinja2 + WeasyPrint
├── contratos/                   # JSON Schema por etapa (referencia para Go)
│   ├── insumo_interpretado.schema.json
│   ├── resultado_busqueda.schema.json
│   └── insight_mercado.schema.json
├── etl/
│   ├── cargar_off.py            # export OFF → filtro 7 cultivos → DuckDB
│   ├── cargar_usda.py
│   └── indexar_vectores.py      # bge-m3 → LanceDB · escribe manifest del snapshot
├── api/main.py                  # FastAPI: POST /consultas · GET /informes/{id} — solo transporte
├── frontend/                    # SPA Vue 3 + Vite (Node 18+) — el mismo SPA sigue con Go
│   └── src/ (App.vue · vistas: ConsultaInsumo · ResultadoInsight · HistorialInformes)
├── evals/
│   ├── set_dorado.yaml          # cáscara de mango, descarte de espárrago, ...
│   └── test_paridad.py          # pytest sobre contratos
├── datasets/                    # snapshots versionados AAAA-MM/ + manifest.json
├── informes/                    # PDFs emitidos
└── .env.example                 # ZAI_API_KEY, USDA_API_KEY, AGROSCOUT_OFFLINE=0
```

## 3. Contratos (Pydantic → JSON Schema)

Cada etapa tiene entrada/salida tipada; `contratos/` se genera con `model_json_schema()` en CI — es la fuente de verdad que Go implementará después.

```python
# dominio/insumo.py
class InsumoInterpretado(BaseModel):
    insumo_normalizado: str
    reconocible: bool
    sinonimos_busqueda: list[str] = Field(min_length=1, max_length=8)

# dominio/producto_existente.py
class ProductoExistente(BaseModel):
    id_fuente: str          # ej. "OFF:5901234123457"
    nombre: str
    categoria: str
    usa_insumo_directo: bool
    fecha_dato: date        # obligatoria: toda cita lleva fecha

# dominio/insight_mercado.py
class InsightDeMercado(BaseModel):
    cobertura: Literal["baja", "media", "alta"]
    resumen: str            # única salida en texto libre del MVP
    citas: list[str]        # ids de fuente; validado: >=1 por afirmación

# dominio/informe_scout.py
class InformeScout(BaseModel):
    parcial: bool
    snapshot_version: str   # ej. "2026-07" — cada informe cita su versión de datos
    ruta_pdf: Path | None
```

## 4. Puertos (interfaces)

```python
# puertos/redactor_llm.py
class RedactorLLM(Protocol):
    async def interpretar(self, texto: str) -> InsumoInterpretado: ...
    async def redactar_insight(self, productos: ResultadoBusqueda) -> InsightDeMercado: ...

# puertos/catalogo_productos.py
class CatalogoProductos(Protocol):
    def buscar(self, sinonimos: list[str], k: int = 30) -> ResultadoBusqueda: ...

# puertos/cache_llm.py — clave = hash(entrada + etapa + snapshot_version)
class CacheLLM(Protocol):
    def obtener(self, clave: str) -> dict | None: ...
    def guardar(self, clave: str, valor: dict) -> None: ...
```

Adaptadores concretos: `redactor_glm.py` usa litellm con `glm-4.7-flashx` (interpretar) y `glm-4.7` (insight) + instructor + tenacity (reintentos). Cambiar a Mistral de respaldo = otro adaptador del mismo puerto, cero cambios arriba.

## 5. Orquestador con guard clauses (early return)

```python
# casos_de_uso/evaluar_insumo.py
async def evaluar_insumo(texto: str, d: Dependencias) -> InformeScout:
    ejecucion = d.auditoria.iniciar(texto, d.snapshot_version)

    interpretado = await etapa(d, ejecucion, 1, interpretar_insumo, texto)
    if not interpretado.reconocible:
        return d.informes.pide_reformulacion(ejecucion)          # guard 1

    resultado = etapa_sync(d, ejecucion, 2, buscar_productos, interpretado)
    if resultado.n_directos <= 2:
        insight = await etapa(d, ejecucion, 3, generar_insight_parcial, resultado)
        return d.informes.emitir(ejecucion, insight, parcial=True)  # guard 2 (caso mango)

    insight = await etapa(d, ejecucion, 3, generar_insight, resultado)
    return d.informes.emitir(ejecucion, insight, parcial=False)
```

`etapa(...)` es el envoltorio único que: consulta cache → llama → valida contra el contrato → registra entrada/salida/duración/costo en SQLite. Un solo lugar para auditoría y cache, ninguna etapa lo reimplementa.

## 6. Persistencia local (heredada de v6)

### SQLite (`agroscout.db`, modo WAL)

```sql
CREATE TABLE ejecuciones (
  id TEXT PRIMARY KEY, insumo_texto TEXT, snapshot_version TEXT,
  estado TEXT CHECK(estado IN ('ok','parcial','reformular','error')),
  creado_en TEXT DEFAULT (datetime('now'))
);
CREATE TABLE etapas_ejecucion (
  ejecucion_id TEXT REFERENCES ejecuciones(id), etapa INTEGER,
  entrada_json TEXT, salida_json TEXT, duracion_ms INTEGER, costo_usd REAL
);
CREATE TABLE cache_llm (
  clave_hash TEXT PRIMARY KEY, etapa INTEGER, modelo TEXT,
  respuesta_json TEXT, snapshot_version TEXT, creado_en TEXT
);
CREATE TABLE informes (
  id TEXT PRIMARY KEY, ejecucion_id TEXT, ruta_pdf TEXT, parcial INTEGER
);
```

### DuckDB (`catalogo.duckdb`) — lo escribe solo el ETL

`productos(id_fuente, nombre, categoria, ingredientes_json, fecha_dato, cultivo)` · `nutricion(fdc_id, nutriente, valor, unidad)` · el manifest del snapshot (`datasets/2026-07/manifest.json`) guarda fechas de descarga, filas y hash de cada fuente.

### LanceDB (`vectores/`) — colección `productos`, embeddings bge-m3, metadato `id_fuente` para citar.

## 7. Configuración y comandos

```
# .env
ZAI_API_KEY=...            # glm-4.7-flashx + glm-4.7
USDA_API_KEY=...
AGROSCOUT_OFFLINE=0        # 1 = demo sin internet (sirve solo desde cache_llm)

# comandos
uv run etl                 # descarga → filtra → DuckDB → vectores → manifest
uv run api                 # uvicorn api.main:app (puerto 8000)
npm run dev --prefix frontend   # SPA Vue con proxy a :8000 (demo local)
npm run build --prefix frontend # estáticos para servir con Caddy (piloto)
uv run evals               # promptfoo + pytest contra set_dorado.yaml
```

Modo `--offline`: `redactor_glm` se reemplaza por un adaptador que solo lee `cache_llm` — mismo puerto, cero ifs en el dominio. Correr el set dorado una vez con internet deja la demo precargada.

## 8. Evals y criterio de aceptación

`evals/set_dorado.yaml` — mínimo 5 casos; el primero es cáscara de mango con las aserciones del caso demo:

- `n_directos <= 2` activa guard 2 y el informe sale `parcial=true`
- el insight menciona que los relacionados usan pulpa/puré, no cáscara
- toda afirmación del resumen lleva cita `[OFF:...]` con fecha
- el PDF declara "orientativo" y la `snapshot_version`

CI corre evals en cada cambio de prompt, modelo o adaptador (puede usar `glm-4.7-flash` gratis para no gastar).

## 9. Definition of Done del MVP

1. `uv run etl` construye el snapshot completo en <3 h en laptop (16 GB, sin GPU).
2. Consulta end-to-end en <15 s con internet; <2 s en `--offline`.
3. Los 5 casos del set dorado pasan en CI.
4. El caso mango produce el PDF parcial correcto, descargable desde la app Vue.
5. `contratos/` generado y versionado (los tres schemas) — listo como referencia para Go.
6. Toda ejecución consultable en SQLite: `SELECT * FROM etapas_ejecucion WHERE ejecucion_id = ?` reconstruye la corrida completa.

Diagrama: `MVP_AgroScout_Arquitectura.svg` · Guion de demo y requerimientos de hardware: `MVP_AgroScout_Arquitectura.md`
