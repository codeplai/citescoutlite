# ADR-002 · Motor de Inteligencia de Mercado (MIM) y agente comercial acotado

- **Estado:** Propuesto
- **Fecha:** 2026-07-22
- **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic) — `v7` → `v7.1`
- **Depende de:** [ADR-001](ADR-001-nucleo-comercial-y-paywall.md)
- **Origen:** correo del CITE con 7 fuentes de consulta + análisis del `sample` (Mintel GNPD)

---

## 1. Contexto

El `sample` que compartió el CITE es material de **Mintel GNPD**: un deck de análisis de mercado (`ANALISIS DE MERCADO.ppt`) y fichas de producto en PDF. El análisis reveló dos cosas:

1. La ficha PDF de Mintel es —campo por campo— la entidad `ProductoEnMercado` definida en el ADR-001 (marca, mercado/país, tienda, canal, precio local + USD, código de barras, ingredientes, valores nutricionales, claims, URL). **El sample valida el modelo de dominio.**
2. Lo que hace valioso a Mintel no es la búsqueda, sino dos capas: la **normalización/taxonomía** (categorías, claims e ingredientes estandarizados) y el **motor de series de tiempo** (lanzamientos por trimestre → % de cambio). Esas dos capas son ≈80% del valor y **sí son replicables barato**; la red global de compradores físicos (el otro 20%) no.

Además, el CITE envió 7 URLs de referencia. Se verificó el método de acceso de cada una (ver §4). Hallazgo clave: **casi todas son regulatorias o de composición/tendencias; ninguna resuelve el precio de anaquel**, que sigue siendo el hueco del eje comercial.

## 2. Decisión

Extender la arquitectura a `v7.1` con dos bloques nuevos, sin alterar la base hexagonal:

### 2.1 Motor de Inteligencia de Mercado (MIM) — normalización + tendencias (el diferencial)

Tres componentes entre las fuentes y los almacenes:

- **Normalización LLM → Taxonomía CITE.** El LLM clasifica cada producto ingerido a una taxonomía canónica (categorías, claims, ingredientes) definida con el CITE. Actúa como **anti-corruption layer** (salida validada contra schema). Es el *moat*: incorpora el know-how agroindustrial del CITE y es lo que convierte fichas sueltas en análisis.
- **Motor de Tendencias (DuckDB).** Series por trimestre de categoría/claim/ingrediente y cálculo de `% de cambio`, marcas nuevas y nuevos ingredientes. Determinista, sin LLM, barato. Reproduce el deck de análisis GNPD del sample.
- **Generador de reportes.** Deck de mercado (PPT) + ficha `ProductoEnMercado` (PDF), replicando el formato de Mintel.

**Conclusión operativa:** Mintel es 20% búsqueda y 80% normalización + series de tiempo. La IA agéntica resuelve ese 20%; el 80% lo resuelve OFF + DuckDB + taxonomía propia, que además es más defendible.

### 2.2 `AgenteInvestigadorComercial` (adaptador agéntico acotado)

Nuevo adaptador detrás del `PuertoDescubrimientoComercial` (nivel 3 de la cascada), para el hueco de precio/retail y productos nuevos no indexados. Es un **agente tool-using acotado**, no autónomo:

- Toolset fijo: `buscar_web` → `abrir_url` → `extraer_producto` (+ cache).
- Salida obligatoria = `ProductoEnMercado` validado contra schema; cada campo con `fuente + url + fecha`; `null` si no se encuentra (**nunca inventar precios**).
- **Topes duros** por run: iteraciones, llamadas a herramientas, tokens y **costo en US$**.
- Envuelto con `cockatiel` (retry + circuit breaker + bulkhead) y decorador de cache (`insumo+país+mes`).
- **Asíncrono, por job**, con eventos de progreso al panel; nunca bloquea el request.
- Se ejecuta **on-demand y tras el paywall**, no en cada consulta gratuita.
- Library-first: runtime Pydantic AI / LangGraph · búsqueda Tavily/Brave/SerpAPI · extractor trafilatura · tool-use con glm-5.2 (puerto LLM sin cambios).

## 3. Estrategia de fuentes

Orden pragmático: **primero el pipeline batch determinista** (fuentes API/bulk + PDF/manual → normalización → tendencias), que ya entrega ~70-80% del valor barato y estable. **Después** el agente para el enriquecimiento de precio/retail, que es el trozo caro y va on-demand tras el paywall.

## 4. Fuentes verificadas (correo del CITE + open data)

| Fuente | Aporta | Acceso (verificado) | Licencia | Clasificación |
|---|---|---|---|---|
| **USDA FoodData Central** | composición + Branded Foods (marca) | API pública `api.nal.usda.gov/fdc/v1` (key data.gov, 1000 req/h) + bulk | CC0 dominio público | Batch API |
| **FDA — eCFR Título 21** | aditivos alimentarios EEUU | API pública `ecfr.gov` + XML masivo | Dominio público | Batch API |
| **EFSA** | opiniones científicas, datasets | API con key gratuita (developer portal, DCAT-AP + DOI) | Abierta | Batch API |
| **Open Food Facts** | marca·país·ingredientes·claims | export completo | ODbL | Batch bulk — base MIM |
| **Open Prices** | precio retail crowdsourced | export/API | ODbL | Batch — cubre precio (parcial) |
| **UN Comtrade** | precio export US$/kg | API pública | Abierta | Batch — precio mayorista |
| **Codex Alimentarius** (GSFA/JECFA) | norma internacional de aditivos | web + PDFs (sin API limpia) | Público | Batch PDF/OCR |
| **INACAL (Perú)** | Normas Técnicas Peruanas | catálogo web; docs de pago; **sin API** | Mixta | Manual — vacío regulatorio Perú |
| **Trend Hunter** | tendencias/innovación (claims) | **sin API oficial**; ToS restrictivo | Propietaria | Agente / live (con cita) |
| **Mintel** | benchmark (fichas + precio) | suscripción de pago, sin API abierta | Licenciada | **EXCLUIDA** (no se consume) |

Decisiones derivadas de la verificación:

- Tres de las fuentes del CITE (USDA, FDA/eCFR, EFSA) tienen **API real** → la verificación regulatoria (etapa 5) pasa de RAG + PDFs a **ingesta batch por API**, y baja la necesidad del agente en lo regulatorio.
- **Mintel se excluye explícitamente**: es el benchmark a sustituir, no una fuente consumible. Su valor se reproduce con OFF + taxonomía + tendencias + agente.
- **Ninguna fuente de la lista resuelve el precio de anaquel**: ese eje depende de OFF + Open Prices + Comtrade + agente.

## 5. Consecuencias

**Positivas**

- El diferencial deja de ser "buscar en internet" y pasa a ser la normalización + taxonomía + tendencias, que es defendible y aprovecha el know-how del CITE.
- La verificación regulatoria se vuelve más barata y confiable al usar APIs oficiales.
- El costo se controla: el agente (lo caro) es acotado, cacheado, medido y on-demand tras el paywall.
- La base local (~US$85/mes), hexagonal y por snapshots se conserva.

**Negativas / riesgos**

- La **taxonomía CITE** es trabajo humano inicial no trivial; su calidad determina el valor del motor.
- **INACAL / Trend Hunter** sin API → ingesta frágil o manual; tratar como fuentes de menor frecuencia.
- El **precio de anaquel** sigue con cobertura parcial; gestionar expectativas del CITE.
- ToS de Trend Hunter y marketplaces: usar con cita, respetar robots; sin scraping masivo.

## 6. Acciones derivadas

- Definir con el CITE la **taxonomía canónica** (categorías, claims, ingredientes) — insumo del *moat*.
- Implementar adaptadores batch: USDA FDC, FDA eCFR, EFSA (con gestión de API keys).
- Implementar el pipeline OFF → normalización → catalogo_comercial + motor de tendencias.
- Especificar el schema `ProductoEnMercado` (calcado del PDF de Mintel) como contrato del agente.
- Implementar `AgenteInvestigadorComercial` con sus topes de costo y validación de salida.
- Instrumentar el generador de reportes (deck PPT + ficha PDF).
