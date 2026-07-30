# MVP AgroScout IA · Walking skeleton demostrable + plan de pruebas de punta a punta

- **Estado:** Propuesto (entregable para demo CDR)
- **Fecha:** 2026-07-29
- **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)
- **Depende de:** [ADR-001](ADR-001-nucleo-comercial-y-paywall.md) · [ADR-002](ADR-002-motor-inteligencia-mercado.md) · [ADR-003](ADR-003-escalado-multitenant.md)
- **Diagrama:** [Arquitectura_AgroScout_IA_MVP.svg](Arquitectura_AgroScout_IA_MVP.svg)

---

## 1. Objetivo y principio

**Objetivo:** demostrar al CITE el resultado de punta a punta — los 6 pasos del DAG, el paywall, el MIM y el agente — con datos reales reducidos, para sustentar la firma del CDR y el contrato.

**Principio: walking skeleton.** El MVP ejecuta el **código real de producción** (v7.2 · fase 1 del ADR-003) en cada paso, con datasets mínimos. No hay maquetas ni resultados precocinados en el camino crítico: si un paso falla en la demo, falla de verdad y se corrige de verdad. El único stub permitido es el adaptador **nivel 2** de la cascada (API licenciada), que aún no se contrata.

Esto significa que el MVP ya incluye la **fase 1 del ADR-003**: Postgres (Supabase) como estado, cola `procrastinate` + worker, presupuestos run/tenant/global con kill-switch, cuarentena `staging_agente` con grounding check, Pydantic AI + Tavily, y `nivel_maximo_costo` en el puerto. Lo que se difiere es infraestructura de volumen (fase 2/3), que no bloquea la demo.

## 2. Alcance

| Componente | En el MVP | Diferido (fase 2/3) |
|---|---|---|
| API | FastAPI, **1 nodo** | LB + 2-3 réplicas |
| Estado de app | Postgres (Supabase) + RLS, 2 organizaciones demo | — |
| Cola / workers | `procrastinate` + **1 worker** (agente·reportes·ETL) | pool dedicado de workers de agente |
| Snapshots | `datasets/2026-07/` **local** en el nodo | object storage (S3/R2) + CDN |
| DAG EvaluarInsumo | **las 6 etapas reales** + paywall | — |
| Puerto DescubrimientoComercial | nivel 1 (snapshot) + nivel 3 (agente) · **nivel 2 = stub** | contratar API licenciada |
| MIM | taxonomía **v0.1** + normalización LLM + tendencias + deck PPT + ficha PDF | taxonomía completa con el CITE |
| Agente | Pydantic AI + Tavily · presupuestos · cuarentena · **promoción manual** | promoción con muestreo sistemático |
| Regulación (etapa 5) | corpus mínimo: eCFR (aditivos del piloto) + 2-3 normas DIGESA | ingesta completa FDA/EFSA/Codex/INACAL |
| Embeddings | bge-m3 (CPU) | mistral-embed |
| Fuentes excluidas | Mintel y Trend Hunter **no se consumen** (ADR-002/003) | — |

## 3. Datos mínimos de la demo

**Insumos piloto (5), todos de la zona Chavimochic:** arándano · palta · espárrago · mango · quinua.

- **Snapshot `2026-07`:** subset de OFF (categorías de los 5 insumos, 50-200 productos por insumo, ≥8 trimestres de histórico para tendencias) + USDA Branded subset + Open Prices/Comtrade de los 5 insumos.
- **Taxonomía CITE v0.1:** ≤5 categorías canónicas, ~30 claims, ~50 ingredientes. Suficiente para demostrar el moat; la versión completa se construye con el CITE post-firma. El snapshot declara `version_taxonomia=0.1`.
- **Corpus regulatorio mínimo:** aditivos eCFR relevantes al piloto + 2-3 normas DIGESA (OCR Mistral).
- **Cuentas demo (Supabase):** `demo-gratuita` (Mipyme) y `demo-premium` (Cooperativa), en **organizaciones distintas** para probar RLS y cost-meter por tenant.
- **Presupuesto de agente para la demo:** tope por run US$0.25 · tope tenant US$2/mes · tope global US$10/mes.

## 4. Plan de pruebas — todos los pasos (P01-P13)

Cada prueba se ejecuta en vivo durante la demo o en CI antes de ella. Criterio global: **13/13 en verde**.

| ID | Paso probado | Cómo se prueba | Criterio de aceptación |
|---|---|---|---|
| **P01** | Auth + entitlement + RLS | Login con ambas cuentas; consultar historial cruzado | Cada organización ve SOLO sus datos; `PoliticaDeSuscripcion` lee el plan correcto |
| **P02** | Etapa 1 · InterpretarInsumo | "arándano" → sinónimos ES/EN; repetir la consulta | Sinónimos correctos (blueberry, etc.); 2ª llamada = **cache hit** (costo LLM $0) |
| **P03** | Etapa 2a · MatchProductos | Match local vectores+DuckDB para los 5 insumos | Productos relevantes, **sin llamada LLM**, p95 < 2 s |
| **P04** | Etapa 2b · MapaComercial (nivel 1) | Puerto con `nivel_maximo_costo=1` (solo snapshot) | Lista de `ProductoEnMercado` con país·marca·precio·URL·fuente·fecha; campos sin dato = `null`, nunca inventados |
| **P05** | Etapa 3 · InsightMercado | Generar insight de la consulta | El texto **solo cita datos entregados** (verificación: cada afirmación tiene cita a un producto del resultado) |
| **P06** | **Paywall** | Misma consulta con `demo-gratuita` y `demo-premium` | Gratuita: early return tras etapa 3 con informe parcial. Premium: continúa a 4-5. Distinto del guard técnico 0-2 productos |
| **P07** | Etapa 4 · Formulación (premium) | Dossier de formulación para 1 insumo | Formulación basada en minería DuckDB + glm-5.2; referencias a productos reales del snapshot |
| **P08** | Etapa 5 · Regulación (premium) | Verificación regulatoria del mismo insumo | Citas verificables al corpus mínimo (eCFR/DIGESA); si no hay norma cargada, lo declara — no inventa |
| **P09** | Etapa 6 · InformeScout | Generar el PDF final | Job de worker produce el PDF; evento en el panel; ejecución del DAG auditada en Postgres con costo por etapa |
| **P10** | **MIM completo** | Correr ETL sobre el subset OFF → normalización → tendencias → reportes | Productos clasificados a taxonomía v0.1 (validación schema); series por trimestre con % de cambio; deck PPT + ficha PDF generados con diseño propio y **metodología declarada** (proxy: fecha de alta en OFF) |
| **P11** | **Agente + cuarentena** | Lanzar `AgenteInvestigadorComercial` para 1 insumo sin precio en snapshot | Job asíncrono con progreso en panel; salida validada a `staging_agente` (`provenance=agente`, `no_verificado`, TTL); **grounding check**: todo valor existe en el HTML de origen; promoción manual → aparece en `catalogo_comercial` |
| **P12** | Presupuesto + kill-switch | Forzar tope de presupuesto (run y global) a mitad de run | Run termina en estado `parcial` con campos obtenidos; kill-switch global desactiva nivel 3 y la cascada **degrada a "sin dato", nunca a error**; sin reintento automático |
| **P13** | Cost-meter por tenant | Revisar el panel tras P02-P11 | Costo por consulta visible (~US$0.01-0.05, menos con cache); gasto de agente atribuido al tenant correcto; cuotas por plan aplicadas |

**Pruebas de regresión en CI (previas a la demo):** golden set de ~30 productos para el extractor del agente · validación de schema de `ProductoEnMercado` · smoke test del DAG completo con la cuenta premium.

## 5. Guion de demo (≈15 min)

1. **(2 min)** Login `demo-gratuita` → consulta "arándano" → mapa comercial global (etapas 1-3): qué existe, dónde, a cuánto, con URL y fuente por campo. *[P01-P05]*
2. **(1 min)** Intento de acceder a formulación → paywall con informe parcial. *[P06]*
3. **(3 min)** Login `demo-premium` → misma consulta → dossier completo: formulación + regulación con citas + PDF final en el panel. *[P07-P09]*
4. **(3 min)** MIM: mostrar el deck PPT de tendencias del piloto (categorías, claims, % de cambio por trimestre) y una ficha `ProductoEnMercado` — "esto es lo que hoy pagan a Mintel, generado con nuestras fuentes abiertas y la taxonomía del CITE". *[P10]*
5. **(4 min)** Agente en vivo: insumo sin precio → job asíncrono con progreso → resultado en cuarentena con fuente+URL+fecha por campo → promoción manual → aparece en el catálogo. Mostrar el costo del run. *[P11]*
6. **(2 min)** Panel de control: costo por consulta y por tenant, presupuestos del agente, kill-switch. "El gasto está acotado por diseño en tres niveles". *[P12-P13]*

## 6. Criterios de "MVP listo"

- [ ] P01-P13 en verde (los 13, sin excepciones).
- [ ] CI en verde: golden set + schema + smoke test del DAG.
- [ ] Costo por consulta medido y visible: ~US$0.01-0.05 (gratuita), agente ≤ US$0.25/run.
- [ ] Cero valores inventados: todo precio/marca con `fuente+url+fecha` o `null`.
- [ ] Los 5 insumos piloto funcionan de punta a punta con ambas cuentas.
- [ ] Guion de demo ensayado con datos reales (sin resultados precocinados).

## 7. Métricas a capturar durante la demo

Latencia p95 por etapa · costo LLM por consulta y acumulado por tenant · tasa de cache hit (etapa 1) · cobertura de precio por insumo (snapshot vs. agente) · costo y duración del run del agente · % de campos `null` (honestidad del sistema, no es un defecto).

---

*El MVP es la fase 1 del ADR-003 con datos reducidos: lo que se demuestra es lo que se escala. Ningún paso de la demo se tira después — solo se le agregan datos e infraestructura.*
