# AgroScout IA Lite — MVP (Python)

**Fecha:** Julio 2026 · **Deriva de:** `../Arquitectura_AgroScout_IA_Lite.md` (v5) · **LLM: familia GLM (Z.ai)**
**Propósito:** demo para la reunión con el CITE + piloto con 2-3 cooperativas. **Lenguaje:** Python (la producción será en Go; los contratos JSON Schema de este MVP son la referencia que Go implementará).

---

## 1. Objetivo y alcance

Demostrar el flujo completo de valor con un caso real (cáscara de mango) — no una plataforma terminada. El MVP implementa **las etapas 1-3 del DAG + informe simple**:

| Incluye | No incluye (se dice explícitamente en la demo) |
|---|---|
| Ingreso de insumo en lenguaje natural (SPA Vue 3) | Formulación (etapa 4) |
| Interpretación + sinónimos ES/EN visibles | Precios (etapa 5) |
| Búsqueda semántica sobre OFF + USDA filtrados a los 7 cultivos de la región | Verificación regulatoria (etapa 6) |
| Insight de mercado con citas (fuente + fecha) por producto | Login/planes (demo con acceso directo) |
| Informe descargable simple (HTML → PDF) | Panel institucional |

**Guard clause central (el momento clave de la demo):** si la etapa 2 encuentra 0-2 productos, el MVP emite un informe parcial honesto — "insumo poco explotado comercialmente = posible hueco de mercado" — en vez de forzar resultados. Es el caso real de la cáscara de mango y lo que construye confianza institucional.

---

## 2. Arquitectura del MVP

Misma Clean Architecture del documento principal, recortada a lo que la demo necesita:

```
┌──────────────────────────────────────────────────┐
│ UI: SPA Vue 3 + Vite — consume la API por HTTP   │
│   (el MISMO SPA sigue en producción con Go)      │
├──────────────────────────────────────────────────┤
│ API: FastAPI — solo transporte, desde el día uno │
├──────────────────────────────────────────────────┤
│ Caso de uso: EvaluarInsumo (etapas 1-5 + informe)│
├──────────────────────────────────────────────────┤
│ Puertos: CatalogoProductos · RedactorLLM ·       │
│          VerificadorRegulatorio · RepositorioInf │
├──────────────────────────────────────────────────┤
│ Adaptadores: LanceDB+DuckDB · Z.ai/GLM · WeasyPrint│
│              openFDA API · RAG Documental Propio │
└──────────────────────────────────────────────────┘
```

### El DAG del MVP

| # | Etapa | Tecnología | LLM |
|---|---|---|---|
| 1 | `InterpretarInsumo` | `glm-4.7-flashx` (Z.ai) + instructor → sinónimos ES/EN en JSON validado | 1 llamada (~US$ 0.0002) |
| 2 | `BuscarProductosSimilares` | bge-m3 (CPU) o LanceDB FTS sobre subset local de OFF + USDA | sin LLM |
| 3 | `GenerarInsightDeMercado` | `glm-4.7` (Z.ai); contexto = solo resultados de la etapa 2, citas obligatorias | 1 llamada (~US$ 0.004) |
| 4 | `FormulacionHipotesis` | `glm-4.7` (Z.ai); NLP para extraer patrones de ingredientes de la literatura y productos | 1 llamada (~US$ 0.004) |
| 5 | `VerificacionRegulatoria` | RAG sobre Base Propia (Codex, DIGESA, EFSA) + openFDA API (EE.UU.) | 1 llamada (~US$ 0.003) |
| 6 | `EmitirInformeCompleto` | Jinja2 (HTML) → WeasyPrint (PDF) | sin LLM |

**Costo por consulta del MVP: < US$ 0.01.** Un piloto de 3 cooperativas × 20 consultas/mes ≈ **US$ 1/mes** de LLM.

### Estructura del repo del MVP

```
agroscout-mvp/
├── dominio/                 # Insumo, ProductoExistente, InsightDeMercado, InformeScout
├── casos_de_uso/
│   ├── evaluar_insumo.py    # DAG etapas 1-3 + informe (guard clauses)
│   └── etapas/
├── puertos/                 # typing.Protocol
├── adaptadores/             # busqueda_lancedb.py · redactor_glm.py · informe_weasyprint.py
├── contratos/               # JSON Schemas (futura referencia para Go)
├── etl/                     # scripts de carga inicial (se corren una vez)
│   ├── cargar_off.py        # filtra export OFF a los 7 cultivos
│   └── cargar_usda.py
├── api/                     # FastAPI: solo transporte
├── frontend/                # SPA Vue 3 + Vite (persiste en producción)
├── evals/                   # set dorado: cáscara de mango, descarte de espárrago, ...
└── .env.example             # ZAI_API_KEY, USDA_API_KEY
```

---

## 3. Requerimientos técnicos

### 3.1 Software

| Componente | Versión / detalle |
|---|---|
| Python | 3.12+ (gestor: uv o pip) |
| Dependencias backend | `fastapi` + `uvicorn`, `pydantic>=2`, `instructor`, `litellm` u `openai` (la API de Z.ai es OpenAI-compatible), `sentence-transformers` (bge-m3), `lancedb`, `duckdb`, `jinja2`, `weasyprint`, `tenacity` |
| Frontend | **Vue 3 + Vite** (Node 18+) — Pinia opcional; el mismo SPA se conserva en producción |
| SO | Windows/macOS para desarrollo; Ubuntu 22.04 LTS para el piloto |
| Evals | promptfoo — usa el mismo Node 18+ que ya exige Vite; opcional en demo, obligatorio en piloto |

### 3.2 Hardware

| Escenario | Mínimo | Notas |
|---|---|---|
| **Desarrollo / demo (laptop)** | 4 núcleos · **16 GB RAM** · 20 GB disco libre | bge-m3 usa ~2-3 GB RAM en CPU; el subset de datos ~2-3 GB. Sin GPU. |
| **Piloto (servidor)** | ReliableSite clearance (desde US$ 49-79/mes, ≥32 GB RAM, NVMe) — o la misma laptop | Caddy para TLS; Docker Compose opcional. El dedicado definitivo (Ryzen 5600X, US$ 85/mes) se contrata recién en fase institucional. |

### 3.3 Datos (carga inicial, una sola vez)

| Fuente | Tamaño aprox. tras filtrar | Cómo |
|---|---|---|
| Open Food Facts (export JSONL) | ~1-2 GB (7 cultivos: palto, espárrago, arándano, mango, piquillo, banano, uva) | `etl/cargar_off.py` — descarga ~9 GB, filtra y descarta el resto |
| USDA FoodData Central (CSV) | ~200 MB | `etl/cargar_usda.py` |
| openFDA (API) | N/A (Consultas en tiempo real) | Adaptador a API oficial de la FDA (EE.UU.) para ingredientes y aditivos |
| Base documental propia (RAG) | ~50 MB (Guías de DIGESA, EFSA, Codex) | Descarga única y actualización periódica; búsqueda semántica propia |
| Índice vectorial LanceDB | ~500 MB-1 GB | generado por el ETL |
| SQLite local (estado de app) | ~MBs | historial de consultas, ejecuciones del DAG y **cache LLM** — el mismo cache alimenta el modo `--offline` de la demo |

### 3.4 Cuentas y claves (variables de entorno)

| Clave | Dónde se obtiene | Costo |
|---|---|---|
| `ZAI_API_KEY` | z.ai (plataforma de desarrolladores) | prepago; US$ 5 sobran para demo + piloto. Para desarrollo/CI: `glm-4.7-flash` es gratis (con rate limit) |
| `USDA_API_KEY` | fdc.nal.usda.gov (registro inmediato) | gratis |
| `OPENFDA_API_KEY` | open.fda.gov (registro opcional pero recomendado) | gratis |
| Mistral / Supabase | **no se necesitan en el MVP inicial** (Mistral entra en fases siguientes para RAG) | — |

### 3.5 Red y plan B de la demo

- La demo requiere internet solo para las 2 llamadas a la API de Z.ai (~5-10 s en total); la búsqueda es 100% local.
- **Plan B sin internet:** flag `--offline` que sirve respuestas cacheadas del set dorado — la demo nunca se cae por el wifi de la sala.

---

## 4. Caso demo: entrada y salida esperada

Caso real basado en la simulación del docx original (cáscara de mango). Es también el primer caso del set dorado en `evals/` y la respuesta cacheada del modo `--offline`.

### Entrada (lo que escribe el usuario en la app Vue)

> **Insumo disponible:** cáscara de mango
> *(campo opcional — región: La Libertad)*

### Salida esperada — Etapa 1 · `InterpretarInsumo` (visible en la UI)

```json
{
  "insumo_normalizado": "cáscara de mango",
  "reconocible": true,
  "sinonimos_busqueda": [
    "mango peel", "mango peel flour", "mango byproduct",
    "harina de cáscara de mango", "mango skin powder"
  ]
}
```

### Salida esperada — Etapa 2 · `BuscarProductosSimilares`

| Resultado | Valor |
|---|---|
| Productos **directos** (usan cáscara como ingrediente) | **0-2** → se activa el guard clause |
| Productos **relacionados** (pulpa, puré, deshidratado de mango) | ~20-30, cada uno con ID, fuente y fecha |

Ejemplo de filas devueltas (formato, no valores exactos — la base OFF cambia):

| Producto | Categoría | Ingrediente de mango | Fuente · fecha |
|---|---|---|---|
| Mango chutney | Salsas/untables | pulpa | OFF:5901234123457 · 2025-11 |
| Dried mango slices | Snacks deshidratados | fruta entera pelada | OFF:7861002300145 · 2026-02 |
| Mango nectar | Bebidas | puré | OFF:0041331124454 · 2025-08 |

### Salida esperada — Etapa 3 · `GenerarInsightDeMercado` (informe parcial, guard activo)

> **Cobertura comercial: BAJA — posible hueco de mercado.**
> Encontramos 0-2 productos comerciales directos con cáscara de mango en las bases abiertas consultadas. Los ~25 productos relacionados usan **pulpa o puré**, no la cáscara [OFF:5901234123457, OFF:0041331124454] — lo que sugiere una oportunidad de diferenciación real.
>
> **Categorías donde aparece el mango:** salsas/untables, snacks deshidratados, bebidas, mermeladas.
> **Formatos comunes:** frasco de vidrio 200-450 g, bolsa resellable 50-100 g, tetra 1 L.
>
> *Cada dato proviene de una base colaborativa abierta con su fecha; tómelo como orientación inicial, no como verdad certificada. La hipótesis de formulación y el precio referencial llegan en la fase siguiente de la plataforma; la validación final la hace el laboratorio del CITE.*

### Salida esperada — Etapa 4 · `EmitirInformeSimple`

PDF de 1-2 páginas descargable: insumo + sinónimos usados · tabla de productos con fuente y fecha · insight con citas · aviso de informe parcial (guard) · pie con fecha de la base de datos consultada.

**Criterio de aceptación del caso (eval):** productos directos ≤ 2 · el insight menciona "pulpa/puré, no cáscara" · toda afirmación lleva cita `[OFF:...]` · el PDF declara que es orientativo.

---

## 5. Guion de demo (10-12 min)

1. **El problema** (2 min): definir un producto nuevo es ensayo y error; el técnico tarda ~1 día en sintetizar lo que la plataforma entrega en segundos.
2. **Caso cáscara de mango en vivo** (5 min): insumo → sinónimos generados visibles → resultados con fuente y fecha → insight con el guard clause: "0-2 productos comerciales directos, pero hueco de mercado real".
3. **Segundo insumo pedido por la audiencia** (2 min): demostrar que no es un video pregrabado.
4. **Roadmap y pedido** (3 min): qué sigue (formulación, precios, regulatorio — ya diseñados) y qué se necesita del CITE: 2-3 cooperativas piloto, lista de insumos prioritarios, fichas manuales para vacíos LATAM.

## 6. Criterios de éxito del piloto

- ≥70% de consultas devuelven insight útil según el técnico del CITE (evaluación ciega simple).
- Síntesis de ~1 día manual → <1 min por consulta.
- 2-3 cooperativas completan ≥5 consultas reales en 4 semanas.

## 7. Cronograma (6-9 semanas)

| Semanas | Entregable |
|---|---|
| 1-3 | ETL inicial + índice vectorial + set dorado de evals |
| 3-7 | Etapas 1-3 + Streamlit + informe PDF + modo `--offline` |
| 7-9 | Ensayo de demo, ajuste de prompts contra evals, despliegue del piloto |

Diagrama: `MVP_AgroScout_Arquitectura.svg`
