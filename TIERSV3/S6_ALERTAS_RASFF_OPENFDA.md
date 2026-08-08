# Semana 6 · ALERTAS DE RETIRO (RASFF + openFDA)

**Objetivo:** Alertas automáticas si ingrediente fue retirado; scoring de riesgo integrado en dossier.

**Duración:** 5 días · **Equipo:** Backend (1) + Data (1) + QA (1)

---

## ITEMS SEMANA 6

### 6.1 DESCARGAR OPENFDA /FOOD/ENFORCEMENT DIARIAMENTE
- **Descripción:** Enforcement actions, recalls, market withdrawals desde FDA
- **Tareas:**
  - [ ] API: `https://api.fda.gov/food/enforcement.json`
  - [ ] Query: últimas 24h (parámetro `search=report_date:[X TO Y]`)
  - [ ] Campos: empresa, producto, razón (patógeno, alérgeno, residuo, foreign object), fecha, país
  - [ ] Guardar tabla `openfda_alerts`:
    - `alert_id, fecha_emitida, empresa, producto_nombre, razón_texto, razón_categoría (patógeno/alérgeno/residuo), país, url_oficial, titulo_enforcement`
  - [ ] Índice: (producto_nombre, razón_categoría, fecha_emitida)
  - [ ] Hashear para dedup (mismo enforcement no se ingiere 2x)
- **Duración:** 1 día
- **Dependencias:** DB (S1)
- **DoD:** openFDA indexada, 100+ alerts disponibles, dedup funciona

---

### 6.2 DESCARGAR RASFF (SISTEMA EUROPEO) DIARIAMENTE
- **Descripción:** Rapid alert system for food (UE)
- **Tareas:**
  - [ ] Fuente: RASFF portal (`https://ec.europa.eu/food/safetyhealthanimals/rasff/`)
  - [ ] Descargar feed XML/JSON; parsear últimas 24h
  - [ ] Campos: producto, hazard (tipo de riesgo), país origen, país destino, acción (blocked, detained, etc.)
  - [ ] Guardar tabla `rasff_alerts`:
    - `rasff_id, fecha_emitida, producto_nombre, hazard_texto, hazard_categoría, país_origen, país_destino, acción, url_oficial, reference_number`
  - [ ] Índice: (producto_nombre, hazard_categoría, fecha_emitida)
- **Duración:** 1 día
- **Dependencias:** DB (S1)
- **DoD:** RASFF indexada, 50+ alerts disponibles

---

### 6.3 MAPEAR INGREDIENTES A ALERTAS (FUZZY MATCHING)
- **Descripción:** Vincular producto en informe con alertas relevantes
- **Tareas:**
  - [ ] Función `buscar_alertas_para_ingrediente(ingrediente_nombre, país='PE'/'EU'/'US') → [alert]`
  - [ ] Técnica: fuzzy string matching (80%+ similarity en nombre)
  - [ ] Buscar en openFDA si país='US', RASFF si país='EU'
  - [ ] Retornar: `[{fuente, producto_alert, razón, fecha, severidad}]`
  - [ ] Ejemplo: buscar "quinua" → puede encontrar "quinoa flour recall USA" si similarity > 80%
  - [ ] Guardar búsqueda en `alert_lookup_log` para auditoría
- **Duración:** 0.5 días
- **Dependencias:** openFDA (6.1), RASFF (6.2)
- **DoD:** Función retorna alertas relevantes, tasa de falsos positivos < 10%

---

### 6.4 IMPLEMENTAR SCORING DE RIESGO
- **Descripción:** Calcular severidad de alerta (critical/high/medium/low)
- **Tareas:**
  - [ ] Función `calcular_severity(alert) → severity_score`:
    ```python
    def score_alert(alert):
        # Patógeno = critical, alérgeno = high, residuo = medium, other = low
        base_score = {"patógeno": 4, "alérgeno": 3, "residuo": 2}.get(alert.razón, 1)
        
        # Antigüedad: si < 30 días, multiply by 1.5
        días_atrás = (now - alert.fecha).days
        if días_atrás < 30:
            base_score *= 1.5
        
        # País relevante: si mismo país que insumo, multiply by 2
        if alert.país == insumo.país_origen:
            base_score *= 2
        
        return min(5, base_score)  # cap at 5 (critical)
    ```
  - [ ] Guardar score en tabla `alert_scores`:
    - `alert_id, score (1-5), severity_label ('critical'/'high'/'medium'/'low'), días_desde_emitida`
- **Duración:** 0.5 días
- **Dependencias:** Mapeo (6.3)
- **DoD:** Scoring coherente, ejemplo verificable

---

### 6.5 INTEGRAR ALERTAS EN ETAPA 5 (REGULACIÓN + ALERTAS)
- **Descripción:** Etapa 5 ahora es "Regulación + Vigilancia de Retiros"
- **Tareas:**
  - [ ] Actualizar etapa 5:
    ```python
    @etapa(nombre="5_Regulacion_Alertas")
    def ejecutar(formulacion_resultado, país):
        # Regulación (como antes)
        regulaciones = buscar_regulaciones(...)
        
        # Nuevas: alertas
        alertas = []
        for ingrediente in formulacion_resultado.ingredientes:
            alerts = buscar_alertas_para_ingrediente(ingrediente, país)
            alertas.extend(alerts)
        
        return VerificacionResult(
            regulaciones=regulaciones,
            alertas=alertas  # NEW
        )
    ```
  - [ ] Informe PDF: nueva sección "Vigilancia de Retiros Activos"
    - [ ] Listar alertas por severidad
    - [ ] Incluir fecha de alerta, país, fuente (openFDA/RASFF)
- **Duración:** 0.5 días
- **Dependencias:** Scoring (6.4), etapa 5 (4.7)
- **DoD:** Etapa 5 retorna alertas, informe las muestra

---

### 6.6 JOB PARA ACTUALIZAR ALERTAS DIARIAMENTE
- **Descripción:** Ingesta nocturna de nuevas alertas
- **Tareas:**
  - [ ] Job: `job_alert_ingest` → corre 03:00 UTC cada noche
  - [ ] Pasos:
    1. Descargar openFDA last 24h
    2. Descargar RASFF last 24h
    3. Hashear; si nuevo, insert en DB
    4. Enviar notificación a CITE si hay alertas críticas para ingredientes piloto
  - [ ] Alert critica: envia email al CITE + PagerDuty low-priority
  - [ ] Logging: qué alertas nuevas se ingirieron
  - [ ] SLA: < 5 min
- **Duración:** 0.5 días
- **Dependencias:** Procrastinate (S3)
- **DoD:** Job corre noche, nuevas alertas aparecen en DB next morning

---

### 6.7 CREAR DASHBOARD DE ALERTAS EN PANEL CITE
- **Descripción:** Sidebar con alertas activas
- **Tareas:**
  - [ ] Panel: nueva sección "Alertas Activas"
  - [ ] Columnas: Ingrediente, Severidad (rojo/naranja/amarillo), Días desde, Fuente, Link
  - [ ] Filtrar: solo alertas activas (< 90 días)
  - [ ] Click en alerta → abre modal con detalles (razón completa, países afectados, empresas)
  - [ ] Contador: "X alertas críticas" en header rojo si > 0
- **Duración:** 1 día
- **Dependencias:** Scoring (6.4)
- **DoD:** Panel muestra alertas en vivo

---

### 6.8 TEST P20 (ALERTAS DE RETIRO)
- **Descripción:** Insumo con ingrediente retirado → dossier lo señala
- **Tareas:**
  - [ ] Setup: manualmente insertar alert en openFDA_alerts para "quinua" (ej: "E. coli contamination")
  - [ ] Query: "quinua" con nivel=3, país='PE'
  - [ ] Resultado: informe dossier incluye sección "Vigilancia"
  - [ ] Verificar: severity=crítica (color rojo), fecha < 30 días, link a FDA oficial
  - [ ] Test negativo: insumo sin alertas → sección dice "Sin alertas activas"
- **Duración:** 0.5 días
- **Dependencias:** Etapa 5 (6.5), scoring (6.4)
- **DoD:** P20 verde

---

### 6.9 INTEGRACIÓN CON MAPA COMERCIAL (OPCIONAL: ALERTAR SI TIENDA VENDE RETIRADO)
- **Descripción:** Si una tienda aún vende producto que fue retirado, flag
- **Tareas:**
  - [ ] Función `validar_producto_no_retirado(ean, país) → is_safe`:
    - [ ] Buscar EAN en alertas openFDA/RASFF
    - [ ] Si match encontrado, retornar `is_safe=false`
  - [ ] Usar en etapa 2b post-búsqueda: si `is_safe=false`, mark como `blocked_by_alert`
  - [ ] En informe: "Nota: Producto X fue reportado en retirada por [razón]; su presencia en góndola requiere investigación"
  - [ ] Esto es "nice to have" en v3; puede ser v4
- **Duración:** 0.5 días
- **Dependencias:** Todo (6.1-6.8)
- **DoD:** Validador implementado, puede usar si tiempo

---

## DEFINITION OF DONE (S6)

- [ ] openFDA /food/enforcement descargado y indexado diariamente
- [ ] RASFF descargado e indexado diariamente
- [ ] Función buscar_alertas_para_ingrediente implementada
- [ ] Scoring de riesgo (1-5 escala) calculado
- [ ] Etapa 5 integrada con búsqueda de alertas
- [ ] Dashboard de alertas en panel CITE
- [ ] Job alert_ingest configuro (cada noche)
- [ ] Notificación de alertas críticas implementada
- [ ] P20 verde (alertas en dossier)
- [ ] Documentación actualizada

---

## RIESGOS S6

| Riesgo | Mitigación |
|---|---|
| openFDA API intermitente | Agregar reintentos (exponential backoff), cache local de 24h |
| RASFF feed formato inconsistente | Parsear defensivamente, log si parsing falla |
| Fuzzy matching genera falsos positivos (alertas irrelevantes) | Ajustar threshold similarity (85%+), revisión manual de samples |
| Scoring es subjetivo, expertosa del CITE discrepa | Hacer scoring parametrizable; CITE puede ajustar weights |
| Ingesta tarda > 5 min | Paralelizar openFDA + RASFF; si aún lento, ejecutar en background |

---

## NOTAS

- **Equipo:** 1 backend (integración) + 1 data (descargas/parsing) + 1 QA (test)
- **Notificación crítica:** enviar email al CITE + Slack webhook si elige
- **Futuro (v4):** integración con supply chain para validación cruzada (¿realmente se compró ese lote retirado?)
