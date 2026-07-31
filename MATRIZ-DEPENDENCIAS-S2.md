# Matriz de Dependencias y Estado: Semana 2

**Visual rápida para auditoría diaria.**

---

## 1. Bloqueantes de Semana 1 (verde = sin bloqueo para S2)

```
┌─────────────────────────────────────────┬──────────┬──────────────────┐
│ Bloqueante S1                           │ Estado   │ Test             │
├─────────────────────────────────────────┼──────────┼──────────────────┤
│ Cost-meter real (costo_usd > 0)         │ ❌ TODO  │ assert costo > 0 │
│ fecha_dato real (no today())            │ ❌ TODO  │ fecha < hoy()    │
│ usa_insumo_directo derivado             │ ❌ TODO  │ parsing texto    │
│ Etapas 4,5 separadas en etapa()         │ ❌ TODO  │ len(etapas)==6   │
│ Modelo por etapa (E1≠E3)                │ ❌ TODO  │ cache key/modelo │
│ Auth + JWT real (bcrypt, exp)           │ ❌ TODO  │ JWT valida exp   │
│ Contratos/ generado                     │ ❌ TODO  │ contratos/*.json │
│ Huawei MaaS modelos GLM verificados     │ ❌ TODO  │ curl API test    │
└─────────────────────────────────────────┴──────────┴──────────────────┘

STATE: 0/8 listo (S1 en progreso hasta ~2026-08-02)
RIESGO: CRÍTICO si alguno falta viernes
```

---

## 2. Tareas de Semana 2 por día

```
┌─────────┬──────────────────────────────────────┬───────────┬───────────────┐
│ Día     │ Tarea                                │ Duración  │ Parallelizable│
├─────────┼──────────────────────────────────────┼───────────┼───────────────┤
│ LUN 5   │ [S2-T01] Setup estructura            │ 2h        │ —             │
│ LUN 5   │ Decidir: OFF live vs offline         │ 0.5h      │ —             │
│ LUN 5   │ Verificar APIs (OFF, USDA)           │ 1h        │ —             │
│         │                                      │           │               │
│ MAR 6   │ [S2-T02] Descarga OFF masivo         │ 4h        │ ✓ Paralelo T03│
│ MAR 6   │ [S2-T03] Descarga USDA               │ 4h        │ ✓ Paralelo T02│
│ MAR 6   │ (Espera: indexación de OFF ~30 min) │           │               │
│         │                                      │           │               │
│ MIE 7   │ [S2-T04] Dedup OFF vs USDA           │ 2h        │ Secuencial    │
│ MIE 7   │ [S2-T05] Embeddings bge-m3           │ 6h        │ ⚠️ Cómputo CPU│
│ MIE 7   │ (Espera: indexación ~5-15 min)      │           │               │
│         │                                      │           │               │
│ JUE 8   │ [S2-T06] Búsqueda vectorial + p95    │ 4h        │ ✓ Paralelo T07│
│ JUE 8   │ [S2-T07] Corpus regulatorio base     │ 6h        │ ✓ Paralelo T06│
│ JUE 8   │ (Espera: OCR DIGESA)                 │           │               │
│         │                                      │           │               │
│ VIE 9   │ [S2-T08] Golden set ampliado         │ 2h        │ QA paralelo   │
│ VIE 9   │ [S2-T09] Manifest + E2E final        │ 3h        │ —             │
│ VIE 9   │ Demostración de 5 hitos              │ 1h        │ —             │
└─────────┴──────────────────────────────────────┴───────────┴───────────────┘

TOTAL CÓDIGO: ~28 horas
TOTAL ESPERA: ~12-24 horas (descargas + embeddings)
RECOMENDACIÓN: 2 devs (OFF/USDA · embeddings/búsqueda) + 1 QA
```

---

## 3. Dependencias de tareas (qué bloquea qué)

```
T01 (Setup)
  └─── T02 (OFF descarga)
  │     └─── T04 (Dedup)
  │           └─── T05 (Embeddings) ◄────── ⚠️ CAMINO CRÍTICO
  │                 └─── T06 (Búsqueda)
  │                       └─── T08 (Golden set)
  │                             └─── T09 (Manifest final)
  │
  └─── T03 (USDA descarga)
        └─── T04 (Dedup) ◄────── SE CRUZA CON OFF

T07 (Corpus regulatorio)
  ├─── T09 (Manifest)
  └─── Base para S3 (pero no bloquea T06)

CRÍTICO: T01→T02→T04→T05→T06 (5 pasos secuenciales)
PARALLELIZABLE: (T02 || T03) + (T06 || T07)
```

---

## 4. Riesgos vs mitigación

```
┌───────────────────────────────────┬──────┬─────────┬──────────────────────┐
│ Riesgo                            │ Prob │ Impacto │ Mitigación           │
├───────────────────────────────────┼──────┼─────────┼──────────────────────┤
│ OFF timeout/fallback a DEMO       │ Med  │ Alto    │ Día 1: Medir + Plan B│
│ bge-m3 indexación lenta (>30 min) │ Bajo │ Medio   │ Modelo pequeño si >30│
│ USDA_API_KEY no disponible        │ Med  │ Bajo    │ Proceder solo OFF    │
│ eCFR/DIGESA no accesible          │ Med  │ Bajo    │ Subset público GRAS  │
│ 4 semanas + imprevisto            │ Alto │ Alto    │ Sacrificar deck PPTX │
│ Postgres S3 sin datos S2          │ Alta │ CRÍTICO │ Data listo Vie 9 EOD │
└───────────────────────────────────┴──────┴─────────┴──────────────────────┘

ESCALATION RULE: Si algo no termina LUN 12 8AM → alertar S3
```

---

## 5. Salida esperada (Viernes EOD)

```
datasets/2026-07/
  ├── manifest.json                  (SHA256 de todos los archivos)
  ├── off_productos.json             (250-1000 filas, sin DEMO)
  ├── usda_productos.json            (10-50 filas, no duplicados)
  ├── productos_merged.json           (merged sin duplicados)
  ├── ecfr_aditivos.json             (≥5 documentos)
  ├── digesa_normas.txt              (≥2000 palabras)
  └── README.md                      (procedimiento reproducible)

vectores/productos.lance/           (LanceDB con embeddings bge-m3)
  ├── _versions/                    (índices)
  └── data/                         (vectores 1024-dim)

test/
  ├── test_off_descarga.py          (✓ PASS)
  ├── test_embeddings.py            (✓ PASS)
  ├── test_latency.py               (✓ p95 < 2s)

evals/
  ├── set_dorado.yaml               (5 casos → 5 pass)
  └── runner_s2.py                  (ejecutor + reporte)

INDICADOR: ✓ P03 en verde, datos navegables en OFF
```

---

## 6. Criterios de aceptación por prueba

```
┌────┬─────────────────────────┬────────────────────────────────────────┐
│ P# │ Prueba                  │ Criterio de aceptación S2              │
├────┼─────────────────────────┼────────────────────────────────────────┤
│ P03│ Búsqueda < 2s           │ p95 latencia < 2s (100+ queries)       │
│    │                         │ ≥30 productos indexados                │
│    │                         │ Sin DEMO data si OFF éxito              │
│    │                         │ fecha_dato real (timestamp Unix)        │
│    │                         │ URL navegable en OFF                   │
│    │                         │ 5/5 golden set pasa                    │
├────┼─────────────────────────┼────────────────────────────────────────┤
│ P04│ Sin valores inventados   │ Preparación: Validador de schema listo │
│    │                         │ Implementación en S3/S4                │
├────┼─────────────────────────┼────────────────────────────────────────┤
│ P05│ Cita = 1 dato           │ Preparación: Validador de citas listo  │
│    │                         │ Implementación en S3/S4                │
├────┼─────────────────────────┼────────────────────────────────────────┤
│ P08│ Corpus regulatorio       │ Preparación: ≥5 eCFR + ≥2 DIGESA       │
│    │                         │ Indexados en LanceDB                   │
│    │                         │ Citas verificables en F5               │
└────┴─────────────────────────┴────────────────────────────────────────┘

META: P03 → VERDE; P04/P05/P08 → Base lista para S3
```

---

## 7. Diagrama de flujo de decisiones (Semana 2)

```
LUNES 5 (Setup)
  │
  ├─ ¿S1 entregó bloqueantes? ──[NO]──> STOP: Esperar S1
  │                           ──[SÍ]──> Continuar
  │
MARTES 6 (Descargas)
  │
  ├─ ¿OFF descarga en < 10 min? ──[NO]──> Plan B: Usar export 2GB
  │                            ──[SÍ]──> Mantener API live
  │
  ├─ ¿USDA_API_KEY disponible? ──[NO]──> Proceder sin USDA
  │                          ──[SÍ]──> Descargar USDA
  │
MIÉRCOLES 7 (Embeddings)
  │
  ├─ ¿bge-m3 indexa en < 30 min? ──[NO]──> Cambiar a modelo pequeño
  │                           ──[SÍ]──> Mantener bge-m3
  │
JUEVES 8 (Búsqueda)
  │
  ├─ ¿p95 latencia < 2s? ──[NO]──> Optimizar; degradar a FTS si necesario
  │                      ──[SÍ]──> Listo para S3
  │
VIERNES 9 (Cierre)
  │
  ├─ ¿Todos 5 hitos verdes? ──[NO]──> Extender a Lunes 12
  │                        ──[SÍ]──> S2 LISTO → S3 puede comenzar

DECISIÓN FINAL: ¿Datos reales navegables en OFF?
  ├─ [SÍ] → Semana 3 comienza sin bloqueantes
  └─ [NO] → Semana 2 se extiende hasta conseguirlo
```

---

## 8. Métricas a medir (Viernes EOD)

```
┌──────────────────────────────────┬──────────┬──────────┬─────────┐
│ Métrica                          │ Target   │ Actual   │ Status  │
├──────────────────────────────────┼──────────┼──────────┼─────────┤
│ Productos OFF descargados        │ ≥250     │ —        │ ⏳      │
│ Productos USDA descargados       │ ≥10      │ —        │ ⏳      │
│ Productos sin DEMO data          │ 100%     │ —        │ ⏳      │
│ Embeddings indexados             │ ≥250     │ —        │ ⏳      │
│ Latencia p95 (ms)                │ <2000    │ —        │ ⏳      │
│ Golden set pase rate             │ 5/5      │ —        │ ⏳      │
│ URLs navegables (manualmente)    │ 100%     │ —        │ ⏳      │
│ Corpus eCFR (documentos)         │ ≥5       │ —        │ ⏳      │
│ Corpus DIGESA (palabras)         │ ≥2000    │ —        │ ⏳      │
│ Tiempo indexación (min)          │ <30      │ —        │ ⏳      │
│ Tamaño dataset (MB)              │ <100     │ —        │ ⏳      │
│ Reproducibilidad (README)        │ completo │ —        │ ⏳      │
└──────────────────────────────────┴──────────┴──────────┴─────────┘

VERIFICACIÓN: Ejecutar script E2E viernes 16:00 hrs
```

---

## 9. Archivos a crear/modificar (checklist)

```
CREAR:
  ☐ datasets/2026-07/manifest.json
  ☐ datasets/2026-07/README.md
  ☐ etl/cargar_usda.py
  ☐ etl/dedup_merge_datasets.py
  ☐ etl/procesar_ecfr.py
  ☐ etl/procesar_regulatorio.py
  ☐ etl/finalizar_manifest.py
  ☐ test/test_off_descarga.py
  ☐ test/test_embeddings.py
  ☐ test/test_latency.py
  ☐ evals/runner_s2.py

MODIFICAR:
  ☐ etl/cargar_off.py (reintentos + fecha real)
  ☐ etl/indexar_vectores.py (embeddings reales bge-m3)
  ☐ adaptadores/busqueda_lancedb.py (vectorial + latencia)
  ☐ evals/set_dorado.yaml (5 casos)
  ☐ pyproject.toml (verificar dependencias)

DOCUMENTACIÓN:
  ☐ Este archivo (MATRIZ-DEPENDENCIAS-S2.md)
  ☐ AUDITORIA-SEMANA-2.md (análisis profundo)
  ☐ PLAN-EJECUCION-S2.md (tareas [S2-T01-T09])
  ☐ RESUMEN-S2-EJECUTIVO.md (summary)
```

---

## 10. Contactos y escalation

```
PREGUNTA                           → VER DOCUMENTO
─────────────────────────────────────────────────────────
"¿Qué está bloqueando S2?"         → AUDITORIA-SEMANA-2.md §5
"¿Cómo implemento T05?"            → PLAN-EJECUCION-S2.md [S2-T05]
"¿Cuál es el riesgo más grande?"   → RESUMEN-S2-EJECUTIVO.md
"¿Qué debería estar listo Martes?" → Abajo

ESCALATION: Si el martes 6 ago PM no hay ≥150 productos OFF descargados
            → cambiar a offline export inmediatamente
```

---

## 11. Hitos de progreso (check diarios)

**LUNES 5 ago (EOD):**
```
✓ datasets/2026-07/ estructura creada
✓ APIs OFF y USDA respondiendo a curl
✓ USDA_API_KEY confirmada (o documentado ausente)
✓ Decisión OFF live vs offline comunicada
✓ Todos en mismo branch sin conflictos
```

**MARTES 6 ago (EOD):**
```
✓ OFF: 150+ productos descargados en JSON
✓ USDA: 10+ productos descargados en JSON (si API key disponible)
✓ Test de OFF pasa (sin DEMO si hay ≥50 reales)
✓ Merge comienza mié temprano
```

**MIÉRCOLES 7 ago (EOD):**
```
✓ productos_merged.json sin duplicados
✓ bge-m3 indexación comenzó o terminó
✓ vectores/productos.lance/ existe con ≥250 filas
✓ Tiempo de indexación registrado
```

**JUEVES 8 ago (EOD):**
```
✓ p95 latencia medida y < 2s
✓ test_latency.py pasa
✓ Corpus eCFR + DIGESA mínimo en LanceDB
✓ Golden set runner listo
```

**VIERNES 9 ago (EOD):**
```
✓ 5/5 golden set pasa
✓ manifest.json con hashes completos
✓ E2E script sin errores
✓ README con procedimiento reproducible
✓ Demostración grabada o screenshot de URLs navegables
```

---

**Matriz generada:** 2026-07-30  
**Última revisión:** Por revisar viernes 1 ago cuando S1 entrega  
**Próxima actualización:** Martes 6 ago PM (punto de control)

