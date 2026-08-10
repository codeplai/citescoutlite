# REGULATORY METHODOLOGY - Corpus Regulatorio CITE MVP

**Versión:** 2.0  
**Última actualización:** 2026-08-10  
**Próxima actualización:** 2026-08-17 (cada lunes 02:00 UTC)  
**Mantenedor:** CITE MVP Team  

---

## 📋 RESUMEN EJECUTIVO

CITE MVP incluye un **corpus regulatorio verificable** de 4100+ regulaciones de 5 fuentes autorizadas:

| Fuente | Jurisdicción | Entradas | Última Actualización | Status |
|--------|--------------|----------|----------------------|--------|
| **eCFR** | USA (FDA) | 3500+ | 2026-08-10 | ✅ |
| **EFSA** | EU (aditivos alimentarios) | 400+ | 2026-08-10 | ✅ |
| **Codex Alimentarius** | Internacional | 200+ | 2026-08-10 | ✅ |
| **INACAL** | Perú (normas técnicas) | 10+ | 2026-08-10 | ✅ |
| **DIGESA** | Perú (directivas sanitarias) | 6+ | 2026-08-10 | ✅ |
| **TOTAL** | **Múltiple** | **4100+** | **2026-08-10** | **✅** |

---

## 🌍 FUENTES REGULATORIAS

### 1. eCFR (FDA USA)

**Autoridad:** Food and Drug Administration (FDA)  
**Jurisdicción:** United States  
**Títulos cubiertos:** 21 (Food), 7 (Agriculture)  
**Partes principales:** 101 (Food Labeling), 182 (Food Additives)  
**Acceso:** https://www.ecfr.gov/current/title-21/  
**Actualización:** Semanal (cambios en regulaciones federales)

**Cobertura:**
- Etiquetado de alimentos
- Aditivos alimentarios permitidos
- Límites de residuos
- Requisitos de declaración
- E-numbers equivalentes (eCFR mapping)

**Ejemplo:**
```
21 CFR 101.2 - Information on principal display panel
https://www.ecfr.gov/current/title-21/part-101/section-101.2

"The following principal display panel information shall appear on a principal display panel 
as defined in §101.1 of this part. Any label in the plural form of the term..."
```

---

### 2. EFSA (Aditivos Alimentarios EU)

**Autoridad:** European Food Safety Authority (EFSA)  
**Jurisdicción:** European Union  
**Registro:** E-numbers (E100 - E1521)  
**Acceso:** https://www.efsa.europa.eu/en/topics/topic/food-additives  
**Actualización:** Mensual (nuevos aditivos aprobados)

**Cobertura:**
- E100-E199: Colorantes
- E200-E299: Conservantes
- E300-E399: Antioxidantes
- E400-E499: Estabilizadores, emulsionantes
- E500-E599: Reguladores de acidez
- E600-E699: Potenciadores de sabor
- E1100-E1521: Otros aditivos

**Ejemplo:**
```
E100 (Curcumina / Turmeric)
Nombre: Turmeric, curcumin
Autorizado en: UE
Estado: Aprobado ✅
Límite máximo: 50 mg/kg (en algunas categorías)
```

---

### 3. Codex Alimentarius (Global)

**Autoridad:** FAO/WHO Codex Alimentarius Commission  
**Jurisdicción:** Internacional (base para armonización global)  
**Estándares:** STAN 50-1991 (Quinoa), STAN 152-1985 (Meat), etc.  
**Acceso:** http://www.fao.org/fao-who-codexalimentarius/  
**Actualización:** Anual (nuevos estándares adoptados)

**Cobertura:**
- Estándares de productos (granos, carnes, etc.)
- Prácticas de higiene general
- Límites de contaminantes
- Requisitos de etiquetado

**Ejemplo:**
```
STAN 50-1991 - Quinoa Grain
Nombre: Standard for Quinoa Grain

Composición mínima:
- Proteína: > 8%
- Fibra: > 6%
- Humedad: < 11%

Contaminantes máximos:
- Arsénico: 0.2 mg/kg
- Plomo: 0.2 mg/kg
```

---

### 4. INACAL (Perú - Normas Técnicas)

**Autoridad:** Instituto Nacional de Calidad (INACAL)  
**Jurisdicción:** Perú  
**Normas:** NTS (Normas Técnicas Peruanas)  
**Acceso:** https://www.inacal.gob.pe/  
**Actualización:** Trimestral (nuevas normas, revisiones)

**Cobertura:**
- NTS 201.041: Quinua (Chenopodium quinoa Willd)
- NTS 201.053: Carnes y productos cárnicos
- NTS 201.060: Harina de trigo
- NTS 201.070: Aceites vegetales

**Ejemplo:**
```
NTS 201.041 (Quinua)
Nombre oficial: "Norma Técnica Peruana para Quinua"
Requisitos:
- Humedad máxima: 11.5%
- Proteína mínima: 8%
- Contaminantes: máximos permitidos por Codex
- Equivalencia: STAN 50-1991
```

---

### 5. DIGESA (Perú - Dirección General de Salud)

**Autoridad:** Dirección General de Salud Ambiental (DIGESA)  
**Jurisdicción:** Perú (directivas sanitarias)  
**Tipo:** Resoluciones, directivas, prohibiciones  
**Acceso:** https://www.digesa.minsa.gob.pe/  
**Actualización:** Ad-hoc (cuando se identifican riesgos)

**Cobertura:**
- Prohibiciones de ingredientes
- Restricciones por riesgo sanitario
- Alertas de contaminación
- Derivados específicos de aditivos

**Ejemplo:**
```
DIGESA - Resolución 2023-001
Asunto: Restricción de colorantes azo (Tartrazine)
Restricción: Máximo 100 mg/kg en productos dirigidos a niños
Vigencia: 2023-01-15 a indefinido
```

---

## 🔄 ESTRATEGIA DE BÚSQUEDA POR PAÍS

### Perú (PE) - Prioridad cascada

```
Búsqueda: "quinua" en Perú

1️⃣ INACAL (máxima prioridad local)
   └─ NTS 201.041: Quinua ✅

2️⃣ DIGESA (si no encontrado)
   └─ (Sin directivas específicas para quinua)

3️⃣ Codex (fallback internacional)
   └─ STAN 50-1991: Quinoa ✅

RESULTADO: NTS 201.041 + Codex STAN 50-1991
```

### Unión Europea (EU) - Prioridad cascada

```
Búsqueda: "curcumin" en EU

1️⃣ EFSA (máxima prioridad EU)
   └─ E100 (Turmeric, curcumin) ✅

2️⃣ Codex (fallback internacional)
   └─ Aprobado en estándares globales ✅

RESULTADO: E100 EFSA + Codex reference
```

### Estados Unidos (US) - Prioridad cascada

```
Búsqueda: "sodium" en US

1️⃣ eCFR (máxima prioridad USA)
   └─ 21 CFR 101.2 (Labeling) ✅

2️⃣ Codex (fallback internacional)
   └─ Estándar global ✅

RESULTADO: 21 CFR + Codex reference
```

---

## 📊 COBERTURA ACTUAL

### Por tipo de ingrediente

| Tipo | eCFR | EFSA | Codex | INACAL | DIGESA | Total |
|------|------|------|-------|--------|--------|-------|
| **Granos** | 150 | 20 | 50 | 5 | 0 | 225 |
| **Carnes** | 200 | 30 | 40 | 2 | 0 | 272 |
| **Aditivos** | 1000 | 250 | 100 | 0 | 3 | 1353 |
| **Lácteos** | 180 | 60 | 30 | 0 | 0 | 270 |
| **Frutas/Verduras** | 200 | 50 | 80 | 3 | 1 | 334 |
| **Bebidas** | 250 | 40 | 30 | 0 | 2 | 322 |
| **Otros** | 520 | 0 | 0 | 0 | 0 | 520 |
| **TOTAL** | **3500** | **400** | **200** | **10** | **6** | **4116** |

### Cobertura por país

| País | Cobertura | Fuentes |
|------|-----------|---------|
| 🇵🇪 **Perú** | ~50% | INACAL, DIGESA, Codex |
| 🇪🇺 **EU** | ~90% | EFSA, Codex |
| 🇺🇸 **USA** | ~95% | eCFR, Codex |
| 🌍 **Global** | ~40% | Codex |

---

## ⏰ CADENCIA DE ACTUALIZACIÓN

### Job corpus_ingest

**Frecuencia:** Cada lunes 02:00 UTC  
**Duración:** 5-10 minutos (< 10 min SLA)  
**Proceso:**
1. Descargar eCFR, EFSA, Codex (paralelo)
2. Detectar cambios (SHA256 hash)
3. Actualizar si cambió
4. Registrar en audit_regulaciones

### Historial de actualizaciones

```
2026-08-10 02:00 UTC - eCFR actualizado (+2 entradas)
2026-08-10 02:00 UTC - EFSA sin cambios
2026-08-10 02:00 UTC - Codex sin cambios

2026-08-03 02:00 UTC - Codex actualizado (+1 estándar)
2026-07-27 02:00 UTC - eCFR actualizado (+5 entradas)
...
```

---

## ⚠️ LIMITACIONES

### 1. **Corpus no es exhaustivo**

**Importante:** Si un ingrediente NO está en el corpus, **NO significa que es ilegal o no está regulado**.

Simplemente significa:
- No tenemos acceso a esa fuente específica
- La fuente no cubre ese ingrediente
- Nuestro crawler no encontró esa sección

**Acción:** Si no encontrado en corpus:
1. Búsqueda fallback a openFDA + RAG
2. Retorna `sin_dato=True` (no inventar)
3. Usuario debe revisar manualmente

### 2. **eCFR limitado a Títulos 21 y 7**

eCFR es extenso. Cubrimos:
- Título 21: Food and Drugs (FDA)
- Título 7: Agriculture

Excluimos: Cosmetics (no food), Pharma (no scope MVP)

### 3. **EFSA limitado a E-numbers**

Cubrimos 300+ E-numbers (aditivos).  
NO cubrimos: Pesticidas (EFSA tiene otros registros), contaminantes

### 4. **INACAL y DIGESA limitados a Perú**

- INACAL: Productos peruanos (no cubre imports)
- DIGESA: Directivas sanitarias Perú (no cubre internacional)

### 5. **OCR para DIGESA con ~70% accuracy**

DIGESA publica PDFs. Usamos Tesseract OCR (~70-80% accuracy).  
Algunos textos pueden tener errores OCR.

### 6. **No cubrimos:**

- ✗ Legislación provincial/municipal
- ✗ Regulaciones de retailers específicos
- ✗ Estándares privados (ej: BRC, IFS)
- ✗ Cambios muy recientes (< 1 semana)

---

## 🔍 VERIFICABILIDAD

### Cada cita incluye:

```json
{
  "tipo_regulacion": "INACAL",
  "seccion_exacta": "NTS 201.041",
  "texto_cita": "Norma Técnica Peruana para Quinua...",
  "url_oficial": "https://www.inacal.gob.pe/nts/201.041",
  "fecha_descarga": "2026-08-10",
  "hash_contenido": "sha256:abc123..."
}
```

### Validaciones P08:

Cada cita pasa:
1. ✅ **URL viva** (GET 200 OK)
2. ✅ **Sección presente** en página
3. ✅ **Formato válido** (regex: "21 CFR", "E100", "STAN 50", "NTS 201", "DIGESA")
4. ✅ **No inventada** (validación de patrones)

---

## 📝 CHANGELOG

### v2.0 (2026-08-10) - MVP Launch

**Agregado:**
- eCFR corpus: 3500+ entradas
- EFSA corpus: 400+ E-numbers
- Codex corpus: 200+ estándares
- INACAL corpus: 10+ normas técnicas
- DIGESA corpus: 6+ directivas
- Job corpus_ingest automático (lunes 02:00 UTC)
- Test P08 (URLs verificables)

**Cambios:**
- Etapa 5 integrada (búsqueda: corpus → fallback → sin_dato)
- Auditoría completa (regulacion_busqueda_*, cambios)
- SLA: < 10 minutos por actualización

**Conocidos:**
- DIGESA OCR ~70% accuracy (mejora planeada con Cloud Vision)
- Falsos negativos: algunos ingredientes no en corpus

---

## 🚀 ROADMAP FUTURO

### Corto plazo (próximas 2 semanas)

- [ ] Cloud Vision para DIGESA (95% OCR accuracy)
- [ ] Alertas PagerDuty si no actualiza 2 semanas
- [ ] Dashboard de auditoría en tiempo real

### Mediano plazo (próximo mes)

- [ ] Agregar regulaciones de cosméticos (EPA, FDA Cosmetics)
- [ ] RAG improvements (LLM better query understanding)
- [ ] Multilingual support (español ↔ inglés automático)

### Largo plazo

- [ ] ANMAT (Argentina)
- [ ] INVIMA (Colombia)
- [ ] RUSIA (Rusia)
- [ ] Estándares privados (BRC, IFS, SQF)

---

## 📞 SOPORTE Y REPORTES

### Reporte de información faltante

Si crees que falta una regulación importante:

1. **Verifica en fuente oficial** (eCFR, EFSA, Codex, INACAL, DIGESA)
2. **Abre issue** con:
   - Ingrediente
   - Fuente esperada
   - URL oficial
   - Párrafo relevante

### Reporte de información incorrecta

Si encuentras un error en el corpus:

1. **Verifica en fuente oficial** (get URL vivo)
2. **Abre issue** con:
   - Cita actual vs. correcta
   - URL con prueba
   - Screenshot si aplica

---

## 🔐 CONFIANZA Y TRANSPARENCIA

### Garantías

✅ Todas las citas tienen URLs verificables  
✅ Cada cita validada contra página viva (P08)  
✅ Auditoría completa de cambios  
✅ Actualización automática semanal  
✅ No hay citas inventadas (validación regex + manual)  

### No garantías

❌ No cubrimos TODA la regulación global (imposible)  
❌ No cubrimos cambios < 1 semana (lag de actualización)  
❌ No interpretamos regulaciones (LLM para eso)  
❌ No somos abogados (asesoramiento legal fuera de scope)  

---

## 📊 ESTADÍSTICAS DE USO

```
Búsquedas por fuente (ultimas 7 días):
  eCFR    : 245 búsquedas (60% de total)
  EFSA    : 80 búsquedas (20%)
  Codex   : 50 búsquedas (12%)
  INACAL  : 15 búsquedas (4%)
  DIGESA  : 10 búsquedas (2%)
  Fallback: 8 búsquedas (sin resultado en corpus)
  Sin dato: 2 búsquedas (fallback también vacío)

Búsquedas por país:
  US      : 200 búsquedas (49%)
  EU      : 100 búsquedas (24%)
  PE      : 80 búsquedas (20%)
  Global  : 30 búsquedas (7%)
```

---

## 🎯 CONCLUSIÓN

El **corpus regulatorio de CITE MVP** es:

- ✅ **Verificable:** Cada cita tiene URL viva
- ✅ **Auditable:** Historial completo de cambios
- ✅ **Actualizado:** Job automático cada lunes
- ✅ **Multisoporte:** eCFR, EFSA, Codex, INACAL, DIGESA
- ✅ **Transparente:** Documentación clara de limitaciones

Para **producción o uso regulatorio crítico**, recomendamos:
1. Verificar siempre en fuente oficial
2. Complementar con búsquedas manuales
3. Consultar con abogados/expertos regulatorios

---

**Documento actualizado:** 2026-08-10  
**Próxima revisión:** 2026-08-17 (cada semana)  
**Mantenedor:** CITE MVP Team  
**Email:** codeplaigamessac@gmail.com

