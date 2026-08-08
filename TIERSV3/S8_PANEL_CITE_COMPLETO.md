# Semana 8 · PANEL CITE COMPLETO

**Objetivo:** Cliente ve TODO: jobs, costos, auditoría, alertas, promociones.

**Duración:** 5 días · **Equipo:** Frontend (2) + Backend (1)

---

## ITEMS SEMANA 8

### 8.1 DASHBOARD DE JOBS (LIVE PROGRESS)
- **Tareas:**
  - [ ] Página: "Jobs" con listado en tiempo real
  - [ ] Columnas: Job ID, Tipo (agente/MIM/PDF), Tenant, Estado, Progreso%, Duración, Log (últimas 20 líneas)
  - [ ] WebSocket: `/ws/jobs` actualiza cada 2s
  - [ ] Filtros: por tenant, por estado (running/completed/failed)
  - [ ] Click en job → modal con logs completos
  - [ ] Botón: "Logs" → descarga archivo .txt
- **Duración:** 1.5 días
- **Dependencias:** eventos_job (S3)
- **DoD:** Dashboard actualiza en vivo, filtros funcionan

---

### 8.2 COST-METER DETALLADO
- **Tareas:**
  - [ ] Página: "Costos" con tabla y gráficos
  - [ ] Tabla: Consulta ID | Tenant | Etapa | Tokens In | Tokens Out | Costo USD | Fecha
  - [ ] Gráficos:
    - [ ] Serie temporal: gasto diario (últimos 30 días)
    - [ ] Desglose por etapa: pie chart (E1: 5%, E2: 10%, E3: 20%, E4: 30%, E5: 35%)
    - [ ] Desglose por tenant: barras (demo-gratuita: $0.50, demo-premium: $1.50)
  - [ ] Cuota de plan: "demo-premium gastó $1.50 de $2.00 (75%)" con barra visual
  - [ ] Exportar: botón "CSV" descarga histórico 30d
  - [ ] Proyección: "Al ritmo actual, mes cierra en $22 (límite global $10)" → alerta roja
- **Duración:** 1.5 días
- **Dependencias:** presupuesto_uso (S2)
- **DoD:** Gráficos legibles, exportación funciona

---

### 8.3 AUDIT TRAIL (QUIEN VIO QUÉ, CUÁNDO)
- **Tareas:**
  - [ ] Página: "Auditoría" con log de cambios
  - [ ] Tabla: Acción | Usuario | Tenant | Entidad | Cambio | Timestamp
  - [ ] Acciones: `plan_changed`, `kill_switch_toggled`, `promotion_manual`, `rule_updated`, `login`, `export`
  - [ ] Filtros: por usuario, por acción, por fecha
  - [ ] Click en row → detalles (antes/después si cambio)
  - [ ] Export: auditoría completa para cumplimiento (CSV o PDF)
  - [ ] Retención: 1 año mínimo
- **Duración:** 1.5 días
- **Dependencias:** Tabla auditoría (debe crear si no existe)
- **DoD:** Audit trail completo, exportable

---

### 8.4 ALERTAS ACTIVAS (ALERTAS DE RETIRO + CORPUS DESACTUALIZADO)
- **Tareas:**
  - [ ] Página: "Alertas" o sidebar widget
  - [ ] Secciones:
    - [ ] Ingredientes en retirada: severity + días desde
    - [ ] Estado de corpus: "eCFR actualizado hace 1 día ✓", "DIGESA hace 5 días ⚠️" (>7 días = 🔴)
    - [ ] Cobertura Shelf Radar: "Plaza Vea: 45/100 ofertas (45%)" → si < 60%, flag
    - [ ] Worker status: "OK" o "⚠️ sin heartbeat 3 min"
  - [ ] Click en alerta → detalles
  - [ ] Tone: crítica en rojo, warning en naranja
- **Duración:** 1 día
- **Dependencias:** Todas (6, 7, S4)
- **DoD:** Dashboard muestra 4+ tipos de alertas

---

### 8.5 KILL-SWITCH UI
- **Tareas:**
  - [ ] Sección en panel: "Presupuestos y Control"
  - [ ] Checkbox: "Kill-Switch Global" (admin only)
  - [ ] Estado: Verde ("Sistema activo"), Naranja ("Pausado manualmente")
  - [ ] Tooltip: "Desactivar agente si se agota presupuesto global"
  - [ ] Log: cada toggle registra en auditoría
  - [ ] Test: toggle on/off → nuevas consultas con nivel=3 devuelven "sin presupuesto disponible"
- **Duración:** 0.5 días
- **Dependencias:** kill_switch logic (S2)
- **DoD:** UI funciona, auditoría registra

---

### 8.6 PROMOVEDOR MANUAL DE OFERTAS
- **Tareas:**
  - [ ] Página: "Promociones" (parcialmente en S7)
  - [ ] Actualizar:
    - [ ] Listar ofertas en staging_agente (watermark=false, 20%)
    - [ ] Para cada: mostrar validation_errors si tiene
    - [ ] Bulk select: checkbox por offer + botón "Promover Seleccionadas"
    - [ ] Filtro: "mostrar rechazadas por precio primero" (smart ordering)
  - [ ] Confirmación: "¿Promover X ofertas?" con detalles de reglas que se ignoran
  - [ ] Result: toaster "15 promovidas" con link a logs
- **Duración:** 1 día
- **Dependencias:** S7 parcial
- **DoD:** Promo manual fluida, auditoría registra

---

### 8.7 EXPORTAR INFORMES EN LOTE (CSV)
- **Tareas:**
  - [ ] Panel: botón "Exportar" en cada informe + bulk export
  - [ ] Formatos: PDF (existe), JSON (nuevo), CSV (nuevo)
  - [ ] Datos: etapas, costo, cobertura, alertas, regulaciones
  - [ ] Para PDF: ya existe; para JSON/CSV: estructura plana/semi-structured
  - [ ] Trigger: enqueue job, WebSocket notifica cuando listo
  - [ ] Descarga: link en panel, TTL 24h
- **Duración:** 1 día
- **Dependencias:** etapa 6 job (S3)
- **DoD:** Exporta funciona, formatos parseables

---

### 8.8 METRICAS DE SISTEMA (SLO DASHBOARD)
- **Tareas:**
  - [ ] Widget: "System Health"
  - [ ] SLOs:
    - [ ] Etapas 1-3: 99.5% uptime (verde si ✓)
    - [ ] Agente: 95% uptime (verde si ✓)
    - [ ] API latencia p95: 500ms (verde si < 500)
    - [ ] DB replication lag: 100ms (verde si < 100)
    - [ ] Cache hit rate: 80% (verde si > 80%)
  - [ ] Color: verde si cumplen, naranja si 90%, rojo si < 90%
  - [ ] Click → detalles gráficos (últimas 24h)
- **Duración:** 0.5 días
- **Dependencias:** Observabilidad (S1), Prometheus queries
- **DoD:** Widget muestra 5 SLOs

---

### 8.9 INTEGRACIÓN TAXA DE PLANES (ENTITLEMENTS)
- **Tareas:**
  - [ ] Mostrar en panel: Plan de cada tenant (demo-gratuita, demo-premium, etc.)
  - [ ] Beneficios por plan:
    - [ ] Gratuita: etapas 1-3, N1 solo
    - [ ] Premium: todas etapas, N1+N2+N3
  - [ ] Dropdown: admin puede cambiar plan (con confirmación)
  - [ ] Log: cambio de plan se audita
  - [ ] Efecto: nivel_maximo_costo se recalcula inmediato
- **Duración:** 0.5 días
- **Dependencias:** Auth + RLS (S1)
- **DoD:** Plan editable, efecto inmediato

---

### 8.10 DOCUMENTACIÓN Y CAPACITACIÓN
- **Tareas:**
  - [ ] Documento: `PANEL_USER_GUIDE.md` (5-10 páginas)
  - [ ] Secciones:
    - [ ] Overview de páginas principales
    - [ ] Cómo leer el cost-meter
    - [ ] Cómo revisar promotiones manuales
    - [ ] Cómo interpretar alertas
    - [ ] Export/reporting
  - [ ] Screenshots anotados para cada sección
  - [ ] Video (opcional): demo 5 min de panel (YouTube/drive)
  - [ ] Live training con CITE: 1h
- **Duración:** 1 día
- **Dependencias:** Todos (8.1-8.9)
- **DoD:** Guía clara, CITE capacitado

---

## DEFINITION OF DONE (S8)

- [ ] Dashboard de jobs en vivo (WebSocket)
- [ ] Cost-meter detallado con gráficos
- [ ] Audit trail completo, exportable
- [ ] Alertas (retiro + corpus + cobertura + worker)
- [ ] Kill-switch UI operacional
- [ ] Promo manual UI fluida
- [ ] Export informes (PDF/JSON/CSV)
- [ ] System Health SLO dashboard
- [ ] Planes y entitlements editables
- [ ] PANEL_USER_GUIDE.md + capacitación CITE

---

## RIESGOS S8

| Riesgo | Mitigación |
|---|---|
| Frontend es lento con datos grandes (30 días de costos) | Paginar, usar virtual scroll, backend cache aggregates |
| WebSocket desconecta, jobs no se actualizan | Reconectar auto cada 5s, fallback a polling |
| Audit trail crece muy rápido | Partición por mes en DB, archive a S3 después de 90d |
| Panel es confuso, CITE necesita entrenamiento recurrente | Tooltips en UI, links a guía, video tutorial |

---

## NOTAS

- **Equipo:** 2 frontend + 1 backend (APIs)
- **Diseño:** Mantener consistente con v2 (colores, iconografía)
- **Accesibilidad:** WCAG 2.1 AA (labels, contrast, keyboard nav)
