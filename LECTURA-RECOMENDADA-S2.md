# Guía de Lectura: Auditoría Semana 2

**"¿Qué leo primero?"** — Depende de tu rol.

---

## 📋 Roles y documentos recomendados

### 👨‍💼 Si eres el CITE o stakeholder

**Tiempo:** 5 minutos  
**Lee:**
1. `RESUMEN-S2-EJECUTIVO.md` — Riesgos, hitos y decisiones
2. `KICKOFF-S2.md` §6-7 — Riesgos + planes B

**Por qué:** Necesitas saber qué puede fallar y cuándo escalar.

---

### 👨‍💻 Si eres Dev A (OFF + USDA)

**Tiempo:** 30 minutos  
**Lee (en orden):**
1. `KICKOFF-S2.md` §2-3 — Bloqueantes de S1 + decisiones críticas
2. `PLAN-EJECUCION-S2.md` [S2-T01] → [S2-T04] — Tus tareas con pseudocódigo
3. `MATRIZ-DEPENDENCIAS-S2.md` §3 — Qué bloquea qué
4. `AUDITORIA-SEMANA-2.md` §5 — Riesgos específicos de descarga

**Qué necesitas hacer:**
- Martes 8 AM: Ejecutar `cargar_off_masivo()` → ver si <10 min
- Martes + Miércoles: Descargar OFF + USDA sin fallos
- Miércoles: Deduplicar y mergear

---

### 👨‍💻 Si eres Dev B (Embeddings + Búsqueda)

**Tiempo:** 45 minutos  
**Lee (en orden):**
1. `KICKOFF-S2.md` §2 — Qué debe haber entregado S1
2. `PLAN-EJECUCION-S2.md` [S2-T05] → [S2-T06] — Pseudocódigo de indexación + búsqueda
3. `AUDITORIA-SEMANA-2.md` §2.2 — Estado actual de embeddings
4. `MATRIZ-DEPENDENCIAS-S2.md` §4 — Riesgos de latencia + indexación

**Qué necesitas hacer:**
- Lunes: Revisar scripts, preparar repositorio
- Miércoles: Ejecutar `indexar_vectores.py` con bge-m3
- Jueves: Medir p95 latencia (meta <2s)

---

### 🧪 Si eres QA

**Tiempo:** 20 minutos  
**Lee:**
1. `KICKOFF-S2.md` §6-7 — Plan de testing diario
2. `PLAN-EJECUCION-S2.md` [S2-T08] — Golden set 5 casos
3. `MATRIZ-DEPENDENCIAS-S2.md` §6 — Criterios de aceptación

**Qué necesitas hacer:**
- Lunes: Ampliar `evals/set_dorado.yaml` a 5 casos
- Viernes: Ejecutar golden set (esperar 5/5 PASS)

---

### 📊 Si eres el Tech Lead o arquitecto

**Tiempo:** 60 minutos (análisis profundo)  
**Lee (en orden):**
1. `RESUMEN-S2-EJECUTIVO.md` — Visión general
2. `AUDITORIA-SEMANA-2.md` — Análisis completo (§1-§8)
3. `PLAN-EJECUCION-S2.md` — Desglose técnico de cada tarea
4. `MATRIZ-DEPENDENCIAS-S2.md` — Diagrama de flujo + dependencias

**Por qué:** Necesitas entender arquitectura, riesgos y palanca de mitigación.

---

## 🎯 Qué leer según tu urgencia

### "Necesito un resumen de 2 minutos"
→ `RESUMEN-S2-EJECUTIVO.md` (primeros 2 párrafos)

### "¿Qué puede salir mal?"
→ `RESUMEN-S2-EJECUTIVO.md` §Riesgos principales  
→ `MATRIZ-DEPENDENCIAS-S2.md` §4

### "¿Qué está bloqueando S2?"
→ `RESUMEN-S2-EJECUTIVO.md` §Bloqueantes de Semana 1  
→ `KICKOFF-S2.md` §2

### "¿Cuándo comienza S2?"
→ `KICKOFF-S2.md` (es el acta oficial)

### "¿Cómo implemento la tarea X?"
→ `PLAN-EJECUCION-S2.md` [S2-T01] a [S2-T09]

### "¿Cuál es el camino crítico?"
→ `MATRIZ-DEPENDENCIAS-S2.md` §3

### "Necesito la auditoría completa para entender todo"
→ `AUDITORIA-SEMANA-2.md` (todas las secciones)

---

## 📚 Índice de documentos

| Documento | Propósito | Audiencia | Tiempo |
|---|---|---|---|
| **RESUMEN-S2-EJECUTIVO.md** | Decisiones rápidas + riesgos | CITE, Tech Lead | 5 min |
| **KICKOFF-S2.md** | Acta de inicio oficial | Todos | 15 min |
| **PLAN-EJECUCION-S2.md** | Pseudocódigo ejecutable de tareas | Devs | 30 min |
| **AUDITORIA-SEMANA-2.md** | Análisis profundo | Tech Lead, Devs | 60 min |
| **MATRIZ-DEPENDENCIAS-S2.md** | Visual de progreso + camino crítico | Todos | 10 min |
| **LECTURA-RECOMENDADA-S2.md** | Este documento (guía de lectura) | Todos | 3 min |

---

## ⚡ Velocidad de lectura recomendada

**Total recomendado por rol:**

```
CITE/Stakeholder:    10 minutos (2 docs)
Dev A (OFF/USDA):    30 minutos (3 docs)
Dev B (Embeddings):  45 minutos (4 docs)
QA:                  20 minutos (3 docs)
Tech Lead:           90 minutos (4 docs) + reference
```

**Si tienes <5 min:** Lee `RESUMEN-S2-EJECUTIVO.md` + `KICKOFF-S2.md` §2-3

---

## 🔗 Flujo de lectura recomendado para TODOS

1. **Lunes mañana (antes de kickoff):** `KICKOFF-S2.md` (15 min)
2. **Lunes tarde (si eres dev):** Tu documento de tareas (30-45 min)
3. **Martes PM (punto de control):** `MATRIZ-DEPENDENCIAS-S2.md` §11 (5 min)
4. **Viernes PM (cierre):** `MATRIZ-DEPENDENCIAS-S2.md` §9 (verificar checklist)

---

## 📌 Acuerdos implícitos en estos documentos

**Todos estos documentos asumen:**

1. **S1 entregará 8 bloqueantes** (ver `RESUMEN-S2-EJECUTIVO.md` / `KICKOFF-S2.md` §2)
   - Si no → S2 no comienza

2. **S2 tiene 5 días hábiles** (Lun 5 - Vie 9 ago)
   - Si se extiende >48h → escalación automática

3. **Datos reales > datos inventados**
   - Si OFF falla → Plan B offline, no fallback a DEMO
   - Si USDA no disponible → proceder solo OFF

4. **Reproducibilidad = requisito no negociable**
   - Manifest.json con SHA256 de todo
   - README.md con procedimiento paso a paso

5. **P03 = criterio de aceptación de S2**
   - P95 latencia < 2s
   - ≥30 productos indexados
   - Sin DEMO data si OFF exitoso

---

## 🚨 Si algo no está claro

**"No entiendo la Decisión B (USDA)"**  
→ Ver `KICKOFF-S2.md` §3 / `RESUMEN-S2-EJECUTIVO.md`

**"¿Qué pasa si OFF tarda >10 min?"**  
→ Ver `RESUMEN-S2-EJECUTIVO.md` § Riesgos / `KICKOFF-S2.md` §6

**"¿Cómo implanto T05?"**  
→ Ver `PLAN-EJECUCION-S2.md` [S2-T05] con pseudocódigo

**"¿Qué hace bge-m3?"**  
→ Ver `AUDITORIA-SEMANA-2.md` §2.2 (embeddings)

**"¿Cuál es el camino crítico?"**  
→ Ver `MATRIZ-DEPENDENCIAS-S2.md` §3 (diagrama)

---

## ✅ Checklist de lectura (marca mientras lees)

**Todos (5 minutos):**
- [ ] `KICKOFF-S2.md` §1-2 (bloqueantes + decisiones)

**Devs (30+ minutos):**
- [ ] Tu rol en `PLAN-EJECUCION-S2.md`
- [ ] Riesgos en `AUDITORIA-SEMANA-2.md` §5

**QA (20 minutos):**
- [ ] Golden set criteria en `PLAN-EJECUCION-S2.md` [S2-T08]
- [ ] Hitos de validación en `MATRIZ-DEPENDENCIAS-S2.md` §6

**Tech Lead (90 minutos):**
- [ ] Toda la auditoría
- [ ] Dependencias en `MATRIZ-DEPENDENCIAS-S2.md` §3
- [ ] Camino crítico vs sacrificios en `AUDITORIA-SEMANA-2.md` §10

---

## 🎓 Después de leer

**Esperamos que entiendas:**

- ✓ Qué debe entregar S1 (8 items)
- ✓ Qué tareas hay en S2 (9 tareas)
- ✓ Qué riesgos principales existen (4 principales)
- ✓ Cuál es el camino crítico (T01→T02→T04→T05→T06)
- ✓ Qué pruebas definen "S2 listo" (5 hitos)
- ✓ Cuándo escalar si hay problemas (>24h retraso)

**Si falta algo de eso → Re-lee `RESUMEN-S2-EJECUTIVO.md`**

---

## 📞 Contactos útiles

```
PREGUNTA                              DOCUMENTO
──────────────────────────────────────────────────────────
"¿Por dónde empiezo?"                 KICKOFF-S2.md
"¿Qué puede fallar?"                  RESUMEN-S2-EJECUTIVO.md
"Dame el pseudocódigo de mi tarea"    PLAN-EJECUCION-S2.md
"¿Qué depende de qué?"                MATRIZ-DEPENDENCIAS-S2.md
"Cuéntame todo con detalle"           AUDITORIA-SEMANA-2.md
"¿Cuándo hay que escalar?"            Cualquiera + KICKOFF-S2.md §6
```

---

**Guía creada:** 2026-07-30  
**Válida desde:** 2026-08-05 (Kickoff S2)  
**Próxima revisión:** Martes 6 ago PM

---

*Leer esto antes de leer los otros documentos: ahorra 20 minutos de confusión.*
