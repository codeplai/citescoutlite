# TIERSV3 — Plan de Trabajo Semanal para MVP v3

**Navegación rápida de las 11 semanas del plan de producción para AgroScout IA v3**

---

## Estructura

Cada semana es un archivo `.md` independiente, puntual y ejecutable. Todos los items están separados numerados con tareas, duraciones, dependencias y DoD (Definition of Done).

### Semana 1: PREPARACIÓN E INFRAESTRUCTURA
📄 [S1_PREPARACION_INFRA.md](S1_PREPARACION_INFRA.md)
- VPC + Postgres replicado
- Load balancer + 2 nodos API
- Observabilidad (Prometheus + Grafana + PagerDuty)
- Object storage (S3) + CDN
- TLS, networking, restore/failover tests
- **Equipo:** DevOps (1) + Infra (1)
- **DoD:** 11 ítems, stack operativo sin cambios en app

---

### Semana 2: AGENTE + CUARENTENA (F4 Parte 1/2)
📄 [S2_AGENTE_CUARENTENA.md](S2_AGENTE_CUARENTENA.md)
- AgenteInvestigadorComercial (Pydantic AI + Tavily)
- Robots.txt + rate-limiting por dominio
- Tabla staging_agente (cuarentena de datos)
- Grounding check (validación sin invención)
- Cascada del puerto (N1 → N2 → N3)
- Presupuestos (3 niveles + kill-switch)
- Cost-meter en vivo
- P11, P12, P13 en verde
- **Equipo:** Backend (2) + QA (1)
- **DoD:** Agente operacional, presupuestos reales

---

### Semana 3: COLA + WORKER + MIM SETUP (F4 P2/2 + F5 P1/2)
📄 [S3_COLA_WORKER_MIM_SETUP.md](S3_COLA_WORKER_MIM_SETUP.md)
- Procrastinate worker (jobs async)
- Tabla eventos_job + WebSocket streaming
- Etapa 6 (PDF) como job
- DuckDB shell_facts_quarterly (histórico de precios)
- Motor de tendencias determinista (sin LLM)
- Job MIM_ETL (noche)
- Taxonomía CITE v0.1
- Anti-corruption layer para claims
- P10 degradada en verde
- **Equipo:** Backend (2) + Data (1)
- **DoD:** Worker funciona, histórico de tendencias iniciado

---

### Semana 4: CORPUS REGULATORIO COMPLETO
📄 [S4_CORPUS_REGULATORIO_COMPLETO.md](S4_CORPUS_REGULATORIO_COMPLETO.md)
- eCFR descargado e indexado (FDA)
- EFSA descargado e indexado (Europa)
- Codex Alimentarius descargado
- INACAL descargado
- OCR de DIGESA (Perú)
- Tabla regulacion_cita con búsqueda
- Función buscar_regulacion()
- Integración en etapa 5
- Job corpus_ingest (actualización semanal)
- P08 verde (citas verificables)
- **Equipo:** Data (2) + Backend (1)
- **DoD:** Toda cita de regulación verificable contra norma

---

### Semana 5: SCRAPLING + BRIGHT DATA (N2 COMPLETA)
📄 [S5_SCRAPLING_BRIGHT_DATA.md](S5_SCRAPLING_BRIGHT_DATA.md)
- ScraplingTransport (30-50 tiendas dinámicas)
- Bright Data Scraper API integrada (5 tiendas anti-bot)
- Tabla sweep_attempts (cobertura declarada)
- Canario diario (quality control)
- Deduplicación por EAN + fusión de fuentes
- Cobertura metadata (coverage_pct)
- N2 en cascada del puerto
- P14, P19 en verde
- **Equipo:** Backend (2) + QA (1)
- **DoD:** 97+ tiendas en cascada, procedencia clara

---

### Semana 6: ALERTAS DE RETIRO (RASFF + openFDA)
📄 [S6_ALERTAS_RASFF_OPENFDA.md](S6_ALERTAS_RASFF_OPENFDA.md)
- openFDA /food/enforcement descargado diariamente
- RASFF descargado e indexado
- Mapeo fuzzy de ingredientes a alertas
- Scoring de riesgo (1-5 escala)
- Integración en etapa 5 (Regulación + Vigilancia)
- Dashboard de alertas en panel CITE
- Job alert_ingest (noche)
- P20 verde (alertas en dossier)
- **Equipo:** Backend (1) + Data (1) + QA (1)
- **DoD:** Alertas automáticas si ingrediente fue retirado

---

### Semana 7: PROMOCIÓN AUTOMÁTICA POR MUESTREO
📄 [S7_PROMOCION_AUTOMATICA.md](S7_PROMOCION_AUTOMATICA.md)
- Watermark binario (80% auto, 20% manual)
- Tabla promotion_rules (configuración de reglas)
- Validador de reglas (anti-garbage)
- Tabla promotion_log (auditoría)
- Job promotion_auto (noche)
- UI manual promotion en panel (20%)
- Campo promotion_source en catálogo
- Statistics y dashboard de promociones
- **Equipo:** Backend (2) + QA (1)
- **DoD:** 80% automático, 20% manual, auditoría completa

---

### Semana 8: PANEL CITE COMPLETO
📄 [S8_PANEL_CITE_COMPLETO.md](S8_PANEL_CITE_COMPLETO.md)
- Dashboard de jobs (live progress)
- Cost-meter detallado (gráficos + desglose)
- Audit trail (quién vio qué, cuándo)
- Alertas activas (retiro + corpus + cobertura)
- Kill-switch UI
- Promovedor manual de ofertas
- Exportar informes (PDF/JSON/CSV)
- System Health (SLO dashboard)
- Planes y entitlements
- Documentación y capacitación CITE
- **Equipo:** Frontend (2) + Backend (1)
- **DoD:** Cliente ve TODO en tiempo real

---

### Semana 9: CI COMPLETA + LOAD TESTING
📄 [S9_CI_LOAD_TESTING.md](S9_CI_LOAD_TESTING.md)
- Golden set 30 productos
- Schema validation en CI
- Smoke test DAG premium
- Load test baseline (50 req/s)
- Load test spike (500 req/s → 10s)
- Load test 24h (memory stable)
- Failover test bajo carga
- Degradation curve (máx load sostenible)
- CI/CD pipeline automático
- Performance report documentado
- **Equipo:** QA (2) + Backend (1)
- **DoD:** Confianza en que v3 aguanta producción

---

### Semana 10: MODELOS LLM Y OPTIMIZACIÓN
📄 [S10_OPTIMIZACION_LLM.md](S10_OPTIMIZACION_LLM.md)
- Validación de Huawei ModelArts MaaS
- Evaluación mistral-embed vs bge-m3
- Cache warming (precalcular embeddings)
- TTL adaptativo de caché
- Medición de latencia etapa 2a (p95 < 2s)
- Optimización de índices Postgres
- Cost breakdown por etapa
- Fallback a Qwen si necesario
- Dashboards latencia + costo
- LLM Strategy documentada
- **Equipo:** Backend (1) + Data/Ops (1)
- **DoD:** Cost minimizado, latencia verificada

---

### Semana 11: GO-LIVE Y FINALIZACIÓN
📄 [S11_GOLIVE_FINALIZACION.md](S11_GOLIVE_FINALIZACION.md)
- Operations runbook (alertas, failover, restauración)
- Capacitación CITE (4-6 horas)
- Testing de rollback (< 5 min)
- Canary deployment (v2 + v3 24h)
- Ramp-up (10% → 50% → 100%)
- Monitoring en vivo (SLOs + alertas)
- As-run log de go-live
- Post-go-live validation (24h críticas)
- Retrospectiva y lecciones aprendidas
- Roadmap v4
- **Equipo:** Todas las disciplinas + CITE
- **DoD:** v3 en producción, CITE capacitado, 24h sin incidents

---

## Matriz de Trazabilidad Rápida

| Semana | Foco | Pruebas | Equipo | Duración |
|---|---|---|---|---|
| S1 | Infraestructura | — | DevOps+Infra | 5 días |
| S2 | Agente | P11, P12, P13 | Backend+QA | 5 días |
| S3 | Cola + MIM setup | P10 (degradada) | Backend+Data | 5 días |
| S4 | Regulación | P08 | Data+Backend | 5 días |
| S5 | Scrapling + Bright Data | P14, P19 | Backend+QA | 5 días |
| S6 | Alertas | P20 | Backend+Data+QA | 5 días |
| S7 | Promoción automática | — | Backend+QA | 5 días |
| S8 | Panel CITE | — | Frontend+Backend | 5 días |
| S9 | CI + Load test | P01-P15 (todas) | QA+Backend | 5 días |
| S10 | LLM optimization | — | Backend+Data/Ops | 5 días |
| S11 | Go-live | — | Todas+CITE | 5 días |

---

## Cómo Usar Este Plan

1. **Por Semana:** Abre el archivo de la semana correspondiente (S1.md, S2.md, etc.)
2. **Items Puntuales:** Cada item es independiente; lee descripción, tareas, duración, dependencias
3. **DoD:** Al final de cada semana, verifica que se cumplieron todos los "Definition of Done"
4. **Riesgos:** Revisa la tabla de riesgos y mitigaciones
5. **Documentación:** Cada semana generan documentos (runbooks, metodologías, etc.)

---

## Dependencias Clave (CRÍTICO LEER)

```
S1 (Infra)
  ├── S2 (Agente) · S3 (Cola)
  ├── S4 (Regulación) [después S3]
  ├── S5 (Scrapling) [después S4]
  ├── S6 (Alertas) [después S5]
  ├── S7 (Promo) [después S6]
  ├── S8 (Panel) [puede paralelizar parcialmente con S7]
  ├── S9 (CI + Load test) [después S8]
  ├── S10 (LLM opt) [parcialmente paralelo con S9]
  └── S11 (Go-live) [final]
```

**Ruta crítica:** S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 → S10 → S11 (11 semanas, no hay paralelización mayor)

---

## Presupuesto Estimado

| Item | Costo |
|---|---|
| Infraestructura cloud (11 semanas) | ~$11,000 |
| Bright Data (S5) | $200 (anual, amortizado) |
| Observabilidad (Prometheus/Grafana/PagerDuty) | Incluido en infra |
| Equipo de desarrollo (11 sem × 3-4 personas) | ~80-100 días-persona |

---

## Contactos y Escalation

- **DevOps/Infra Lead:** [asignar]
- **Backend Lead:** [asignar]
- **Frontend Lead:** [asignar]
- **QA Lead:** [asignar]
- **Data/ML Lead:** [asignar]
- **Product Manager (CITE):** [asignar]
- **On-call rotation (S11+):** [definir]

---

## Changelog

- **2026-08-08:** Creado plan TIERSV3 (11 semanas post-firma)
- **[futuro]:** Actualizar a medida que avance desarrollo

---

*Last updated: 2026-08-08 · Autor: Claude Code · Status: DRAFT*
