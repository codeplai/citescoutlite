# Dataset Semana 2: 5 Insumos Piloto

**Fecha de generación:** 2026-07-30  
**Versión snapshot:** 2026-07  
**Versión taxonomía:** 0.1

---

## Procedimiento de reproducibilidad

### 1. Descarga OFF Masivo

**Estrategia decidida:** OPCIÓN B (Export offline)

**Razón:** OFF API retorna 503 (Service Unavailable). Usar export local es más confiable.

```bash
# Descargar export masivo de OFF (~2GB)
wget -c "https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz" \
  -O ~/off_export.csv.gz

# Descomprimir (toma ~2-5 min)
tar xzf ~/off_export.csv.gz -C datasets/2026-07/

# Filtrar a los 5 insumos piloto
python -m etl.cargar_off_masivo --bulk datasets/2026-07/en.openfoodfacts.org.products.csv
```

**Esperado:** `datasets/2026-07/off_productos.json` ≥250 filas

**Alternativa si Opción B falla:**
```bash
# Volver a intentar API live
python etl/cargar_off.py
```

### 2. Descarga USDA Branded

**Estado:** USDA_API_KEY NO disponible en esta máquina

```bash
# Si en el futuro se obtiene clave:
USDA_API_KEY=$YOUR_KEY python -m etl.cargar_usda
```

**Por ahora:** Proceder solo con OFF

### 3. Merge y deduplicación

```bash
python -m etl.dedup_merge_datasets
```

**Esperado:** `datasets/2026-07/productos_merged.json` ≥250 filas

### 4. Embeddings con bge-m3

```bash
# Genera embeddings 1024-dimensional
python -m etl.indexar_vectores
```

**Esperado:** `vectores/productos.lance/` con tabla `productos` indexada

### 5. Validación completa

```bash
# Validar dataset completo
python -m evals.validar_dataset --dataset 2026-07
```

**Criterios:**
- manifest.json válido
- ≥250 productos
- Embeddings presentes (1024-dim)
- p95 latencia < 2s
- URLs navegables

---

## Insumos piloto

```
├─ Arándano (blueberry)
├─ Palta (avocado)
├─ Espárrago (asparagus)
├─ Mango
└─ Quinua (quinoa)
```

---

## Decisiones de S2 (TIER 1)

| Decisión | Valor | Razón |
|---|---|---|
| **D-A: Estrategia OFF** | Opción B (offline) | OFF API down (503) |
| **D-B: USDA disponible** | No | API key no configurada |
| **D-C: Motor PDF** | xhtml2pdf (actual) | Funciona; WeasyPrint es S4+ |

---

## Estructura de archivos

```
datasets/2026-07/
  ├── README.md                    (este archivo)
  ├── manifest.json               (metadatos versionado)
  ├── off_productos.json          (TIER 2)
  ├── usda_productos.json         (TIER 2, si disponible)
  ├── productos_merged.json       (TIER 3)
  ├── ecfr_aditivos.json         (TIER 6)
  └── digesa_normas.json         (TIER 6)

vectores/
  └── productos.lance/           (TIER 4)
      ├── _versions/
      ├── data/
      └── _transactions/
```

---

## Métricas esperadas (Viernes 9 ago EOD)

```
TIER 2 (Descargas):
  ✓ OFF: 250-1000 productos
  ✓ USDA: 0 (no disponible)
  ✓ Total: ≥250

TIER 3 (Limpieza):
  ✓ productos_merged.json: ≥250 filas
  ✓ Duplicados removidos: 0-5

TIER 4 (Embeddings):
  ✓ Indexed: ≥250 filas
  ✓ Dimensiones: 1024
  ✓ Tiempo: <30 min

TIER 5 (Búsqueda):
  ✓ p95 latencia: <2s
  ✓ Consultas: ≥100
  ✓ Sin DEMO data: 100%

TIER 6 (Corpus):
  ✓ eCFR: ≥5 docs (si disponible)
  ✓ DIGESA: ≥2000 palabras (si disponible)

TIER 7 (Cierre):
  ✓ Golden set: 5/5 pases
  ✓ E2E workflow: PASSED
  ✓ Manifest SHA256: Listo
```

---

**Procedimiento escrito:** 2026-07-30  
**Última actualización:** Lunes 5 agosto (post-TIER 1)

