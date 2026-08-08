# Semana 9 · CI COMPLETA + LOAD TESTING

**Objetivo:** Confianza en que v3 aguanta producción; SLOs verificados.

**Duración:** 5 días · **Equipo:** QA (2) + Backend (1)

---

## ITEMS SEMANA 9

### 9.1 GOLDEN SET EXPANDIDO (30 PRODUCTOS REALES)
- **Tareas:**
  - [ ] Seleccionar 6 productos por cada insumo piloto (5 insumos = 30 total)
  - [ ] Por cada producto: verificable en navegador (OFF, Comtrade, Shelf Radar)
  - [ ] Datos: nombre, EAN, ingredientes, alérgenos, país, precio, tiendas encontradas
  - [ ] Crear test case con expected outputs para cada etapa (1-6)
  - [ ] Suite: ejecutar DAG completo sobre los 30; verificar campos no inventados
  - [ ] Archivos: guardar en `tests/fixtures/golden_set.json`
- **Duración:** 1.5 días
- **Dependencias:** Datos (S1-S8)
- **DoD:** 30 productos en suite, DAG completo pasa

---

### 9.2 VALIDACIÓN DE SCHEMA (CONTRATO DE DATOS)
- **Tareas:**
  - [ ] CI task: para cada etapa, generar `model_json_schema()` de Pydantic
  - [ ] Guardar en `contratos/etapa_N.json`
  - [ ] Test: ejecutar DAG, verificar JSON schema válido
  - [ ] Assertions:
    - [ ] Campo sin dato = `null`, no `""` o `0`
    - [ ] Tipos correctos (string/int/bool/array)
    - [ ] Campos requeridos presentes (audit_id, timestamp, etc.)
    - [ ] Sin campos extras no declarados
  - [ ] Fail CI si schema incorrecto
- **Duración:** 1 día
- **Dependencias:** Pydantic models
- **DoD:** Schema en git, CI valida

---

### 9.3 SMOKE TEST DEL DAG PREMIUM (NIVEL 3)
- **Tareas:**
  - [ ] Test: ejecutar consulta sobre "quinua" con nivel=3
  - [ ] Verificar:
    - [ ] Etapa 1: insumo interpretado
    - [ ] Etapa 2a: match sin LLM, p95 < 2s
    - [ ] Etapa 2b: mapa comercial N1+N2, cobertura > 60%
    - [ ] Etapa 3: insight con citas a datos
    - [ ] Paywall: no bloqueado en gratuita (se pasa nivel_maximo_costo=1)
    - [ ] Etapa 4: formulación (premium)
    - [ ] Etapa 5: regulación + alertas
    - [ ] Etapa 6: PDF generado < 30s
  - [ ] Logs: todo auditado, costos registrados
- **Duración:** 1 día
- **Dependencias:** DAG completo (S2-S8)
- **DoD:** Smoke test pasa, logs limpios

---

### 9.4 LOAD TEST 1: BASELINE (50 REQ/S POR 5 MIN)
- **Tareas:**
  - [ ] Herramienta: k6 o Apache JMeter
  - [ ] Carga: 50 req/s contra `/consultas` (gratuita, nivel=1) por 5 minutos
  - [ ] Métricas capturadas:
    - [ ] Latencia: p50, p95, p99, max
    - [ ] Throughput: req/s real
    - [ ] Error rate
    - [ ] CPU, memoria de nodos API
    - [ ] DB qps, conexiones activas
    - [ ] Cache hit rate
  - [ ] Baseline: guardar en `performance/baseline.json`
  - [ ] Threshold: p95 < 500ms, error rate < 0.1%
- **Duración:** 1 día
- **Dependencias:** Infra (S1), API (S2+)
- **DoD:** Baseline capturado, p95 < 500ms

---

### 9.5 LOAD TEST 2: SPIKE (500 REQ/S POR 10S, LUEGO NORMAL)
- **Tareas:**
  - [ ] Simulación de pico (ej: evento de prensa, virality)
  - [ ] Rampa: 50 → 500 req/s en 10s, luego vuelve a 50 en 10s
  - [ ] Verificar:
    - [ ] API queue crece, se procesa sin perder requests
    - [ ] Latencia p99 sube, pero no hay timeouts
    - [ ] LB distribución balanceada entre 2 nodos
    - [ ] Post-spike: p95 vuelve a < 500ms en 5 min
  - [ ] Fail si: % de errores > 0.5%, o timeouts > 100
- **Duración:** 0.5 días
- **Dependencias:** Baseline (9.4)
- **DoD:** Spike manejado sin errores críticos

---

### 9.6 LOAD TEST 3: SOSTENIDO 24H (10 REQ/S)
- **Tareas:**
  - [ ] Correr overnight: 10 req/s por 24 horas
  - [ ] Verificar: sin memory leaks, conexiones DB estables, cache warm
  - [ ] Métricas: mismas que baseline, pero watch:
    - [ ] Memory creep (debe ser flat, no crecer)
    - [ ] DB connection pool (no debe alcanzar max)
    - [ ] Logs (no debe haber errores repetitivos)
  - [ ] Post-test: latencias siguen siendo p95 < 500ms
- **Duración:** 0.5 días (test corre automático, review es rápida)
- **Dependencias:** Baseline (9.4)
- **DoD:** 24h test completo, no leaks detectadas

---

### 9.7 FAILOVER TEST BAJO CARGA
- **Tareas:**
  - [ ] Setup: baseline load (50 req/s)
  - [ ] Matar DB primary → replica promueve (simular)
  - [ ] Verificar:
    - [ ] Failover < 30s
    - [ ] Error rate pico < 1% durante failover
    - [ ] Post-failover: 0 data loss, queries idénticas
  - [ ] Mismo con: matar 1 nodo API → tráfico fluye a otro
- **Duración:** 0.5 días
- **Dependencias:** Infra (S1), load test (9.4)
- **DoD:** Failover bajo carga manejado

---

### 9.8 DEGRADATION CURVE (CÓMO FALLA GRACEFULLY)
- **Tareas:**
  - [ ] Rampa de carga: 10 → 100 → 500 → 1000 → 5000 req/s
  - [ ] En cada nivel: registrar latencia, error rate, throughput
  - [ ] Graficar: curva de degradación (dónde se quiebra)
  - [ ] Documentar: "a partir de 1500 req/s, error rate sube > 1%"
  - [ ] Conclusión: max sustainable load ~1000 req/s (2 nodos actuales)
- **Duración:** 0.5 días
- **Dependencias:** Load test (9.4)
- **DoD:** Curva documentada, punto de quiebre identificado

---

### 9.9 CI PIPELINE: EJECUTAR TESTS AUTOMÁTICAMENTE
- **Tareas:**
  - [ ] Setup: CI/CD (GitHub Actions o Jenkins)
  - [ ] Triggers: PR, merge a main, nightly
  - [ ] Jobs:
    - [ ] Unit tests (modelos Pydantic, funciones)
    - [ ] Schema validation
    - [ ] Smoke test DAG
    - [ ] Golden set (30 productos)
    - [ ] Load test baseline (si PR grande, solo en nightly)
  - [ ] Report: fallos bloquean merge
  - [ ] Artifacts: guardar logs, métricas para análisis
- **Duración:** 1.5 días
- **Dependencias:** Todos (9.1-9.8)
- **DoD:** CI pasa PR, no hay regresos

---

### 9.10 DOCUMENTACIÓN: PERFORMANCE REPORT
- **Tareas:**
  - [ ] Documento: `PERFORMANCE_REPORT.md`
  - [ ] Secciones:
    - [ ] Baseline: p50/p95/p99 latencias, throughput
    - [ ] SLO tracking: 99.5% uptime etapas 1-3, 95% agente
    - [ ] Degradation curve: máx load sostenible
    - [ ] Failover results: tiempo, data loss
    - [ ] Recommendations: escalar a 3 nodos si > 1500 req/s
  - [ ] Gráficos: incluir PNG de Grafana
- **Duración:** 0.5 días
- **Dependencias:** Todos (9.1-9.9)
- **DoD:** Report legible, compartible con CITE

---

## DEFINITION OF DONE (S9)

- [ ] Golden set 30 productos en fixtures
- [ ] Schema validation en CI
- [ ] Smoke test DAG premium pasa
- [ ] Load test baseline: p95 < 500ms
- [ ] Load test spike: 500 req/s sin errores
- [ ] Load test 24h: memory stable, no leaks
- [ ] Failover test: zero data loss
- [ ] Degradation curve documentada
- [ ] CI/CD pipeline automático
- [ ] PERFORMANCE_REPORT.md escrito

---

## RIESGOS S9

| Riesgo | Mitigación |
|---|---|
| Load test revela p99 > 5s (inaceptable) | Optimizar queries DB, agregar índices, caché Redis |
| CI tarda demasiado (> 30 min), bloquea PRs | Paralelizar jobs; load test solo en nightly |
| Golden set produce resultados inconsistentes (flaky) | Fijar seeds, disable randomness, usar test fixtures fijas |
| Failover detecta data loss | Aumentar replication redundancy o frequency |

---

## NOTAS

- **Equipo:** 2 QA (load tests) + 1 backend (CI setup)
- **Load test herramienta:** k6 es más legible que JMeter; opción preferida
- **Horario:** Load 24h corre overnight (no bloquea dev)
