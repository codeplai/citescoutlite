# ADR-003 · Escalado multi-tenant: separación de planos, estado en PostgreSQL y endurecimiento del agente

- **Estado:** Propuesto
- **Fecha:** 2026-07-29
- **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic) — `v7.1` → `v7.2`
- **Depende de:** [ADR-001](ADR-001-nucleo-comercial-y-paywall.md) · [ADR-002](ADR-002-motor-inteligencia-mercado.md)
- **Origen:** revisión de arquitectura de producción (hallazgos sobre `v7.1`) + nueva proyección de demanda: **varios cientos de clientes** (multi-tenant), no 50-100 usuarios de una sola institución

---

## 1. Contexto

`v7.1` fue dimensionada para 50-100 usuarios institucionales sobre **un servidor dedicado** (~US$85/mes) con SQLite como estado de aplicación. La nueva proyección comercial (varios cientos de organizaciones cliente) invalida esa implementación, **no la arquitectura**: la base hexagonal, los snapshots inmutables y la cascada por costo escalan bien; lo que no escala es el estado compartido en SQLite y la ausencia de infraestructura de ejecución asíncrona.

La revisión de producción de `v7.1` identificó además estos hallazgos, que este ADR resuelve:

| # | Hallazgo | Resuelto en |
|---|---|---|
| H1 | "Asíncrono, por job" sin infraestructura de jobs definida (cola, worker, reintentos, idempotencia) | §2.3 |
| H2 | Topes del agente solo *por run*; sin presupuesto global ni por cliente, sin kill-switch | §2.5 |
| H3 | El agente escribe directo en `catalogo_comercial` compartido: un dato malo contamina a todos los clientes | §2.5 |
| H4 | Validar contra schema no impide alucinación de valores; falta grounding check y golden set | §2.5 |
| H5 | Trend Hunter con ToS restrictivo dentro del toolset del agente = riesgo legal | §2.5 |
| H6 | Runtime del agente sin decidir ("Pydantic AI / LangGraph", "Tavily/Brave/SerpAPI") | §2.5 |
| H7 | Fuga de entitlement: el puerto decide si llega al nivel 3 (agente), que es política de negocio | §2.6 |
| H8 | SQLite single-writer, sin plan de backup para historial/informes; único servidor = SPOF | §2.2, §3 |
| H9 | Migración "MVP FastAPI → Prod Go" sin justificación de carga | §2.4 |
| H10 | Taxonomía sin versionar; re-normalización histórica sin estrategia | §3 |
| H11 | Motor de tendencias usa fecha de alta en OFF como proxy de lanzamiento (sesgo vs. GNPD); formato visual de reportes "= Mintel" roza trade dress | §2.7 |

**Análisis de carga.** Cientos de clientes generan tráfico asimétrico: la mayoría es **plano de lectura** (etapas 1-3, mapa comercial sobre datasets inmutables DuckDB/vectores — replicable barato) y una minoría es **plano de escritura** (ETL mensual, runs del agente, generación de reportes — baja frecuencia, pero requiere cola, presupuesto y durabilidad). El cuello de botella real nunca será el framework HTTP: será la I/O hacia LLM y el gasto del agente.

## 2. Decisión

Evolucionar a `v7.2` con seis cambios. Todos son **swaps de adaptadores o adiciones de infraestructura**; el dominio y los puertos de ADR-001/002 no cambian.

### 2.1 Separación de planos lectura / escritura

- **Plano de lectura:** API stateless que sirve consultas sobre snapshots inmutables locales (DuckDB + vectores). Escala horizontal copiando el snapshot.
- **Plano de escritura:** workers dedicados que procesan jobs (agente, reportes, ETL) y escriben en almacenes y object storage. Nunca dentro del ciclo request/response.

### 2.2 Estado de aplicación: SQLite → PostgreSQL (Supabase)

SQLite (single-writer, no compartible entre nodos) deja de ser el estado de app. Pasan a **PostgreSQL gestionado (el mismo Supabase que ya provee auth/planes)**:

- historial, ejecuciones DAG (auditoría), eventos del panel;
- cost-meter **por etapa y por tenant**, cuotas por plan;
- cache LLM y cache del agente (hoy locales → deben ser compartidos entre réplicas);
- la cola de jobs (§2.3).

Multi-tenancy con **RLS por organización** en Postgres: el aislamiento de datos de cliente vive en la capa de datos gestionada, no en código propio (library-first).

**DuckDB, LanceDB/vectores y los snapshots NO cambian**: son lectura pura y escalan por réplica. SQLite puede sobrevivir solo como cache local efímero de nodo, nunca como fuente de verdad.

### 2.3 Cola de jobs + workers (resuelve H1)

- Cola **sobre Postgres** con `procrastinate` (Python, library-first): jobs persistentes, reintentos con backoff, visibilidad de estado. Evita añadir Redis mientras el volumen no lo exija; ruta de upgrade documentada: Redis + `arq`.
- **Workers separados del API** para: runs del `AgenteInvestigadorComercial`, generación de reportes (PPT/PDF) y ETL mensual.
- **Idempotencia** por clave natural `insumo+país+mes` (la misma clave de cache del agente): un job duplicado no genera un run duplicado.
- Eventos de progreso del job → panel (ya previsto en ADR-002), ahora persistidos en Postgres.
- Fallo por tope de costo a mitad de run → el job termina en estado `parcial`, entrega los campos obtenidos con su provenance y lo reporta al panel; nunca reintenta automáticamente un run que murió por presupuesto.

### 2.4 API stateless + snapshots distribuidos (resuelve H9)

- FastAPI **stateless, 2-3 réplicas** detrás de un load balancer. **Se cancela la reescritura en Go**: a esta escala el cuello es I/O de LLM, no el framework; la migración era costo sin retorno.
- Cada nodo descarga al arranque el snapshot vigente `datasets/AAAA-MM/` desde object storage (§3). Al ser inmutables y versionados, no hay sincronización entre nodos: solo *pull* del último snapshot publicado.
- Rate-limiting por plan en el borde (gateway/LB), alimentado por el entitlement de Supabase.

### 2.5 Endurecimiento del agente (resuelve H2-H6)

- **Presupuestos en tres niveles** (además del tope por run ya definido en ADR-002):
  1. **por tenant**: US$/mes de agente según plan (enforcement contra el cost-meter en Postgres);
  2. **global**: presupuesto mensual de plataforma con **kill-switch** que desactiva el adaptador 3 (la cascada degrada a batch: "sin dato", nunca error);
  3. **concurrencia**: cap de workers de agente simultáneos (bulkhead a nivel de pool, no solo por llamada).
- **Cuarentena (`staging_agente`)**: la salida del agente ya NO escribe directo en `catalogo_comercial`. Entra a un área de staging con `provenance=agente`, `estado=no_verificado` y **TTL** (los precios de retail caducan). Promoción al catálogo compartido solo tras:
  1. **grounding check**: todo valor extraído (precio, marca, presentación) debe aparecer literalmente en el contenido obtenido por `abrir_url`; si no, se descarta el campo (queda `null`);
  2. validación automática contra reglas de dominio (rangos de precio plausibles por categoría/país);
  3. muestreo humano del **Laboratorio CITE** (que ya valida la etapa 6; se le añade este muestreo).
  El solicitante premium ve su resultado inmediatamente (marcado `no_verificado`); el resto de clientes solo ve datos promovidos.
- **Golden set** de ~30 productos conocidos como test de regresión del extractor en CI.
- **Cumplimiento de acceso como componente**, no como nota: allowlist/denylist de dominios, respeto de robots.txt, rate-limit por dominio, user-agent identificado.
- **Trend Hunter sale del toolset del agente** (ToS restrictivo × cientos de clientes = riesgo legal multiplicado). Se degrada a referencia manual del consultor CITE, como Mintel.
- **Decisión de runtime (cierra H6): Pydantic AI** — salida tipada nativa contra el schema `ProductoEnMercado`, superficie mínima para un agente de 3 herramientas. Búsqueda: **una sola API primaria (Tavily)** con fallback documentado (Brave); SerpAPI se descarta.

### 2.6 Entitlement fuera del puerto (resuelve H7)

El puerto `DescubrimientoComercial` no lee planes ni decide si "merece" llegar al nivel 3. La capa de aplicación (donde vive `PoliticaDeSuscripcion`, ADR-001 §2.4) le pasa un parámetro **`nivel_maximo_costo`** (o política de presupuesto). El puerto obedece la cascada hasta ese nivel. Coherente con ADR-001: el tiering vive en aplicación, nunca en dominio ni en puertos.

### 2.7 Honestidad metodológica y formato propio (resuelve H11)

- Todo reporte de tendencias **declara la metodología**: el proxy de "lanzamiento" es la fecha de alta en OFF, no el lanzamiento real como en GNPD. Evita que el CITE compare curvas contra Mintel y pierda confianza.
- El generador de reportes replica la **estructura de información** de la ficha Mintel (campos), con **diseño visual propio** del CITE. No se copia el look-and-feel.

## 3. Impacto en almacenes, ETL y operación

- **Object storage (S3-compatible: S3/R2) como fuente de verdad** de: snapshots `datasets/AAAA-MM/`, `/informes` (PDF/PPT) y corpus PDF regulatorio. Los nodos hacen pull; el NVMe local pasa a ser cache de trabajo. Esto resuelve de paso el backup de datasets (H8).
- **Backups**: Postgres → gestionado por Supabase (PITR); objetos → versionado del bucket. Objetivo simple: RPO ≤ 24 h, RTO ≤ 4 h.
- **Taxonomía versionada (H10)**: cada snapshot declara `version_taxonomia`. Un cambio de taxonomía dispara re-normalización **en un snapshot nuevo, nunca in-place** (con su costo LLM estimado antes de ejecutar). Se fija además la versión del modelo de normalización por snapshot para evitar drift.
- **Observabilidad**: logs estructurados + métricas por tenant (consultas, gasto LLM, runs de agente) + traza por run del agente (secuencia de tool calls) persistida para depuración. Suficiente con Postgres + un dashboard; sin stack pesado por ahora.
- **Costo estimado**: de ~US$85/mes a **US$200-400/mes** en fases 2-3 (LB + 2-3 nodos + Supabase + bucket). Marginal frente al costo LLM, que es lo que los presupuestos por tenant protegen.

## 4. Alternativas consideradas

1. **Microservicios / Kubernetes.** Rechazada: para cientos (no cientos de miles) de clientes, un monolito modular + workers + Postgres + object storage es el tamaño correcto. K8s añade operación sin resolver ningún cuello real.
2. **Motor analítico servidor (ClickHouse / warehouse).** Rechazada: DuckDB sobre snapshots replicados aguanta este volumen de lectura de sobra y mantiene la filosofía "cero servidores de BD analítica".
3. **Reescritura del API en Go.** Rechazada (cancelada del roadmap): el cuello es I/O de LLM; FastAPI stateless escala horizontal.
4. **Redis como cola desde el día 1.** Pospuesta: Postgres ya está en la foto por Supabase; una dependencia menos. Upgrade path documentado si el throughput de jobs lo exige.
5. **Mantener SQLite + litestream.** Rechazada: resuelve backup pero no el multi-writer ni el estado compartido entre réplicas.
6. **Postgres autogestionado en el dedicado.** Rechazada: Supabase ya está contratado (auth/planes) e incluye RLS, backups y PITR; operar Postgres propio es carga sin diferencial.

## 5. Consecuencias

**Positivas**

- La arquitectura escala a cientos de tenants sin tocar dominio ni puertos: se confirma el retorno de la inversión hexagonal de ADR-001/002.
- El gasto del agente queda acotado en tres niveles (run, tenant, global) y el catálogo compartido queda protegido por cuarentena: los dos riesgos principales de operar con cientos de clientes.
- Un solo lugar para estado, entitlement, cuotas y cola (Postgres/Supabase): menos piezas, menos modos de fallo.
- Backups y SPOF resueltos por servicios gestionados, no por operación propia.

**Negativas / riesgos**

- **Migración de estado** SQLite → Postgres: requiere script de migración y ventana de corte; hacerla antes de firmar clientes, no después.
- Dependencia operativa mayor de **Supabase** (auth + estado + cola): mitigada porque todo es Postgres estándar — portable a cualquier Postgres gestionado.
- La cuarentena añade **latencia de promoción** al catálogo compartido: el dato del agente beneficia a los demás clientes días después, no al instante. Es deliberado (calidad > frescura).
- `procrastinate` es menos común que Celery/arq: riesgo de madurez aceptado por la ventaja de "cola = Postgres"; el upgrade path lo acota.
- El costo fijo sube (~US$200-400/mes): trivial frente a ingresos de cientos de suscripciones, pero debe entrar al modelo financiero del CDR.

## 6. Fases de adopción

| Fase | Disparador | Cambios |
|---|---|---|
| **1 · Ahora (pre-contrato)** | — | Postgres para estado + RLS · cola `procrastinate` + workers · presupuestos por tenant/global + kill-switch · cuarentena + grounding check · runtime fijado (Pydantic AI + Tavily) · `nivel_maximo_costo` en el puerto |
| **2 · ~100-300 clientes** | p95 de latencia o CPU sostenida | 2-3 réplicas API + LB · object storage fuente de verdad · observabilidad por tenant |
| **3 · 300+ clientes** | volumen de informes/runs de agente | pool dedicado de workers de agente · CDN para `/informes` · mistral-embed (ya planificado) |

## 7. Acciones derivadas

- Script de migración SQLite → Postgres (historial, auditoría, cache) + ventana de corte.
- Modelar `staging_agente` (schema + TTL + estados) y el flujo de promoción con muestreo del Laboratorio CITE.
- Implementar cost-meter por tenant + enforcement de presupuestos (run/tenant/global) + kill-switch.
- Implementar la cola `procrastinate` y extraer los workers (agente, reportes, ETL) del proceso API.
- Componente de cumplimiento de acceso del agente (robots.txt, allowlist, rate-limit por dominio, UA).
- Golden set de extracción (~30 productos) en CI.
- Publicar snapshots e informes a object storage; bootstrap de nodos por pull.
- Añadir `version_taxonomia` y versión de modelo al manifiesto de cada snapshot.
- Retirar Trend Hunter del toolset del agente; documentarlo como referencia manual.
- Actualizar el modelo financiero del CDR con el nuevo costo fijo (US$200-400/mes).
