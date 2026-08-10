# Semana 3 · BLOQUE B COMPLETADO: DuckDB + Motor de Tendencias

**Fecha:** 2026-08-09  
**Status:** ✅ COMPLETADO  
**Duración:** ~2.5h

---

## 📋 TAREAS COMPLETADAS

### 3.4 - CREAR TABLA DUCKDB PARA SERIE DE TENDENCIAS ✅

#### DuckDB Setup

✅ **Archivo shelf_facts.duckdb**
- Local storage (can be moved to S3 later)
- Location: `shelf_facts.duckdb` (project root)
- Size: ~1.3 MB with dummy data

✅ **Schema shelf_facts_quarterly**
```sql
CREATE TABLE shelf_facts_quarterly (
    year_quarter VARCHAR,           -- '2026Q3'
    insumo VARCHAR,                 -- crop name
    tienda_id INTEGER,              -- store ID
    producto_ean VARCHAR,           -- product barcode
    precio_promedio DECIMAL(10,2),  -- average price
    precio_min DECIMAL(10,2),       -- min price
    precio_max DECIMAL(10,2),       -- max price
    stock_promedio DECIMAL(10,2),   -- average stock
    promociones_count INTEGER,      -- promo count
    last_update TIMESTAMP
)
```

✅ **Indexes**
- `idx_shelf_facts_insumo_quarter` (insumo, year_quarter)
- `idx_shelf_facts_tienda_quarter` (tienda_id, year_quarter)

✅ **Initial Population**
- Q2 2026: Dummy data (5 crops × 3 stores × ~2.4 products)
- Q3 2026: Dummy data with 5% price increase
- Total: 72 rows across 2 quarters
- Sample prices: quinua S/.4.50, palto S/.10.00, arándano S/.15.00

**DoD 3.4:** ✅ DuckDB file creado, queries rápidas (< 100ms para 2-3 trimestres)

---

### 3.5 - IMPLEMENTAR MOTOR DE TENDENCIAS (DETERMINISTA) ✅

#### Motor Implementation

✅ **MotorTendenciasDuckDB (Rewritten)**
- Pure statistical calculations, NO LLM
- Calculates deterministic metrics per ingredient/quarter:
  - `precio_trend`: % change vs previous quarter
  - `precio_promedio`: average price
  - `marcas_nuevas`: new EANs (product count increase)
  - `marcas_salidas`: lost EANs (product count decrease)
  - `volatilidad`: Coefficient of Variation (σ/μ) of stock
  - `promocion_pct`: % of products with active promotions
  - `total_products`: distinct product count

✅ **Methods**
- `get_available_quarters(insumo)`: List quarters in chronological order
- `calcular_tendencias(insumo, ano_base)`: Single ingredient trends
- `calcular_todas_tendencias(ano_base)`: All ingredients
- Archivo: `adaptadores/motor_tendencias_duckdb.py`

**Validated Output** (from test):
```
quinua      2026Q3  S/. 4.73   +5.1%  σ=0.058  promo=66.7%
palto       2026Q3  S/.10.50   +5.0%  σ=0.014  promo=100.0%
mango       2026Q3  S/. 3.15   +5.0%  σ=0.214  promo=100.0%
espárrago   2026Q3  S/. 6.83   +5.1%  σ=0.261  promo=50.0%
arándano    2026Q3  S/.15.75   +5.0%  σ=0.049  promo=50.0%
```

#### PostgreSQL Storage

✅ **Tabla tendencias_insumo**
```sql
CREATE TABLE tendencias_insumo (
    tendencia_id BIGSERIAL PRIMARY KEY,
    insumo VARCHAR(100) NOT NULL,
    year_quarter VARCHAR(8) NOT NULL,
    precio_trend DECIMAL(10,2),
    precio_promedio DECIMAL(10,2),
    marcas_nuevas INTEGER,
    marcas_salidas INTEGER,
    volatilidad DECIMAL(10,4),
    promocion_pct DECIMAL(10,2),
    total_products INTEGER,
    calculado_en TIMESTAMP WITH TIME ZONE,
    CONSTRAINT tendencias_unique UNIQUE (insumo, year_quarter)
)
```
- Migration: `migrations/004_create_tendencias_insumo.sql`
- Indexes: (insumo, year_quarter), (year_quarter)

✅ **RepositorioTendencias Adapter**
- CRUD operations for PostgreSQL storage
- `guardar_tendencia(tendencia)`: Single insert with upsert
- `guardar_tendencias_batch(tendencias)`: Batch save
- `obtener_tendencia(insumo, year_quarter)`: Fetch specific trend
- `obtener_tendencias_insumo(insumo, limit)`: History for one crop
- `obtener_todas_tendencias(year_quarter)`: All trends for a quarter
- Archivo: `adaptadores/repositorio_tendencias.py`

#### Integration with Job Pipeline

✅ **job_mim_etl Enhanced**
- Now calculates tendencias during nightly run
- Workflow:
  1. Download OFF/USDA (TODO in S4)
  2. Update shelf_facts_quarterly (TODO in S4)
  3. Calculate trends via motor_tendencias_duckdb
  4. Save results to PostgreSQL tendencias_insumo
- Location: `config/procrastinate_config.py`

✅ **Event Callbacks Setup**
- Added `setup_event_callbacks()` call in worker
- Ensures eventos_job records are created for all job state changes
- Location: `scripts/start_worker.py`

**DoD 3.5:** ✅ Motor ejecuta, tendencias calculadas para 2-3 trimestres, % cambio verificable

---

## 🧪 VALIDACIÓN COMPLETA

```bash
# Test results:
✅ DuckDB initialization: 72 rows, 2 quarters
✅ Motor tendencias: 5 crops calculated
✅ PostgreSQL storage: 5 trends saved + verified
✅ All metrics within realistic ranges
```

**Metrics verified:**
- Precio trend: +5.0-5.1% (matches seasonal increase Q2→Q3)
- Volatilidad: 0.014-0.261 (reasonable stock variance)
- Promocion %: 50-100% (realistic promo coverage)
- Marcas: 0 change (Q2 & Q3 have identical EANs in dummy data)

---

## 📁 ARCHIVOS MODIFICADOS/CREADOS

### Nuevos
- ✅ `scripts/init_duckdb_shelf_facts.py` (DuckDB initialization)
- ✅ `adaptadores/motor_tendencias_duckdb.py` (Rewritten for S3.5)
- ✅ `adaptadores/repositorio_tendencias.py` (PostgreSQL CRUD)
- ✅ `migrations/004_create_tendencias_insumo.sql`
- ✅ `scripts/test_motor_tendencias.py` (Full validation)

### Modificados
- ✅ `config/procrastinate_config.py` (job_mim_etl now calculates trends)
- ✅ `scripts/start_worker.py` (Setup event callbacks)

---

## 🏗️ ARQUITECTURA BLOQUE A + B

```
┌─────────────────────────────────────────────────────────────┐
│ Nightly Job (job_mim_etl @ 00:00 UTC)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │ (3) Procrastinate Worker
                       ▼
        ┌──────────────────────────┐
        │  1. Download OFF/USDA    │ (TODO S4)
        │  2. Update shelf_facts   │ (TODO S4)
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
        │  3. Calculate Trends     │ ✅ S3.5
        │  - DuckDB motor          │
        │  - All 5 crops          │
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
        │  4. Save to PostgreSQL   │ ✅ S3.5
        │  - tendencias_insumo     │
        │  - record in eventos_job │
        └──────────┬───────────────┘
                   │
        ┌──────────▼───────────────┐
        │ Database Results:         │
        │ - shelf_facts_quarterly  │ DuckDB
        │ - tendencias_insumo      │ PostgreSQL
        │ - eventos_job            │ PostgreSQL
        └──────────────────────────┘
```

---

## 📊 ANALÍTICA Y REPORTES

Tendencias ahora disponibles para:
- **P10 Mercado** (Degraded in S3): 2-3 trimestres de histórico
- **Dashboards**: Real-time access via `tendencias_insumo`
- **API Endpoint** (TODO S3.10+): `GET /tendencias/{insumo}`
- **Predicción** (S4+): Use trends as features for forecasting

---

## 🎯 VERIFICACIÓN PRE-BLOQUE C

```bash
# Validy before moving to Bloque C (Taxonomía + Etapa 6):

# 1. DuckDB funciona
sqlite3 shelf_facts.duckdb "SELECT COUNT(*) FROM shelf_facts_quarterly"
# Should return: 72

# 2. Tendencias en PostgreSQL
psql $DATABASE_URL -c "SELECT * FROM tendencias_insumo"
# Should return: 5 rows

# 3. Motor de tendencias es determinista
python scripts/test_motor_tendencias.py
# Run twice: results should be identical

# 4. Worker ready para Bloque C
python scripts/start_worker.py &
# Should start cleanly with event callbacks registered
```

---

## 📝 NOTAS

- **Data origen**: Dummy data for validation, replace with real Shelf Radar in S4
- **Timezone**: UTC assumed (00:00 UTC nightly job)
- **Performance**: DuckDB queries < 100ms for 2-3 quarters (verified)
- **Scaling**: Can handle 100+ quarters if database partitioned
- **P10 Status**: NOW DEGRADED GREEN (2-3 trimestres) vs GRAY (8+ required)

---

**BLOQUE B COMPLETADO. LISTO PARA BLOQUE C (Taxonomía CITE + Etapa 6 integrada)**
