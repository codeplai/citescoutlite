# Kickoff Semana 2 · Lunes 5 de Agosto, 8:00 AM

**Documento oficial de inicio de Semana 2**

---

## Acta de Reunión de Inicio

**Fecha:** 2026-08-05  
**Asistentes:** [names], CITE, equipo técnico  
**Duración:** 30 min  
**Objetivo:** Desbloquear tareas parallelizables, confirmar decisiones críticas

---

## 1. Pre-requisitos checkeados (Sí/No/Parcial)

- [ ] S1 entregó 8 bloqueantes (ver §3 abajo)
- [ ] `.env.local` tiene `USDA_API_KEY` (o documentado "no disponible")
- [ ] OFF y USDA APIs respondiendo a `curl` (3 min test)
- [ ] Rama principal sin conflictos Git
- [ ] Equipo asignado: Dev A (OFF+USDA), Dev B (embeddings+búsqueda), QA

**Si alguno es NO → STOP, no comenzar S2**

---

## 2. Bloqueantes S1 de verificación rápida

```python
# Run en 2 minutos:
from api.main import app
from casos_de_uso.etapas.ejecutor import etapa

# ✓ Cost-meter real
assert etapa.costo_usd > 0, "Cost-meter sigue siendo 0"

# ✓ fecha_dato real (no today)
from datetime import date
assert resultado["fecha_dato"] != int(date.today().timestamp()), "Fecha inventada"

# ✓ Etapas separadas
from casos_de_uso.etapas import interpretar_insumo, buscar_productos, insight_mercado
# Debe haber 6 etapas, no 5 fusionadas

# ✓ Auth JWT
headers = {"Authorization": "Bearer fake"}
response = app.test_client().get("/consultas", headers=headers)
assert response.status_code in (401, 403), "Endpoint no protegido"
```

**Si alguno falla → Contactar S1 lead, no continuar.**

---

## 3. Decisiones críticas (finalizar HOY)

### Decisión A: OFF descarga (live vs offline)

**Opción 1 (live API):** Continuar con `cargar_off_masivo()` API web
- **Ventaja:** Datos frescos
- **Desventaja:** Lento, a veces timeout
- **Tiempo esperado:** 5-20 min para 5 insumos

**Opción 2 (offline export):** Descargar ~2 GB comprimido, descomprimir, filtrar local
- **Ventaja:** Reproducible, confiable
- **Desventaja:** ~15 min descarga + almacenamiento
- **Tiempo esperado:** 30-45 min una vez, después ~5 min

**Decisión de hoy:**
```
Ejecutar PRUEBA HOY (antes de 10 AM):
time python -m etl.cargar_off_masivo --test

Si < 10 min total → Opción 1 (live)
Si ≥ 10 min → Opción 2 (offline, implementar Día 1)
```

**Responsable:** Dev A · **Deadline:** 10 AM · **Comunicar:** Team Slack

---

### Decisión B: USDA API Key

**Verificar:**
```bash
curl -s "https://api.nal.usda.gov/fdc/v1/foods/search?query=blueberry&pageSize=1&api_key=$USDA_API_KEY" | jq .foods[0].description
```

**Opciones:**
- ✓ API key disponible → Descargar USDA (Dev A, Día 2)
- ✗ No disponible → Proceder solo OFF, documentar en `README.md`

**Responsable:** Verificar en `.env.local` · **Deadline:** HOY

---

### Decisión C: Motor de PDF (información)

**Estado:** xhtml2pdf funciona hoy (WeasyPrint está en docs pero nunca se usa).

**Acción:** Mantener xhtml2pdf; renombrar clase `InformeWeasyPrint` → `InformeXHTML2PDF` (cosmetica).

**Responsable:** S1 cierre · **Impacto en S2:** Ninguno

---

## 4. Plan parallelizable (Día 2-3)

**Dev A:** OFF + USDA descarga (8 horas, Día 2-3)

```python
# pseudocode
productos_off = cargar_off_masivo()  # 4-20 min
assert len(productos_off) >= 250, "OFF insuficiente"

productos_usda = cargar_usda()  # 5-15 min
assert len(productos_usda) >= 10

# Guardar
save_json("datasets/2026-07/off_productos.json", productos_off)
save_json("datasets/2026-07/usda_productos.json", productos_usda)
```

**Dev B:** Leer PLAN-EJECUCION-S2.md, preparar scripts para embeddings (4 horas, Día 2-3)

```python
# Preparar pero no ejecutar aún (T05 depende de T04):
# - Revisar etl/indexar_vectores.py (será reescrito)
# - Test que bge-m3 carga sin error: from sentence_transformers import SentenceTransformer
# - Medir espacio en disco disponible
```

**QA:** Leer documentación, crear plan de testing (2 horas, Día 1)

```
Revisar:
- AUDITORIA-SEMANA-2.md §4 (riesgos)
- PLAN-EJECUCION-S2.md [S2-T08] (golden set)
- Preparar evals/set_dorado.yaml (5 casos)
```

---

## 5. Hitos diarios (publicar en Slack EOD)

**LUNES 5 ago (Setup):**
```
✓ Estructura datasets/2026-07/ creada
✓ APIs OFF y USDA respondiendo
✓ Decisiones A+B tomadas
✓ Dev A + Dev B ramas sincronizadas
```

**MARTES 6 ago (Descargas):**
```
✓ OFF: N productos descargados (N >= 250)
  → Timestamp de descarga: HH:MM
  → Tiempo total: X min
✓ USDA: N productos (o "no disponible")
✓ Test de OFF pasa
```

**MIÉRCOLES 7 ago (Embeddings):**
```
✓ Merge OFF + USDA sin duplicados
✓ bge-m3 indexación iniciada
  → Tiempo esperado: X min
  → Espacio usado: Y MB
```

**JUEVES 8 ago (Búsqueda + Regulatorio):**
```
✓ Embeddings indexados (N filas)
✓ P95 latencia: X ms (meta < 2000 ms)
✓ Corpus regulatorio: eCFR + DIGESA en LanceDB
```

**VIERNES 9 ago (Cierre):**
```
✓ Golden set 5/5 pasa
✓ E2E sin errores
✓ manifest.json con hashes completos
✓ Demo: URLs navegables en OFF (screenshot o video)
```

---

## 6. Riesgos principales + planes B

### Riesgo 1: OFF timeout el Martes

**Plan B (mismo Día 2 tarde):**
1. Cambiar a offline export (wget 2GB, ~15 min)
2. Descomprimir locally
3. Ejecutar filtrado local (5 min)
4. Continuar Miércoles sin retraso

**Responsable alertar:** Dev A  
**Threshold:** Si OFF > 15 min total

---

### Riesgo 2: bge-m3 indexación > 30 min

**Plan B (mismo Miércoles):**
1. Abortar indexación actual
2. Cambiar a `sentence-transformers bge-small-en-v1.5` (33 MB)
3. Re-indexar (≈10 min)
4. Documentar en manifest.json: `"modelo": "bge-small-en-v1.5 (fallback)"`

**Responsable alertar:** Dev B  
**Threshold:** Si indexación > 20 min

---

### Riesgo 3: Cualquier cosa bloqueada > 24h

**Escalation automática:** 
- Contactar CITE lead
- Ejecutar Plan C (sacrificar OCR DIGESA, mantener eCFR)
- Continuar Jueves

---

## 7. Recursos entregados hoy

**Documentos en repo:**
- `PLAN-EJECUCION-S2.md` — Tareas [S2-T01-T09] con pseudocódigo
- `AUDITORIA-SEMANA-2.md` — Análisis profundo de riesgos
- `MATRIZ-DEPENDENCIAS-S2.md` — Visual de progreso
- `RESUMEN-S2-EJECUTIVO.md` — Checklist ejecutivo
- Este documento: `KICKOFF-S2.md`

**Scripts disponibles:**
```bash
# Test de API
curl -s "https://world.openfoodfacts.org/cgi/search.pl?search_terms=blueberry&json=1&page_size=1" | jq .products[0].product_name

# Test de embeddings (no ejecutar hasta Mié)
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-m3'); print(len(m.encode('test')))"

# Test de latencia (no ejecutar hasta Jue)
pytest test/test_latency.py -v
```

---

## 8. Contactos y escalation

```
PREGUNTA                           → CONTACTO
───────────────────────────────────────────────────
"¿Qué debería estar listo martes?" → MATRIZ-DEPENDENCIAS-S2.md §11
"¿Cómo hago T05?"                  → PLAN-EJECUCION-S2.md [S2-T05]
"OFF va lento, ¿cambio a offline?" → Sí, implementar Plan B arriba
"¿Se puede paralelizar más?"       → No, camino crítico es T01→T02→T04→T05
"¿Está bloqueado S2?"              → Ver §2 arriba: verificar 8 bloqueantes S1
```

---

## 9. Definición de "Semana 2 LISTO"

**Todos estos DEBEN estar verdes Viernes EOD:**

```bash
# 1. Datos reales
ls -lh datasets/2026-07/off_productos.json
# Esperado: archivo de varios MB

# 2. Embeddings
python -c "import lancedb; db=lancedb.connect('vectores/'); print(db.open_table('productos').count_rows())"
# Esperado: ≥250

# 3. P95 < 2 segundos
pytest test/test_latency.py::test_p95_latency -v
# Esperado: PASS

# 4. Golden set 5/5
python -m evals.runner_s2
# Esperado: 5/5 PASS

# 5. Datos navegables
# Manual: Click en URL de PDF → verifica en OFF que existe producto
# Esperado: ✓ Producto real en OFF
```

**Si alguno falla → Semana 2 extiende a Lunes 12**

---

## 10. Cierre de Kickoff

**Acuerdos:**

- [ ] Dev A comienza OFF descarga Martes 8 AM
- [ ] Dev B prepara scripts Lunes-Martes
- [ ] QA revisa golden set criteria hoy
- [ ] Decisiones A+B comunicadas a Team Slack antes de las 12 PM
- [ ] Todos revisan PLAN-EJECUCION-S2.md hoy (30 min)
- [ ] Daily standup: 9 AM y 5 PM Slack (no reunión, solo update)

**Próxima reunión:** Martes 6 ago PM (punto de control: ¿OFF en <10 min?)

---

## Firma de Kickoff

**Confirmación de asistencia + responsables:**

```
Dev A (OFF+USDA):     ____________  Fecha: ___________
Dev B (Embeddings):   ____________  Fecha: ___________
QA:                   ____________  Fecha: ___________
Tech Lead S1:         ____________  Fecha: ___________
CITE Contact:         ____________  Fecha: ___________
```

---

**Documento oficial de inicio Semana 2 del plan de 4 semanas hacia demo CDR 2026-08-28.**

---

## Anexo: Quick Links (copiar a favoritos)

| Recurso | Link |
|---|---|
| Plan de tareas | `./PLAN-EJECUCION-S2.md` |
| Auditoría completa | `./AUDITORIA-SEMANA-2.md` |
| Matriz de progreso | `./MATRIZ-DEPENDENCIAS-S2.md` |
| Resumen ejecutivo | `./RESUMEN-S2-EJECUTIVO.md` |
| Este documento | `./KICKOFF-S2.md` |
| Memoria persistente | `./memory/semana-2-auditoria.md` |
| Hilo Slack S2 | [crear hoy] |

---

**Impreso:** 2026-08-05  
**Estado:** Listo para kickoff  
**Próxima revisión:** Martes 6 ago 17:00 hrs (punto de control)
