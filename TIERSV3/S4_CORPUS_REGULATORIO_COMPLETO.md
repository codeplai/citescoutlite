# Semana 4 · CORPUS REGULATORIO COMPLETO

**Objetivo:** Toda cita de regulación es verificable contra norma en la base.

**Duración:** 5 días · **Equipo:** Data (2) + Backend (1)

---

## ITEMS SEMANA 4

### 4.1 DESCARGAR E INDEXAR eCFR COMPLETO (FDA)
- **Descripción:** Electronic Code of Federal Regulations (todos los títulos)
- **Tareas:**
  - [ ] Fuente: FDA eCFR JSON feed (`https://www.ecfr.gov/api/`)
  - [ ] Filtrar títulos relevantes: 21 (Food & Drugs), 7 (Agriculture)
  - [ ] Parsear por: Título, Parte, Sección, Subsección
  - [ ] Campos relevantes: aditivos permitidos, límites de residuos, composición
  - [ ] Guardar en Postgres tabla `ecfr_regulations`:
    - `regulation_id, title (21/7), part, section, subsection, texto_completo, url_oficial, fecha_efectiva, last_update`
  - [ ] Índices: (title, part), full-text search
  - [ ] Hashear contenido para change detection (detectar si FDA actualiza)
- **Duración:** 1 día
- **Dependencias:** DB (S1)
- **DoD:** eCFR indexado, búsqueda rápida (< 100ms), 2000+ reglamentos

---

### 4.2 DESCARGAR E INDEXAR EFSA (EUROPA)
- **Descripción:** European Food Safety Authority regulations
- **Tareas:**
  - [ ] Fuente: EFSA Register (`https://www.efsa.europa.eu/`)
  - [ ] E-additives autorizados: nombre, E-number, max levels por categoría de alimento
  - [ ] Authorized uses por ingrediente
  - [ ] Guardar tabla `efsa_regulations`:
    - `regulation_id, e_number, ingredient_name, authorized_uses (array), max_levels_pct, url_oficial, last_update`
  - [ ] Búsqueda: por E-number o nombre ingrediente
- **Duración:** 1 día
- **Dependencias:** DB (S1)
- **DoD:** EFSA indexada, coverage > 95% de aditivos comunes

---

### 4.3 DESCARGAR CODEX ALIMENTARIUS (ONU/FAO)
- **Descripción:** International food standards
- **Tareas:**
  - [ ] Fuente: Codex Alimentarius Commission (`https://www.fao.org/fao-who-codexalimentarius/`)
  - [ ] Estándares relevantes: composición, etiquetado, higiene, pesticidas, residuos
  - [ ] Guardar tabla `codex_standards`:
    - `standard_id, nombre_estándar, código_cat (ej 'STAN 50-1991'), versión, año, texto, url_oficial`
  - [ ] Conversión ISO si aplica (ej: Codex → INACAL equivalente)
- **Duración:** 0.5 días
- **Dependencias:** DB (S1)
- **DoD:** Codex indexado, 200+ estándares principales

---

### 4.4 DESCARGAR INACAL (PERÚ) Y NORMALIZAR CON eCFR/EFSA
- **Descripción:** Normas técnicas peruanas, vinculadas a estándares internacionales
- **Tareas:**
  - [ ] Fuente: INACAL (`https://www.inacal.gob.pe/`)
  - [ ] Descargar PDF de NTS (Normas Técnicas Peruanas) para alimentos
  - [ ] Tablas relevantes: carnes, lácteos, frutas, hortalizas, conservas
  - [ ] Guardar tabla `inacal_nts`:
    - `nts_id, nombre_nts, código_nts (ej 'NTS 201.041'), versión, texto, url_oficial`
  - [ ] Anti-corruption: mapear INACAL nombre ingrediente → eCFR nombre → EFSA E-number
  - [ ] Tabla `mapping_regulaciones`:
    - `ecfr_ref, efsa_ref, inacal_ref, codex_ref, ingrediente_canónico`
- **Duración:** 1 día
- **Dependencias:** eCFR (4.1), EFSA (4.2), Codex (4.3)
- **DoD:** INACAL indexado, mapping 80%+ de ingredientes piloto

---

### 4.5 OCR DE DIGESA (PERU) - DIRECTIVAS EN PDF
- **Descripción:** Extraer información de PDFs de DIGESA (improvisados)
- **Tareas:**
  - [ ] Descargar PDFs de DIGESA (importación, etiquetado, vigilancia)
  - [ ] OCR: Tesseract (libre) o Google Vision API (paid)
  - [ ] Parsear campos: ingrediente bloqueado, límite permitido, justificación
  - [ ] Guardar tabla `digesa_directivas`:
    - `directiva_id, asunto, ingrediente, acción (bloqueado/restringido/permitido), límite, justificación, fecha_emitida, archivo_pdf_url`
  - [ ] Quality control: validar OCR (revisar 10% a mano si necesario)
- **Duración:** 1.5 días
- **Dependencias:** DB (S1)
- **DoD:** DIGESA indexada, 70%+ accuracyOCR (aceptable)

---

### 4.6 CREAR TABLA REGULACION_CITAS Y LINKING
- **Descripción:** Estructura para que etapa 5 pueda hacer queries
- **Tareas:**
  - [ ] Tabla `regulacion_cita`:
    - `cita_id, ingrediente, tipo_regulacion ('eCFR'/'EFSA'/'Codex'/'INACAL'/'DIGESA'), regulation_id (FK), sección_exacta, texto_cita, url_oficial, versión_norma, fecha_acceso`
  - [ ] Índices: (ingrediente, tipo_regulacion), full-text search
  - [ ] Función `buscar_regulacion(ingrediente, país='PE'/'EU'/'US') → [regulacion_cita]`
    - Si país='PE': buscar INACAL, DIGESA, Codex (en ese order de prioridad)
    - Si país='EU': buscar EFSA, Codex
    - Si país='US': buscar eCFR, Codex
  - [ ] Test: buscar "quitosano" en PE → debe retornar DIGESA directiva si existe
- **Duración:** 0.5 días
- **Dependencias:** Todas las fuentes (4.1-4.5)
- **DoD:** Función buscar_regulacion retorna citas con URLs vivas

---

### 4.7 INTEGRAR EN ETAPA 5 (REGULACIÓN)
- **Descripción:** Etapa 5 ahora cita normas reales
- **Tareas:**
  - [ ] Actualizar etapa 5 `VerificacionRegulatoria`:
    ```python
    @etapa(nombre="5_Regulacion")
    def ejecutar(formulacion_resultado, país):
        regulaciones = []
        for ingrediente in formulacion_resultado.ingredientes:
            citas = buscar_regulacion(ingrediente, país)
            regulaciones.append({
                "ingrediente": ingrediente,
                "citas": citas,  # cada cita tiene URL verificable
                "estatus": "permitido" if citas else "sin_regulacion_conocida"
            })
        return VerificacionRegulatoriaResult(regulaciones)
    ```
  - [ ] Auditoría: registrar cada búsqueda en audit_log
  - [ ] Informe: si no hay regulación, declare "sin regulación conocida" (no invente)
  - [ ] Cost: glm-5.2 toca para synthesizar (pequeño, ~$0.001)
- **Duración:** 0.5 días
- **Dependencias:** Regulacion_cita (4.6), etapa 5 estructura
- **DoD:** Etapa 5 retorna citas con URLs, no valores inventados

---

### 4.8 TEST P08 (REGULACIÓN VERIFICABLE)
- **Descripción:** Cada cita en el informe es URL viva + sección exacta
- **Tareas:**
  - [ ] Query sobre "quinua" + "fibra" (ingrediente/claim)
  - [ ] Informe dossier incluye "Regulación: fibra permitida bajo Codex STAN 50-1991, sección 3.2"
  - [ ] Test: hacer GET a URL + buscar "STAN 50-1991" en la página → 200 ok, texto presente
  - [ ] Verificar: no hay citas inventadas (regex en test suite)
  - [ ] Verificar P18 prep: corpus integridad (eCFR tiene > 5000 entries, EFSA > 500, etc.)
- **Duración:** 0.5 días
- **Dependencias:** Etapa 5 (4.7)
- **DoD:** P08 verde, citas verificables, URLs activas

---

### 4.9 SETUP DE ACTUALIZACIÓN DIARIA DE CORPUS
- **Descripción:** Corpus no es estático, debe actualizarse periódicamente
- **Tareas:**
  - [ ] Job: `job_corpus_ingest` cada lunes 02:00 UTC
  - [ ] Pasos:
    1. Descargar eCFR feed, hash previous, si cambió → update
    2. Descargar EFSA, hash, si cambió → update
    3. Descargar Codex, hash, si cambió → update
    4. Detectar y registrar cambios en audit_log
  - [ ] SLA: < 10 min
  - [ ] Alert si falla 2 semanas seguidas (sin actualización)
- **Duración:** 0.5 días
- **Dependencias:** Procrastinate (S3)
- **DoD:** Job corre cada lunes, detecta cambios

---

### 4.10 DOCUMENTACIÓN: METODOLOGÍA DE REGULACIÓN
- **Descripción:** Aclarar qué es v3 y qué no
- **Tareas:**
  - [ ] Documento: `REGULATORY_METHODOLOGY.md`
  - [ ] Secciones:
    - [ ] Fuentes: eCFR (US), EFSA (EU), Codex (global), INACAL (PE), DIGESA (PE)
    - [ ] Cobertura: % por país, último update
    - [ ] Limitaciones: "si no está en corpus, no significa no existe" → "sin regulación conocida"
    - [ ] Actualización: cada lunes, changelog disponible
  - [ ] Incluir en informe PDF: small print que cita metodología
- **Duración:** 0.5 días
- **Dependencias:** Todas (4.1-4.9)
- **DoD:** Documento claro, clientes entienden cobertura

---

## DEFINITION OF DONE (S4)

- [ ] eCFR descargado, indexado, searchable
- [ ] EFSA descargado, indexado
- [ ] Codex descargado, indexado
- [ ] INACAL descargado, indexado
- [ ] DIGESA PDFs con OCR, indexados
- [ ] Tabla regulacion_cita poblada, queries rápidas
- [ ] Función buscar_regulacion(ingrediente, país) implementada
- [ ] Etapa 5 integrada con búsqueda de regulación
- [ ] P08 verde (citas verificables)
- [ ] Job corpus_ingest configurado
- [ ] REGULATORY_METHODOLOGY.md escrito

---

## RIESGOS S4

| Riesgo | Mitigación |
|---|---|
| eCFR/EFSA feed no es estable, URLs cambian | Descarga periódica, versionar cada copy |
| OCR de DIGESA tiene < 60% accuracy | Usar Google Vision (pago); si aún bajo, marcar como "manual review needed" |
| Mapping entre regulaciones es incompleto | Trabajar con especialista del CITE; acepta 80% como v3 |
| Query de regulación es lenta (> 100ms) | Agregar índices full-text; considerar Elasticsearch si Postgres slow |
| Corpus se queda desactualizado (no corre job) | Alerta en PagerDuty; manual fallback: ejecutar job en request |

---

## NOTAS

- **Equipo:** 2 data engineers (descargas + OCR) + 1 backend (integración)
- **Orden:** eCFR → EFSA → Codex → INACAL → DIGESA (paralelizar descargas primeras 4)
- **Especialista:** CITE debe validar OCR DIGESA y mapping (es la parte más riesgosa)
- **Costo adicional:** OCR Google Vision ~$1.5/1000 images (few hundred PDFs = $1-2)
