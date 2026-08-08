# Plan MVP v3 — De demo a producción escalada

**Fecha:** 2026-08-08 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)

- **v2 (base del MVP actual):** `ARQUITECTURA_AGROSCOUT_IA_MVP_v2_ShelfRadar.md` · demo en 4 semanas (2026-08-28) · 10/15 pruebas
- **v3 (esta propuesta):** release de producción · cierre de todas las fases diferidas de v2 + escalado operacional
- **Marco de referencia:** ADR-003 (fase 1 completa) + ADR-004 (Shelf Radar N1+N2) + roadmap post-firma

---

## 0. Resumen ejecutivo

Tres conclusiones:

1. **v2 es un walking skeleton honesto.** Demuestra el eje de valor (mapa comercial + paywall + presupuestos) sobre 5 insumos piloto, 67 tiendas reales (N1) y datos verificables. Deja diferidas dos fases críticas: el agente con cuarentena (F4) y el MIM con 8 trimestres de histórico (F5).

2. **v3 no es iteración, es completitud.** Cierra F4 + F5 + F6 (el trabajo diferido de v2), suma la infraestructura de producción (LB, CDN, réplicas, observabilidad) y expande el alcance: full corpus regulatorio (EFSA, Codex, INACAL), Scrapling + Bright Data en Shelf Radar, alertas de retiro (RASFF + openFDA), y promoción automática por muestreo.

3. **El cronograma es tight pero alcanzable.** v2 toma 4 semanas (demo CDR); v3 toma **11 semanas más** (arquitectura post-firma del ADR-003). Con inicio post-firma (asumiendo ~octubre 2026), el release de producción llega en enero 2027.

**Decisión comprometida: v3 es el contrato completo, no un MVP.** Las fases F4-F6 del ADR-003 entran aquí en su totalidad; las cosas que entran son lo que v2 declaró diferido más lo que la operación exige.

---

## 1. Diff de alcance — v2 (demo) vs v3 (producción)

| Dimensión | v2 (4 semanas, demo CDR) | v3 (11 sem, post-firma) | Cambio |
|---|---|---|---|
| **Propósito** | Demostrar eje de valor + multi-tenancy + paywall sobre datos reales | Sistema de producción con SLOs, observabilidad y compliance total | **Reencuadre** |
| **Ámbito de Shelf Radar** | N1 real (42 tiendas) · N2 declarado como stub · N3 diseño sin código | **N1+N2 completo** (42+5 tiendas) · **N3 agente operacional** con cuarentena | **Ampliación 2.5 sem** |
| **Cascada de costo** | 3 niveles en interfaz pero solo N1 funciona | **Cascada funcional end-to-end:** N1 llena, N2 consulta Bright Data, N3 presupuestado con kill-switch real | **Nueva** |
| **Agente + cuarentena** | Diseño en ADR; N3 declarado "no disponible en este MVP" | **`AgenteInvestigadorComercial` operacional:** Pydantic AI + Tavily + trafilatura + glm-5.2; grounding check; promoción manual en UI | **F4 completa (2.5 sem)** |
| **MIM** | Taxonomía v0.1 con CITE; tendencias aún en proxy OFF | **Motor de tendencias real en DuckDB:** ≥8 trimestres de Shelf Radar, % cambio, marcas nuevas, determinista; **deck PPTX + ficha `ProductoEnMercado`** | **F5 completa (2 sem)** |
| **Cola de jobs** | PDF síncrono en <15s; declarado como fase 1 | **`procrastinate` + 1 worker:** agente/MIM/ETL async; eventos de progreso; integración con panel CITE | **Nueva (parcial con F4)** |
| **Corpus regulatorio** | eCFR piloto (aditivos) + 2-3 normas DIGESA | **Full eCFR (todos los títulos) · EFSA (E-additives + authorized uses) · Codex Alimentarius (standares internacionales) · INACAL (normas peruanas completas) · OCR de DIGESA con extracción estructurada** | **Ampliación masiva (1 sem)** |
| **Alertas y retiros** | No existen | **openFDA `/food/enforcement` (US) + RASFF (UE):** ingesta diaria, scoring de riesgo por HS, avisabilidad al informe | **Nueva (1 sem)** |
| **Shelf Radar extensión** | 42 tiendas vivas (N1) · 5 licenciadas (N2 stub) | **+ Scrapling (tiers C/D):** DOM parsing dinámico para 30-50 tiendas adicionales con rendimiento degradado pero verificable · **+ Bright Data anti-bot:** Amazon, Costco, Instacart, Kroger, Meituan operacionales | **Ampliación (1.5 sem)** |
| **Promoción** | Manual: grounding check + SQL delante del público | **Automática por muestreo sistemático:** watermark binario sobre raw_offers, reglas de validación en `promotion_rules`, auditoría en panel | **Nueva (1 sem)** |
| **Infraestructura** | 1 nodo FastAPI · snapshot local · Postgres autoalojado sin backups automatizados | **LB + 2 réplicas read · object storage S3/R2 · CDN (Cloudflare o Bunny) · Postgres con replicación + PITR 7 días · observabilidad (Prometheus + Grafana) · alertas PagerDuty** | **Ampliación (2 sem)** |
| **Modelos LLM** | glm-4.7-flashx (E1) + glm-4.7 (E3) + glm-5.2 (E4 y agente) | **Huawei ModelArts verificado · mistral-embed reemplaza bge-m3 en embeddings (MVT) · evaluación de trade-off costo/latencia en búsqueda** | **Revisión (0.5 sem)** |
| **Panel CITE** | Mínimo: costo por consulta, historial, kill-switch | **Completo:** progreso de jobs con logs en vivo, cost-meter por etapa/tenant/run, dashboard de alertas (retiros/bloqueos), promoción manual, audit trail, exportación CSV | **Ampliación (1.5 sem)** |
| **Plan de pruebas** | P01-P15 con 10 en verde | **P01-P15 + P16-P20 nuevas** (alertas, scrapling, full compliance, SLOs, failover) · todo en verde · load testing (p99, spike, degradation curves) | **Ampliación** |
| **Cronograma** | 4 semanas (demo) | **11 semanas post-firma** (fases F4-F6 de ADR-003 + infra + escalado) |

---

## 2. Fases diferidas de v2 — ahora cerradas en v3

| Fase | v2 Status | v3 Contenido | Semanas | Cierra |
|---|---|---|---|---|
| **F4** | Diseño sin código | Cola `procrastinate`, AgenteInvestigadorComercial, cuarentena con grounding check, topes de presupuesto real | 2.5 | P11, P12, P13 |
| **F5** | Diseño sin código | Motor de tendencias DuckDB (≥8 trimestres), deck PPTX, ficha ProductoEnMercado con metodología declarada | 2.0 | P10 |
| **F6** | Panel mínimo | Panel completo, CI avanzada (golden set de 30, validation, smoke test premium, load test), guion de demo v3 | 1.5 | Métrica |

**Lo que v2 dejó diferido y v3 cierra:**
- Agente operacional: cuarentena, grounding check, escalera de procedencia completa
- MIM con histórico real (Shelf Radar no comienza en 2028 con datos ajenos, sino con serie propia desde v3)
- Infraestructura de producción: escalado, observabilidad, recuperación ante fallos
- Corpus regulatorio sin tapujos: si dice "regulación" en el dossier, cada cita es verificable contra norma en la base

---

## 3. Deuda nueva en v3 — lo que la producción exige

Esto no está en v2 porque v2 es un demo. v3 lo debe tener antes de firmar acuerdos de SLO:

| Bloque | Pieza | Razón |
|---|---|---|
| **Observabilidad** | Prometheus + Grafana · alertas PagerDuty · dashboards por etapa y tenant | Sin esto, un cliente enterprise no paga por uptime que no ve. |
| **Backups y PITR** | `pg_dump` automatizado · S3 cross-region · recuperación 7 días · test mensual | Postgres autoalojado sin respaldo es una falla operativa. |
| **Rate-limiting por tenant** | Cuotas por plan en Postgres · circuit-breaker por endpoint · degradación elegante | El paywall no sirve si un tenant consume todo el presupuesto en 1 hora. |
| **Audit trail** | Tabla `auditoria_eventos` con quién/qué/cuándo/resultado · exportable por org | Compliance: si un cliente pide una auditoría interna, hay que poder entregarla. |
| **Cache warming** | Precalcular embeddings al ingesta · cache caliente al inicio · gestión activa de TTL | El p95 de búsqueda sube con la base fría; v2 no lo mide. |
| **Failover del agente** | Circuit breaker entre Tavily/Brave · reintento con exponential backoff · fallback a datos viejos en `staging_agente` | Tavily puede caerse; necesitamos seguir funcionando. |
| **Versionamiento de modelo** | LLM pinning en `snapshot_version` · reproducibilidad de modelo a través del tiempo | Si Huawei cambia el modelo, una evaluación vieja no es reproducible. |
| **Seguridad** | CORS reestringido · secrets en env vault · rate-limit anti-bot en la API · audit de cambios de plan | Una demo local no es igual a producción donde hay datos de múltiples clientes. |
| **SLOs y errorbudget** | Comprometerse a 99.5% uptime de etapas 1-3, 95% de agente (L3 es best-effort) | v2 no mide esto; v3 debe tenerlo antes de vender "fiabilidad". |

---

## 4. Plan de 11 semanas (post-firma)

**Regla:** cada semana termina con tests ejecutables (nuevas pruebas P16-P20 + load testing).

**Supuesto:** la firma del contrato sucede a finales de septiembre 2026; desarrollo comienza 2026-10-01.

### Semana 1 · Preparación y setup de producción
*Objetivo: infraestructura lista para recibir código.*

- **Día 1-2:** Aprovisionamiento de infraestructura
  - VPC en cloud (AWS/DigitalOcean/Hetzner; decidir proveedor con el CITE)
  - Postgres replicado: primary + 2 replicas read, PITR 7 días, backups diarios a S3/R2
  - Load balancer + 2 nodos API (read-only clones de código v2)
  - Observabilidad: Prometheus (scrape), Grafana (dashboards), PagerDuty (alerting)
  - Object storage: S3 compatible; CDN Cloudflare/Bunny para `datasets/` y PDFs

- **Día 3-4:** Integración con datos
  - Migración de `datasets/2026-07/` a object storage; validar checksums
  - Certificados TLS; CORS reconfigurado
  - Networking: whitelist de Tavily, Bright Data, openFDA IPs

- **Día 5:** Validación end-to-end
  - Restore test: backup → nueva BD → datos íntegros
  - Failover test: matar primary → replica promueve
  - Load test de línea base: 10 req/s contra los endpoints v2
  - Prueba P16: infraestructura resiliente (failover < 30s, zero data loss)

**Salida:** Stack de producción operativo, datos replicados, observabilidad verde. v2 corre en la infra nueva sin cambios de código.

---

### Semana 2 · Agente + cuarentena (F4 parte 1/2)
*Objetivo: N3 funcional en cascada, presupuestos con kill-switch.*

- **Día 1-2:** `AgenteInvestigadorComercial`
  - Pydantic AI + Tavily (con Brave como fallback); trafilatura para extracción
  - Toolset: `buscar_web(query, país) → abrir_url(url) → extraer_producto(html) → esquema validado`
  - Robots.txt + rate-limit por dominio (token bucket 0.4 req/s) + user-agent identificado con `/bot`
  - Idempotencia por (insumo, país, mes): si ya existe en `staging_agente`, devolver sin reintentar

- **Día 3:** Cuarentena y grounding check
  - `staging_agente` schema: `provenance='agente'`, `no_verificado`, TTL 24h
  - **Grounding check:** cada valor literal debe estar en el HTML capturado (no inventado)
  - Reglas de validación: precio dentro de ±50% del rango histórico, stock > 0, URL válida
  - `promotion_rules` en Postgres: criterios binarios para "promover a `catalogo_comercial`"

- **Día 4:** Integración con cascada
  - Puerto `DescubrimientoComercial` completo: N1 llena `catalogo_comercial` directo, N2 consulta Bright Data, N3 se invoca solo si `nivel_maximo_costo >= 3`
  - Presupuestos en tiempo real: `run_cost_usd`, `tenant_cost_month`, `global_cost_day`
  - Kill-switch: cuando se alcanza tope, `status='parcial'`, degrada a "sin dato comercial", SIN error

- **Día 5:** Tests y SLOs
  - P11: agente → cuarentena → grounding check (no valores inventados)
  - P12: presupuestos con kill-switch (3 niveles, degradación, sin reintento)
  - P13: cost-meter por tenant, cuota por plan validable
  - Prueba P17: failover del agente (Tavily cae → Brave toma) sin perder presupuesto

**Salida:** N3 operacional, presupuestos en verde, datos de agente cuarentenados pero promovibles.

---

### Semana 3 · Agente + MIM setup (F4 parte 2/2 + F5 parte 1/2)
*Objetivo: histórico de Shelf Radar acumulado; MIM comienza su serie.*

- **Día 1-2:** Cola `procrastinate` + worker
  - `procrastinate` sobre Postgres (ya existe en F2), 1 worker con retry strategy
  - Jobs: `job_agente_run`, `job_mim_etl`, `job_informe_pdf`, `job_corpus_ingest`
  - Eventos de progreso: `job_created`, `job_started`, `job_progress`, `job_completed` → persistidos en tabla `eventos_job`, los lee el panel en vivo

- **Día 3-4:** Motor de tendencias DuckDB
  - **Histórico:** Shelf Radar data existe desde v2 (2026-08-28 en adelante); v3 suma los datos reales
  - Particionado por trimestre en DuckDB; cada trimestre = serie de `raw_offers` agregado por (tienda, producto, fecha)
  - **Cálculos:** % cambio vs trimestre anterior, insumos/marcas que entraron, que salieron, variación de precio por percentil
  - **Metodología declarada:** "datos v2+ de Shelf Radar (dato real de góndola) + Comtrade (precio export) + OFF (ingredientes)"; sin proxy
  - Queries precalculadas cada noche; cache en DuckDB

- **Día 5:** Primera promoción manual
  - UI en panel CITE: fila de `staging_agente` → checkbox "promover" → aplicar reglas → mover a `catalogo_comercial`
  - Auditoría: quién promovió, cuándo, qué reglas se cumplieron
  - Prueba P10 degradada: tendencias sobre 2-3 trimestres de Shelf Radar (no es ≥8 aún, pero ya es real)

**Salida:** Cola funcional, histórico de tendencias iniciado, MIM con datos reales (aunque cortito).

---

### Semana 4 · Corpus regulatorio ampliado (1 semana dedicada)
*Objetivo: toda cita de regulación es verificable contra norma en la base.*

- **Día 1:** eCFR completo + parsing
  - Descargar eCFR JSON (FDA) o XML (CFR Reader); parsear por título, parte, sección
  - Filtrar aditivos (21 CFR 182, 184, 186), contaminantes, límites de residuos
  - Indexar en Postgres con búsqueda full-text; pgvector para búsqueda semántica

- **Día 2:** EFSA (Europa) + Codex (Internacional)
  - EFSA Register of food ingredients → e-additives autorizados, maximum levels per food category
  - Codex Alimentarius Standards (ISO converter) → composición, pesos netos, alérgenos, inocuidad
  - Ambas fuentes con versión y fecha; hasheo para change detection

- **Día 3:** INACAL (Perú) + OCR de DIGESA
  - INACAL NTS: carnes, lácteos, frutas, hortalizas, conservas. Descargar PDFs, OCR con Tesseract
  - DIGESA directivas: importación, etiquetado, vigilancia. OCR y extracción de campos (ingrediente bloqueado, límite, justificación)
  - Anti-corruption layer: normalizar nombres de ingredientes (OFF EAN → INACAL nombre → eCFR número)

- **Día 4:** Etapa 5 completada en v3
  - Regulación ahora es una etapa real (no un campo de otra etapa)
  - Validar: cada afirmación en dossier tiene URL + sección + versión de norma que la sostiene
  - Si no hay norma, dossier lo dice explícitamente: "sin regulación conocida en eCFR para [ingrediente]"

- **Día 5:** Tests
  - P08: citas verificables (cada una tiene URL viva y está en corpus)
  - P18: corpus íntegro (cobertura por país: eCFR completo, EFSA >95%, Codex >90%, INACAL >80%, DIGESA >70%)

**Salida:** Dossier v3 cita regulación verdadera, verificable, completa. Sin invención.

---

### Semana 5 · Scrapling + Bright Data (N2 completa)
*Objetivo: cascada comercial con 97+ tiendas verificadas.*

- **Día 1-2:** Scrapling (dinámico, tiendas difíciles)
  - Adaptar httpx para renderizado JS (Scrapling o Playwright headless)
  - Huellas digitales de 30-50 tiendas con JS pesado: Shopify dinámicas, SPAs, lazy-load
  - Rate-limit conservador (0.1 req/s por dominio), timeout 30s, retry backoff
  - Canario diario: 2-3 tiendas conocidas, verificar estructura, alertar si rota

- **Día 3:** Bright Data integración
  - API Scraper con webhook: trigger → snapshot_id → webhook con datos
  - 5 tiendas anti-bot (Amazon, Costco, Instacart, Kroger, Meituan): modelo asíncrono
  - Manejo de throttling: si falla, esperar, reintentar (hasta N veces), alertar si muere

- **Día 4:** Dedup + fusión
  - EAN es llave primaria en catalogo_comercial; si dos fuentes dan EAN idéntico, tomar la de menor costo
  - Procedencia declarada por campo: `price.fuente='N1_VTEX'`, `price.fuente='N2_BrightData'`, `price.fuente='N1_Scrapling'`
  - Cobertura actualizada: `sweep_attempts` refleja qué se intentó hoy

- **Día 5:** P14 en verde bajo presión
  - Prueba P14 (cobertura declarada): 97+ tiendas escaneadas, cada una 1 fila en `sweep_attempts` aunque falle
  - P19: adaptor no se cae silenciosamente (canario diario detecta roturas)

**Salida:** N2 operacional, 97+ tiendas en cascada, procedencia clara por campo.

---

### Semana 6 · Alertas de retiro (RASFF + openFDA)
*Objetivo: si un ingrediente en el informe fue retirado, el cliente lo sabe.*

- **Día 1:** openFDA `/food/enforcement`
  - Ingesta diaria: enforcement actions, recalls, market withdrawals
  - Parsear: fecha, empresa, producto, ingrediente clave, razón (patógeno, alérgeno, residuo)
  - Hashear por ingrediente + país; detectar cambios

- **Día 2:** RASFF (Europa)
  - European rapid alert system for food (RASFF)
  - Descargar XML/JSON; campos: producto, hazard, country, date
  - Fusionar con eCFR y EFSA para deducir nivel de riesgo (critical/high/medium)

- **Día 3:** Scoring de riesgo
  - Para cada ingrediente en un insumo: buscar en openFDA + RASFF
  - Score binario: `hay_alerta=true/false`; severity `critical/high/medium/low`
  - Edad de la alerta (días): si < 30 días, flag rojo; < 90, amarillo

- **Día 4:** Integración en informe
  - Etapa 5 (regulación) se expande: "Regulación + Alertas de retiro"
  - Dossier incluye un bloque: "Vigilancia: [lista de alerts activas]" con links a openFDA/RASFF
  - Dashboard del panel: "Ingredientes en alerta" con fecha de ingesta

- **Día 5:** P20: alertas de retiro
  - Prueba P20: insumo con ingrediente retirado recientemente → dossier lo señala en rojo

**Salida:** Alerting automático integrado en dossier; cliente se entera de retiros sin delay.

---

### Semana 7 · Promoción automática por muestreo
*Objetivo: N3 se promueve a catálogo sin intervención manual en el 80% de casos.*

- **Día 1-2:** Muestreo sistemático
  - No promocionar todo: sesgo de cobertura. Muestrear por (tienda, categoría, precio_range)
  - Watermark binario en `raw_offers`: hash(offer_id, seed_semanal) % 100 < 80 → candidata a promoción automática
  - Mantener el 20% de "promoción manual" para casos Edge

- **Día 3:** Reglas de validación (anti-garbage)
  - Precio: dentro de ±2σ del histórico de esa tienda + ese producto
  - Stock: > 0 en tiendas de retailer serio; ≥ 1000 en marketplaces
  - URL: válida, accesible, 200 OK en últimas 24h
  - Fecha: recent (< 7 días)

- **Día 4:** Auditoría automática
  - Tabla `promotion_log`: quién (sistema o user), qué (offer_id), cuándo, por qué reglas, resultado
  - Estadísticas: % promocionado automático, % manual, % rechazado, motivo de rechazo

- **Día 5:** P15 en verde de verdad
  - Prueba P15 (gate de categoría): buscar quinua en droguería → 0 resultados automáticamente
  - Validar que la promoción automática respeta el gate

**Salida:** 80% de agente promocionado automático; 20% manual queda para edge cases.

---

### Semana 8 · Panel CITE completo
*Objetivo: el cliente ve todo lo que cuesta, todo lo que se procesa, todo lo que falla.*

- **Día 1-2:** Dashboard de jobs
  - Lista en vivo de jobs (`job_agente_run`, `job_mim_etl`, etc.)
  - Barra de progreso por job; logs en vivo (últimas 100 líneas)
  - Filtrar por tenant, por estado (running/completed/failed), por etapa

- **Día 3:** Cost-meter por tenant + run
  - Tabla: consulta_id | etapa | tenant | costo_usd | cuota_restante | status
  - Gráfico de gastos: serie temporal, desglose por etapa, proyección mensual
  - Cuota de plan: verde si < 80%, naranja si 80-95%, rojo si > 95%

- **Día 4:** Audit trail + alertas
  - Histórico de cambios: quién (org) pasó de plan A a plan B, cuándo, efecto en cuota
  - Alertas activas: scaffolding Tavily/Bright Data caído, corpus desactualizado, cobertura de Shelf Radar < 60%
  - Kill-switch visible: si está activado, mensaje prominente

- **Día 5:** P09 verde + exportación
  - Prueba P09: Panel muestra auditoría completa del DAG (cada etapa, costo, time)
  - Exportación CSV: histórico de 30 días por tenant; descargar para compliance

**Salida:** Panel completo, cliente ve TODO. Transparencia total en costos y operación.

---

### Semana 9 · CI completa + load testing
*Objetivo: confianza en que v3 aguanta producción.*

- **Día 1-2:** Golden set expandido
  - 30 productos reales (5 insumos × 6 productos cada uno) con datos verificables
  - Cada producto: OFF record, ingredientes, alérgenos, Shelf Radar encontrado, regulación applicable, Comtrade price
  - Suite: verificar que DAG completo (1-6) produce informe sin `null` inventados

- **Día 3:** Validación de schema + contratos
  - `contratos/` en CI: `model_json_schema()` para cada etapa
  - `campo sin dato = null`, nunca inventado, nunca falta
  - `coverage` campo: in_scope, verified, blocked, failed, coverage_pct, publishable

- **Día 4:** Load test
  - 50 req/s contra `/consultas` (límite de plan premium); medir p95, p99, error rate
  - Spike: 500 req/s en 10s; ver degradación elegante (no 500, sino pending queue)
  - Sostenido 24h: memoria, CPU, conexiones DB, cache hit rate

- **Día 5:** Failover + restore test
  - Matar DB primary → replica promueve en < 30s
  - Restore desde backup → 1 hora, datos íntegros
  - Failover de Tavily → Brave; cache de datos viejos por 1h

**Salida:** CI verde, SLOs verificados (99.5% etapas 1-3, 95% agente, 90% MIM), cargas dentro de presupuesto.

---

### Semana 10 · Modelos LLM y optimización
*Objetivo: cost per query minimizado, latencia p95 verificada.*

- **Día 1:** Huawei ModelArts full evaluation
  - Verificar disponibilidad de glm-4.7-flashx, glm-4.7, glm-5.2
  - Comparar contra alternativas: Qwen, LLaMA (si self-hosted es opción)
  - Tarificación real: token in/out por modelo

- **Día 2:** mistral-embed vs bge-m3
  - Evaluar mistral-embed en p95 de búsqueda (match de 2a)
  - Si es más lento, mantener bge-m3 y cuestionar mistral
  - Medir recall a través de golden set (¿encuentra el producto correcto?)

- **Día 3-4:** Optimización de caché
  - Cache warming: al inicio del día, precalcular embeddings de productos trending
  - TTL adaptativo: keep hot products longer, old ones shorter
  - Medir cache hit rate; target > 80%

- **Día 5:** P16 redefinida (no es failover, es SLO)
  - Prueba P16: etapa 2a (match) tiene p95 < 2s, p99 < 5s bajo carga sostenida
  - Etapa 1 (interpretar): cache hit = 0s (la 2ª llamada no cuesta)

**Salida:** Modelo(s) confirmado(s), latencia verificada, cache optimizado.

---

### Semana 11 · Ensayo, documentación y go-live
*Objetivo: v3 está listo para operación sostenida.*

- **Día 1-2:** Documentación operacional
  - Runbook de operación: alertas, escalation, restauración
  - SLO + error budget: 99.5% uptime etapas 1-3 = 21.6 minutos downtime/mes
  - Capacitación del CITE: panel, promoción manual, escalation

- **Día 3:** Guion de demo v3
  - Escenario: cliente premium consulta "quinua" con agente activado
  - Demostrar: agente corre, promueve, cuota actualiza, alerta de retiro si aplica
  - Énfasis: "esto es producción, no demo; datos auditables cada segundo"

- **Día 4:** Go-live rehearsal
  - Full stack: v3 corriendo en producción, v2 corriendo en paralelo (canary)
  - Verificar: datos nuevos entran en ambos, estadísticas convergen
  - Rollback plan: volver a v2 en < 5 min

- **Día 5:** Monitoring y alertas finales
  - Dashboard de SLO en vivo: verde si 99.5%, naranja si cae, rojo si < 95%
  - PagerDuty: on-call rotates; alertas críticas despiertan
  - Historial: logs de cambios de plan, desorbitamientos de presupuesto, corpus update

**Salida:** v3 en producción, monitoreo activo, equipo CITE entrenado, error budget auditable.

---

## 5. Qué queda fuera de v3 — y por qué es aceptable

| Pieza | Razón de la demora | Propuesta de v4 |
|---|---|---|
| **Minería DuckDB de formulación** | Requiere ≥8 trimestres de recetas normalizadas; v3 tiene 2-3 trimestres | Diferir a v4 Q2 2027; hoy usar LLM sobre snapshot |
| **Deck PPTX automático** | Generador PPTX es complejo; la ficha PDF es suficiente para MVP | Igual, ficha PDF cubre la necesidad de reportes |
| **Réplicas de read en tiers < premium** | Costo de infraestructura; tiers gratuito y estándar usan primary con read-only endpoint | Tiering: free/basic = single DB, premium = replicas |
| **Shelf Radar tiers E/F (nuevas tiendas)** | Investigación manual de cada tienda; solo automatizar las 97 alcanzables hoy | v4: roadmap de "20 tiendas por semana" con SLA |
| **Integración con MaaS alternativas (OpenAI, Gemini)** | Complicaría la matriz de modelos; hoy Huawei es lo comprometido | v4: multi-provider si cliente lo pide (sobrecoste de mantenimiento) |

---

## 6. Riesgos de las 11 semanas

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| **eCFR descarga / parsing falla** | Media | Descargar día 1 de S4; tener plan B: ingestar desde FDA XML feed (SFTP) |
| **Tavily/Bright Data quotas insuficientes** | Baja | Verificar limits con ambos proveedores en semana 1; sumar margen 2x |
| **DuckDB trunca en histórico > 3 trimestres** | Baja | Usar particiones por trimestre, no tabla única; pre-test con datos reales |
| **PagerDuty integration tarda más** | Baja | Alternativa: webhooks simples a Slack + alertas manual en panel |
| **Infraestructura cloud tiene outage** | Muy baja | Multi-region no es v3, pero sí multi-AZ; failover a otra región asume 2h de downtime max |
| **Modelo GLM de Huawei cambia tarificación** | Baja | Cláusula en contrato: re-negociar si sube > 20%; mantener fallback Qwen público |
| **Golden set insuficiente** | Baja | Expandir a 50 productos si p95 no cierra en S9 |

---

## 7. Matriz de trazabilidad: qué cierra en v3

| Prueba | v2 Status | v3 Status | Cierra en |
|---|---|---|---|
| P01 | Verde | Verde | (hereda) |
| P02 | Verde | Verde | (hereda) |
| P03 | Verde | Verde | (hereda) |
| P04 | Verde | Verde | (hereda) |
| P05 | Verde | Verde | (hereda) |
| P06 | Verde | Verde | (hereda) |
| P07 | Degradada (sin minería DuckDB) | Degradada (igual, sin minería) | S10 (no cierra) |
| P08 | Parcial (eCFR piloto) | Verde | **S4** |
| P09 | Parcial (PDF síncrono) | Verde | **S3** |
| P10 | Parcial (2-3 trimestres) | Verde | **S3** |
| P11 | Diseño | Verde | **S2** |
| P12 | Verde (v2) | Verde | (hereda) |
| P13 | Verde (v2) | Verde | (hereda) |
| P14 | Verde (v2) | Verde | **S5** |
| P15 | Verde (v2) | Verde | (hereda) |
| **P16** | **N/A** | **Verde** | **S1** (failover, restore) |
| **P17** | **N/A** | **Verde** | **S2** (failover Tavily) |
| **P18** | **N/A** | **Verde** | **S4** (corpus íntegro) |
| **P19** | **N/A** | **Verde** | **S5** (canario adaptor) |
| **P20** | **N/A** | **Verde** | **S6** (alertas RASFF) |

**14/15 v2 heredadas en verde · 6 nuevas pruebas P16-P21 cierran en v3 · total 20 pruebas en verde.**

---

## 8. Diferencia con v2 en el guion de demo

v3 es **producción**, no demo. El guion es de 30 minutos + Q&A, no 15.

| # | Min | Contenido | Cambio vs v2 |
|---|---|---|---|
| 1 | 3 | Login `demo-premium` → "quinua" → etapas 1-3 en vivo (datos reales, verificables en navegador) | Igual |
| 2 | 3 | Mapa comercial: 97+ tiendas, N1/N2 funcional, procedencia clara por campo | **Expande v2** (era solo N1 en v2) |
| 3 | 5 | **Agente en vivo:** consultar "quinua + aditivo X" → busca en web → extrae → cuarentena → reglas de validación → promoción automática si cumple | **NUEVO (era diseño en v2)** |
| 4 | 5 | Dossier premium: formulación + **regulación con citas verificables (eCFR + EFSA + Codex + DIGESA)** | **Expande v2** (ERA piloto) |
| 5 | 3 | **Alertas:** mostrar que "banana, marzo 2026" tuvo recall en FDA → dossier lo señala en rojo | **NUEVO** |
| 6 | 4 | MIM: tendencias sobre 4 trimestres reales de Shelf Radar (no proxy OFF) → deck PPTX exportado | **Expande v2** (era 2-3 trimestres) |
| 7 | 3 | Panel: cost-meter, audit trail, SLO en vivo (99.5%), kill-switch declarado (no activado) | **Expande v2** (era mínimo) |
| 8 | 2 | RLS: consulta cruzada → 0 filas; auditoría de quién vio qué | Igual |
| 9 | 2 | Escalabilidad: architecture diagram; cómo escala a 1000 insumos, 500 tiendas | **NUEVO** |

**Cierre:** "Lo que v2 hizo honesto con 5 insumos, v3 lo hace con fidelidad en producción. Cada dato es verificable; cada costo es auditado; cada alerta es accionable."

---

## 9. Cronograma y gestión de riesgos

| Semana | Hito | Riesgo | Fallback |
|---|---|---|---|
| S1 | Infra lista | Proveedor cloud saturado | Cambiar región / proveedor (1-2 días) |
| S2-S3 | Agente + MIM | API de terceros cae (Tavily, Bright Data) | Circuit breaker, datos viejos, modo offline (1 sem atrás) |
| S4 | Corpus regulatorio | OCR falla, PDFs ilegibles | DIGESA proporciona data estructurada (request formal) |
| S5 | Scrapling | Anti-bot se activa, tiendas bloquean | Reducir a 70 tiendas, mantener threshold de cobertura |
| S6 | Alertas RASFF | Feed no actualiza, delays | Fallback a alertas manual semanal, menos frecuencia |
| S7-S8 | Promoción + panel | UI tarda, UX es confusa | Simplificar: 3 vistas, no 10; promoción manual solamente |
| S9 | Load test | p99 > 10s, unacceptable | Escalar a 3 nodos (costo), reducir golden set a 20 |
| S10 | Optimización | Modelo de Huawei no cumple SLO | Fallback a Qwen (menor costo), tolerar p95 3s |
| S11 | Go-live | Bug crítico en canary | Mantener v2 en prod por 2 semanas más, rollback fácil |

---

## 10. Presupuesto de infraestructura (estimado, depende del proveedor)

| Item | USD/mes | Notas |
|---|---|---|
| Compute (2 nodos API, 4 vCPU c/u) | $300-400 | AWS t4g.xlarge o equiv |
| Database (Postgres replicado, 100 GB) | $200-300 | Primary + 2 replicas, PITR 7d |
| Object storage (S3, 500 GB) | $50-100 | datasets/, PDFs, backups |
| CDN (Cloudflare/Bunny) | $50-100 | datasets/, informe PDFs |
| Observabilidad (Prometheus, Grafana) | $100-200 | Managed service o self-hosted |
| Bright Data license (5 tiendas) | $200 | API Scraper (ya existe en v2) |
| PagerDuty + alerting | $50-100 | On-call, escalation |
| **Total/mes** | **~$1000** | Escalable; crecimiento linear con tiendas (no exponencial) |

---

## Apéndice A — Documentos a actualizar

| Documento | Cambio |
|---|---|
| `ARQUITECTURA_AGROSCOUT_IA_MVP_v2_ShelfRadar.md` | Crear v3: agregar N2 funcional, agente en cascada, alertas RASFF, tiers Scrapling |
| `MVP-AgroScout-IA.md` | Guion de demo v3 (30 min) en lugar del de v2 (15 min) |
| `Arquitectura_AgroScout_IA_MVP_v3_Produccion.svg` | Nuevo diagrama: LB, replicas, CDN, observabilidad, agente + cuarentena en cascada |
| `SHELF_RADAR_ARQUITECTURA.md` | Adicionar: Scrapling adaptor, Bright Data webhook handling, canario diario, cobertura por país |
| `CLAUDE.md` | ADR-005: decisión de Huawei ModelArts + mistral-embed; ADR-006: SLO 99.5% etapas 1-3 |

---

*v3 es donde el MVP se convierte en producto. Las 11 semanas que siguen a v2 no son "más features"; son el trabajo de hacer una sistema de producción que respete el contrato que v2 prometió.*

