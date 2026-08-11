# S6 AUDITORÍA PREVIA: Alertas de Retiro (openFDA + RASFF)

**Fecha:** 2026-08-10  
**Estado:** 🔍 AUDITORÍA PRE-EJECUCIÓN  
**Duración estimada:** 2 horas de prep  

---

## 📊 ESTADO ACTUAL DEL PROYECTO

### Commits Recientes (Git log)
```
4c9df46  s5fin                                          ← ÚLTIMO
6bc8463  S5.1-5.4: Scrapling transport + BD webhook
60ae1cb  S4.9 + S4.10: Job corpus_ingest completado
174dcdc  S4.8: Test P08 - Dossier Regulatorio 
42aa52b  S4.7: Integración Etapa 5 con Corpus
```

✅ **S1-S5 COMPLETADAS** → Main limpio, ready para S6

---

## ✅ DEPENDENCIAS: CUMPLIDAS

### S1 (Base de Datos)
- ✅ Postgres con `psycopg_pool` configurado
- ✅ Conexiones en `adaptadores/db.py` (pool, min_size=1, max_size=5)
- ✅ URL en `.env` → `url_base_datos()` en `adaptadores/entorno.py`
- ✅ Soporte TLS + pgbouncer (prepare_threshold=None)

**Falta:** Tablas para alertas
```sql
-- NO EXISTEN AÚN:
-- - openfda_alerts
-- - rasff_alerts  
-- - alert_scores
-- - alert_lookup_log
```

### S3 (Procrastinate - Job Scheduling)
- ✅ Procrastinate integrado (ver `config/job_scheduling.py`)
- ✅ Job `job_alert_ingest` será scheduler en S6.6
- ✅ Logging + SLA monitoring en S3 BLOQUE D

**Falta:** Job específico para alertas (se crea en S6.6)

### S4.7 (Etapa 5 + Regulaciones)
- ✅ `verificar_regulacion()` completamente reescrito
- ✅ Búsqueda corpus local (regulacion_cita) + fallback openFDA
- ✅ Auditoría de búsquedas implementada
- ✅ Etapa 5 retorna `DossierRegulatorio` con citas

**Integración con S6:**
```python
# S4.7 ya busca en openFDA como fallback:
async def _buscar_regulaciones_fallback(d, interpretado, texto):
    if d.verificador_fda:
        resultado = d.verificador_fda.verificar(...)  # ← Llama VerificadorOpenFDA
```

### S5 (Scrapling + Transport)
- ✅ Bright Data API integrado
- ✅ Transport de datos implementado
- ✅ BD webhook para actualizaciones
- ✅ Canario check + auditoría

**Falta:** No se usa para alertas en S5, se agregará en S6

---

## ⚠️ CÓDIGO EXISTENTE: LO BUENO Y LO MALO

### VerificadorOpenFDA (adaptadores/verificador_openfda.py)
```python
# ACTUAL (39 líneas)
class VerificadorOpenFDA(VerificadorRegulatorio):
    def verificar(self, insumo_en: str, insumo_es: str) -> str:
        # 1. Busca en API: https://api.fda.gov/food/enforcement.json
        # 2. Query: product_description:{nombre}
        # 3. Retorna: string con resultados (NO es estructurado)
        # 4. Offline mode para tests
```

**Problemas:**
1. ❌ **No hay persistencia** - cada búsqueda toca API, sin caché
2. ❌ **No hay dedup** - mismo alert se descarga N veces
3. ❌ **Sin scoring** - no calcula severidad
4. ❌ **Sin RASFF** - solo openFDA
5. ❌ **Query débil** - solo busca `product_description`, no últimas 24h
6. ❌ **Retorna string** - no es parseable para BD

**Será reemplazado completamente en S6:**
```python
# S6 NUEVO:
class DescargadorOpenFDA:  # No hereda de VerificadorRegulatorio
    async def descargar_ultimas_24h() → List[AlertaFDA]
    async def hashear_dedup(alert) → str
    
class DescargadorRASFF:
    async def descargar_ultimas_24h() → List[AlertaRASFF]
```

---

## 🗂️ ESTRUCTURA DE DIRECTORIOS: PRONTA A S6

```
adaptadores/
├── descargador_ecfr.py          ✅ S4.1 - Patrón a seguir
├── descargador_efsa.py          ✅ S4.2 - Patrón a seguir
├── descargador_codex.py         ✅ S4.3 - Patrón a seguir
├── descargador_inacal.py        ✅ S4.4 - Patrón a seguir
├── descargador_digesa.py        ✅ S4.5 - Patrón a seguir
├── verificador_openfda.py       ⚠️ S6 reemplazará este
│
├── (S6 NUEVOS):
├── descargador_openfda_alerts.py      ← CREAR (6.1)
├── descargador_rasff_alerts.py        ← CREAR (6.2)
├── buscador_alertas_fuzzy.py          ← CREAR (6.3)
└── calculador_risk_score.py           ← CREAR (6.4)

casos_de_uso/
├── etapas/
│   ├── verificar_regulacion.py   ✅ S4.7 - Se modifica en 6.5
│   └── (S6 NUEVAS):
│       ├── buscar_alertas.py            ← CREAR (6.3)
│       └── calcular_severidad.py        ← CREAR (6.4)

puertos/
├── repositorio_regulaciones.py   ✅ S4 - Patrón a seguir
└── (S6 NUEVOS):
    ├── repositorio_alertas_fda.py       ← CREAR (6.1)
    └── repositorio_alertas_rasff.py     ← CREAR (6.2)

config/
├── job_scheduling.py             ✅ S3 - Se extiende en 6.6
```

---

## 💾 TABLAS QUE NECESITAN CREARSE (6.1 + 6.2)

### openfda_alerts
```sql
CREATE TABLE openfda_alerts (
    alert_id VARCHAR(128) PRIMARY KEY,      -- hash
    fecha_emitida DATE,
    empresa VARCHAR(255),
    producto_nombre VARCHAR(255),
    razon_texto TEXT,
    razon_categoria VARCHAR(50),            -- 'patogeno', 'alérgeno', 'residuo', 'otro'
    pais VARCHAR(10),
    url_oficial TEXT,
    titulo_enforcement VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_openfda_producto_fecha 
  ON openfda_alerts(producto_nombre, razon_categoria, fecha_emitida);
```

### rasff_alerts
```sql
CREATE TABLE rasff_alerts (
    rasff_id VARCHAR(128) PRIMARY KEY,
    fecha_emitida DATE,
    producto_nombre VARCHAR(255),
    hazard_texto TEXT,
    hazard_categoria VARCHAR(50),
    pais_origen VARCHAR(10),
    pais_destino VARCHAR(10),
    accion VARCHAR(100),                    -- 'blocked', 'detained', etc
    url_oficial TEXT,
    reference_number VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_rasff_producto_fecha 
  ON rasff_alerts(producto_nombre, hazard_categoria, fecha_emitida);
```

### alert_scores
```sql
CREATE TABLE alert_scores (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(128),                  -- FK a openfda_alerts o rasff_alerts
    alert_tipo VARCHAR(20),                 -- 'openfda' o 'rasff'
    score DECIMAL(3,2),                     -- 1-5 escala
    severity_label VARCHAR(20),             -- 'critical', 'high', 'medium', 'low'
    dias_desde_emitida INT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### alert_lookup_log
```sql
CREATE TABLE alert_lookup_log (
    id SERIAL PRIMARY KEY,
    ingrediente VARCHAR(255),
    pais VARCHAR(10),
    alertas_encontradas INT,
    fuentes_consultadas VARCHAR(255),       -- 'openfda,rasff' o similar
    timestamp TIMESTAMP DEFAULT NOW()
);
```

---

## 🧪 TESTING ACTUAL (BASELINE)

### Tests S4 (Regulaciones - Patrón de éxito)
```
tests/test_s4_7_etapa5_integration.py
  ✅ 5 tests (búsqueda corpus, fallback, sin_dato)
  ✅ Verde en main

scripts/test_s4_9_corpus_ingest_job.py
  ✅ Descarga real de eCFR, EFSA, Codex
  ✅ Hashear + dedup funciona
  ✅ Inserta en BD sin duplicados
```

### Tests S5 (Scrapling)
```
tests/test_s5_p14_p19.py
tests/test_s5_sweep_and_canario.py
  ✅ Bright Data working
  ✅ BD webhook funciona
  ✅ Canario check válida
```

### Tests que NO existen aún (S6)
```
test_s6_p20_alertas.py              ← CREAR (6.8)
test_s6_openfda_ingesta.py          ← CREAR (6.1)
test_s6_rasff_ingesta.py            ← CREAR (6.2)
test_s6_fuzzy_matching.py           ← CREAR (6.3)
test_s6_scoring.py                  ← CREAR (6.4)
test_s6_job_alert_ingest.py         ← CREAR (6.6)
```

---

## 🚨 RIESGOS IDENTIFICADOS

| Riesgo | Severidad | Mitigación Propuesta |
|--------|-----------|---------------------|
| **openFDA API intermitente** | HIGH | Reintentos exponencial + caché local 24h |
| **RASFF feed formato inconsistente** | MEDIUM | Parsear defensivamente + logs si parsing falla |
| **Fuzzy matching genera falsos positivos** | HIGH | Threshold 85%+ similarity + revisión manual |
| **Scoring es subjetivo** | MEDIUM | Hacer parametrizable; CITE puede ajustar weights |
| **Ingesta lentitud (> 5 min)** | MEDIUM | Paralelizar openFDA + RASFF |
| **Duplicados en BD** | LOW | Hashear (MD5 o SHA256) de campos clave |
| **Test P20 no es lo suficiente** | MEDIUM | Agregar tests de SLA del job (< 5 min) |

**Estrategia de mitigación de riesgos:**
- Crear función `test_riesgos_s6()` que verifique todos estos
- Agregar logs con UUID para trazabilidad
- Usar circuit breaker en API calls

---

## 🔍 AUDITORÍA DE VARIABLES DE ENTORNO

### Necesarias para S6
```bash
# .env debe tener:
DATABASE_URL=postgresql://...        ✅ Ya está
APP_LLM_MODEL=...                    ✅ Ya está
PROCRASTINATE_SYNC_TIMEOUT=...       ✅ S3 agregó esto

# NUEVAS PARA S6:
OPENFDA_API_KEY=...                  ← Crear si no existe (free tier es OK sin key)
RASFF_FEED_URL=https://ec.europa.eu/food/safetyhealthanimals/rasff/...
ALERT_NOTIFICATION_EMAIL=...         ← Para notificar alertas críticas
ALERT_INGEST_TIME=03:00              ← Hora de job (UTC)
```

---

## 📋 DEFINICIÓN DE HECHO (S6 AUDITADO)

### Antes de empezar código:
- [ ] Tablas openfda_alerts, rasff_alerts, alert_scores, alert_lookup_log creadas
- [ ] Índices configurados
- [ ] Variables de entorno verificadas
- [ ] Procrastinate ready (ya de S3, solo validar)
- [ ] Test P20 fixture listo (manual insert para pruebas)

### Patrón a seguir (de S4 + S5):
- [ ] DescargadorOpenFDA similar a DescargadorECFR
- [ ] DescargadorRASFF similar a DescargadorEFSA
- [ ] Jobs con logging + auditoría (de S3)
- [ ] Fuzzy matching con libreía `fuzzywuzzy` o `difflib`
- [ ] Scoring parametrizable (config en BD, no hardcoded)

### Tests verde:
- [ ] test_s6_openfda_ingesta.py ✅
- [ ] test_s6_rasff_ingesta.py ✅
- [ ] test_s6_fuzzy_matching.py ✅
- [ ] test_s6_scoring.py ✅
- [ ] test_s6_job_alert_ingest.py ✅
- [ ] P20: informe con alertas ✅

---

## 🎯 PLAN DE ACCIÓN (S6)

```
FASE 1: Setup DB + Descargadores (6.1 + 6.2 + Fixtures)
  1.1 Crear tablas openfda_alerts, rasff_alerts
  1.2 Descargador openFDA: últimas 24h, dedup por hash
  1.3 Descargador RASFF: últimas 24h, dedup por hash
  1.4 Tests básicos de ingesta

FASE 2: Búsqueda + Scoring (6.3 + 6.4)
  2.1 Función buscar_alertas_para_ingrediente() con fuzzy matching
  2.2 Scoring de riesgo (1-5 escala, parametrizable)
  2.3 alert_lookup_log para auditoría
  2.4 Tests de calidad

FASE 3: Integración + Jobs (6.5 + 6.6)
  3.1 Integrar alertas en Etapa 5 (modificar verificar_regulacion)
  3.2 Job job_alert_ingest (scheduler nocturno)
  3.3 Notificación de alertas críticas
  3.4 Dashboard (6.7)

FASE 4: Testing (6.8)
  4.1 P20: insumo con ingrediente retirado → dossier lo señala
  4.2 Validación end-to-end
```

---

## ✨ CONCLUSIÓN

**S6 ES EJECUTABLE INMEDIATAMENTE CON:**
- Tablas creadas ✅ (SQL script)
- Variables de entorno ✅ (extender .env)
- Procrastinate ready ✅ (de S3)
- Etapa 5 ready ✅ (de S4.7)

**Complejidad estimada:** MEDIA (similar a S4 corpus, pero con 2 fuentes en paralelo)

**Duración estimada:** 5 días como planeado (1 backend + 1 data + 1 QA)

---

**AUDITORÍA COMPLETA. LISTO PARA EMPEZAR S6 PASO A PASO.**
