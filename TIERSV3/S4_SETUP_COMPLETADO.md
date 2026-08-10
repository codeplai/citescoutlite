# Semana 4 · SETUP COMPLETADO

**Fecha:** 2026-08-10  
**Estado:** ✅ SETUP COMPLETADO  
**Duración:** 2.5 horas  
**Siguiente:** Implementar descargadores (4.1-4.5)  

---

## 📋 INFRAESTRUCTURA CREADA

### 1️⃣ Migración SQL (006_create_regulaciones_s4.sql)

✅ **8 tablas nuevas:**

```sql
ecfr_regulations        (FDA - 21 CFR, 7 CFR)
efsa_regulations        (E-numbers autorizados)
codex_standards         (Estándares internacionales)
inacal_nts              (Normas técnicas peruanas)
digesa_directivas       (Directivas DIGESA + OCR)
regulacion_cita         (Unified citations table)
mapping_regulaciones    (Cross-reference)
audit_regulaciones      (Job audit trail)
```

**Índices full-text:** Español e inglés en `texto_completo` y `texto_cita`  
**Índices compuestos:** (title, part) en eCFR, (ingrediente, tipo_regulacion) en regulacion_cita  
**Hash detection:** Para change detection en corpus updates  
**Foreign keys:** mapping_regulaciones → todas las tablas (ON DELETE SET NULL)

**Tamaño esperado:** ~500 MB (estimado para 5000+ eCFR, 500+ EFSA, 200+ Codex, etc.)

---

### 2️⃣ Puertos (Interfaces)

✅ **puertos/repositorio_regulaciones.py**
- `guardar_ecfr(regulaciones)` → int
- `guardar_efsa(regulaciones)` → int
- `guardar_codex(regulaciones)` → int
- `guardar_inacal(regulaciones)` → int
- `guardar_digesa(regulaciones)` → int
- `buscar_por_ingrediente(ingrediente, pais) → List[cita]`
- `buscar_por_tipo(tipo_regulacion) → List[cita]`
- `obtener_mapping(ingrediente) → Dict`
- `guardar_mapping(...) → mapping_id`
- `contar_por_fuente() → Dict[str, int]`
- `registrar_cambio(...) → None` (audit trail)
- `limpiar_corpus() → None`

✅ **puertos/descargador_regulaciones.py**
- `DescargadorRegulaciones` (interfaz base)
- `DescargadorECFR` (subinterfaz)
- `DescargadorEFSA` (subinterfaz)
- `DescargadorCodex` (subinterfaz)
- `DescargadorINACAL` (subinterfaz)
- `DescargadorDIGESA` (subinterfaz + OCR)

---

### 3️⃣ Adaptadores (Implementaciones)

✅ **adaptadores/repositorio_regulaciones_postgres.py**
- Implementación PostgreSQL completa
- Usa psycopg2 (ya disponible)
- Batch insert con `execute_batch()` (eficiente)
- Búsqueda por ingrediente con prioridad por país
- Manejo de errores + logging detallado

**Métodos implementados:**
- ✅ `guardar_ecfr()` - INSERT ON CONFLICT UPDATE
- ✅ `guardar_efsa()` - INSERT ON CONFLICT UPDATE
- ✅ `guardar_codex()` - INSERT ON CONFLICT UPDATE
- ✅ `guardar_inacal()` - INSERT ON CONFLICT UPDATE
- ✅ `guardar_digesa()` - INSERT simple (nuevos registros)
- ✅ `buscar_por_ingrediente()` - Búsqueda ILIKE con prioridad por país
- ✅ `buscar_por_tipo()` - COUNT queries
- ✅ `obtener_mapping()` - Lookup simple
- ✅ `guardar_mapping()` - INSERT con RETURNING
- ✅ `contar_por_fuente()` - Resumen por tabla
- ✅ `registrar_cambio()` - INSERT en audit_regulaciones
- ✅ `limpiar_corpus()` - TRUNCATE CASCADE (desarrollo)

✅ **adaptadores/descargador_ecfr.py** (stub)
- `descargar()` → [] (TODO: implementar)
- `validar_acceso()` → HEAD request
- `normalizar()` → [] (TODO: implementar)
- SHA256 hasher para change detection

✅ **adaptadores/descargador_efsa.py** (stub)
- `descargar()` → [] (TODO: implementar)
- `validar_acceso()` → HEAD request
- `normalizar()` → [] (TODO: implementar)

✅ **adaptadores/descargador_codex.py** (stub)
- `descargar()` → [] (TODO: implementar)
- `validar_acceso()` → HEAD request
- `normalizar()` → [] (TODO: implementar)

✅ **adaptadores/descargador_inacal.py** (stub)
- `descargar()` → [] (TODO: implementar)
- `validar_acceso()` → HEAD request
- `normalizar()` → [] (TODO: implementar)

✅ **adaptadores/descargador_digesa.py** (stub)
- `descargar()` → [] (TODO: implementar con OCR)
- `validar_acceso()` → HEAD request
- `normalizar()` → [] (TODO: implementar)
- `procesar_ocr()` → "" (TODO: Tesseract o Google Vision)
- `_ocr_tesseract()` (stub)
- `_ocr_google_vision()` (stub)

---

### 4️⃣ Configuración

✅ **config/regulaciones_config.py**
- `crear_repositorio_regulaciones()` → Factory
- `crear_descargadores()` → Factory (todos los descargadores)
- `get_repositorio()` → Singleton lazy
- `get_descargadores()` → Singleton lazy

**Uso:**
```python
from config.regulaciones_config import get_repositorio

repo = get_repositorio()
citas = await repo.buscar_por_ingrediente("quinua", pais="PE")
```

---

### 5️⃣ Dependencias Inyectadas

✅ **casos_de_uso/dependencias.py** (actualizado)
- ✅ Import `RepositorioRegulaciones`
- ✅ Campo `repositorio_regulaciones: RepositorioRegulaciones = None`
- ✅ Comentario explicando degradación graceful si ausente

**Ahora Dependencias contiene:**
```python
@dataclass
class Dependencias:
    redactor: RedactorLLM
    catalogo: CatalogoProductos
    cache: CacheLLM
    informes: RepositorioInformes
    auditoria: Auditoria
    verificador_fda: VerificadorRegulatorio = None
    verificador_rag: VerificadorRegulatorio = None
    descubrimiento: DescubrimientoComercial = None
    precios: Any = None
    repositorio_regulaciones: RepositorioRegulaciones = None  # ← NUEVO
    presupuesto: Any = None
    # ... resto igual
```

---

## 🏗️ ARQUITECTURA S4

```
┌─────────────────────────────────────────────────────────┐
│                    ETAPA 5 (VERIFICACIÓN)               │
│              verificar_regulacion.py (mejora S4)        │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
   Busca:                        Fallback:
   ┌─────────────────┐      ┌──────────────┐
   │ Repositorio     │      │ openFDA      │
   │ Regulaciones    │      │ RAG normativo│
   │ (corpus local)  │      └──────────────┘
   └────────┬────────┘
            │
    ┌───────┴────────────────────────┬───────────────┐
    │                                 │               │
 Busca por:                    Prioridad país:
 ┌──────────────┐              ┌──────────┐
 │ Ingrediente  │              │ PE → INACAL
 │ País (PE/EU) │              │      DIGESA
 │ Tipo (ECFR)  │              │      Codex
 └──────┬───────┘              │ EU → EFSA
        │                       │      Codex
        │                       │ US → eCFR
        │                       │      Codex
        └───────────────────────┴──────────────┘
                  │
   ┌──────────────┴──────────────────┬───────────┐
   │                                  │           │
   ▼                                  ▼           ▼
ECFR_REGS                         EFSA_REGS   INACAL_NTS
mapping_regulaciones            Codex_STD    Digesa_DIR
    │                            audit_regs
    └────────────────────────────┬───────────┘
                                 │
                        ┌────────┴────────┐
                        │                 │
                    PostgreSQL       audit_regulaciones
                    8 tablas         (job tracking)
                    indexes
                    FKs
```

---

## ✅ ESTADO ACTUAL

| Componente | Status | Notas |
|---|---|---|
| **Migration 006** | ✅ Completa | 8 tablas, índices, hashes |
| **Puertos** | ✅ Definidos | 2 interfaces, 12 métodos |
| **Repositorio PG** | ✅ Implementado | Completo, 12 métodos |
| **Descargadores** | 🟡 Stub | 5 descargadores, TODO implementar |
| **Config** | ✅ Factory | Lazy singletons |
| **Dependencias** | ✅ Inyección | Campo repositorio_regulaciones |

---

## 📚 PRÓXIMOS PASOS (S4.1-4.5)

### 4.1 - Descargador eCFR (1 día)
- [ ] Validar acceso a `https://www.ecfr.gov/api/`
- [ ] Implementar `DescargadorECFR.descargar()`
- [ ] Parsear JSON response
- [ ] Guardar en `ecfr_regulations`
- [ ] Test: verificar eCFR > 5000 entries

### 4.2 - Descargador EFSA (1 día)
- [ ] Validar acceso a EFSA Register
- [ ] Scraping/parsing E-numbers
- [ ] Guardar en `efsa_regulations`
- [ ] Test: verificar EFSA > 500 entries

### 4.3 - Descargador Codex (0.5 días)
- [ ] Validar acceso a Codex Alimentarius
- [ ] Descargar estándares relevantes
- [ ] Guardar en `codex_standards`
- [ ] Test: verificar Codex > 200 entries

### 4.4 - INACAL + Mapping (1 día)
- [ ] Descargar INACAL NTS
- [ ] Crear mapping: INACAL ↔ eCFR/EFSA/Codex
- [ ] Validar con especialista CITE (80%+ coverage)
- [ ] Guardar en `mapping_regulaciones`

### 4.5 - DIGESA OCR (1.5 días)
- [ ] Descargar PDFs DIGESA
- [ ] Decidir: Tesseract vs Google Vision
- [ ] Implementar OCR processor
- [ ] Validar accuracy > 70%
- [ ] Guardar en `digesa_directivas`

### 4.6 - regulacion_cita table (0.5 días)
- [ ] Crear helper `buscar_regulacion()`
- [ ] Poblar `regulacion_cita` desde mapping
- [ ] Test queries

### 4.7 - Integrar en Etapa 5 (0.5 días)
- [ ] Actualizar `verificar_regulacion()`
- [ ] Usar `repositorio_regulaciones.buscar_por_ingrediente()`
- [ ] Retornar URLs verificables

### 4.8 - Test P08 (0.5 días)
- [ ] Test: búsqueda "quinua" → citas con URLs
- [ ] Test: GET URL → 200 OK + texto presente
- [ ] Validar sin citas inventadas

### 4.9 - Job corpus_ingest (0.5 días)
- [ ] Crear job: 02:00 UTC diarios
- [ ] Hash change detection
- [ ] Alert si falla 2 semanas

### 4.10 - Documentación (0.5 días)
- [ ] REGULATORY_METHODOLOGY.md
- [ ] Coverage por país
- [ ] Changelog

---

## 🎯 MÉTRICAS ÉXITO SETUP

| Métrica | Target | Actual |
|---------|--------|--------|
| Migraciones SQL | 1 | ✅ 1 |
| Puertos definidos | 2 | ✅ 2 |
| Adaptadores | 6 | ✅ 1 (Postgres) + 5 stubs |
| Métodos repositorio | 12 | ✅ 12 |
| Config factories | 2 | ✅ 2 |
| Dependencias inyectadas | 1 | ✅ 1 |

---

## 🚀 TESTING SETUP

Para probar el setup:

```python
# 1. Crear repositorio
from config.regulaciones_config import get_repositorio
repo = get_repositorio()

# 2. Validar descargadores
from adaptadores.descargador_ecfr import DescargadorECFR
ecfr = DescargadorECFR()
can_download = await ecfr.validar_acceso()
print(f"eCFR accessible: {can_download}")

# 3. Guardar test data
regulaciones = [{'title': '21', 'part': '101', ...}]
count = await repo.guardar_ecfr(regulaciones)
print(f"Saved {count} eCFR entries")

# 4. Buscar
citas = await repo.buscar_por_ingrediente("quinua", pais="PE")
print(f"Found {len(citas)} citations")

# 5. Contar
counts = await repo.contar_por_fuente()
print(f"Corpus: {counts}")
```

---

## 📝 NOTAS

- **Async:** Todo usa `async/await` (compatible con FastAPI + Procrastinate)
- **Psycopg2:** Conexión directa a PostgreSQL (Supabase compatible)
- **Batch insert:** 100 registros por lote (eficiente)
- **Logging:** Detallado en cada operación
- **Graceful degradation:** Si `repositorio_regulaciones = None` → etapa 5 devuelve sin_dato (no error)
- **Change detection:** Hash SHA256 de contenido para saber si FDA/EFSA actualizaron
- **Audit trail:** Cada cambio registrado en `audit_regulaciones` para job monitoring

---

**SETUP COMPLETADO. Listo para implementar descargadores en S4.1-4.5.**
