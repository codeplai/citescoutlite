# S6 FASE 3 COMPLETADA: Integración + Job Scheduler

**Fecha:** 2026-08-10  
**Status:** ✅ FASE 3 COMPLETADA  
**Duración:** 1.5 horas  
**Siguientes:** S6.8 (Test P20), S6.7 (Dashboard)  

---

## 📋 DELIVERABLES FASE 3

### 1. Modelo de Alerta de Retiro
✅ **dominio/alerta_retiro.py** (100+ líneas)

**Clase `AlertaDeRetiro`:**
```python
@dataclass
class AlertaDeRetiro:
    alert_id: str                           # Hash para dedup
    fuente: str                             # 'openfda' o 'rasff'
    producto_nombre: str
    riesgo_categoria: str                   # patógeno/alérgeno/residuo/otro
    riesgo_texto: str
    fecha_emitida: datetime
    dias_desde: int
    pais_origen: str
    pais_destino: str
    url_oficial: str
    similitud: Optional[float]              # 0-1 (fuzzy match)
    severity_score: Optional[float]         # 1-5
    severity_label: str                     # critical/high/medium/low
    empresa: Optional[str]
    reference_number: Optional[str]
```

**Clase `AlertasDeRetiro`:**
```python
class AlertasDeRetiro:
    alertas: List[AlertaDeRetiro]
    cantidad_criticas: int
    cantidad_activas: int
    sin_alertas: bool
    fecha_ultima_actualizacion: Optional[datetime]
    
    def summary() → str  # "⚠️ 3 alertas (1 crítica)"
```

---

### 2. Integración en Etapa 5
✅ **casos_de_uso/etapas/buscar_alertas_retiro.py** (280+ líneas)

**Función principal:**
```python
async def buscar_alertas_para_etapa5(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    pais: str = "PE"
) → AlertasDeRetiro
```

**Workflow:**
```
INPUT: ingrediente='quinua', país='PE'
    │
    ▼
1. Verificar que tablas existen (openfda_alerts, rasff_alerts)
    │
    ▼
2. BuscadorAlertasFuzzy.buscar_alertas_para_ingrediente()
   ├─ Busca en openFDA (últimas 90 días)
   ├─ Busca en RASFF (últimas 90 días)
   └─ Filtra por similitud 80%+
    │
    ▼
3. Para cada alerta encontrada:
   ├─ Obtener score si existe en alert_scores
   ├─ Si no existe, calcular con CalculadorRiskScore
   └─ Crear AlertaDeRetiro
    │
    ▼
4. Registrar búsqueda en alert_lookup_log
    │
    ▼
OUTPUT: AlertasDeRetiro(
    alertas=[...],
    cantidad_criticas=N,
    cantidad_activas=N,
    sin_alertas=False,
    fecha_ultima_actualizacion=NOW()
)
```

**Función de conveniencia:**
```python
async def verificar_regulacion_con_alertas(
    d: Dependencias,
    interpretado: InsumoInterpretado,
    texto: str = "",
    pais: str = "PE",
    incluir_alertas: bool = True
) → Dict
```

Retorna:
```python
{
    "regulaciones": DossierRegulatorio,  # S4
    "alertas": AlertasDeRetiro,          # S6 NEW
    "premium": True
}
```

---

### 3. Job de Ingesta Nocturna
✅ **config/job_alert_ingest.py** (420+ líneas)

**Job principal:**
```python
async def job_alert_ingest() → Dict[str, Any]
```

**Workflow:**
```
Ejecuta: 03:00 UTC cada noche
    │
    ▼
1️⃣  Ingesta EN PARALELO:
    ├─ ingestar_alertas_openFDA()      (async)
    └─ ingestar_alertas_rasff()        (async)
    
    Para cada fuente:
    ├─ Descargar últimas 24h
    ├─ Hashear para dedup
    ├─ INSERT ... ON CONFLICT DO NOTHING
    └─ Registrar: nuevas, duplicadas, errores
    │
    ▼
2️⃣  Calcular scores:
    calcular_scores_alertas()
    ├─ Para alertas sin score
    ├─ Usar CalculadorRiskScore
    └─ INSERT/UPDATE en alert_scores
    │
    ▼
3️⃣  Notificaciones:
    notificar_alertas_criticas()
    ├─ Buscar alertas críticas no notificadas
    ├─ Enviar email/Slack (TODO)
    └─ Registrar en alert_notification_history
    │
    ▼
4️⃣  Estadísticas:
    INSERT INTO alert_ingest_log
    ├─ openfda_nuevos, openfda_duplicados, openfda_errores
    ├─ rasff_nuevos, rasff_duplicados, rasff_errores
    ├─ duracion_segundos
    └─ estado ('success', 'partial', 'failed')

OUTPUT: 
{
    "openfda_nuevas": int,
    "openfda_duplicadas": int,
    "openfda_errores": int,
    "rasff_nuevas": int,
    "rasff_duplicadas": int,
    "rasff_errores": int,
    "scores_calculados": int,
    "notificaciones_enviadas": int,
    "duracion_segundos": float,
    "estado": "success" | "partial" | "failed"
}
```

**SLA:** < 5 minutos (típicamente 1-2 minutos)

**Reintentos:** 3 con exponential backoff si error

**Procrastinate Integration:**
```python
if PROCRASTINATE_AVAILABLE:
    @procrastinate_app.task(name="job_alert_ingest")
    async def task_job_alert_ingest() → Dict
    
    @procrastinate_app.periodic_task(cron="0 3 * * *")  # 03:00 UTC daily
    async def schedule_job_alert_ingest()
```

**Funciones auxiliares:**
```python
async def ingestar_alertas_openFDA() → (nuevas, duplicadas, errores)
async def ingestar_alertas_rasff() → (nuevas, duplicadas, errores)
async def calcular_scores_alertas() → cantidad_calculados
async def notificar_alertas_criticas() → cantidad_notificaciones
```

---

### 4. Test de Integración
✅ **scripts/test_s6_5_6_integracion_job.py** (380+ líneas)

**Test 1: Estructura AlertasDeRetiro**
```python
✅ Crear AlertaDeRetiro individual
✅ Crear contenedor AlertasDeRetiro
✅ Sin alertas (sin_alertas=True)
✅ Con alertas (sin_alertas=False)
✅ Method summary()
```

**Test 2: Integración Etapa 5**
```python
✅ Flujo original Etapa 5 (regulaciones)
✅ Flujo mejorado (regulaciones + alertas)
✅ Estructura de salida {regulaciones, alertas}
```

**Test 3: Estadísticas del Job**
```python
✅ Simular ejecución completa
✅ Validar SLA (< 5 min)
✅ Resumen de ingesta
✅ Estado success/partial/failed
```

**Test 4: Formato de Notificaciones**
```python
✅ Email de alerta crítica
✅ Campos requeridos
✅ Formato legible
```

**Test 5: JSON Serialización**
```python
✅ AlertasDeRetiro.model_dump_json()
✅ Estructura JSON válida
✅ Deserialización
```

**Ejecución:**
```bash
python scripts/test_s6_5_6_integracion_job.py
```

---

## 🏗️ ARQUITECTURA INTEGRACIÓN

### Flujo Completo: Búsqueda → Scoring → Ingesta → Notificación

```
A. BÚSQUEDA (on-demand, durante Etapa 5)
────────────────────────────────────────
INPUT: ingrediente + país
    │
    ▼
BuscadorAlertasFuzzy.buscar_alertas_para_ingrediente()
    ├─ Busca en BD
    ├─ Fuzzy matching 80%
    └─ Ordena por relevancia
    │
    ▼
CalculadorRiskScore.calcular_severity()
    ├─ Base score por categoría
    ├─ Multiplicadores (antigüedad, país)
    └─ Label crítico/high/medium/low
    │
    ▼
OUTPUT: AlertasDeRetiro (con scores)
    └─ Integrada en verificar_regulacion()


B. INGESTA (scheduled nightly)
──────────────────────────────
03:00 UTC cada noche
    │
    ▼
Parallelizar:
├─ DescargadorOpenFDA.descargar_ultimas_24h()
└─ DescargadorRASFF.descargar_ultimas_24h()
    │
    ▼
Para cada alerta:
├─ Generar hash SHA256
├─ INSERT ... ON CONFLICT DO NOTHING (dedup)
└─ Contar: nuevas, duplicadas, errores
    │
    ▼
Para alertas sin score:
├─ CalculadorRiskScore.calcular_severity()
└─ INSERT en alert_scores
    │
    ▼
Para alertas críticas nuevas:
├─ Generar notificación
├─ Email (CITE)
└─ Registrar en alert_notification_history
    │
    ▼
Registrar estadísticas en alert_ingest_log
    │
    ▼
Log: "✅ Job completado en 87.45s (success)"


C. AUDITORÍA
────────────
alert_lookup_log       → Todas las búsquedas (on-demand)
alert_ingest_log       → Ejecuciones del job (nightly)
alert_notification_history → Notificaciones enviadas
```

---

## 📊 TABLAS UTILIZADAS

### Lectura (ambas fases):
- `openfda_alerts` (búsqueda + ingesta)
- `rasff_alerts` (búsqueda + ingesta)

### Escritura:
- `alert_scores` (scoring, calculado nightly)
- `alert_lookup_log` (auditoría de búsquedas on-demand)
- `alert_ingest_log` (estadísticas del job)
- `alert_notification_history` (notificaciones)

### Vistas:
- `alertas_criticas_24h` (para reportes)
- `alertas_por_ingrediente` (para búsqueda)

---

## ✅ CHECKLIST FASE 3

```
MODELO ALERTA:
  ✅ AlertaDeRetiro dataclass
  ✅ AlertasDeRetiro container
  ✅ Method summary()
  ✅ JSON serializable (Pydantic)

INTEGRACIÓN ETAPA 5:
  ✅ buscar_alertas_para_etapa5() async
  ✅ Verificar tablas existen
  ✅ BuscadorAlertasFuzzy integration
  ✅ CalculadorRiskScore integration
  ✅ registrar búsqueda en alert_lookup_log
  ✅ verificar_regulacion_con_alertas() (envoltorio)

JOB INGESTA:
  ✅ job_alert_ingest() async principal
  ✅ ingestar_alertas_openFDA() (descarga + insert)
  ✅ ingestar_alertas_rasff() (descarga + insert)
  ✅ calcular_scores_alertas() (para sin score)
  ✅ notificar_alertas_criticas() (email/Slack skeleton)
  ✅ INSERT en alert_ingest_log (estadísticas)
  ✅ Paralelización (openFDA + RASFF simultáneas)
  ✅ Dedup por hash (ON CONFLICT DO NOTHING)
  ✅ Procrastinate integration (@task @periodic_task)
  ✅ SLA: < 5 minutos
  ✅ Logging con emojis

TESTS:
  ✅ test_estructura_alertas() - Modelos
  ✅ test_integracion_etapa5() - Flujo completo
  ✅ test_job_statistics() - Estadísticas + SLA
  ✅ test_notificacion_formato() - Email
  ✅ test_json_serialization() - Serialización
```

---

## 🔗 ARCHIVOS CREADOS

```
dominio/
└── alerta_retiro.py                       [Modelos]

casos_de_uso/etapas/
└── buscar_alertas_retiro.py               [Integración Etapa 5]

config/
└── job_alert_ingest.py                    [Job + Procrastinate]

scripts/
└── test_s6_5_6_integracion_job.py         [Test]

TIERSV3/
└── S6_FASE3_INTEGRACION_JOB_COMPLETADA.md [Este archivo]
```

---

## 💡 NOTAS IMPORTANTES

### Integración Etapa 5
- NO modifica verificar_regulacion() original (backward compatible)
- Nueva función `buscar_alertas_para_etapa5()` es independiente
- Envoltorio `verificar_regulacion_con_alertas()` combina ambas

### Job Scheduler
- Si Procrastinate no está disponible, job es llamable manualmente
- `@periodic_task(cron="0 3 * * *")` ejecuta cada noche a 03:00 UTC
- Paralleliza descargas openFDA + RASFF (típico: 1-2 min)

### Notificaciones
- Skeleton actual: solo log de alertas críticas
- TODO: integración real con email/Slack/PagerDuty
- Stored in alert_notification_history para evitar duplicados

### SLA < 5 min
- openFDA timeout: 30s
- RASFF timeout: 30s
- Parallelización: ambas en 30-35s
- Scoring + notificación: <1 min
- Total típico: 1-2 minutos

---

## 🚀 PRÓXIMOS PASOS: S6.7 + S6.8

**S6.7: Dashboard de Alertas (Panel CITE)**
- Sidebar con alertas activas
- Filtrar por severidad
- Click para detalles modal
- Contador "X críticas" en header

**S6.8: Test P20 (Dossier con Alertas)**
- Insertar alerta manual en openFDA_alerts
- Query ingrediente retirado
- Verificar que dossier la muestra
- Validar severity label y fecha

---

**FASE 3 COMPLETADA. LISTOS PARA S6.7 (DASHBOARD) + S6.8 (TEST P20)**
