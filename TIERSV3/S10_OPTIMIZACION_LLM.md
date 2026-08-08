# Semana 10 · MODELOS LLM Y OPTIMIZACIÓN

**Objetivo:** Cost per query minimizado, latencia p95 verificada, modelos confirmados.

**Duración:** 5 días · **Equipo:** Backend (1) + Data/Ops (1)

---

## ITEMS SEMANA 10

### 10.1 VALIDACIÓN COMPLETA DE HUAWEI MODELARTS MAAS
- **Tareas:**
  - [ ] Verificar disponibilidad de modelos:
    - [ ] glm-4.7-flashx (E1 cheap)
    - [ ] glm-4.7 (E3 mid)
    - [ ] glm-5.2 (E4 expensive, agente)
  - [ ] Consultar pricing real:
    - [ ] Tokens input/output por modelo
    - [ ] Bulk pricing si > 1M tokens/mes
    - [ ] Latencia P95 de cada modelo
  - [ ] Alternativa: Qwen si mejor pricing; verificar exactitud en tasks piloto
  - [ ] Decision: confirmar proveedor con CITE
  - [ ] Documento: `LLM_PROVIDER_SELECTION.md`
- **Duración:** 1 día
- **Dependencias:** Ninguna
- **DoD:** Proveedor confirmado, tarjetas documentadas

---

### 10.2 EVALUACIÓN MISTRAL-EMBED VS BGE-M3 (BÚSQUEDA)
- **Tareas:**
  - [ ] Setup: embeddings con ambos modelos
  - [ ] Dataset test: 50 productos piloto, 100 queries
  - [ ] Métricas:
    - [ ] Recall: ¿encuentra el producto correcto en top-5?
    - [ ] Latencia: tiempo para embeddear 1 query
    - [ ] Dimensiones: mistral-embed (384-768) vs bge-m3 (384)
    - [ ] Cost: mistral-embed (API), bge-m3 (CPU local)
  - [ ] Decision: mistral-embed si recall > 95% Y latencia p95 < 100ms; else mantener bge-m3
  - [ ] Documento: `EMBEDDING_MODEL_EVAL.md`
- **Duración:** 1.5 días
- **Dependencias:** Modelos disponibles
- **DoD:** Recall/latencia medidos, decisión documentada

---

### 10.3 CACHE WARMING (PRECALCULAR EMBEDDINGS HOT PATH)
- **Tareas:**
  - [ ] Identify hot set: productos que reciben > 10 queries/semana en v2
  - [ ] Precalcular embeddings noche antes (job cron)
  - [ ] Guardar en Redis con TTL: productos trending
  - [ ] Hit rate: monitorear qué % de queries acierta cache
  - [ ] Target: hit rate > 80% en prime hours (09:00-17:00)
- **Duración:** 1 día
- **Dependencias:** Redis (new infra), embeddings (10.2)
- **DoD:** Cache warming job corre, hit rate > 70% al inicio

---

### 10.4 TTL ADAPTATIVO DE CACHÉ
- **Tareas:**
  - [ ] Regla: Keep hot products (> 50 queries/semana) por 7 días
  - [ ] Keep warm products (10-50 queries/semana) por 3 días
  - [ ] Keep cold products (< 10 queries/semana) por 1 día
  - [ ] Recalcular categorías cada noche basado en stats
  - [ ] Evict cuando Redis memory > 80%
  - [ ] Logging: qué se evictó, por qué
- **Duración:** 0.5 días
- **Dependencias:** Cache warming (10.3)
- **DoD:** TTL adaptativo funciona, memory usado

---

### 10.5 MEDIR LATENCIA P95 ETAPA 2A (MATCH SIN LLM)
- **Tareas:**
  - [ ] Test: 100 queries aleatorias contra producto DB
  - [ ] Capturar latencia de 2a (inicio hasta retorno de results)
  - [ ] Breakdown: embedding (10-20ms), búsqueda DB (5-10ms), dedup (5ms), gate categoría (10ms)
  - [ ] Target: p95 < 2000ms (2s desde v2 spec)
  - [ ] Si > 2s: optimizar índices DB o cache embeddings
  - [ ] Documento: `ETAPA2A_LATENCY_ANALYSIS.md`
- **Duración:** 1 día
- **Dependencias:** Embeddings (10.2), DB tuning (S1)
- **DoD:** p95 < 2s, breakdown documentado

---

### 10.6 OPTIMIZACIÓN DE ÍNDICES EN POSTGRES
- **Tareas:**
  - [ ] Analizar queries lentas en Postgres (pg_stat_statements)
  - [ ] Top queries lentas (top 10):
    - [ ] Match de producto por embeddings + categoría
    - [ ] Búsqueda de regulación (full-text)
    - [ ] Cobertura de sweeps (group by)
  - [ ] Crear índices faltantes:
    - [ ] BRIN en shelf_facts (date range)
    - [ ] GiST/GIST en pgvector (embeddings)
    - [ ] GIN en full-text search (regulación)
  - [ ] VACUUM + ANALYZE
  - [ ] Medir antes/después
- **Duración:** 1 día
- **Dependencias:** DB (S1), queries logging
- **DoD:** Índices añadidos, queries más rápidas (10%+ mejora)

---

### 10.7 COST OPTIMIZATION POR ETAPA
- **Tareas:**
  - [ ] Auditar costo de cada etapa (del histórico S9 load test):
    - [ ] E1 (flashx): ~$0.001 per call
    - [ ] E2a (embeddings): ~$0 (CPU local, cache helps)
    - [ ] E2b (N1): ~$0 (direct API)
    - [ ] E3 (glm-4.7): ~$0.002
    - [ ] E4 (glm-5.2): ~$0.010
    - [ ] E5 (glm-5.2): ~$0.005
    - [ ] TOTAL: ~$0.018 per premium query
  - [ ] Target: < $0.020 (estaba en spec)
  - [ ] Si > $0.020: considerar bajar modelo E5 a glm-4.7 (menos costo)
- **Duración:** 0.5 días
- **Dependencias:** Cost-meter (S2)
- **DoD:** Cost breakdown documentado, dentro de budget

---

### 10.8 FALLBACK DE MODELO (SI HUAWEI COSTO SUBE)
- **Tareas:**
  - [ ] Implementar fallback: Qwen si Huawei sube > 20%
  - [ ] Setup Qwen endpoint (open source, puede ser self-hosted)
  - [ ] Adapter pattern: `LLMProvider = Huawei | Qwen`
  - [ ] Test: mismo prompt a ambos → verificar diferencia en output
  - [ ] Switch: via config (no requiere recompile)
  - [ ] Document: cómo cambiar de provider en producción
- **Duración:** 1 día
- **Dependencias:** Huawei eval (10.1)
- **DoD:** Fallback implementado, switcheable

---

### 10.9 MONITOREO DE LATENCIA Y COSTOS EN VIVO
- **Tareas:**
  - [ ] Dashboard Grafana: nuevos paneles
    - [ ] Latencia por etapa (p50/p95/p99 en vivo)
    - [ ] Cost per query (últimas 100 queries)
    - [ ] Cost trend (últimos 7 días)
    - [ ] Alerts: si p95 > 2s E2a, o cost > $0.025, notificar
  - [ ] Test: simular latencia alta → alerta dispara
- **Duración:** 0.5 días
- **Dependencias:** Observabilidad (S1)
- **DoD:** Dashboards live, alerts funciona

---

### 10.10 DOCUMENTACIÓN: LLM STRATEGY Y SLA
- **Tareas:**
  - [ ] Documento: `LLM_STRATEGY.md`
  - [ ] Secciones:
    - [ ] Provider (Huawei ModelArts, fallback Qwen)
    - [ ] Models por etapa (flashx, 4.7, 5.2)
    - [ ] Cost projections ($/consulta, $/tenant·mes)
    - [ ] Latency SLOs (E1: < 500ms, E2a: < 2s, etc.)
    - [ ] Escalation: si pricing sube, qué faire
- **Duración:** 0.5 días
- **Dependencias:** Todos (10.1-10.9)
- **DoD:** Documento claro, compartible con CITE

---

## DEFINITION OF DONE (S10)

- [ ] Huawei ModelArts validado, tarjetas documentadas
- [ ] Mistral-embed vs bge-m3 evaluado (recall + latencia)
- [ ] Cache warming job corre noche
- [ ] TTL adaptativo de cache implementado
- [ ] Etapa 2a: p95 < 2s verificado
- [ ] Índices DB optimizados (10%+ mejora)
- [ ] Cost breakdown por etapa documentado
- [ ] Fallback a Qwen implementado
- [ ] Dashboards latencia + costo en Grafana
- [ ] LLM_STRATEGY.md escrito

---

## RIESGOS S10

| Riesgo | Mitigación |
|---|---|
| Mistral-embed peor recall que bge-m3 | Mantener bge-m3, no es crítico cambiar |
| p95 etapa 2a > 2s por DB lento | Agregar réplica read, usar connection pooling |
| Cache warming tarda > 1h | Paralelizar, procesar por chunks |
| Huawei costo sube 50% mid-mes | Cláusula contrato: re-negociar si sube > 20%; activar fallback Qwen |

---

## NOTAS

- **Equipo:** 1 backend (setup) + 1 data/ops (benchmarking)
- **Decisión de proveedor:** tomar con CITE si Huawei pricing no sale
- **Embedding model:** decision flexible (bge-m3 es solido, mistral es futuro)
