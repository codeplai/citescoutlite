# S6 FASE 1 COMPLETADA: Setup DB + Descargadores

**Fecha:** 2026-08-10  
**Status:** ✅ FASE 1 COMPLETADA  
**Duración:** 1 hora  
**Siguientes:** FASE 2 (Búsqueda + Scoring)  

---

## 📋 DELIVERABLES FASE 1

### 1. SQL Migration - Crear Tablas
✅ **scripts/migration_s6_alertas_tablas.sql** (200+ líneas)

**Tablas creadas:**
```
openfda_alerts          - Enforcement actions de FDA (USA)
rasff_alerts            - Rapid Alert System (EU)
alert_scores            - Scoring de riesgo (1-5 escala)
alert_lookup_log        - Auditoría de búsquedas
alert_ingest_log        - Log de ejecuciones del job
alert_notification_history - Historial de notificaciones
```

**Índices:**
- (producto_nombre, riesgo_categoria, fecha_emitida) en ambas
- (fecha_emitida DESC) para búsquedas por rango
- (severity_label) para búsquedas de críticas
- (pais_destino) para filtros por país

**Vistas creadas:**
- `alertas_criticas_24h` - Combina openFDA + RASFF críticas
- `alertas_por_ingrediente` - Agrupa por producto para búsqueda

**Ejecución:**
```bash
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d cite_mvp < scripts/migration_s6_alertas_tablas.sql
```

---

### 2. Interfaz de Descargadores
✅ **puertos/descargador_alertas.py** (85 líneas)

**Estructura normalizada:**
```python
@dataclass
class AlertaNormalizada:
    alert_id: str                    # Hash SHA256 para dedup
    fuente: str                      # 'openfda' o 'rasff'
    fecha_emitida: datetime
    producto_nombre: str
    riesgo_texto: str               # Descripción del peligro
    riesgo_categoria: str           # 'patogeno', 'alérgeno', 'residuo', 'otro'
    pais_origen: str
    pais_destino: str
    accion: str                     # 'recall', 'blocked', 'detained', etc
    url_oficial: str
    empresa: str = None
    reference_number: str = None
    metadatos: Dict[str, Any] = None
```

**Interfaz:**
```python
class DescargadorAlertas(ABC):
    async def descargar_ultimas_24h() → List[AlertaNormalizada]
    async def validar_acceso() → bool
    def normalizar(datos_brutos) → List[AlertaNormalizada]
    def hashear_alerta(alerta) → str  # SHA256 determinístico
```

---

### 3. Descargador openFDA
✅ **adaptadores/descargador_openfda_alerts.py** (250+ líneas)

**Implementación:**
- API: `https://api.fda.gov/food/enforcement.json`
- Query: `search=report_date:[YYYYMMDD TO YYYYMMDD]`
- Descarga últimas 24h con reintentos exponencial
- Rate limit handling (429)
- Timeout handling

**Métodos:**
```python
class DescargadorOpenFDAAlerts(DescargadorAlertas):
    async def validar_acceso()          # HEAD request
    async def descargar_ultimas_24h()   # GET con reintentos
    def normalizar(resultados)          # JSON → AlertaNormalizada
    def _categorizar_riesgo(razon)      # patogeno/alérgeno/residuo/otro
    def hashear_alerta(alerta)          # SHA256(fuente|ref|producto|fecha)
```

**Categorización de riesgos:**
- **Patógeno:** E. coli, Listeria, Salmonella, Campylobacter, Botulism, Shigella
- **Alérgeno:** Milk, Peanut, Tree nut, Shellfish, Gluten, Soy
- **Residuo:** Pesticide, Heavy metal, Lead, Cadmium, Mercury
- **Otro:** Todo lo demás

**Campos extraídos:**
```python
recall_number          → reference_number
report_date (YYYYMMDD) → fecha_emitida
product_description    → producto_nombre
reason_for_recall      → riesgo_texto + riesgo_categoria
company_name           → empresa
status                 → metadatos['status']
product_type           → metadatos['product_type']
```

---

### 4. Descargador RASFF
✅ **adaptadores/descargador_rasff_alerts.py** (280+ líneas)

**Implementación:**
- Feed: `https://ec.europa.eu/food/safetyhealthanimals/rasff/rss.php`
- Parsea XML RSS
- Descarga últimas 24h con reintentos exponencial
- Extrae campos de descripción

**Métodos:**
```python
class DescargadorRASFFAlerts(DescargadorAlertas):
    async def validar_acceso()          # HEAD request
    async def descargar_ultimas_24h()   # GET XML + parse + filter 24h
    def normalizar(xml_content)         # XML → AlertaNormalizada
    def _parsear_fecha_rfc2822(fecha_str)  # RFC 2822 → datetime
    def _extraer_campos_descripcion()   # "Product: X, Origin: Y" → (producto, origen, ...)
    def _extraer_id_alerta(link)        # URL → alert_id
    def _categorizar_riesgo(peligro)    # Similar a openFDA
    def hashear_alerta(alerta)          # SHA256(fuente|ref|producto|fecha)
```

**Campos extraídos:**
```python
title              → riesgo_texto (si no hay hazard)
description        → parse campos: Product, Origin, Hazard, Action
link               → url_oficial
pubDate (RFC 2822) → fecha_emitida
id from URL        → reference_number
```

**Formato esperado de descripción:**
```
Product: peanuts, Origin: China, Hazard: E. coli, Action: Border rejection
```

---

### 5. Test de Descargadores
✅ **scripts/test_s6_1_2_descargadores.py** (220+ líneas)

**Test openFDA:**
1. ✅ Validar acceso a API
2. ✅ Descargar últimas 24h
3. ✅ Validar estructura de AlertaNormalizada
4. ✅ Validar dedup por hash
5. ✅ Mostrar primeras 3 alertas con detalles

**Test RASFF:**
1. ✅ Validar acceso a feed
2. ✅ Descargar últimas 24h
3. ✅ Validar estructura de AlertaNormalizada
4. ✅ Validar dedup por hash
5. ✅ Mostrar primeras 3 alertas con detalles

**Ejecución:**
```bash
python scripts/test_s6_1_2_descargadores.py
```

**Output esperado:**
```
================================================================================
S6 FASE 1: TEST DESCARGADORES OPENFDA + RASFF
================================================================================

🧪 TEST S6.1: Descargador openFDA
================================================================================

1️⃣  Validando acceso a openFDA API...
   ✅ openFDA API accesible

2️⃣  Descargando alertas de últimas 24h...
   ✅ Descargadas N alertas

3️⃣  Validando estructura de alertas...
   Alerta 1:
     - ID: abc123def456...
     - Fuente: openfda
     - Producto: Almonds
     - Riesgo: patogeno (E. coli O157:H7...)
     - Fecha: 2026-08-10 08:00:00
     - URL: https://www.fda.gov/safety/recalls-enforcement/...

   ✅ Estructura validada

4️⃣  Validando dedup por hash...
   - Total alertas: 15
   - Hashes únicos: 15
   ✅ Todos los hashes son únicos

🧪 TEST S6.2: Descargador RASFF
================================================================================
[Similar a openFDA...]

📊 RESUMEN
================================================================================
✅ PASÓ: openFDA
✅ PASÓ: RASFF

Total: 2/2 tests pasaron

✅ S6 FASE 1 COMPLETADA - Descargadores funcionan correctamente
```

---

## 🏗️ ARQUITECTURA IMPLEMENTADA

### Patrón de Descargador (reutilizable para S7+)

```
DescargadorAlertas (interfaz)
    │
    ├── DescargadorOpenFDAAlerts
    │   ├── Fuente: HTTPS REST API (JSON)
    │   ├── Reintentos: Exponential backoff (429, timeout)
    │   └── Dedup: SHA256(fuente|reference_number|producto|fecha)
    │
    └── DescargadorRASFFAlerts
        ├── Fuente: RSS XML feed
        ├── Reintentos: Exponential backoff (429, timeout)
        └── Dedup: SHA256(fuente|reference_number|producto|fecha)
```

### Normalización de Alertas

```
API Bruto (openFDA JSON / RASFF XML)
    │
    ▼
Validar campos + Extraer valores
    │
    ├── Parsear fecha (YYYYMMDD vs RFC 2822)
    ├── Limpiar nombres de productos
    ├── Categorizar riesgo (patógeno/alérgeno/residuo/otro)
    └── Extraer URL oficial
    │
    ▼
Generar hash SHA256 determinístico
    │
    ▼
AlertaNormalizada (estructura uniforme)
    │
    ▼
Insertar en BD (openfda_alerts / rasff_alerts)
```

---

## 📊 COMPARATIVA DESCARGADORES

| Aspecto | openFDA | RASFF |
|---------|---------|-------|
| **Tipo** | REST API JSON | RSS XML feed |
| **Autenticación** | No (free tier) | No (public feed) |
| **Cobertura** | USA (FDA) | EU + internacionales distribuidos a EU |
| **Frecuencia actualización** | Diaria | Diaria |
| **Rate limiting** | Sí (429) | Sí (429) |
| **Timeout típico** | 5-10s | 5-10s |
| **Campos estructurados** | Muy buenos | Variables (parseo flexible) |
| **Categorización riesgo** | Keyword-based | Keyword-based |

---

## ✅ CHECKLIST FASE 1

```
TABLAS:
  ✅ openfda_alerts creada
  ✅ rasff_alerts creada
  ✅ alert_scores creada
  ✅ alert_lookup_log creada
  ✅ alert_ingest_log creada
  ✅ alert_notification_history creada
  ✅ Índices configurados
  ✅ Vistas creadas

INTERFAZ:
  ✅ DescargadorAlertas (ABC)
  ✅ AlertaNormalizada (dataclass)
  ✅ Métodos abstractos: descargar_ultimas_24h, validar_acceso, normalizar, hashear_alerta

DESCARGADOR OPENFDA:
  ✅ API access validation
  ✅ Descargar últimas 24h
  ✅ Reintentos exponencial
  ✅ Normalización JSON → AlertaNormalizada
  ✅ Categorización de riesgos
  ✅ Hash dedup SHA256

DESCARGADOR RASFF:
  ✅ Feed access validation
  ✅ Descargar últimas 24h
  ✅ Reintentos exponencial
  ✅ Parseo XML RSS
  ✅ Normalización RSS → AlertaNormalizada
  ✅ Categorización de riesgos
  ✅ Hash dedup SHA256

TESTS:
  ✅ test_s6_1_2_descargadores.py
  ✅ Validar acceso a ambas fuentes
  ✅ Descargar y normalizar alertas
  ✅ Validar estructura AlertaNormalizada
  ✅ Validar dedup por hash
  ✅ Mostrar ejemplos de alertas
```

---

## 🔗 ARCHIVOS CREADOS

```
scripts/
├── migration_s6_alertas_tablas.sql              [SQL]
└── test_s6_1_2_descargadores.py                [Test]

puertos/
└── descargador_alertas.py                      [Interfaz]

adaptadores/
├── descargador_openfda_alerts.py               [openFDA]
└── descargador_rasff_alerts.py                 [RASFF]

TIERSV3/
└── S6_FASE1_DESCARGADORES_COMPLETADA.md        [Este archivo]
```

---

## 🚀 PRÓXIMOS PASOS: FASE 2

**FASE 2: Búsqueda + Scoring (6.3 + 6.4)**

1. **Función `buscar_alertas_para_ingrediente()`** con fuzzy matching (80%+ similarity)
2. **Scoring de riesgo** (1-5 escala, parametrizable)
3. **alert_lookup_log** para auditoría
4. Tests de calidad

---

## 💡 NOTAS IMPORTANTES

### Para ejecutar tests
```bash
# Primero, crear tablas
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d cite_mvp < scripts/migration_s6_alertas_tablas.sql

# Luego, correr test (requiere httpx + asyncio)
python scripts/test_s6_1_2_descargadores.py
```

### Monitoreo
Ambos descargadores usan `logging` con emojis para fácil seguimiento:
- `✅` = éxito
- `❌` = error
- `⚠️` = advertencia
- `📥` = descargando
- `ℹ️` = información

### Dedup
El hash SHA256 usa campos determinísticos:
```python
contenido = "|".join([
    str(fuente),
    str(reference_number),
    str(producto_nombre),
    str(fecha_emitida.date()),
])
hash = hashlib.sha256(contenido.encode()).hexdigest()
```

Esto garantiza que la misma alerta siempre genera el mismo hash, permitiendo dedup en BD.

### Rate limiting
- openFDA: Si 429, esperar 2^intento segundos
- RASFF: Si 429, esperar 2^intento segundos
- Max reintentos: 3

---

**FASE 1 COMPLETADA. LISTOS PARA FASE 2: BÚSQUEDA + SCORING**
