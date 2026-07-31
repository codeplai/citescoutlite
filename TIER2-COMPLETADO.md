# TIER 2 COMPLETADO - Descargas masivas

**Fecha:** 2026-07-30 19:02 UTC  
**Duración:** ~2.5 horas (1 min descarga + 6 min procesamiento + documentación)  
**Status:** ✅ 100% COMPLETADO

---

## Tareas ejecutadas

### ✅ T2.1: Descarga OFF masivo (OPCIÓN B - Export offline)

**Procedimiento ejecutado:**

1. Descargar export masivo de OFF desde `https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz` (~2GB)
2. Descomprimir y filtrar a 5 insumos piloto (arándano, palta, espárrago, mango, quinua)
3. Validar que todos tienen fecha real y URL

**Resultados:**

```
Total productos descargados:    28,236
Archivo: datasets/2026-07/off_productos.json (32 MB)

Cobertura por insumo:
  Arándano (blueberry):          5,438
  Palta (avocado):               3,058
  Espárrago (asparagus):           760
  Mango:                        10,927
  Quinua (quinoa):               8,969
  Total:                        28,236

Validaciones:
  ✓ 100% son datos reales de OFF (no DEMO)
  ✓ 100% tienen URL navegable
  ✓ 100% tienen fecha_dato real (timestamp Unix, no today())
  ✓ 310,597 líneas de JSON
```

**Criterio de éxito:** ≥250 productos alcanzado ✓ (28,236)

---

### ✅ T2.2: Descarga USDA Branded

**Status:** **SALTADO (mitigado)**

**Razón:** USDA_API_KEY no está configurada en `.env.local`

**Acción tomada:** Crear archivo vacío documentado:
```json
{
  "estado": "SALTADO",
  "razon": "USDA_API_KEY no disponible",
  "productos": [],
  "nota": "USDA Branded puede agregarse en futuro si se obtiene API key"
}
```

**Impacto:** Ninguno. OFF solo es suficiente para ≥250 productos. USDA es aditivo, no bloqueante.

---

## 🎯 DoD (Definition of Done) de TIER 2

```
Checklist:
  [✓] off_productos.json: ≥250 filas (28,236)
  [✓] usda_productos.json: ≥10 filas o documentado (saltado, documentado)
  [✓] Sin DEMO data (100% OFF)
  [✓] fecha_dato son timestamps reales (no today())
  [✓] Todos tienen URL navegable
  [✓] Tiempo de descarga documentado
  [✓] Métricas por insumo registradas
  [✓] Listo para TIER 3 (merge + dedup)

Resultado: 8/8 COMPLETADOS
```

---

## 📊 Estadísticas de TIER 2

| Métrica | Valor | Target | Status |
|---|---|---|---|
| Total productos | 28,236 | ≥250 | ✓ 112x |
| Archivos generados | 2 | 2 | ✓ |
| Datos inventados (DEMO) | 0 | 0 | ✓ |
| URLs válidas | 28,236 | 100% | ✓ |
| Fechas reales | 28,236 | 100% | ✓ |
| Tiempo total | ~2.5h | <8h | ✓ |

---

## 💾 Archivos creados/modificados

| Archivo | Tamaño | Descripción |
|---|---|---|
| `etl/cargar_off_bulk.py` | 5.2 KB | Script nuevo: descarga export masivo |
| `datasets/2026-07/off_productos.json` | 32 MB | 28,236 productos reales |
| `datasets/2026-07/usda_productos.json` | 151 B | Placeholder (saltado) |
| `datasets/2026-07/etl_off_bulk.log` | ~5 KB | Log de ejecución |

---

## 🚀 Próximos pasos (TIER 3 - Miércoles 7 agosto)

**TIER 3: Limpieza de datos**

- T3.1: Deduplicación OFF vs USDA (saltado, USDA vacío)
- T3.2: Merge a `productos_merged.json`

**Entrada:** `datasets/2026-07/off_productos.json` (28,236)  
**Salida:** `datasets/2026-07/productos_merged.json` (28,236 deduplicado)

**Duración:** 2-3 horas

---

## 📝 Notas importantes

1. **OFF Export fue descargado una sola vez** - está en caché en `~/off_export.csv.gz`. Ejecuciones futuras de T2.1 serán instantáneas (solo filtrado local ~6 min).

2. **28,236 productos es mucho más que los 250 mínimos requeridos** - da libertad para experimentos en S4 (MIM, agente).

3. **USDA fue saltado correctamente sin bloquear** - es una mitigación documentada, no regresión.

4. **Todos los datos son verificables en OFF navegador** - cada URL es real, clickeable.

---

## ✅ Estado de TIER 2

```
TIER 1: COMPLETADO (preparación + decisiones)
TIER 2: COMPLETADO (descargas + validaciones)
TIER 3: LISTO (depende de TIER 2)
  ├─ Entrada: 28,236 + 0 = 28,236 productos
  └─ Espera: Deduplicación y merge (2-3h)

BLOQUEANTES: NINGUNO
MITIGACIONES: USDA saltado (documentado)
```

---

**Firma de cierre TIER 2:**

- ✓ Descarga masiva OFF exitosa (28,236 productos)
- ✓ Datos reales, verificables, sin inventados
- ✓ USDA mitigado correctamente
- ✓ Listo para TIER 3 sin bloqueantes

**Próximo hito:** Miércoles 7 de agosto  
**Tarea:** TIER 3 - Limpieza de datos

---

*TIER 2 completado el 30 de julio de 2026 a las 19:02 UTC*  
*Tiempo real: ~2.5 horas (dentro del presupuesto de 8h)*  
*Equipo: Listo para TIER 3*
