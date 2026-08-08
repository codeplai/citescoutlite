# AgroScout IA — Arquitectura v2

**Shelf Radar integrado como N1+N2 del puerto DescubrimientoComercial**

| | |
|---|---|
| Versión | 2.0 |
| Fecha | 2026-08-08 |
| Base | v1 (MVP walking skeleton · ADR-003 fase 1 con datos reducidos) |
| Cliente | CITEagroindustrial Chavimochic |
| Diagrama | `Arquitectura_AgroScout_IA_MVP_v2_ShelfRadar.svg` |
| Documento hermano | `SHELF_RADAR_ARQUITECTURA.md` (detalle técnico del barrido) |

---

## 1. Qué cambia en v2 — y qué no

**Nada de v1 se descarta.** El DAG de 6 etapas, el contrato del puerto, el paywall, la cuarentena del agente y el modelo de suscripción son idénticos. v2 no rediseña: **llena los huecos que v1 dejó declarados como snapshot o stub**.

| Componente | v1 | v2 |
|---|---|---|
| Puerto N1 | snapshot local congelado `datasets/2026-07/` | **Shelf Radar** · 42 tiendas vivas, serie diaria |
| Puerto N2 | STUB | **Bright Data Scraper API** · 5 tiendas, ~US$200/año |
| Puerto N3 | agente REAL, presupuestado | igual, pero **se dispara mucho menos** |
| Open Food Facts | ficha técnica **+ proxy de mercado** | solo ficha técnica **+ llave EAN** |
| Precio de góndola | Open Prices (parcial) + hueco que llena el agente | `shelf_facts` · 67 tiendas · 29 países |
| Procedencia | agente → cuarentena | **escalera de 5 niveles**: conectores directo, agente a cuarentena |
| Pruebas | P01–P13 | P01–**P15** |

La razón de fondo: v1 usaba el agente LLM para tapar un hueco de dato que en realidad se resuelve con conectores deterministas a una décima de milésima del costo. El agente pasa a hacer lo que solo él puede hacer — buscar lo que no está en ninguna API.

---

## 2. Principios

Los cuatro de v1 se mantienen:

1. **Nada se inventa.** Campo sin dato es `null`, nunca un valor plausible.
2. **Toda afirmación cita su dato.** El insight no es opinión del modelo, es lectura de una fila entregada.
3. **El presupuesto es un invariante, no una alerta.** Al tope, el sistema degrada a "sin dato"; jamás devuelve error ni gasta de más.
4. **Multi-tenant desde el día uno.** RLS por organización, cost-meter por tenant.

v2 agrega dos:

5. **La confianza del dato depende de su origen, no de su forma.** Un JSON de una API documentada con checksum no necesita el mismo control que una extracción por LLM sobre HTML. La escalera de procedencia (§5.3) lo formaliza.
6. **La cobertura se declara, incluida la que falta.** Una fila de intento por cada tienda del scope, aunque haya fallado o esté vedada por política. Es la diferencia entre "no hay producto" y "no pudimos mirar".

---

## 3. Capa de aplicación

Sin cambios respecto de v1.

```
FastAPI · 1 nodo (MVP)          Vue 3 SPA · stateless
Supabase                        auth · planes · RLS por organización
                                PolíticaDeSuscripción → nivel_maximo_costo
Panel CITE                      progreso de jobs · cost-meter · informes
```

`nivel_maximo_costo` sigue siendo el parámetro que la aplicación pasa al puerto y que decide hasta qué nivel de la cascada se permite escalar. En v2 ese parámetro cobra más sentido porque los tres niveles existen de verdad.

**Cuentas demo:** `demo-gratuita` (Mipyme, etapas 1-3, informe parcial) y `demo-premium` (Cooperativa, DAG completo + agente on-demand). Dos organizaciones distintas para probar RLS [P01].

---

## 4. DAG EvaluarInsumo — las 6 etapas

Sin cambios estructurales. Insumos piloto: **arándano, palta, espárrago, mango, quinua**.

| # | Etapa | Motor | Cambio en v2 |
|---|---|---|---|
| 1 | InterpretarInsumo | glm-4.7-flashx · sinónimos ES/EN | — (2ª llamada = cache hit) |
| 2a | MatchProductos | vectores + DuckDB · sin LLM · p95 < 2s | **llave EAN desde OFF** explícita |
| 2b | MapaComercial ★ | puerto DescubrimientoComercial | **N1 = Shelf Radar** en vez de snapshot |
| 3 | InsightMercado | glm-4.7 (Z.ai) | ahora cita precios reales, no proxy |
| 4 | Formulación | minería DuckDB + glm-5.2 · premium | — |
| 5 | Regulación | eCFR piloto + DIGESA · premium | — |
| 6 | InformeScout | PDF por worker · auditoría DAG | — |

**Paywall** entre etapa 3 y 4: early return con informe parcial [P06]. No confundir con el guard de 0-2 productos, que es otra condición.

### 4.1 Nota sobre la etapa 2a y la llave EAN

En v1 el match era por similitud de vectores sobre título y categoría. Eso funciona dentro de un mismo idioma y falla entre mercados: "arándano deshidratado" en Plaza Vea y "getrocknete Heidelbeeren" en EDEKA no se parecen ni en el embedding ni en el texto.

El código de barras resuelve eso de forma exacta. **Open Food Facts tiene el EAN/GTIN como clave primaria**, y VTEX lo expone en `items[].ean`. La cadena queda:

```
producto en góndola (VTEX) → ean → OFF → ficha técnica canónica
                                        ↓
                            mismo ean visto en otra tienda/país
```

Cuando no hay EAN (Shopify casi nunca lo publica), se cae al match por vectores con el gate de categoría de §5.4. El campo `match_method` registra cuál se usó, y eso viaja al informe.

---

## 5. Puerto DescubrimientoComercial ★

El corazón de v2. El contrato con la etapa 2b **no cambia**: recibe `insumo + país + nivel_maximo_costo` y devuelve `ProductoEnMercado[]` con `fuente + url + fecha`, o `null` en los campos sin dato.

### 5.1 La cascada

```
                   nivel_maximo_costo
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
   N1 · Shelf Radar   N2 · Licenciado   N3 · Agente
   42 tiendas         5 tiendas         solo huecos
   httpx + Scrapling  Bright Data       Pydantic AI + Tavily
   ~US$0.0001/consulta ~US$200/año      US$0.25/run
        │                 │                 │
        └────────┬────────┘                 │
                 ▼                          ▼
        catalogo_comercial            staging_agente
        (verificado, directo)         (cuarentena, manual)
```

**N1 · Shelf Radar (REAL, default).** 42 tiendas resueltas por conectores deterministas:

| Adaptador | Transporte | Tiendas | Cómo |
|---|---|---|---|
| VTEX | httpx | ~15 | `/api/catalog_system/pub/products/search?ft=` — API pública documentada por VTEX |
| Shopify | httpx | ~15 | `/products.json` + `/search/suggest.json` — endpoints públicos de la plataforma |
| JSON-LD | httpx | ~12 | `sitemap.xml` → `application/ld+json` con `@type: Product` |
| Dynamic | Scrapling | ~12 | solo cuando el contenido requiere ejecución de JS |

**N2 · Licenciado (REAL).** Bright Data Scraper API para las 5 tiendas con anti-bot fuerte (Amazon, Costco, Instacart, Kroger, Meituan). Modelo asíncrono: `trigger` → `snapshot_id` → webhook. En v1 esto era un stub declarado.

**N3 · Agente (REAL, presupuestado).** Sin cambios en su implementación: `AgenteInvestigadorComercial` con Pydantic AI + Tavily (fallback Brave), trafilatura y glm-5.2 tool-use. Lo que cambia es **cuándo se invoca**: solo para los huecos que N1 y N2 no cubren.

### 5.2 Impacto económico

Los topes de v1 se mantienen: **US$0.25/run · US$2/tenant·mes · US$10 global·mes + kill-switch** [P12].

Lo que cambia es el rendimiento de ese presupuesto. US$2/tenant·mes son 8 corridas de agente. En v1, cualquier consulta premium que necesitara dato comercial podía consumir una. En v2, 42 tiendas se resuelven antes de llegar al agente, y esas 8 corridas quedan para los casos que de verdad las necesitan.

| Escenario | Costo de dato comercial |
|---|---|
| v1 · 1 consulta que dispara el agente | US$0.25 |
| v2 · 1 consulta resuelta en N1 | ~US$0.0001 |
| v2 · barrido semanal 50 productos × 42 tiendas | ~US$0.60/año en N1 |
| v2 · N2 Bright Data, 5 tiendas, semanal | ~US$200/año |

### 5.3 Escalera de procedencia [P14]

La regla nueva de v2. **No todo el dato merece el mismo control.**

| `provenance` | Origen | Verificación | Destino |
|---|---|---|---|
| `conector_api` | VTEX, Shopify | checksum SHA-256 del payload | `catalogo_comercial` directo |
| `conector_jsonld` | sitemap + JSON-LD | checksum + canario diario | `catalogo_comercial` directo |
| `conector_dinamico` | Scrapling | checksum + canario diario | `catalogo_comercial` directo |
| `licenciado` | Bright Data | contrato + checksum | `catalogo_comercial` directo |
| `agente` | N3 · extracción por LLM | **grounding check** + promoción manual | `staging_agente` → cuarentena |

La justificación: la cuarentena de v1 existe porque un LLM extrayendo de HTML puede producir un valor que no está en el origen. Un endpoint VTEX que devuelve `{"Price": 24.90}` con checksum no tiene ese modo de fallo. Someterlo al mismo circuito de promoción manual sería teatro de control, no control.

Lo que **sí** aplica a los conectores es el canario diario: un barrido de un producto conocido contra las 67 tiendas con aserciones. Si una tienda pasa de 20 ofertas a 0, hay un rediseño de sitio y el adaptador está roto.

### 5.4 Gate de categoría [P15]

El control de calidad que evita el error clásico de este tipo de sistema: mezclar productos que no son de la categoría consultada.

```
similitud coseno (embedding del título vs centroide de categoría)
   < 0.55        → descartar · no entra a catalogo_comercial
   0.55 – 0.75   → juez LLM binario (~5% de los casos)
   > 0.75        → aceptar
```

Se resuelve en Postgres con pgvector, en la misma consulta que trae las ofertas. Criterio de prueba: buscar "quinua" en una droguería devuelve **0 productos con `coverage: no_match`**, no cinco cremas faciales.

### 5.5 Cortesía y política de acceso

Heredado de v1 (robots/allowlist, rate-limit por dominio, idempotencia por `insumo+país+mes`) y extendido a los conectores:

- `robots.txt` parseado como código, con `Disallow`, `Crawl-delay` y `Request-rate`
- User-Agent identificado con URL de contacto y página `/bot` con opt-out
- Token bucket por dominio: ~0.4 req/s con jitter, concurrencia 1
- Circuit breaker: 3 fallos → 6h de pausa
- **Tiers de permiso P0–P4**: las tiendas P2 (ToS restrictivo) y P3 (requiere login o anti-bot activo) **no se consultan**; se declaran o se licencian
- Prohibición explícita de evasión anti-bot en código propio, con regla de linter en CI (ver ADR-003 de `SHELF_RADAR_ARQUITECTURA.md`)

---

## 6. Almacenes

```
snapshot datasets/2026-08/     OFF subset + USDA · ficha técnica
  (local, DuckDB + bge-m3)     corpus regulatorio mínimo (eCFR + DIGESA)
                               version_taxonomia = 0.1

shelf_facts ★ NUEVO            serie diaria de precios · 67 tiendas
                               particionado por mes · raw_offers inmutable
                               sweep_attempts: 1 fila por tienda, SIEMPRE

catalogo_comercial ★           ProductoEnMercado con fuente + url + fecha
                               N1/N2 entran directo · N3 solo si fue promovido

staging_agente                 provenance = agente · no_verificado · TTL
                               grounding check + promoción manual

PostgreSQL (Supabase)          RLS 2 organizaciones · historial · auditoría DAG
                               cache LLM · cola procrastinate (1 worker)
                               cost-meter por etapa y tenant
                               pgvector: gate de categoría
```

### 6.1 Tablas nuevas de v2

```sql
-- inmutable, con checksum: la evidencia
CREATE TABLE raw_offers (
    offer_id    UUID NOT NULL DEFAULT gen_random_uuid(),
    sweep_id    UUID NOT NULL,
    store_id    TEXT NOT NULL,
    source_url  TEXT NOT NULL,
    payload     JSONB NOT NULL,
    checksum    CHAR(64) NOT NULL,
    transport   TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (offer_id, captured_at)
) PARTITION BY RANGE (captured_at);

-- una fila por (barrido, tienda) SIEMPRE, incluso si falló o no se intentó
CREATE TABLE sweep_attempts (
    sweep_id     UUID NOT NULL,
    store_id     TEXT NOT NULL,
    status       TEXT NOT NULL,   -- ok | failed | blocked_policy | blocked_server
                                  -- | blocked_robots | skipped_budget
                                  -- | circuit_open | deferred | out_of_scope
    transport    TEXT,
    offers_found INT NOT NULL DEFAULT 0,
    cost_usd     NUMERIC(10,6) NOT NULL DEFAULT 0,
    error_reason TEXT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (sweep_id, store_id)
);
```

El esquema completo (stores, shelf_facts, fx_rates, category_centroids, vistas materializadas) está en `SHELF_RADAR_ARQUITECTURA.md` §10.

### 6.2 Cobertura declarada

Se calcula por SQL directo sobre `sweep_attempts` — por eso la fila garantizada:

```json
"coverage": {
  "in_scope": 53, "verified": 39, "blocked": 9,
  "skipped_budget": 3, "failed": 2,
  "coverage_pct": 73.6, "publishable": true,
  "note": "Kroger, Instacart y Amazon requieren licencia; no se consultaron."
}
```

`publishable = false` si `coverage_pct < 60`, y el informe lo dice en la portada.

---

## 7. Fuentes

| Fuente | Rol en v2 | Licencia | Alimenta |
|---|---|---|---|
| **Open Food Facts** (subset) | **ficha técnica + llave EAN** — ingredientes, alérgenos, nutrición, NOVA, Nutri-Score | ODbL | 2a, 4, MIM |
| **USDA Branded** ✓API | composición + marca · tapa el hueco de OFF en LATAM | CC0 | 2a, 4 |
| **Shelf Radar** ★ NUEVO | precio real, stock, promoción · 67 ecommerces, 29 países | conectores propios | 2b (N1/N2), MIM |
| **UN Comtrade** | precio de exportación US$/kg · flujos y socios por HS | abierta | 3, informe |
| **Corpus regulatorio** | eCFR (aditivos del piloto) + 2-3 normas DIGESA (OCR) | pública | 5 |
| **Fichas CITE + taxonomía v0.1** | know-how agroindustrial · insumos de Chavimochic | propia | 4, MIM |
| **Agente live** | solo huecos · on-demand · premium · presupuestado | — | 2b (N3) |

### 7.1 El cambio de rol de Open Food Facts

En v1, OFF hacía dos trabajos: ficha técnica **y** proxy de mercado (el bloque de tendencias del MIM decía explícitamente *"metodología declarada (proxy OFF)"*). El segundo trabajo lo hacía mal, y v1 era honesto al declararlo.

En v2, OFF **se queda** pero pierde el segundo trabajo. Su valor real es insustituible en tres cosas que las 67 tiendas no dan:

1. **Ingredientes parseados** en múltiples idiomas, con alérgenos marcados. El retail casi nunca publica la lista de ingredientes en forma estructurada; cuando la publica, suele estar en una imagen.
2. **Nutrición por 100g + NOVA + Nutri-Score + Eco-Score.** Clasificaciones ya calculadas que de otro modo habría que construir.
3. **La llave EAN/GTIN.** Es su clave primaria. Sin ella no se puede afirmar que el producto visto en Plaza Vea es el mismo que en EDEKA.

**Salidas eliminadas:** Open Prices deja de ser fuente propia — su dato de precio retail es escaso y colaborativo, y `shelf_facts` lo reemplaza con dato real de góndola. Comtrade se queda solo con lo que sí aporta: el precio de exportación.

**Cuidados con OFF:**

- **Cobertura sesgada.** Excelente en Francia y Europa, débil en Perú y LATAM. Para producto peruano hay huecos grandes que tapan USDA Branded (CC0) y las fichas CITE.
- **ODbL tiene share-alike sobre bases de datos derivadas, no sobre obras producidas.** Traducido: vender informes PDF o decks derivados de OFF requiere solo atribución. Distribuir o vender una **base de datos** que incorpore OFF obliga a publicarla también bajo ODbL. Como el producto son informes y fichas, la operación está del lado seguro — pero si un cliente enterprise pide "danos el dataset", la cláusula aplica y hay que decirlo antes de firmar.

---

## 8. MIM — inteligencia de mercado

Sin cambios estructurales: taxonomía CITE v0.1 → tendencias (DuckDB, determinista, sin LLM) → reportes (deck PPT + ficha ProductoEnMercado, misma estructura de campos que Mintel, diseño propio).

### 8.1 Migración de la serie de tendencias

El punto más importante de planificación de todo v2.

El MIM exige **≥8 trimestres de histórico**. Hoy ese histórico viene de OFF, con la metodología declarada como proxy. Shelf Radar arranca su serie **en cero** y tarda dos años en acumular 8 trimestres.

```
2026  ──────────────────────────────────────────────►  2028
      OFF sostiene las tendencias (proxy declarado)
      ├── Shelf Radar captura en paralelo (sin usarse aún)
      │
      └────────────────────────► Shelf Radar toma el relevo
                                 (dato real de góndola)
```

**Consecuencia operativa: la captura diaria de Shelf Radar empieza YA, aunque todavía no se use para tendencias.** El histórico no se compra retroactivamente. Cada semana que se posterga el barrido es una semana que falta en 2028.

Durante la transición, ambas series conviven y cada informe declara cuál usó.

---

## 9. Plan de pruebas de punta a punta

Criterio: **15/15 en verde**. CI previa: golden set ~30 productos + validación de schema + smoke test del DAG.

| # | Prueba |
|---|---|
| P01 | RLS + entitlement: cada organización ve solo lo suyo |
| P02 | InterpretarInsumo + cache hit (2ª llamada = costo $0) |
| P03 | Match local sin LLM · p95 < 2 s |
| P04 | Mapa comercial N1 · campos sin dato = `null`, jamás inventados |
| P05 | Insight: cada afirmación con cita a un dato entregado |
| P06 | Paywall: early return con informe parcial (≠ guard 0-2 productos) |
| P07 | Formulación premium: minería DuckDB + glm-5.2, refs reales |
| P08 | Regulación: citas verificables al corpus · si no hay norma, lo declara |
| P09 | InformeScout PDF por worker + auditoría DAG con costo por etapa |
| P10 | MIM: ETL → taxonomía v0.1 → tendencias → deck PPT + ficha PDF |
| P11 | Agente → cuarentena → grounding check → promoción manual → catálogo |
| P12 | Presupuestos run/tenant/global + kill-switch → degrada, nunca error |
| P13 | Cost-meter por tenant: ~US$0.01-0.05/consulta · agente ≤ US$0.25/run |
| **P14** | **Shelf Radar: cobertura declarada — 1 fila por tienda aunque falle o esté vedada** |
| **P15** | **Gate de categoría (pgvector): buscar quinua en droguería devuelve 0, no cosméticos** |

Guion de demo (15 min): ver `MVP-AgroScout-IA.md` §5.

---

## 10. ADR-004 — Shelf Radar como N1+N2 del puerto

**Contexto.** v1 declaró el `Puerto DescubrimientoComercial` con una cascada de tres niveles, pero solo N3 (el agente) estaba implementado de verdad. N1 era un snapshot congelado y N2 un stub. En la práctica, toda consulta que necesitaba dato comercial fresco terminaba en el agente, a US$0.25 por corrida.

**Decisión.** Implementar N1 y N2 con conectores deterministas sobre las 67 tiendas del registry (`tiendas.xlsx`), **sin modificar el contrato del puerto ni el DAG**.

**Consecuencias positivas:**

- El costo del dato comercial baja tres órdenes de magnitud en el caso mayoritario.
- El presupuesto del agente queda para lo que solo el agente puede hacer.
- Se obtiene serie temporal propia de precios, que es el activo que ninguna fuente pública da y que el MIM necesitará en 2028.
- El dato de conectores es verificable por checksum, lo que refuerza la promesa de trazabilidad.

**Consecuencias negativas y mitigaciones:**

- **Mantenimiento de adaptadores.** Mitigado con adaptadores por plataforma (6 para 67 tiendas) y canario diario.
- **Riesgo de bloqueo.** Mitigado con tiers de permiso P0–P4, cortesía estricta y prohibición de evasión por regla de CI. Lo que no se puede obtener legítimamente se declara no cubierto.
- **Cero histórico al inicio.** Mitigado manteniendo OFF como fuente de tendencias hasta 2028 y arrancando la captura de inmediato.

**Alternativas descartadas:**

- *Extender Bright Data a las 67 tiendas.* ~US$24.000/año en barrido diario contra ~US$800 del híbrido. Se usa quirúrgicamente en 5 tiendas.
- *Usar solo el agente.* Insostenible con los topes de presupuesto y sin trazabilidad determinista.
- *Eliminar Open Food Facts.* Se pierde la llave EAN, los ingredientes parseados y el histórico de tendencias. Ver §7.1.

**Relación con ADRs previos.** No modifica ADR-002 ni ADR-003: Mintel y Trend Hunter siguen sin consumirse, y v2 sigue siendo fase 1 con datos reducidos — solo que ahora los datos reducidos incluyen góndola real.

---

## 11. Roadmap

| Fase | Alcance | Días |
|---|---|---|
| 0 | Limpieza del registry: ISO-2, `permission_tier` leyendo robots.txt real, marcar los 6 no-ecommerce | 2 |
| 1 | Postgres + `PoliteTransport` + fingerprinting de las 67 tiendas | 4 |
| **2** | **VTEX + Shopify (~30 tiendas) → N1 operativo** | **5** |
| 3 | Resolución de entidad: unidades, FX, gate de categoría, dedup | 5 |
| 4 | Cobertura declarada + integración con etapa 2b + P14/P15 en verde | 4 |
| 5 | JSON-LD (~42 tiendas) · cobertura Europa | 4 |
| 6 | Scrapling (~54 tiendas) · cobertura UK/Asia | 8 |
| 7 | Bright Data (5) → N2 operativo + scheduler diario | 5 |

**Camino crítico: fases 0→2.** En dos semanas, 30 tiendas devolviendo precio real con costo variable prácticamente cero, alimentando la etapa 2b sin tocar el DAG.

**Diferido a fase 2/3** (heredado de v1, actualizado):

- LB + 2-3 réplicas API (MVP: 1 nodo)
- Object storage (S3/R2) + CDN (MVP: snapshot local)
- mistral-embed (MVP: bge-m3 CPU)
- Ingesta regulatoria completa: eCFR completo · EFSA · Codex · INACAL
- Alertas y retiros: openFDA `food/enforcement` (US) + RASFF (UE) — señal de riesgo de exportación, distinta de la norma
- Shelf Radar tiers C/D en producción: Scrapling + Bright Data de pago
- Promoción con muestreo sistemático (MVP: manual)

---

## 12. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Adaptador roto por rediseño de tienda | pérdida silenciosa de cobertura | canario diario con aserciones + `sweep_attempts` visible |
| Bloqueo por comportamiento | tienda cae del scope | rate limit conservador, UA identificado, circuit breaker |
| Bloqueo por política (ToS) | no se puede scrapear | tier P2/P3 → no se consulta; se declara o se licencia |
| Sesgo de cobertura (solo se mide donde es fácil) | conclusiones torcidas | `coverage_pct` por país; nunca promediar países con cobertura desigual |
| Gate de categoría mal calibrado | ruido en el catálogo | métrica `gate_discarded_total` vigilada; golden set en CI |
| ODbL de OFF | restricción al distribuir dataset | vender obras producidas (informes), no bases de datos |
| Cero histórico de Shelf Radar hasta 2028 | MIM sin base propia | OFF sostiene tendencias; captura arranca ya |

---

## Anexo A — Registry de tiendas

67 tiendas · 29 países · fuente `tiendas.xlsx`

| Bloque | Tiendas |
|---|---|
| Perú | 15 |
| Alemania · Estados Unidos | 6 c/u |
| China · Francia · India · Japón · Suiza | 3 c/u |
| Chile · Corea del Sur · EAU · Reino Unido | 2 c/u |
| Resto (17 países) | 1 c/u |

**Correcciones aplicadas al registry:** Ahold Delhaize (holding → `ah.nl`/`bol.com`), Made-in-China (B2B industrial → excluida), Foodstuffs (corporativa → `newworld.co.nz`/`paknsave.co.nz`), Carrefour (landing global → `carrefour.fr`/`carrefour.es`), Rappn (agregador → solo validación cruzada). Amazon, Rakuten, Lazada, Tokopedia, Naver, Meituan e Instacart se marcan `store_class = marketplace` y **nunca se promedian con retailers**: dan señal de demanda y competencia de cola larga, no de decisión de surtido.

## Anexo B — Documentos relacionados

| Documento | Contenido |
|---|---|
| `SHELF_RADAR_ARQUITECTURA.md` | detalle técnico del barrido: httpx, adaptadores, DDL completo, ADR-001 a ADR-006 |
| `Arquitectura_AgroScout_IA_MVP_v2_ShelfRadar.svg` | diagrama de esta arquitectura |
| `shelf-radar-arquitectura.svg` | diagrama de capas de Shelf Radar aislado |
| `MVP-AgroScout-IA.md` | guion de demo (§5) |
| `tiendas.xlsx` | registry semilla de las 67 tiendas |
