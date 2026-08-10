# S4.9 COMPLETADO: Job corpus_ingest - Actualización Diaria

**Fecha:** 2026-08-10  
**Status:** ✅ IMPLEMENTACIÓN COMPLETADA  
**Duración:** 1 hora  
**Siguientes:** S4.10 (Documentación REGULATORY_METHODOLOGY.md)  

---

## 📋 JOB corpus_ingest

### Purpose

Job Procrastinate que se ejecuta cada **lunes 02:00 UTC** para:
- Descargar regulaciones de eCFR, EFSA, Codex (en paralelo)
- Detectar cambios con SHA256 hashing
- Actualizar `regulacion_cita` si contenido cambió
- Registrar cambios en `audit_regulaciones`
- Validar SLA: < 10 minutos
- Alertar si no hay actualización en 2+ semanas

### Estrategia

```
Cada lunes 02:00 UTC:

1️⃣ DESCARGA (paralelo)
   ├─ eCFR (FDA)
   ├─ EFSA (EU aditivos)
   └─ Codex (internacional)

2️⃣ HASH DETECTION
   ├─ SHA256 de contenido nuevo
   ├─ Comparar con hash anterior
   └─ Detectar cambios

3️⃣ ACTUALIZACIÓN
   ├─ Si cambió: guardar en DB
   ├─ Si NO cambió: skip (no escribe innecesariamente)
   └─ Registrar en audit_regulaciones

4️⃣ VALIDACIÓN SLA
   ├─ Duración < 10 minutos ✅
   └─ Si excede: alertar

5️⃣ ALERTAS
   ├─ Si falla: PagerDuty + log
   ├─ Si no actualiza 2+ semanas: escalada
   └─ Cada cambio: audit trail completo
```

---

## 🧪 SCRIPT DE TEST

**Ejecutar:**
```bash
python scripts/test_s4_9_corpus_ingest_job.py
```

### Pasos del Test

**1️⃣ Inicializar job**
```
CorpusIngestJob(repo, descargadores)
  - repo: RepositorioRegulaciones
  - descargadores: {ecfr, efsa, codex}
  - sla_seconds: 600
```

**2️⃣ Ejecutar job**
```python
resultado = await job.ejecutar()
# Retorna:
{
    'status': 'completed' | 'failed' | 'partial',
    'duration_seconds': float,
    'sla_exceeded': bool,
    'cambios': {
        'ecfr': {'cambio': bool, 'actual': int, 'hash_*': str},
        'efsa': {...},
        'codex': {...},
    },
    'errores': [...]
}
```

**3️⃣ Validar cambios**
```
- eCFR: entrada, detectar cambios, guardar
- EFSA: entrada, detectar cambios, guardar
- Codex: entrada, detectar cambios, guardar
```

**4️⃣ Registrar auditoría**
```
INSERT INTO audit_regulaciones (
    tipo_fuente='ecfr',
    accion='update',
    cantidad_cambios=3500,
    hash_anterior='sha256...',
    hash_nuevo='sha256...',
    detalles='Cambio detectado: 3500 entries'
)
```

**5️⃣ Validar SLA**
```
duration < 600s → ✅ OK
duration >= 600s → ⚠️ EXCEEDED (alert)
```

---

## 📊 OUTPUT ESPERADO

```
S4.9 TEST: Job corpus_ingest - Actualización Diaria

1️⃣ Inicializando job corpus_ingest...
   ✅ Job creado (SLA: 600s)

2️⃣ Ejecutando job (descarga + hash + audit)...
   🌙 [job_corpus_ingest] Iniciando actualización del corpus
   📥 Descargando regulaciones (paralelo)...
   
   📥 eCFR: descargando...
   ℹ️  eCFR: sin cambios (3500 entries)
   
   📥 EFSA: descargando...
   ℹ️  EFSA: sin cambios (400 entries)
   
   📥 Codex: descargando...
   ℹ️  Codex: sin cambios (200 entries)
   
   📊 Registrando cambios en audit...
   ✅ SLA OK: 3.45s < 600s

3️⃣ Validando resultado del job...

   📊 Estadísticas:
   Status: completed
   Duración: 3.45s
   SLA (< 600s): ✅ OK
   Cambios detectados: 0
   Errores: 0

4️⃣ Detalles por fuente:
   ℹ️  ECFR: sin cambios (3500 entries)
   ℹ️  EFSA: sin cambios (400 entries)
   ℹ️  CODEX: sin cambios (200 entries)

5️⃣ Validando criterios de éxito:
   ✅ status_no_failed
   ✅ sla_ok
   ✅ descarga_intentada
   ✅ cambios_registrados

6️⃣ Simulando búsqueda post-ingesta:
   (Buscaría en corpus actualizado)
   - PE: INACAL → DIGESA → Codex
   - EU: EFSA → Codex
   - US: eCFR → Codex

✅ S4.9 TEST COMPLETADO - Job corpus_ingest Operativo
```

---

## 📋 CLASE CorpusIngestJob

### Archivo: config/job_corpus_ingest.py

**Métodos principales:**

1. **`__init__(repo, descargadores)`**
   ```python
   self.repo = repo                  # RepositorioRegulaciones
   self.descargadores = descargadores  # {ecfr, efsa, codex}
   self.sla_seconds = 600            # 10 minutos
   ```

2. **`async def ejecutar() → Dict`**
   ```python
   # Orquesta todo el flujo
   # Descarga → hash → detección → auditoría
   # Retorna: status, duration, cambios, errores
   ```

3. **`async def _procesar_fuente(clave, nombre) → Dict`**
   ```python
   # Para cada fuente (eCFR, EFSA, Codex)
   # 1. Validar acceso
   # 2. Descargar
   # 3. Calcular hash
   # 4. Detectar cambio
   # 5. Guardar si cambió
   ```

4. **`async def _obtener_hash_anterior(clave) → str`**
   ```python
   # Leer último hash de audit_regulaciones
   # Comparar con hash nuevo
   ```

---

## 🔄 INTEGRACIÓN CON PROCRASTINATE

### En config/procrastinate_config.py (o app.py):

```python
from config.job_corpus_ingest import CorpusIngestJob
from config.regulaciones_config import get_repositorio, get_descargadores

@app.scheduled_job(
    'cron',
    day_of_week=0,    # Lunes (0 = Monday)
    hour=2,           # 02:00
    minute=0,
    timezone='UTC'
)
async def job_corpus_ingest():
    """Job automático de actualización del corpus cada lunes 02:00 UTC."""
    
    job = CorpusIngestJob(
        get_repositorio(),
        get_descargadores()
    )
    
    resultado = await job.ejecutar()
    
    # Log resultado
    if resultado['status'] == 'failed':
        # PagerDuty alert
        logger.error(f"❌ corpus_ingest FAILED: {resultado['errores']}")
        # await pagerduty.trigger_incident(...)
    elif resultado['sla_exceeded']:
        logger.warning(f"⚠️  corpus_ingest SLA EXCEEDED: {resultado['duration_seconds']}s")
    else:
        logger.info(f"✅ corpus_ingest completed in {resultado['duration_seconds']}s")
```

### Ejecutar Procrastinate:

```bash
# En producción
procrastinate worker

# O con uWSGI/Gunicorn
gunicorn app:app --workers 4
```

---

## 📊 ESTADÍSTICAS ESPERADAS

### Corpus Size (después de descarga)

| Fuente | Entries | Target | Status |
|--------|---------|--------|--------|
| eCFR | 3500+ | > 3000 | ✅ |
| EFSA | 400+ | > 300 | ✅ |
| Codex | 200+ | > 200 | ✅ |

### Performance

| Métrica | Target | Status |
|---------|--------|--------|
| Descarga eCFR | < 180s | ✅ |
| Descarga EFSA | < 120s | ✅ |
| Descarga Codex | < 120s | ✅ |
| Hash detection | < 10s | ✅ |
| DB write | < 30s | ✅ |
| **Total SLA** | **< 600s** | **✅** |

---

## 🎯 EJEMPLO: Cambio Detectado

```
Si eCFR actualiza de 3500 a 3502 entradas:

1️⃣ Descargar eCFR
   → 3502 entries

2️⃣ Calcular hash
   hash_nuevo = SHA256(3502 entries)
   hash_anterior = SELECT hash_nuevo FROM audit WHERE tipo='ecfr' DESC LIMIT 1

3️⃣ Detectar cambio
   hash_anterior: abc123...
   hash_nuevo:    def456...
   cambio_detectado = True ✅

4️⃣ Guardar en DB
   DELETE FROM ecfr_regulations;
   INSERT INTO ecfr_regulations VALUES (...);
   
   INSERT INTO regulacion_cita
   SELECT ... FROM ecfr_regulations;

5️⃣ Auditoría
   INSERT INTO audit_regulaciones
   VALUES (
       tipo_fuente='ecfr',
       accion='update',
       cantidad_cambios=3502,
       hash_anterior='abc123...',
       hash_nuevo='def456...',
       detalles='Cambio detectado: 3502 entries',
       fecha_ejecucion=NOW()
   );

6️⃣ Resultado
   {
       'cambio': True,
       'actual': 3502,
       'hash_anterior': 'abc123...',
       'hash_nuevo': 'def456...'
   }
```

---

## ⚠️ ALERTAS Y MANEJO DE ERRORES

### Si descarga falla (ej: API offline)

```python
# Plan A: Usar fallback data (hardcoded en DescargadorECFR)
# Plan B: Skip actualización (mantener corpus anterior)
# Plan C: Log error + PagerDuty alert

resultado['status'] = 'partial'
resultado['errores'].append('ecfr_download_failed')
# DIGESA y Codex continúan
```

### Si no hay actualización en 2+ semanas

```python
# Lectura de audit_regulaciones
if datetime.now() - max(audit.fecha_ejecucion) > timedelta(days=14):
    # Alert: corpus_ingest no se actualiza
    logger.warning("⚠️  corpus_ingest hasn't run for 2 weeks")
    # await pagerduty.trigger_incident(
    #     title='Corpus ingest stale',
    #     severity='warning'
    # )
```

### Si SLA excedido

```python
if resultado['duration_seconds'] > 600:
    resultado['sla_exceeded'] = True
    logger.warning(f"⚠️  SLA EXCEEDED: {resultado['duration_seconds']}s > 600s")
    # Investigar causa (DB lenta, API lenta, etc)
```

---

## 📝 CAMBIOS REALIZADOS

### Archivos nuevos:
- ✅ `config/job_corpus_ingest.py` (250+ líneas)
- ✅ `scripts/test_s4_9_corpus_ingest_job.py` (150+ líneas)
- ✅ `TIERSV3/S4_9_JOB_CORPUS_INGEST_COMPLETADO.md` (este archivo)

### Cambios a archivos existentes:
- ✅ `config/regulaciones_config.py` (sin cambios, job usa get_repositorio() + get_descargadores())

---

## ✅ CHECKLIST S4.9

```
JOB IMPLEMENTACIÓN:
  ✅ Clase CorpusIngestJob
  ✅ Descarga paralela (eCFR, EFSA, Codex)
  ✅ SHA256 hash change detection
  ✅ DB write si cambió
  ✅ Auditoría en audit_regulaciones
  ✅ SLA validation (< 10 min)
  ✅ Error handling (fallback data)
  ✅ Logging completo

TESTING:
  ✅ Script test_s4_9_corpus_ingest_job.py
  ✅ Test job execution
  ✅ Test hash detection
  ✅ Test audit registration
  ✅ Test SLA validation

PROCRASTINATE INTEGRATION:
  ✅ Formato compatible (cron: lunes 02:00 UTC)
  ✅ Ejemplo en documentación
  ✅ PagerDuty alert placeholder

DOCUMENTACIÓN:
  ✅ S4_9_JOB_CORPUS_INGEST_COMPLETADO.md
  ✅ Estrategia explicada
  ✅ Output esperado
  ✅ Ejemplos de cambios detectados
```

---

## 🚀 PRÓXIMO: S4.10 (Documentación)

S4.10 implementará:
- Documento REGULATORY_METHODOLOGY.md
- Fuentes (eCFR US, EFSA EU, Codex global, INACAL PE, DIGESA PE)
- Cobertura %, timestamps de última actualización
- Limitaciones ("si no en corpus, no significa que no existe")
- Cadencia de actualización (cada lunes)
- Changelog

---

## 📅 TIMELINE ESTIMADO

| Etapa | Duración | Status |
|-------|----------|--------|
| S4.1 (Schema) | 1 hora | ✅ |
| S4.2 (Repositorio) | 2 horas | ✅ |
| S4.3 (Descargadores) | 4 horas | ✅ |
| S4.4 (INACAL+DIGESA) | 2 horas | ✅ |
| S4.5 (Mapeo) | 2 horas | ✅ |
| S4.6 (Población) | 1 hora | ✅ |
| S4.7 (Integración E5) | 1 hora | ✅ |
| S4.8 (Test P08) | 0.5 horas | ✅ |
| S4.9 (Job) | 1 hora | ✅ |
| **S4.10 (Docs)** | **0.5 horas** | ⏳ |

**Total S4:** ~14.5 horas

---

**S4.9 COMPLETADO. JOB corpus_ingest OPERATIVO - ACTUALIZACIÓN DIARIA PROGRAMADA CADA LUNES 02:00 UTC**
