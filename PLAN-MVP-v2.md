# Diferencia v1 → v2 y plan de la nueva versión

**Fecha:** 2026-07-29 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)

- **v1 (base del código actual):** `MVP_AgroScout_Arquitectura.md` + `MVP.md` + `MVP_AgroScout_Arquitectura.svg`
- **v2 (nueva propuesta):** `../MVP-AgroScout-IA.md` + `../Arquitectura_AgroScout_IA_MVP.svg`
- **Marco de referencia:** ADR-001 (núcleo comercial y paywall) · ADR-002 (MIM) · ADR-003 (escalado multi-tenant, fase 1)

---

## 0. Resumen ejecutivo

Tres conclusiones, en orden de importancia:

1. **v2 no es una extensión de v1: cambia el eje de valor y el sustrato técnico.**
   El eje de la demo pasa del *guard clause* ("cáscara de mango: 0-2 productos = hueco de mercado") al **mapa comercial global + paywall + agente en vivo**. El sustrato pasa de **SQLite mono-usuario y todo síncrono** a **Postgres multi-tenant con RLS, cola de jobs, workers y presupuestos con kill-switch**. El guard clause sigue existiendo en v2 (P06 lo distingue explícitamente del paywall), pero deja de ser el clímax.

2. **Hay una tercera brecha que ninguno de los dos documentos reconoce: el código actual está por debajo de lo que v1 ya promete.** El repo es un esqueleto de ~880 líneas de Python sobre **3 productos escritos a mano** (`data/` pesa 6 KB). No hay embeddings, no hay DuckDB, no hay ETL masivo, no hay `contratos/`, no hay `datasets/`, el cost-meter está en `0.0` fijo y las etapas 4 y 5 no son etapas sino campos de un único prompt. Ver §4: 17 puntos con archivo:línea.

3. **Son tres frentes, no uno.** *Sanear* la deuda de v1 (§4), *reestructurar* para tenancy y paywall (§5), y *construir* lo genuinamente nuevo (MIM, agente, cascada, cola). v2 completo son **≈13 semanas** (§12), contra las 6-9 que declaraba v1; v2 no declara cronograma.

**Decisión tomada (§6): la demo del CDR es en ≤4 semanas.** El plan comprometido es por tanto el de **§7**, con alcance recortado: informe gratuito completo + paywall + premium + multi-tenant con RLS, todo sobre datos reales de los 5 insumos. **El agente (P11) y el MIM completo (P10) se presentan como diseño ya decidido en los ADR, no como demo** — el detalle de cómo se presenta está en §8 y el guion revisado en §9. Alcanzables 10 de las 13 pruebas.

> **Arreglar hoy, cuesta 10 minutos:** `markdown`, `requests` y `xhtml2pdf` se usan sin estar declarados en `pyproject.toml` (§4, punto 19). En una máquina limpia el MVP no arranca.

---

## 1. Diff de alcance — documento v1 vs propuesta v2

| Dimensión | v1 (MVP Lite) | v2 (walking skeleton) | Tipo de cambio |
|---|---|---|---|
| **Propósito** | Demo del flujo de valor; "no una plataforma terminada" | Código real de producción = fase 1 del ADR-003 con datos reducidos; sustentar firma del CDR | **Reencuadre** |
| **Etapas del DAG** | 1-3 + informe simple (4 y 5 diseñadas pero colapsadas) | 6 etapas reales: 1 · 2a · **2b MapaComercial (nueva)** · 3 · 4 · 5 · 6 | **Ampliación + split** |
| **Entidad central** | `ProductoExistente` (id, nombre, categoría, ingredientes, fecha) | + **`ProductoEnMercado`** (insumo, producto, país, marca, precioRango, fuente, url, fecha) | **Nueva** |
| **Clímax de la demo** | Guard clause 0-2 productos (cáscara de mango) | Mapa comercial + paywall + agente en vivo + panel de costos | **Reencuadre** |
| **Insumos piloto** | 7 cultivos: palto, espárrago, arándano, mango, piquillo, banano, uva | 5: arándano, palta, espárrago, mango, **quinua** | **Reemplazo** (entran quinua; salen piquillo, banano, uva) |
| **Monetización** | Ninguna | **Paywall**: gratuita = 1·2a·2b·3 con informe parcial; premium = + 4·5 | **Nueva** |
| **Estado de app** | SQLite local (`agroscout.db`, WAL) | **PostgreSQL (Supabase)** + RLS por organización | **Migración** |
| **Auth / tenancy** | Tabla `usuarios`, 1 usuario, sin organizaciones | Supabase auth + **`PoliticaDeSuscripcion`** + planes + 2 organizaciones demo + RLS | **Nueva** |
| **Cascada de costo** | No existe | Puerto **`DescubrimientoComercial`**: N1 snapshot (real) · N2 API licenciada (**stub**) · N3 agente (real) · parámetro `nivel_maximo_costo` | **Nueva** |
| **Agente web** | No existe | **`AgenteInvestigadorComercial`**: Pydantic AI + Tavily (fallback Brave) + trafilatura + glm-5.2 tool-use | **Nueva** |
| **Cuarentena de datos** | No existe | **`staging_agente`**: `provenance=agente`, `no_verificado`, TTL, **grounding check**, promoción manual → `catalogo_comercial` | **Nueva** |
| **Jobs / workers** | Todo síncrono en el request | **`procrastinate`** + 1 worker (agente · reportes · ETL) + eventos de progreso al panel | **Nueva** |
| **Presupuestos** | No existen | 3 niveles: US$0.25/run · US$2/tenant·mes · US$10 global·mes + **kill-switch** → degrada a "sin dato", nunca error | **Nueva** |
| **Cost-meter** | Solo tokens en SQLite | Costo en US$ **por etapa y por tenant**, visible en panel, con cuotas por plan | **Ampliación** |
| **MIM** | No existe | Taxonomía CITE v0.1 (≤5 categorías, ~30 claims, ~50 ingredientes) + normalización LLM con schema + motor de tendencias DuckDB (≥8 trimestres, % de cambio, marcas nuevas) | **Nueva** |
| **Salidas** | PDF (WeasyPrint) | + **deck PPTX** de tendencias + ficha `ProductoEnMercado` | **Ampliación** |
| **Búsqueda** | bge-m3 (CPU) + LanceDB sobre subset OFF+USDA | Vectores + **DuckDB**, sin LLM, **p95 < 2 s** | **Ampliación** |
| **Fuentes** | OFF, USDA, openFDA (live), base documental propia (Codex/DIGESA/EFSA) | OFF subset (base del MIM) · USDA Branded · **Open Prices** · **Comtrade** · **eCFR** · DIGESA (OCR) · fichas CITE · agente live. Mintel y Trend Hunter **excluidos por ToS** | **Ampliación + exclusión explícita** |
| **Snapshots** | `datasets/AAAA-MM/` + manifest (diseñado) | `datasets/2026-07/` local + `version_taxonomia=0.1` | **Igual (ninguno construido)** |
| **Modelos LLM** | glm-4.7-flashx (E1) + glm-4.7 (E3) · <US$0.01/consulta | glm-4.7-flashx (E1) + glm-4.7 (E3) + **glm-5.2 flagship** (E4 y agente) · US$0.01-0.05/consulta | **Ampliación de gama** |
| **Plan de pruebas** | `evals/set_dorado.yaml`, mínimo 5 casos, DoD de 6 puntos | **P01-P13** en verde + CI (golden set ~30 productos, validación de schema, smoke test del DAG) | **Ampliación** |
| **Plan B sin internet** | Flag `--offline` sirviendo desde `cache_llm` | **No aparece** — y el agente en vivo (P11) lo hace imposible tal cual | **Regresión / hueco** |
| **Cronograma** | 6-9 semanas, con fases | **No declarado** | **Hueco** |
| **Guion de demo** | 10-12 min, 4 bloques | 15 min, 6 bloques | Ampliación |
| **Infra diferida** | Servidor dedicado en fase institucional | Explícito: LB + réplicas, object storage + CDN, mistral-embed, ingesta regulatoria completa, promoción por muestreo | Mejor delimitado |

---

## 2. Diff del DAG, etapa por etapa

| v2 | v1 (documento) | Código hoy | Qué falta |
|---|---|---|---|
| **1 · InterpretarInsumo** — glm-4.7-flashx, sinónimos ES/EN, 2ª llamada = cache hit | Etapa 1, igual | ✅ Existe ([interpretar_insumo.py](casos_de_uso/etapas/interpretar_insumo.py)) pero usa **glm-5.2**, no flashx | Bajar de modelo; incluir modelo en la clave de cache |
| **2a · MatchProductos** — vectores + DuckDB, sin LLM, p95 < 2 s | Etapa 2 `BuscarProductosSimilares` — bge-m3 + LanceDB | ⚠️ Solo **LanceDB FTS** sobre 3 filas; **sin embeddings, sin DuckDB** | Embeddings reales, DuckDB, subset de 5×(50-200) productos, medición p95 |
| **2b · MapaComercial ★** — puerto N1, país·marca·precio·URL, `null` nunca inventado | **No existe en v1** | ❌ | Entidad `ProductoEnMercado`, tabla `catalogo_comercial`, puerto en cascada, fuentes de precio (Open Prices/Comtrade) |
| **3 · InsightMercado** — glm-4.7, cada afirmación con cita a un dato | Etapa 3 `GenerarInsightDeMercado`, igual | ⚠️ Existe pero **fusiona 3, 4 y 5** en un solo prompt/objeto | Separar; validar "1 cita por afirmación" (P05) |
| **PAYWALL** — early return con informe parcial | **No existe en v1** | ❌ | `PoliticaDeSuscripcion`, planes, entitlement en frontera de aplicación |
| **4 · Formulación** — minería DuckDB + glm-5.2, premium | Etapa 4 `FormulacionHipotesis` (diseñada) | ⚠️ Es el campo `hipotesis_formulacion` del insight — **no es etapa**: sin auditoría, sin costo, sin posibilidad de paywall | Extraer a etapa propia dentro de `etapa()`; minería DuckDB real |
| **5 · Regulación** — eCFR piloto + DIGESA, citas verificables, premium | Etapa 5 `VerificacionRegulatoria` (RAG + openFDA) | ⚠️ Es el campo `verificacion_regulatoria`; el contexto se arma **fuera** del envoltorio `etapa()` ([evaluar_insumo.py:17-23](casos_de_uso/evaluar_insumo.py#L17)) → no auditado, no cacheado, sin costo | Extraer a etapa; corpus eCFR + DIGESA con OCR; verificación de citas |
| **6 · InformeScout** — PDF por **job de worker**, evento en panel, auditoría con costo por etapa | Etapa 6 `EmitirInformeSimple` — Jinja2 + WeasyPrint síncrono | ✅ PDF funciona; ❌ no es job, no hay evento, `costo_usd=0.0` fijo | Cola + worker + eventos + costo real |

**Nota de consistencia del documento v2:** §2 y el SVG dicen "las 6 etapas reales", pero el DAG dibuja **7 nodos** (1, 2a, 2b, 3, 4, 5, 6). Conviene fijar la numeración antes de que se convierta en el contrato de auditoría (`etapas_ejecucion.etapa` es un `INTEGER` hoy; con 2a/2b hay que decidir si pasa a texto o a `2.1/2.2`).

---

## 3. Lo que ya está construido y se conserva

Esto es real y v2 lo reutiliza sin cambios estructurales:

- **Clean Architecture con la regla de dependencia respetada**: `dominio/` sin imports externos, `casos_de_uso/` sobre `puertos/`, adaptadores intercambiables, `api/` solo transporte, frontend solo HTTP. Es lo más valioso del repo: el cambio SQLite→Postgres y el agente entran como **adaptadores nuevos**, no como reescritura.
- **El envoltorio único `etapa()`** ([ejecutor.py](casos_de_uso/etapas/ejecutor.py)): cache → llamada → validación → auditoría en un solo lugar. Es exactamente el gancho donde entra el cost-meter por tenant y el presupuesto. Ya captura tokens de entrada/salida desde LiteLLM.
- **Contratos Pydantic por etapa** (`InsumoInterpretado`, `ResultadoBusqueda`, `InsightDeMercado`, `InformeScout`).
- **Puertos definidos**: `RedactorLLM`, `CatalogoProductos`, `CacheLLM`, `RepositorioInformes`, `Auditoria`, `VerificadorRegulatorio`.
- **Generación de PDF** funcionando (159 líneas; hay PDFs en `informes/`) — aunque el motor real es `markdown` + `xhtml2pdf.pisa`, no Jinja2 + WeasyPrint (ver punto 18 de §4).
- **SPA Vue 3 + Vite** con login, búsqueda, resultado y panel de tokens (5 componentes, ~840 líneas).
- **Adaptador openFDA** y RAG normativo sobre LanceDB FTS — sirven como base del corpus regulatorio de la etapa 5.
- **`evals/`** con runner y set dorado (2 casos).

---

## 4. Deuda oculta — lo que v1 promete y el código no hace

Esto **no** está en la diferencia v1↔v2 y por eso es el riesgo más fácil de subestimar. Cada punto bloquea al menos una prueba de P01-P13.

### Datos y búsqueda

1. **No hay embeddings.** `indexar_vectores.py` crea una tabla LanceDB y un índice **FTS**; nunca calcula vectores ([indexar_vectores.py:40-43](etl/indexar_vectores.py#L40)). `busqueda_lancedb.py` consulta con `query_type="fts"` ([busqueda_lancedb.py:22](adaptadores/busqueda_lancedb.py#L22)). `sentence-transformers` no está en `pyproject.toml`. → Bloquea P03.
2. **DuckDB es dependencia declarada y nunca importada** (0 usos en todo el código). → Bloquea 2a, 4 y todo el motor de tendencias.
3. **El ETL no filtra un export masivo: hace una búsqueda live de 50 resultados** en la API web de OFF, con un fallback de **2 productos escritos a mano** ([cargar_off.py:5-32](etl/cargar_off.py#L5)). `data/` = 6 KB total: 2 productos OFF, 1 USDA, 4 normativas. → Bloquea P03, P04, P10.
4. **`usa_insumo_directo` está fijo en `True`** para todo producto ingerido ([cargar_off.py:45](etl/cargar_off.py#L45)). Es decir: `n_directos` == total de resultados. El guard clause —"el momento clave de la demo" según v1— **solo dispara porque el dataset tiene 2 filas**. Con un subset real de 50-200 productos nunca disparará.
5. **`fecha_dato` se inventa: `datetime.date.today()`** ([busqueda_lancedb.py:33](adaptadores/busqueda_lancedb.py#L33)). Contradice directamente el contrato de v1 ("obligatoria: toda cita lleva fecha") y el criterio de v2 "cero valores inventados: todo dato con fuente+url+fecha o `null`". → Bloquea P04 y el criterio de MVP listo.
6. **No existe `datasets/AAAA-MM/` ni manifest.** `snapshot_version="2026-07"` es una cadena fija en [main.py:51](api/main.py#L51) sin nada detrás. → Bloquea la reproducibilidad que sostiene el argumento de auditoría.
7. **No existe `contratos/`** con los JSON Schema, que es el punto 5 del Definition of Done de v1.
8. **El entry point del ETL está roto**: `pyproject.toml` declara `etl = "etl.indexar_vectores:main"` y el módulo define `indexar_vectores()`, no `main`.

### Costos y modelos

9. **El cost-meter no existe:** `costo_usd=0.0` está fijo en las dos rutas de `etapa()` ([ejecutor.py:52,58](casos_de_uso/etapas/ejecutor.py#L52)). Solo hay tokens. → Bloquea P13 y los presupuestos de P12 completos.
10. **Todo corre con `glm-5.2`**, el modelo más caro, en ambas etapas LLM ([redactor_glm.py:19,51](adaptadores/redactor_glm.py#L19)) — contra el diseño de v1 (flashx + 4.7) y el de v2. El argumento de "<US$0.01 por consulta" no se sostiene con la configuración actual.
11. **El proveedor real es Huawei ModelArts MaaS**, no Z.ai: `HUAWEI_MAAS_API_KEY` / `modelarts-maas.com` ([main.py:31-32](api/main.py#L31)). **Ambos documentos dicen Z.ai y `ZAI_API_KEY`.** Hay que decidir cuál es la verdad y alinear docs, `.env.example` y presupuesto.
12. **La clave de cache no incluye el modelo** ([ejecutor.py:14](casos_de_uso/etapas/ejecutor.py#L14)): cambiar de modelo sirve respuestas viejas. Y el `INSERT` solo llena `clave_hash` y `respuesta_json` — las columnas `etapa`, `modelo`, `snapshot_version` quedan siempre en NULL ([cache_sqlite.py:33-36](adaptadores/cache_sqlite.py#L33)).
13. **El modo `--offline` no existe.** `AGROSCOUT_OFFLINE` se lee en [main.py:33](api/main.py#L33) y **nunca se usa**. El plan B de la demo de v1 es papel.

### Seguridad y multi-tenancy (prerrequisito de P01)

14. **Contraseñas en texto plano.** `update_schema.py` inserta `cite2026` en la columna `password_hash` y el login compara literalmente ([main.py:65](api/main.py#L65), [update_schema.py:22](update_schema.py#L22)).
15. **El token es una cadena fija:** `"mvp-real-db-token-123"` ([main.py:71](api/main.py#L71)). No es un JWT, no expira, no identifica al usuario.
16. **Ningún endpoint está protegido.** `/consultas`, `/informes/{id}` y `/ejecucion/{id}/tokens` no verifican nada; `/informes/{id}` sirve cualquier PDF por id. Hoy **no hay frontera de tenant que RLS pueda defender**: P01 no es una migración de base de datos, es construir la autorización desde cero.
17. **CORS `allow_origins=["*"]` con `allow_credentials=True`** ([main.py:23-29](api/main.py#L23)).

### Reproducibilidad del entorno

18. **El motor de PDF no es el que dicen los documentos.** La clase se llama `InformeWeasyPrint` pero el PDF lo genera `markdown` + **`xhtml2pdf.pisa`** ([informe_weasyprint.py:148-151](adaptadores/informe_weasyprint.py#L148)). `weasyprint` y `jinja2` están declarados como dependencias y **nunca se importan**. Decidir uno (xhtml2pdf es más pobre en CSS; WeasyPrint es lo que ambos documentos prometen) antes de invertir en el diseño del deck y las fichas.
19. **Tres paquetes se usan sin estar declarados:** `markdown`, `requests` y `xhtml2pdf` no están en `pyproject.toml`. Un `uv sync` en máquina limpia **no arranca**. Es el riesgo más tonto y más probable del día de la demo.
20. **`sentence-transformers` está instalado en el `.venv`** (arrastrado por otra dependencia) pero ni declarado ni usado — probablemente el origen de la impresión de que "los embeddings ya están".

---

## 5. Lo que hay que construir desde cero para v2

Ninguno de estos existe ni en el código ni en v1:

| Bloque | Piezas |
|---|---|
| **Tenancy** | Organizaciones, planes, `PoliticaDeSuscripcion`, RLS en Postgres, 2 cuentas demo en orgs distintas, rate-limit por plan |
| **Paywall** | Early return en la frontera de aplicación, informe parcial premium-aware, distinción explícita vs el guard técnico |
| **Núcleo comercial** | `ProductoEnMercado`, `catalogo_comercial`, etapa 2b, puerto `DescubrimientoComercial` con cascada N1/N2-stub/N3 y `nivel_maximo_costo` |
| **Agente** | Pydantic AI + Tavily/Brave + trafilatura + glm-5.2; toolset `buscar_web → abrir_url → extraer_producto`; salida validada contra schema; robots.txt + allowlist + rate-limit por dominio + user-agent identificado; idempotencia `insumo+país+mes` |
| **Cuarentena** | `staging_agente` con `provenance` / `no_verificado` / TTL, grounding check (todo valor literal en el HTML de origen), reglas de dominio de rangos de precio, promoción manual |
| **Presupuestos** | Topes run / tenant / global, kill-switch, degradación a "sin dato", estado de run `parcial`, sin reintento automático |
| **Cola** | `procrastinate` sobre Postgres, 1 worker, jobs de agente/reportes/ETL, eventos de progreso persistidos |
| **MIM** | Taxonomía CITE v0.1 versionada, normalización LLM con anti-corruption layer, motor de tendencias DuckDB con ≥8 trimestres, metodología declarada (proxy = fecha de alta en OFF) |
| **Reportes** | Generador de deck PPTX + ficha `ProductoEnMercado`, diseño visual propio |
| **Fuentes nuevas** | OFF bulk, USDA Branded con key, Open Prices, Comtrade, eCFR, DIGESA con OCR, fichas CITE |
| **Panel CITE** | Progreso de jobs, cost-meter por etapa y tenant, listado de informes, kill-switch. **v2 no presupuesta el trabajo de frontend que esto implica** |
| **CI** | Golden set de ~30 productos para el extractor, validación de schema, smoke test del DAG premium |

---

## 6. Decisiones

### Cerradas (2026-07-29)

| # | Decisión | Consecuencia |
|---|---|---|
| **D1** | **Demo del CDR en ≤4 semanas** (objetivo: 2026-08-28) | El plan pasa de 13 semanas a **4**. Alcance replanteado en §7: agente y MIM se presentan como **diseño**, no como demo. 10 de 13 pruebas alcanzables |
| **D2** | **Huawei ModelArts MaaS es el proveedor real** | Alinear ambos documentos y `.env.example` (`HUAWEI_MAAS_API_KEY`, no `ZAI_API_KEY`). **Verificar el día 1** qué modelos de la familia GLM expone: si no hay un modelo barato tipo `glm-4.7-flashx`, el costo por consulta del pitch sube y hay que recalcularlo ahora, no en la semana 4 |
| **D3** | **PostgreSQL autoalojado, sin Supabase** | Auth y RLS son trabajo propio: bcrypt + JWT + políticas RLS a mano con `SET LOCAL`. **≈3 de los 5 días de la semana 3.** `procrastinate` seguiría funcionando cuando entre, pero pierde el auth gestionado y el PITR de Supabase — planificar backups |

### Abiertas

| # | Decisión | Recomendación |
|---|---|---|
| D4 | **¿La regulación se va entera a premium?** Hoy el informe gratuito ya incluye `verificacion_regulatoria`; ADR-001 hablaba de "regulación básica" en la etapa 3 gratuita. | Dejar un párrafo regulatorio básico en el informe gratuito y el dossier con citas verificables en premium — quitarle algo que hoy funciona al plan gratuito debilita la demo |
| D5 | **Plan B sin internet.** El agente en vivo (P11) y el paso 5 del guion lo requieren. | Mantener `--offline` para las etapas 1-6 (cache real, que hoy no existe) y grabar un run del agente como respaldo declarado, no como resultado precocinado |
| D6 | **Numeración de etapas con 2a/2b** en `etapas_ejecucion.etapa` (hoy `INTEGER`). | Pasar a `TEXT` con `'1','2a','2b','3','4','5','6'` antes de acumular historial |
| D7 | **Insumos piloto: entra quinua, salen piquillo/banano/uva.** | Confirmar con el CITE que los 5 son los prioritarios de Chavimochic antes de correr el ETL (es la carga más caras del plan) |
| D8 | **Alcance de frontend del Panel CITE.** No presupuestado en v2. | Presupuestar explícitamente (~1.5 semanas) o recortar el panel a lo mínimo que P09/P12/P13 exigen |
| D9 | **Motor de PDF: xhtml2pdf (lo que corre) o WeasyPrint (lo que dicen los documentos).** v2 añade deck PPTX y ficha con "diseño visual propio". | WeasyPrint: el CSS de xhtml2pdf no va a sostener un entregable que se compara con Mintel. Y renombrar la clase o el archivo, hoy mienten |

---

## 7. Plan de 4 semanas (alcance comprometido)

**Regla:** cada semana termina con pruebas de P01-P13 en verde, no con código escrito.

**Alcance:** el informe gratuito completo de v2 (1 · 2a · 2b · 3) + paywall + premium (4 · 5) + multi-tenant con RLS + cost-meter por tenant, todo sobre **datos reales de los 5 insumos piloto**. El agente (P11), el MIM completo (P10) y la cola de jobs se presentan como diseño ya decidido en los ADR.

### Semana 1 · Saneamiento y separación de etapas
*Objetivo: que nada de lo que se muestre sea inventado, y que el paywall sea técnicamente posible.*

- **Día 1, bloqueante:** verificar qué modelos GLM expone Huawei MaaS y recalcular el costo por consulta del pitch (D2). En paralelo, **arrancar la descarga del export masivo de OFF** — es la tarea con más varianza del plan y no puede empezar en la semana 2.
- Declarar `markdown`, `requests`, `xhtml2pdf`; decidir motor de PDF (D9); verificar `uv sync` en máquina limpia.
- **Cost-meter real:** `costo_usd` = tokens × tarifa por modelo, por etapa, con las tarifas en configuración.
- `fecha_dato` proveniente de la fuente; `null` cuando no hay. Eliminar `date.today()`.
- `usa_insumo_directo` derivado del texto de ingredientes → el guard clause vuelve a ser real.
- **Separar etapas 4 y 5** de `InsightDeMercado` en etapas propias dentro de `etapa()`. `etapas_ejecucion.etapa` a `TEXT` (D6). Es el prerrequisito estructural del paywall.
- Modelo por etapa; añadir el modelo a la clave de cache; llenar las columnas de `cache_llm`.
- Auth real: bcrypt + JWT con expiración + dependencia de autorización en **todos** los endpoints. Cerrar CORS.
- `contratos/` generado con `model_json_schema()` en CI.

**Salida:** una consulta reconstruible al 100% desde la auditoría, con costo en US$ por etapa y sin un solo valor inventado.

### Semana 2 · Datos reales de los 5 insumos
*La inversión de mayor retorno: hoy todo corre sobre 3 filas escritas a mano.*

- ETL sobre el **export masivo** de OFF → filtro a arándano · palta · espárrago · mango · quinua → 50-200 productos por insumo con marca, país, claims y fecha reales.
- USDA Branded subset con `USDA_API_KEY` propia (hoy hay fallback a `DEMO_KEY`).
- **Embeddings bge-m3** + índice vectorial (declarar `sentence-transformers`); medir p95 → **P03**.
- `datasets/2026-07/` + `manifest.json` (fecha de descarga, filas y hash por fuente). `snapshot_version` deja de ser una cadena fija.
- Corpus regulatorio mínimo: aditivos eCFR del piloto + 2-3 normas DIGESA → base de **P08**.
- Set dorado ampliado a 5 casos con datos reales.

**Salida:** P03 en verde y los 5 insumos respondiendo de punta a punta con datos que el CITE puede verificar en el navegador durante la demo.

### Semana 3 · Multi-tenant en Postgres propio + paywall
*≈3 de los 5 días son auth y RLS a mano: es el costo de D3.*

- Postgres autoalojado; migrar `ejecuciones`, `etapas_ejecucion`, `cache_llm`, `informes`; añadir `organizaciones`, `usuarios`, `planes`.
- **RLS** con `SET LOCAL app.current_org` por request sobre 4 tablas; rol de aplicación sin `BYPASSRLS`. Prueba negativa: consulta cruzada devuelve 0 filas → **P01**.
- `PoliticaDeSuscripcion` en la frontera de aplicación; `nivel_maximo_costo` derivado del plan.
- **Paywall** como early return con informe parcial, distinguible del guard técnico → **P06**.
- Cost-meter por tenant + cuota por plan + kill-switch sobre las etapas LLM → **P13** y **P12 parcial**.
- Dos cuentas demo en organizaciones distintas.

**Salida:** P01, P02, P06, P13 en verde; P12 parcial.

### Semana 4 · Mapa comercial, panel mínimo y ensayo

- Entidad `ProductoEnMercado` + tabla `catalogo_comercial`, con `fuente+url+fecha` **por campo**.
- **Etapa 2b** sobre el snapshot (N1): país, marca, presentación, URL y fecha reales desde OFF. **El precio va a salir mayormente `null`** — y eso se dice en voz alta (ver §9, bloque 2).
- Puerto `DescubrimientoComercial` con la **cascada completa en la interfaz** y N2/N3 como stubs declarados que registran "nivel no disponible en este MVP": la arquitectura del ADR-001 queda demostrada aunque el agente no corra.
- Validación de schema "campo sin dato = `null`" → **P04**. Validador de "cada afirmación con cita a un dato entregado" → **P05**.
- Etapas 4 y 5 sobre datos reales: formulación sobre el snapshot (sin minería DuckDB), regulación con citas al corpus → **P07/P08 degradados**.
- Panel mínimo: costo por consulta y por tenant, historial, informes.
- CI: golden set de ~30 productos para el **match** (el del extractor no aplica sin agente) + validación de schema + smoke test del DAG premium.
- Ensayo del guion de §9 y verificación del plan B `--offline`.

**Salida:** 10/13 con P09 degradado; P10 y P11 presentados como diseño.

---

## 8. Qué queda fuera y cómo se presenta

| Pieza | Por qué se difiere | Cómo se presenta en la demo |
|---|---|---|
| **Agente + cuarentena (P11)** | 2.5 semanas y la pieza de mayor riesgo técnico y legal | Mostrar el puerto en cascada con N3 declarado y **los campos `null` del mapa comercial como el hueco exacto que el agente llena**. Pedir en el CDR el presupuesto acotado (US$0.25/run, US$2/tenant·mes, US$10 global·mes) |
| **MIM completo (P10)** | Requiere ≥8 trimestres normalizados y la taxonomía construida con el CITE | Convertirlo en el **pedido central del CDR**: "la taxonomía es el moat y lo construimos con ustedes". Un entregable conjunto convence más que un deck a medias |
| **Cola `procrastinate` + workers (P09 pleno)** | El PDF síncrono en <15 s alcanza para la demo | Declarar que la cola es fase 1 del ADR-003 y que el diseño ya la contempla |
| **Presupuesto de agente en 3 niveles (P12 pleno)** | Sin agente no hay run que presupuestar | Demostrar el tope por tenant y el kill-switch sobre las etapas LLM |
| **Deck PPTX, OCR de DIGESA, minería DuckDB de formulación, UI de promoción** | Recortes de §10 | No se mencionan como faltantes; están en el roadmap del ADR |

> **Desviación que hay que declarar internamente.** Con la cola y el agente diferidos, el MVP **ya no es** "la fase 1 del ADR-003 con datos reducidos" que promete §1 de `MVP-AgroScout-IA.md`. Es la fase 1 **menos la cola y menos el nivel 3**. Conviene corregir esa frase en el documento antes de mostrarlo: si se deja como está, el CITE lee una promesa que el código no cumple, y eso es exactamente lo que el principio de walking skeleton buscaba evitar.

---

## 9. Guion de demo revisado (15 min)

Reemplaza al de `MVP-AgroScout-IA.md` §5, cuyos bloques 4 (MIM) y 5 (agente) son 7 de los 15 minutos.

| # | Min | Contenido | Pruebas |
|---|---|---|---|
| 1 | 2 | Login `demo-gratuita` → "arándano" → etapas 1-3 con productos reales de OFF, cada uno con fuente, URL y fecha **verificables en vivo en el navegador** | P01-P03, P05 |
| 2 | 3 | Mapa comercial: país, marca, presentación, URL. Señalar los campos en `null`: *"no inventamos precios; ese hueco es exactamente lo que el nivel 3 llena, y aquí está su presupuesto acotado"* | P04 |
| 3 | 2 | Intento de acceder a formulación → paywall con informe parcial | P06 |
| 4 | 3 | Login `demo-premium` → dossier: formulación + regulación con citas al corpus + PDF | P07-P09 |
| 5 | 2 | **RLS en vivo:** consulta cruzada entre organizaciones → 0 filas. El argumento del contrato multi-cooperativa | P01 |
| 6 | 2 | Panel: costo por consulta y por tenant, cuota por plan, kill-switch. *"El gasto está acotado por diseño"* | P12-P13 |
| 7 | 1 | Roadmap: agente y MIM **ya decididos** en ADR-002/003. El pedido: taxonomía con el CITE, insumos prioritarios, presupuesto del agente | — |

El clímax se mueve del guard clause (v1) y del agente en vivo (v2) a **la honestidad del dato + el paywall funcionando + RLS demostrable**. Es el argumento correcto para una firma de contrato multi-organización.

---

## 10. Riesgos del plan de 4 semanas

| Riesgo | Mitigación |
|---|---|
| **El ETL masivo de OFF es la tarea con más varianza** (~9 GB de descarga, filtrado, indexado). Si se atrasa, todo se atrasa. | Arrancarlo el **día 1 de la semana 1**, en paralelo con el saneamiento. No esperar a la semana 2 |
| **La cobertura de precio en OFF/Open Prices para los 5 insumos es incierta.** | Verificar con una muestra en la semana 1. Si es ~0%, el bloque 2 del guion cambia de tono: de "aquí están los precios" a "aquí está el hueco, cuantificado" |
| **Auth + RLS a mano consume 3 de los 5 días de la semana 3** (costo de D3). | Si se desborda: RLS sobre 2 tablas (`ejecuciones`, `informes`) y filtrado por aplicación en el resto, **declarándolo** |
| **Si Huawei MaaS no expone un modelo barato tipo flashx**, el costo por consulta del pitch sube. | Verificar el día 1 y recalcular la proyección antes de imprimir cifras |
| **4 semanas no admiten imprevistos.** | Orden de sacrificio: OCR de DIGESA → minería DuckDB de formulación → panel a lo mínimo → embeddings (volver a FTS, declarándolo) |
| **Postgres autoalojado sin PITR de Supabase.** | `pg_dump` diario + retención de 7 días antes de cargar el snapshot; probar una restauración antes de la demo |

---

## 11. Apéndice — plan completo post-firma (13 semanas)

Este era el plan sin restricción de fecha. Sirve como roadmap del contrato: las fases F4 y F5 son lo que se difiere por D1.

Regla del plan: **cada fase termina con pruebas de P01-P13 en verde**, no con código escrito. Las fases F0 y F1 no aportan features visibles pero sin ellas ninguna prueba de v2 es verificable.

### F0 · Saneamiento del walking skeleton — *~1.5 sem*
Convierte el esqueleto en algo auditable. Sin esto, P04, P05, P12 y P13 son imposibles de demostrar honestamente.

- Cost-meter real: `costo_usd` calculado por etapa desde tokens × tarifa del modelo (sustituye el `0.0` fijo).
- `fecha_dato` proveniente de la fuente; si no hay dato → `null`. Eliminar `date.today()`.
- `usa_insumo_directo` derivado del texto de ingredientes (no hardcodeado) → el guard clause vuelve a ser real.
- **Separar etapas 4 y 5** de `InsightDeMercado` en etapas propias, ambas dentro del envoltorio `etapa()`. Prerrequisito estructural del paywall.
- Modelo por etapa (flashx en E1, 4.7 en E3, 5.2 solo en E4 y agente); añadir modelo a la clave de cache y llenar las columnas de `cache_llm`.
- Auth de verdad: bcrypt, JWT con expiración, dependencia de autorización en **todos** los endpoints. Cerrar CORS.
- Generar `contratos/` con `model_json_schema()` en CI.
- `datasets/2026-07/` con `manifest.json` (fecha de descarga, filas, hash por fuente) y `version_taxonomia`.
- Arreglar el entry point `uv run etl`; implementar de verdad el adaptador `--offline`.
- Declarar `markdown`, `requests` y `xhtml2pdf` en `pyproject.toml`; quitar `jinja2`/`weasyprint`/`duckdb` si no se van a usar, o usarlos (D9). Verificar `uv sync` en máquina limpia.
- Alinear los documentos con el proveedor LLM real (D2).

**Salida:** una consulta reconstruible al 100% desde la auditoría, con costo en US$ por etapa y sin un solo valor inventado.

### F1 · Datos reales del piloto — *~2 sem*
- ETL sobre el **export masivo** de OFF → filtro a los 5 insumos → 50-200 productos por insumo, con marca, país y claims. A DuckDB.
- USDA Branded subset (`USDA_API_KEY`), Open Prices, Comtrade.
- **Embeddings bge-m3 reales** + índice vectorial (hoy solo FTS); medir p95 → **P03**.
- Histórico de **≥8 trimestres** (prerrequisito del MIM).
- Corpus regulatorio mínimo: aditivos eCFR del piloto + 2-3 normas DIGESA con OCR → base de **P08**.

**Salida:** P03 en verde; datos suficientes para que 2b, 4, 5 y el MIM tengan de qué hablar.

### F2 · Multi-tenant y paywall — *~2 sem*
- Postgres/Supabase; migrar `ejecuciones`, `etapas_ejecucion`, `cache_llm`, `informes` + tablas nuevas de organizaciones y planes. RLS por organización.
- `PoliticaDeSuscripcion` en la frontera de aplicación; `nivel_maximo_costo` derivado del plan.
- Dos cuentas demo en organizaciones distintas → **P01**.
- Paywall como early return con informe parcial → **P06**.
- Cost-meter por tenant y cuotas por plan → **P13** (parcial, se cierra en F4).

**Salida:** P01, P06 y P02 (cache hit con clave correcta) en verde.

### F3 · Mapa comercial y puerto en cascada — *~1.5 sem*
- Entidad `ProductoEnMercado` + tabla `catalogo_comercial` con `fuente+url+fecha` por campo.
- Etapa **2b MapaComercialGlobal** sobre el snapshot (N1).
- Puerto `DescubrimientoComercial`: N1 real, **N2 stub declarado**, N3 como hueco para F4; obedece `nivel_maximo_costo`.
- Validación de "campo sin dato = `null`" en el schema → **P04**.
- Validador de "cada afirmación con cita a un dato entregado" en la etapa 3 → **P05**.

**Salida:** P04 y P05 en verde; el informe gratuito de v2 completo (1·2a·2b·3).

### F4 · Cola, worker y agente — *~2.5 sem* (la fase más riesgosa)
- `procrastinate` + 1 worker; etapa 6 pasa a ser job; eventos de progreso al panel → **P09**.
- `AgenteInvestigadorComercial` con Pydantic AI, Tavily (+ Brave), trafilatura, glm-5.2; toolset de 3 herramientas; salida validada → **P11**.
- Cumplimiento de acceso como componente: robots.txt, allowlist/denylist, rate-limit por dominio, user-agent identificado.
- `staging_agente` con provenance/TTL + **grounding check** + reglas de rango de precio + promoción manual → **P11**.
- Presupuestos run/tenant/global + kill-switch + estado `parcial` sin reintento → **P12**.
- Golden set de ~30 productos en CI para el extractor.

**Salida:** P09, P11, P12, P13 en verde.

### F5 · MIM y reportes — *~2 sem*
- Taxonomía CITE v0.1 (≤5 categorías, ~30 claims, ~50 ingredientes), versionada en el snapshot.
- Normalización LLM contra schema (anti-corruption layer), versión de modelo fijada por snapshot.
- Motor de tendencias en DuckDB: series por trimestre, % de cambio, marcas e ingredientes nuevos, determinista y sin LLM.
- Generador de deck PPTX + ficha `ProductoEnMercado`, con **metodología declarada** (proxy: fecha de alta en OFF).
- Etapas 4 y 5 sobre datos reales: minería DuckDB para formulación, citas verificables para regulación → **P07, P08**.

**Salida:** P07, P08, P10 en verde.

### F6 · Panel, CI y ensayo — *~1.5 sem*
- Panel CITE: progreso de jobs, cost-meter por etapa y tenant, listado de informes, kill-switch (ver D8).
- CI completa: golden set + validación de schema + smoke test del DAG premium.
- Métricas de `MVP-AgroScout-IA.md` §7 instrumentadas (latencia p95 por etapa, cache hit, cobertura de precio, % de `null`).
- Guion de 15 min ensayado con datos reales; plan B de D5 verificado.

**Salida:** 13/13 en verde y los 6 criterios de "MVP listo".

---

## 12. Cronograma completo y matriz de trazabilidad

| Fase | Semanas | Acumulado | Pruebas que cierra |
|---|---|---|---|
| F0 Saneamiento | 1.5 | 1.5 | — (habilita todo) |
| F1 Datos del piloto | 2.0 | 3.5 | P03 |
| F2 Tenancy y paywall | 2.0 | 5.5 | P01, P02, P06 |
| F3 Mapa comercial | 1.5 | 7.0 | P04, P05 |
| F4 Cola y agente | 2.5 | 9.5 | P09, P11, P12, P13 |
| F5 MIM y reportes | 2.0 | 11.5 | P07, P08, P10 |
| F6 Panel, CI, ensayo | 1.5 | **13.0** | 13/13 + DoD |

Con inicio el 2026-08-03 → **finales de octubre 2026**. Por D1 la demo es en 4 semanas, así que este cronograma pasa a ser el roadmap del contrato: F0-F3 comprimidos en §7 y F4-F5 diferidos según §8.

---

## 13. Camino crítico del plan completo

**Orden obligado:** F0 → F1 → F2 → F3 → F4 → F5. F5 (MIM) puede solaparse con F4 si hay dos personas: el MIM solo depende de F1 (datos + trimestres), no del agente.

Si hay que llegar antes, recortar **en este orden**, declarándolo en la demo:

1. **Deck PPTX del MIM** → mostrar la ficha PDF y las series en pantalla, no el deck. (−0.5 sem, degrada P10)
2. **Etapa 4 Formulación con minería DuckDB** → mantener la hipótesis vía LLM sobre el snapshot, sin minería. (−0.5 sem, degrada P07)
3. **Panel CITE** → reducir a las tres vistas que P09/P12/P13 exigen. (−1 sem)
4. **Promoción manual con UI** → hacerla por SQL delante del público, es honesto y v2 ya dice "manual". (−0.5 sem)

**Lo que no se puede recortar sin romper el argumento de la demo:** F0 completa (sin cost-meter real ni fechas reales, "cero valores inventados" es falso y el CITE lo puede pinchar en vivo), P01 (RLS es el requisito de un contrato multi-organización) y P11/P12 (el agente con presupuestos es la respuesta a "¿y cuánto cuesta esto al mes?").

---

*El código actual conserva lo más difícil de conseguir —la arquitectura hexagonal limpia— y le falta casi todo lo que la sostiene con datos. Ese es el trabajo de v2.*
