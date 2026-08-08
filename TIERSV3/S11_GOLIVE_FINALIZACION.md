# Semana 11 · GO-LIVE Y FINALIZACION

**Objetivo:** v3 en producción, equipo CITE capacitado, operación sostenida iniciada.

**Duración:** 5 días · **Equipo:** Todas las disciplinas + CITE

---

## ITEMS SEMANA 11

### 11.1 DOCUMENTACIÓN OPERACIONAL (RUNBOOKS)
- **Tareas:**
  - [ ] Documento: `OPERATIONS_RUNBOOK.md` (15-20 págs)
  - [ ] Secciones:
    - [ ] Alertas: cómo responder (PagerDuty escalation)
    - [ ] Failover DB: pasos exactos
    - [ ] Failover API: reemplazar nodo
    - [ ] Restauración desde backup: paso a paso
    - [ ] Rollback a v2: si v3 falla critical
    - [ ] Corpus update falló: qué hacer
    - [ ] Worker colgado: cómo reiniciar
    - [ ] Out of memory: análisis de logs
  - [ ] Screenshots: cada procedimiento anotado
  - [ ] Contactos: quién on-call, teléfono 24/7
- **Duración:** 1 día
- **Dependencias:** Infra (S1-S8)
- **DoD:** Runbook claro, ops team lo valida

---

### 11.2 CAPACITACIÓN DEL CITE (4-6 HORAS)
- **Tareas:**
  - [ ] Sesión 1 (2h): Product overview + demo de flujo completo
  - [ ] Sesión 2 (2h): Panel CITE (jobs, costos, auditoría, alertas)
  - [ ] Sesión 3 (1h): Promoción manual + reglas de validación
  - [ ] Sesión 4 (1h): Qué hacer si alertas, corpus desactualizado, worker cae
  - [ ] Materiales: slides + video recordings + guía impresa
  - [ ] Q&A: feedback, qué confundió, qué mejorar
  - [ ] Post-training: recurso de contacto (Slack, email)
- **Duración:** 1.5 días
- **Dependencias:** Panel (S8), runbooks (11.1)
- **DoD:** CITE capacitado, comfortable con operación

---

### 11.3 TESTING DE ROLLBACK (REVERT A V2 EN < 5 MIN)
- **Tareas:**
  - [ ] Plan: si v3 tiene bug crítico, volver a v2 rápido
  - [ ] Pasos:
    1. LB: cambiar target de v3 nodos a v2 nodos (1 minuto)
    2. DB: si schema cambió, revert a backup v2 (3 minutos, or skip si compatible)
    3. Verificar: /health devuelve 200 OK
    4. Monitoreo: latencias, error rate normales
  - [ ] Test: hacer rollback en test environment, cronometrar
  - [ ] Documentar: tiempo real y pasos ejecutados
- **Duración:** 0.5 días
- **Dependencias:** Infra (S1)
- **DoD:** Rollback < 5 min verificado

---

### 11.4 CANARY DEPLOYMENT (V2 + V3 EN PARALELO 24H)
- **Tareas:**
  - [ ] Setup: LB envía 90% tráfico a v2, 10% a v3 (tráfico real)
  - [ ] Monitoreo: dashboards lado-a-lado
    - [ ] v2 latencia vs v3 latencia
    - [ ] v2 error rate vs v3 error rate
    - [ ] Comparar resultados (mismo query → output igual?)
  - [ ] Duración: 24h
  - [ ] Criterio de paso: v3 p95 < 10% peor que v2, error rate < 0.5%
  - [ ] Si falla: rollback a v2, debug, re-intentar
  - [ ] Si pasa: proceder a 50/50, luego full v3
- **Duración:** 1.5 días
- **Dependencias:** v3 ready, v2 running
- **DoD:** Canary 24h completo, métricas recolectadas

---

### 11.5 RAMP UP (TRAFICO GRADUAL 10% → 50% → 100%)
- **Tareas:**
  - [ ] Fase 1 (1h): 10% v3 (canary base)
  - [ ] Fase 2 (2h): 50% v3 (comparar lado-a-lado)
  - [ ] Fase 3 (2h): 90% v3 (validar sin v2)
  - [ ] Fase 4 (final): 100% v3
  - [ ] Si error rate sube en cualquier fase: pause, debug, rollback
  - [ ] Métrica de decisión: p95 latencia, error rate, cache hit rate
  - [ ] Logging: cada ramp-up step documentado
- **Duración:** 0.5 días
- **Dependencias:** Canary (11.4)
- **DoD:** 100% tráfico en v3, métricas green

---

### 11.6 MONITORING EN VIVO (METRICAS + ALERTAS HOT)
- **Tareas:**
  - [ ] Dashboards en Grafana: principal + SLO + alertas
  - [ ] SLOs en vivo:
    - [ ] 99.5% uptime etapas 1-3: must be green
    - [ ] 95% uptime agente: yellow if < 95%, red if < 90%
    - [ ] Cache hit rate > 80%: yellow if < 80%
  - [ ] Alertas PagerDuty:
    - [ ] Critical: error rate > 1%, latencia p99 > 10s
    - [ ] High: corpus > 7 días sin update
    - [ ] Medium: cache hit < 70%
  - [ ] Verificar: alerts disparan correctamente (test alert)
- **Duración:** 0.5 días
- **Dependencias:** Observabilidad (S1), SLOs (S9)
- **DoD:** SLO dashboard live, alertas funciona

---

### 11.7 DOCUMENTING AS-RUN (QUE PASÓ DURANTE GO-LIVE)
- **Tareas:**
  - [ ] Log: timestamped events
    - [ ] 10:00 - Canary deployment started (10% traffic)
    - [ ] 10:45 - Metrics nominal, proceed to 50%
    - [ ] 12:30 - 100% traffic reached, no incidents
    - [ ] 14:00 - SLO validation: 99.8% uptime, cache hit 82%
  - [ ] Issues encontrados (si hay):
    - [ ] Describa qué pasó
    - [ ] Cómo se resolvió
    - [ ] Follow-up: issue tracking, PR para fix
  - [ ] Celebración: v3 en prod! 🎉
- **Duración:** 0.5 días
- **Dependencias:** Ramp-up (11.5)
- **DoD:** Log completado, issues tracked

---

### 11.8 POST-GO-LIVE VALIDATION (PRIMEROS 24H CRÍTICOS)
- **Tareas:**
  - [ ] Día 1: monitoreo continuo
    - [ ] On-call team en chat
    - [ ] Verificar cada etapa con datos reales
    - [ ] Chequear: regulación citas vivas, alertas fetch, agente presupuestos
    - [ ] Promoción automática noche 1: logs checkeados
  - [ ] SLA verificado: latencias, errores, uptime
  - [ ] Reporte al CITE: "v3 estable, aquí está el status"
- **Duración:** 1 día
- **Dependencias:** Todos (11.1-11.7)
- **DoD:** 24h de operación sin incidents críticos

---

### 11.9 RETROSPECTIVA Y LECCIONES APRENDIDAS
- **Tareas:**
  - [ ] Reunión: 1h con el team
  - [ ] Preguntas:
    - [ ] ¿Qué salió bien?
    - [ ] ¿Qué no salió tan bien?
    - [ ] ¿Qué deberíamos cambiar en v4?
    - [ ] ¿Cómo mejoró v3 vs v2?
  - [ ] Documento: `RETRO_V3_GOLIVE.md`
  - [ ] Datos: tiempo de deploy, issues encontrados, time-to-resolution
  - [ ] Action items: backlog de mejoras menores
- **Duración:** 0.5 días
- **Dependencias:** Post-go-live (11.8)
- **DoD:** Retro documentada, action items tracked

---

### 11.10 PREPARAR ROADMAP V4
- **Tareas:**
  - [ ] Documento: `ROADMAP_V4.md` (borrador)
  - [ ] Basado en:
    - [ ] Issues encontrados en v3 go-live
    - [ ] Feature requests del CITE
    - [ ] Deuda técnica (minería DuckDB, OCR DIGESA completa, multi-region)
  - [ ] Proponer: próximas 6 semanas post-go-live (junio 2027)
  - [ ] Estimar: esfuerzo de cada feature
  - [ ] Priorizar: crítico, importante, nice-to-have
  - [ ] Reunión: revisar con CITE, confirmar prioridades
- **Duración:** 0.5 días
- **Dependencias:** Retro (11.9)
- **DoD:** Roadmap v4 draft, validado con CITE

---

## DEFINITION OF DONE (S11)

- [ ] OPERATIONS_RUNBOOK.md escrito y validado por ops
- [ ] CITE capacitado en 4 sesiones (2-3 personas, listas para operar)
- [ ] Rollback a v2 testado, < 5 min
- [ ] Canary 24h completo, métricas recolectadas
- [ ] Ramp-up (10% → 50% → 100%) exitoso
- [ ] SLO dashboard live en Grafana
- [ ] PagerDuty alertas funciona
- [ ] As-run log documentado
- [ ] Post-go-live 24h sin incidents críticos
- [ ] Retrospectiva realizada, lecciones documentadas
- [ ] ROADMAP_V4.md draft, prioridades confirmadas

---

## RIESGOS S11

| Riesgo | Mitigación |
|---|---|
| Canary revela bug crítico | Rollback a v2 (plan listo), fix, re-intentar |
| Ramp-up error rate sube inesperadamente | Pause, investigar logs, rollback si necesario |
| Primer día en prod tiene picos de tráfico | Monitoreo 24/7, on-call team listo |
| CITE aún no entiende cómo operar panel | Post-training extra, Slack support live |
| Corpus update falla noche 1 (lunes 2am) | Fallback: usar corpus viejo, alertar CITE, fix martes |

---

## TIMELINE EXACTO (ASUMIENDO INICIO MONDAY 9AM UTC)

| Hora | Evento |
|---|---|
| 09:00 | Todos en call, verificar health checks |
| 09:15 | LB: switch 10% a v3 (canary) |
| 09:30 | Monitoreo: latencias, error rate OK? |
| 10:00 | Si OK: proceder a 50% |
| 12:00 | Si OK: proceder a 90% |
| 14:00 | Final check: 100% v3 live |
| 15:00 | Celebración (si todo verde!) |
| 15:30-EOD | Monitoreo continuo, issue response |
| Noche | On-call team watching (alertas configuradas) |

---

## NOTAS

- **Duración:** S11 es 1 semana, pero go-live ocupa 1 día (lunes); resto es acompañamiento
- **Equipo:** Todas las disciplinas presentes (en chat si remoto)
- **Cliente:** CITE en standby, disponible para questions
- **Post-go-live:** SLA de 24h sin dormir; luego rotation normal
- **Éxito:** Si llegan a EOD viernes sin rollback, v3 está en producción
