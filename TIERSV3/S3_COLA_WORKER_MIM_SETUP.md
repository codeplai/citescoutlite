# Semana 3 · COLA PROCRASTINATE + MIM SETUP (F4 P2/2 + F5 P1/2)

**Objetivo:** Worker operacional, jobs de agente/reportes/ETL async, histórico de tendencias iniciado.

**Duración:** 5 días · **Equipo:** Backend (2) + Data (1)

---

## ITEMS SEMANA 3

### 3.1 IMPLEMENTAR PROCRASTINATE WORKER + JOB QUEUE
- **Descripción:** Cola de tareas async sobre Postgres
- **Tareas:**
  - [ ] Instalar procrastinate SDK
  - [ ] Connector a Postgres (ya existe DB en S1)
  - [ ] Crear 3 job definitions:
    - [ ] `job_agente_run(run_id, insumo, país, nivel_maximo_costo)`
    - [ ] `job_mim_etl(snapshot_version)` (correr noche)
    - [ ] `job_informe_pdf(run_id)` (generar PDF async)
  - [ ] Worker: ejecutar en 1 nodo dedicado (puede ser mismo que API, o diferente si hay $)
  - [ ] Retry strategy: exponential backoff (1s, 2s, 4s, 8s), max 3 intentos
  - [ ] Timeout: 5 min por job (agente puede tardar)
  - [ ] Logging: guardar logs en stdout (Prometheus scrape)
- **Duración:** 1.5 días
- **Dependencias:** DB (S1), agente job definition (2.11)
- **DoD:** Worker corre, jobs se encolan, logs en Prometheus

---

### 3.2 CREAR TABLA EVENTOS_JOB Y STREAMING DE PROGRESO
- **Descripción:** Dashboard ve progreso en vivo de jobs (no requiere polling)
- **Tareas:**
  - [ ] Migración SQL: tabla `eventos_job`
    - Campos: `event_id, run_id, job_id, evento ('created','started','progress','completed','failed'), data_json, timestamp`
    - Índice: (run_id, timestamp) para queries rápidas
  - [ ] Callback en procrastinate: al cambiar state de job, insert en eventos_job
  - [ ] WebSocket endpoint en FastAPI: `/ws/run/{run_id}` → stream de eventos
  - [ ] Frontend (Vue 3): conectar a WebSocket, actualizar barra de progreso en tiempo real
  - [ ] Test: enqueue job → ver evento 'created' → job comienza → ver 'started' → termina → 'completed'
- **Duración:** 1.5 días
- **Dependencias:** Procrastinate (3.1), DB (S1)
- **DoD:** WebSocket streaming eventos en vivo, no polling

---

### 3.3 INTEGRAR ETAPA 6 (INFORME PDF) COMO JOB
- **Descripción:** Generar PDF en worker, no en request
- **Tareas:**
  - [ ] Extraer `InformeScout` de etapa 6 a job async:
    ```python
    @job_definition
    def job_informe_pdf(run_id):
        resultado_ejecutable = fetch_run(run_id)
        pdf_bytes = generar_informe_pdf(resultado_ejecutable)
        guardar_en_s3(f"informes/{run_id}.pdf", pdf_bytes)
        actualizar_run(run_id, pdf_url=f"https://cdn.agroscout.ai/informes/{run_id}.pdf")
    ```
  - [ ] Enqueue automático: al terminar etapa 5, enqueue job_informe_pdf
  - [ ] Fallback: si job falla, run queda con status 'parcial', puede reintentar manualmente
  - [ ] Target: PDF generado < 30s (Jinja2 + xhtml2pdf es rápido)
- **Duración:** 1 día
- **Dependencias:** Procrastinate (3.1), eventos_job (3.2)
- **DoD:** Etapa 6 como job, PDF en S3, evento 'completed' dispara

---

### 3.4 CREAR TABLA DuckDB PARA SERIE DE TENDENCIAS
- **Descripción:** Almacenar histórico de precios por trimestre
- **Tareas:**
  - [ ] DuckDB setup: archivo `shelf_facts.duckdb` en S3 (o local si preferible)
  - [ ] Schema: tabla `shelf_facts_quarterly`
    - Campos: `year_quarter (CHAR 4, ej '2026Q3'), insumo, tienda_id, producto_ean, precio_promedio, precio_min, precio_max, stock_promedio, promociones_count, last_update`
    - Particionado por year_quarter para queries rápidas
  - [ ] Población inicial: agregar Q2 2026 (junio 2026 data dummy) + Q3 2026 real data from Shelf Radar (desde v2)
  - [ ] Indices: (insumo, year_quarter), (tienda_id, year_quarter)
- **Duración:** 1 día
- **Dependencias:** Data (S1 - datos v2 disponibles)
- **DoD:** DuckDB file creado, queries rápidas (< 100ms para serie de 3 trimestres)

---

### 3.5 IMPLEMENTAR MOTOR DE TENDENCIAS (DETERMINISTA, SIN LLM)
- **Descripción:** Calcular % cambio, marcas nuevas, estadísticas sin IA
- **Tareas:**
  - [ ] Función `calcular_tendencias(insumo, año_base)`:
    - [ ] Para cada (trimestre, tienda):
      - [ ] Precio medio vs trimestre anterior: % cambio
      - [ ] Marcas: qué entró (nuevo count), qué salió
      - [ ] Stock: volatilidad (CV = std/mean)
      - [ ] Promociones: % de ofertas vs todos los productos
    - [ ] Agregar por insumo (promedio ponderado por tienda/país)
    - [ ] Retornar: `{insumo, year_quarter, precio_trend, marcas_nuevas, marcas_salidas, volatilidad, promocion_pct}`
  - [ ] Ejecutar noche: `SELECT MAX(year_quarter) FROM shelf_facts_quarterly` → calcular siguiente trimestre
  - [ ] Resultado guardado en tabla `tendencias_insumo` (reutilizable)
  - [ ] Metodología documentada: "Dato real de Shelf Radar sin proxy"
- **Duración:** 1.5 días
- **Dependencias:** DuckDB (3.4)
- **DoD:** Motor ejecuta, tendencias calculadas para 2-3 trimestres, % cambio verificable

---

### 3.6 IMPLEMENTAR JOB MIM_ETL (NOCHE)
- **Descripción:** Procesar tendencias, actualizar base histórica
- **Tareas:**
  - [ ] Job: `job_mim_etl(snapshot_version)` que corre cada noche (00:00 UTC)
  - [ ] Pasos:
    1. Descargar OFF subset (si hay actualizaciones) y USDA (si hay nuevas marcas)
    2. Actualizar `shelf_facts_quarterly` con datos del día (raw_offers hoy → shelf_facts)
    3. Ejecutar `calcular_tendencias()` para insumos piloto
    4. Guardar resultado en `tendencias_insumo`
    5. Registrar evento `mim_etl_completed`
  - [ ] Logging: qué productos se añadieron, qué marcas nuevas
  - [ ] SLA: terminar en < 30 min
  - [ ] Alert si tarda > 30 min
- **Duración:** 1.5 días
- **Dependencias:** Tendencias motor (3.5), Procrastinate (3.1)
- **DoD:** Job corre cada noche, registra evento de completitud

---

### 3.7 INICIALIZAR TAXONOMÍA CITE V0.1
- **Descripción:** Base de claims y categorías del CITE
- **Tareas:**
  - [ ] Migración SQL: tabla `taxonomia_cite`
    - Campos: `categoria_id, nombre_categoria, claims (array de strings), version='0.1', created_at`
    - Datos: ≤5 categorías de piloto (quinua, palto, espárrago, mango, arándano)
    - Claims: ~30 por categoría (ej: "alto en fibra", "libre de OGM", "alérgeno", etc.)
  - [ ] Tabla `ingredientes_cite` (vinculada):
    - Campos: `ingrediente_id, nombre, EAN, INACAL_code, USDA_id, OFF_id, alérgeno, claims_aplicables`
    - ~50 ingredientes por insumo piloto
  - [ ] Constraint: cada claim debe estar en lista conocida (anti-corruption layer)
- **Duración:** 0.5 días
- **Dependencias:** DB (S1)
- **DoD:** Tablas pobladas con 5 categorías, 150+ ingredientes, queries rápidas

---

### 3.8 ANTI-CORRUPTION LAYER PARA NORMALIZACIÓN LLM
- **Descripción:** Cuando LLM en etapa 4 genera claims, validar contra taxonomía
- **Tareas:**
  - [ ] Función `validar_claim_contra_taxonomia(claim_texto, insumo_categoria)`:
    - [ ] Buscar claim_texto en `taxonomia_cite` para esa categoría (fuzzy match, 80%+ similarity)
    - [ ] Si match, usar claim canónico; si no, retornar error "claim no en taxonomía"
  - [ ] Etapa 4 (Formulación): antes de retornar, validar todos los claims
  - [ ] Si hay rechazo, incluir en audit: "claim rechazado por taxonomía"
  - [ ] Versionado: guardar qué versión de taxonomía se usó
- **Duración:** 0.5 días
- **Dependencias:** Taxonomía (3.7)
- **DoD:** Validador rechaza claims no canónicos, audit registra

---

### 3.9 TEST P10 (MIM DEGRADADO: 2-3 TRIMESTRES)
- **Descripción:** Validar que motor de tendencias produce output
- **Tareas:**
  - [ ] Query: `calcular_tendencias('quinua', 2026)`
  - [ ] Resultado:
    - [ ] Histórico de 3 trimestres (Q1, Q2, Q3 2026)
    - [ ] % cambio de precio (ej: -5% Q2→Q3)
    - [ ] Marcas nuevas: [marca_A, marca_B]
    - [ ] Marcas que salieron: [marca_C]
  - [ ] Exportar a tabla temporal → este es el insumo para deck PPTX (S8)
  - [ ] Verify: series existen, cálculos no son NaN
  - [ ] Nota: "2-3 trimestres" en v3, "≥8 trimestres" sería v4 (cuando pase tiempo real)
- **Duración:** 0.5 días
- **Dependencias:** Tendencias motor (3.5)
- **DoD:** P10 degradada (verde pero con 2-3 trimestres, no 8)

---

### 3.10 INTEGRACIÓN: AGENDA NIGHTLY JOBS
- **Descripción:** Programar jobs que corren automáticamente
- **Tareas:**
  - [ ] Usar Procrastinate scheduler o simple cron en el worker
  - [ ] Jobs a programar:
    - [ ] `job_mim_etl` → 00:00 UTC cada noche
    - [ ] `job_corpus_ingest` → 02:00 UTC (prep para S4, pero por ahora dummy)
  - [ ] Logging: cada ejecución registrada en eventos_job
  - [ ] Alerta: si job falta 1 noche, PagerDuty notifica
- **Duración:** 0.5 días
- **Dependencias:** Procrastinate (3.1)
- **DoD:** Cron/scheduler configurado, jobs se ejecutan en horario

---

### 3.11 DOCUMENTACIÓN: FLOWCHART DE JOBS Y EVENTOS
- **Descripción:** Visualizar cómo fluyen datos a través de cola
- **Tareas:**
  - [ ] Crear diagrama: request → enqueue job → worker procesa → evento → WebSocket notifica
  - [ ] Incluir: timeouts, retries, fallback paths
  - [ ] Documento: `JOBS_WORKFLOW.md` en repo
- **Duración:** 0.5 días
- **Dependencias:** Todos (3.1-3.10)
- **DoD:** Diagrama comprensible para CITE, docstring en código

---

## DEFINITION OF DONE (S3)

- [ ] Procrastinate worker implementado y corriendo
- [ ] Job definitions creados (agente, MIM, PDF)
- [ ] Tabla eventos_job poblada con callbacks
- [ ] WebSocket streaming eventos en vivo
- [ ] Etapa 6 integrada como job
- [ ] DuckDB shelf_facts_quarterly creado y poblado
- [ ] Motor de tendencias determinista funciona
- [ ] Job MIM_ETL corre cada noche
- [ ] Taxonomía CITE v0.1 en DB
- [ ] Anti-corruption layer valida claims
- [ ] P10 degradada en verde
- [ ] Scheduler nightly jobs configurado
- [ ] Documentación JOBS_WORKFLOW.md

---

## RIESGOS S3

| Riesgo | Mitigación |
|---|---|
| Worker se cuelga, jobs quedan pendientes | Healthcheck del worker en Prometheus, alert si sin heartbeat > 5 min |
| DuckDB particionado es lento | Usar índices agresivos; test con 10M+ rows si posible |
| Motor de tendencias calcula erróneamente % cambio | Unit tests para cada fórmula; validar a mano con datos del CITE |
| Job MIM tarda > 30 min, cumple SLA | Simplificar: solo procesar insumos piloto, no todas las tiendas |
| Taxonomía v0.1 es incompleta | Trabajar con CITE en paralelo (puede ser item de S8 también) |

---

## NOTAS

- **DuckDB vs Postgres:** Decidir dónde guardar tendencias (DuckDB es más rápido para analytics, Postgres es más simple); en v3 preferencia DuckDB local
- **Nightly jobs:** Horario 00:00 UTC asume zona del servidor; ajustar si CITE prefiere otra zona
- **Equipo:** 2 backend (cola + tendencias) + 1 data engineer (DuckDB tuning)
- **Parallelización:** Items 3.1-3.2 en paralelo, luego 3.4-3.5 en paralelo
