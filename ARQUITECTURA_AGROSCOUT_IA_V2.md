# AgroScout IA — Arquitectura v2.1

**Shelf Radar como N1+N2 del puerto DescubrimientoComercial · tabla precalculada como N1+N2 del puerto AutorizaciónAditivo**

| | |
|---|---|
| Versión | 2.1 |
| Fecha | 2026-08-24 |
| Base | v2 (2026-08-08) · ADR-004 · a su vez sobre v1 (walking skeleton, ADR-003 fase 1) |
| Cliente | CITEagroindustrial Chavimochic |
| Diagrama | `Arquitectura_AgroScout_IA_MVP_v2_ShelfRadar.svg` |
| Documento hermano | `SHELF_RADAR_ARQUITECTURA.md` (detalle técnico del barrido) |

---

## 1. Qué cambia en v2 y en v2.1 — y qué no

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

### 1.1 Qué añade v2.1

**El mismo movimiento, en la otra dimensión.** v2 lo hizo con el dato comercial;
v2.1 lo hace con el dato regulatorio, y por la misma razón: había un agente LLM
resolviendo en 36 segundos una pregunta cuyo universo de respuestas cabe en una
tabla de tres mil filas.

| Componente | v2 | v2.1 |
|---|---|---|
| Autorización de aditivos · **UE** | Anexo II en fichero local · < 8 ms | igual, promovido a `aditivo_mercado` |
| Autorización de aditivos · **CODEX** | tabla GSFA curada · < 1 ms | igual, promovido a `aditivo_mercado` |
| Autorización de aditivos · **US** | **agente en vivo · 15-36 s · 1-3 llamadas al modelo** | **tabla precalculada** · agente solo para huecos |
| Sección del 21 CFR aplicable | se redescubre en cada consulta, hasta 3 candidatas | `aditivo_seccion_us` · 35 filas curadas |
| Persistencia del veredicto | caché de LLM opaca, TTL 90 días | tabla consultable, auditable y corregible a mano |
| Pruebas | P01–P15 | P01–**P17** |

Lo que **no** cambia: el DAG, los contratos, el paywall, la escalera de
procedencia, el modelo de suscripción y la implementación del agente del eCFR.
El agente sigue existiendo y sigue siendo el que cierra los huecos — solo deja
de ser el primer recurso para ser el último. Detalle en §6, decisión en §12.

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

## 6. Puerto AutorizaciónAditivo ★ NUEVO en v2.1

La segunda mitad de la tesis de v2, aplicada al dato regulatorio. ADR-004 quitó
al agente comercial el trabajo que un conector determinista hace mil veces más
barato; **ADR-005 (§12) hace lo mismo con el agente regulatorio.**

El puerto responde a una pregunta muy concreta —*¿está autorizado este aditivo,
en esta matriz alimentaria, en este mercado?*— y devuelve una `EvaluacionMercado`
con veredicto, límite, cita literal y URL oficial. No se confunde con el
`VerificadorRegulatorio` de la etapa 5, que produce un dossier por insumo (§6.6).

### 6.1 El problema, medido

La pestaña de análisis de aditivos consulta tres mercados, y **los tres no se
parecen en nada**:

| Mercado | Mecanismo en v2 | Latencia | Coste |
|---|---|---|---|
| **UE** | Anexo II ingerido en local (321 pares número→nombre) | < 8 ms | US$0 |
| **CODEX** | tabla GSFA curada a mano | < 1 ms | US$0 |
| **US** | **agente en vivo contra el eCFR** · búsqueda + `glm-5.2` | **15–36 s** | 1–3 llamadas al modelo |

Es decir: dos de los tres mercados ya son lo que este puerto propone —una tabla
consultada por clave exacta— y el tercero es un agente. La ineficiencia no está
repartida: está entera en una columna.

Y se paga por celda, no por producto. Un producto lleva **mediana de 2 aditivos
y hasta 9**, así que la pestaña ya evalúa todos en paralelo para que el producto
cueste lo que su aditivo más lento. Eso acota la espera, no el gasto.

### 6.2 La cascada

Misma forma que la del puerto comercial. El agente deja de ser el primer
recurso y pasa a ser el último.

```
                    ¿aditivo + matriz + mercado?
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
   N1 · tabla             N2 · sección              N3 · Agente eCFR
   aditivo_mercado        aditivo_seccion_us        búsqueda en vivo
   veredicto precalculado 35 filas curadas          + glm-5.2 + grounding
   UE · CODEX · US        aditivo → § 21 CFR        solo huecos de N1/N2
   < 8 ms · US$0          evita el bucle de 3       15-36 s · 1 llamada
        │                      │                           │
        └──────────┬───────────┘                           ▼
                   ▼                                  se persiste en N1
            se sirve directo                          tras pasar grounding
```

**N1 · `aditivo_mercado`.** El veredicto ya calculado, con su cita y su URL. Es
donde la UE y el Codex viven hoy de hecho, solo que en fichero; US se suma.

**N2 · `aditivo_seccion_us`.** El mapa curado de aditivo → sección del 21 CFR.
Hoy esa sección se redescubre en cada consulta y el agente prueba **hasta 3
candidatas, cada una con su llamada al modelo** (`MAX_CANDIDATAS`). Con el mapa
curado el peor caso baja de 3 llamadas a 1. Son 35 filas, revisables a ojo, y lo
más estable del sistema: §172.120 no cambia de número.

**N3 · Agente eCFR.** Sin cambios en su implementación —búsqueda en vivo,
lectura con `glm-5.2`, `grounding()` obligatorio, el veredicto lo decide el
código y no el modelo—. Lo que cambia es **cuándo se invoca**: solo para lo que
no está en tabla, y su resultado se escribe en N1 en vez de evaporarse.

### 6.3 Por qué relacional y no vectorial

La pregunta que motivó esta sección. La respuesta es **relacional**, y no por
rendimiento:

La clave de consulta es un **código exacto** —número E/INS más categoría de
alimento—, no un texto parecido a otro. Una búsqueda por similitud siempre
devuelve *lo más cercano*, y en una tabla regulatoria el aditivo más cercano a
E200 es una respuesta equivocada que se ve bien. Eso choca de frente con el
principio 1: campo sin dato es `null`, nunca un valor plausible.

`EvaluadorUE` y `EvaluadorCodex` ya lo demuestran: consultan por clave exacta,
responden en microsegundos y **no pueden equivocarse de aditivo**. La propuesta
es extender esa propiedad a la tercera columna, no sustituirla por otra cosa.

### 6.4 El espacio de claves cabe entero en una tabla

El dato que cierra la decisión: **el universo es finito y pequeño**, y ya está
acotado por el código actual.

| Dimensión | Cardinalidad | Dónde |
|---|---|---|
| Aditivos con término de búsqueda en inglés | **35** | `TERMINO_EN` |
| Términos de alimento en inglés | **95** | `MAPA` (113 entradas) |
| Códigos del Anexo II derivados | 58 | `MAPA` |

Techo absoluto: **35 × 95 ≈ 3.325 celdas**. Y un aditivo que no está en
`TERMINO_EN` ya devuelve `SIN_DATO` sin consultar nada, así que el techo es real,
no una estimación.

En la práctica es bastante menos, por una propiedad que el propio agente ya
distingue: cuando la sección da cobertura `GENERAL` —GRAS por buenas prácticas,
sin lista de alimentos— **el veredicto no depende del alimento**. Es el caso del
ácido sórbico. Para esos aditivos basta **una fila con `categoria = NULL`**, no
95. Solo los que traen tabla de alimentos —el EDTA de §172.120, con su fila
"Cucumbers pickled 220"— necesitan la dimensión de categoría.

Consecuencia operativa: el llenado es un **job por lotes**, no trabajo por
petición. Se corre una vez, con el mismo `grounding()` que ya está escrito, y lo
que no pase el grounding **queda como hueco declarado** en vez de publicarse a
medias. Es el principio 6 de v2 aplicado al corpus regulatorio.

### 6.5 Dónde sí entra lo vectorial

En el otro extremo del problema, y ahí sí hace falta.

`mapear_categoria` traduce el texto libre de OpenFoodFacts a una categoría del
Anexo II. `MAPA` cubre 113 segmentos contra **8.322 valores distintos** de
categoría en el snapshot, con un techo declarado del **79,5 %** (§4.1 y el
módulo). Resolver por similitud contra los 58 códigos del Anexo II sube esa
cobertura, y encaja con el `pgvector` que ya está previsto para el gate de
categoría [P15].

Con una condición que el código ya sabe imponer: una categoría resuelta por
similitud es **deducida**, y `_con_asterisco` degrada cualquier `SI` limpio a
`SI_CONDICIONADO`. **El vector ayuda a encontrar la fila; nunca produce el
veredicto.** Es la misma frontera que separa a `_leer()` de `_veredicto()` en el
agente: el modelo lee, el código decide.

### 6.6 Coexistencia con la etapa 5 — decisión abierta

Hay que declararlo porque hoy conviven dos caminos regulatorios:

| | Etapa 5 · `VerificacionRegulatoria` | Pestaña de aditivos · este puerto |
|---|---|---|
| Pregunta | dossier regulatorio de un **insumo** | autorización de un **aditivo en una matriz** |
| Almacén | `regulacion_cita`, `mapping_regulaciones` | `aditivo_mercado`, `aditivo_seccion_us` |
| Origen | corpus ingerido (migración 006) | corpus local + agente en vivo |
| Entrada | DAG, etapa 5, premium | producto del mapa comercial (etapa 2b) |

`mapping_regulaciones` es casi la tabla que describe §7.1, pero le falta la
dimensión que aquí manda: **la categoría de alimento**. Mapea *ingrediente →
norma*; este puerto necesita *(aditivo, mercado, categoría) → veredicto*, que es
otra granularidad.

**Recomendación:** tabla nueva y estrecha, no una vista sobre el esquema de la
migración 006. Forzar las dos preguntas a la misma tabla mezcla dos
granularidades y obliga a que una de las dos consulte con comodines. Unificarlas
es trabajo de fase 2, cuando el corpus de la etapa 5 esté completo.

---

## 7. Almacenes

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

aditivo_mercado ★ NUEVO v2.1   veredicto por (aditivo, mercado, categoría)
                               cita literal + URL oficial + verificado_en
                               categoria NULL = cobertura GENERAL, vale para todo

aditivo_seccion_us ★ NUEVO     35 filas: aditivo → sección del 21 CFR
                               curada a mano · evita el bucle de 3 candidatas

PostgreSQL (Supabase)          RLS 2 organizaciones · historial · auditoría DAG
                               cache LLM · cola procrastinate (1 worker)
                               cost-meter por etapa y tenant
                               pgvector: gate de categoría
```

### 7.1 Tablas nuevas de v2 (Shelf Radar)

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

### 7.2 Tablas nuevas de v2.1 (AutorizaciónAditivo)

Los campos de `aditivo_mercado` son **los de `EvaluacionMercado`**, el tipo que
ya devuelve el analizador. No es casualidad ni comodidad: significa que el
adaptador nuevo entra como un evaluador más delante del agente y **no obliga a
tocar `AnalizadorAditivos`**.

```sql
-- N2: qué sección del 21 CFR responde por cada aditivo. 35 filas, curadas.
-- Es lo más estable del sistema: §172.120 no cambia de número.
CREATE TABLE aditivo_seccion_us (
    e_number     TEXT PRIMARY KEY,          -- E200, E385...
    termino_en   TEXT NOT NULL,             -- 'sorbic acid' (hoy en TERMINO_EN)
    seccion_cfr  TEXT NOT NULL,             -- '182.3089'
    url_oficial  TEXT NOT NULL,
    cobertura    TEXT NOT NULL,             -- GENERAL | LISTA_ALIMENTOS
    curado_por   TEXT,                      -- NULL = lo propuso el agente
    verificado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- N1: el veredicto ya calculado. categoria_ue NULL = cobertura GENERAL,
-- es decir, el veredicto NO depende del alimento (caso del ácido sórbico).
CREATE TABLE aditivo_mercado (
    e_number        TEXT NOT NULL,
    mercado         TEXT NOT NULL,          -- US | EU | CODEX
    categoria_ue    TEXT,                   -- '04.1.2.8' · NULL = vale para toda matriz
    autorizado      TEXT NOT NULL,          -- SI | SI_CONDICIONADO | NO | NO_CONDICIONADO
    limite_valor    NUMERIC,                -- NULL = sin cifra, NO 'sin límite'
    limite_unidad   TEXT,                   -- mg/kg | ppm | BPM | N/A
    categoria_alimento TEXT,                -- 'Cucumbers pickled', tal cual en la norma
    referencia_texto TEXT NOT NULL,         -- '21 CFR § 172.120' · lo pone el código
    referencia_url  TEXT NOT NULL,          -- sin URL no se pinta veredicto
    cita_literal    TEXT NOT NULL,          -- vacío solo si autorizado = SIN_DATO
    origen          TEXT NOT NULL,          -- AGENTE_ECFR | ANEXO_II | CURADO_CODEX
    verificado_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    validado_por    TEXT,                   -- especialista del CITE que la revisó
    nota            TEXT,
    PRIMARY KEY (e_number, mercado, categoria_ue)
);

CREATE INDEX idx_aditivo_mercado_lookup ON aditivo_mercado (e_number, mercado);
```

Dos cosas que la tabla hace y la caché de LLM no:

- **Se puede listar y auditar.** «Todos los aditivos con veredicto `NO` en US» es
  una consulta; contra un blob JSON en `cache_llm` no lo es.
- **Se puede corregir a mano.** `validado_por` guarda quién revisó la celda, y una
  corrección del especialista del CITE **sobrevive al TTL** en vez de perderse a
  los 90 días.

`SIN_DATO` no se persiste, por la misma razón por la que hoy no se cachea: casi
siempre viene de un timeout o un fallo de red, y guardarlo convertiría un
tropiezo de un minuto en una celda vacía durante un trimestre.

### 7.3 Cobertura declarada

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

## 8. Fuentes

| Fuente | Rol en v2 / v2.1 | Licencia | Alimenta |
|---|---|---|---|
| **Open Food Facts** (subset) | **ficha técnica + llave EAN** — ingredientes, alérgenos, nutrición, NOVA, Nutri-Score | ODbL | 2a, 4, MIM |
| **USDA Branded** ✓API | composición + marca · tapa el hueco de OFF en LATAM | CC0 | 2a, 4 |
| **Shelf Radar** ★ NUEVO | precio real, stock, promoción · 67 ecommerces, 29 países | conectores propios | 2b (N1/N2), MIM |
| **UN Comtrade** | precio de exportación US$/kg · flujos y socios por HS | abierta | 3, informe |
| **Corpus regulatorio** | eCFR (aditivos del piloto) + 2-3 normas DIGESA (OCR) | pública | 5 |
| **eCFR título 21** ★ | 8.406 secciones desde bulkdata del GPO · el texto en local, el ranking en vivo | pública (federal US) | AutorizaciónAditivo N2/N3 |
| **Anexo II · Reg. (CE) 1333/2008** ★ | 321 pares número→nombre + categorías de alimento de la UE | pública | AutorizaciónAditivo N1 (UE) |
| **GSFA / Codex** ★ | tabla curada a mano · hoy mayoritariamente PENDIENTE | pública (FAO) | AutorizaciónAditivo N1 (CODEX) |
| **Fichas CITE + taxonomía v0.1** | know-how agroindustrial · insumos de Chavimochic | propia | 4, MIM |
| **Agente live** | solo huecos · on-demand · premium · presupuestado | — | 2b (N3) |

### 8.1 El cambio de rol de Open Food Facts

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

## 9. MIM — inteligencia de mercado

Sin cambios estructurales: taxonomía CITE v0.1 → tendencias (DuckDB, determinista, sin LLM) → reportes (deck PPT + ficha ProductoEnMercado, misma estructura de campos que Mintel, diseño propio).

### 9.1 Migración de la serie de tendencias

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

## 10. Plan de pruebas de punta a punta

Criterio: **17/17 en verde**. CI previa: golden set ~30 productos + validación de schema + smoke test del DAG.

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
| **P16** | **AutorizaciónAditivo N1: una celda servida de tabla es idéntica a la del agente, en < 50 ms y con 0 llamadas al modelo** |
| **P17** | **Un aditivo fuera de tabla cae a N3, pasa grounding y se persiste; si el grounding falla NO se persiste nada** |

Guion de demo (15 min): ver `MVP-AgroScout-IA.md` §5.

---

## 11. ADR-004 — Shelf Radar como N1+N2 del puerto comercial

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
- *Eliminar Open Food Facts.* Se pierde la llave EAN, los ingredientes parseados y el histórico de tendencias. Ver §8.1.

**Relación con ADRs previos.** No modifica ADR-002 ni ADR-003: Mintel y Trend Hunter siguen sin consumirse, y v2 sigue siendo fase 1 con datos reducidos — solo que ahora los datos reducidos incluyen góndola real.

---

## 12. ADR-005 — Tabla precalculada como N1+N2 del puerto AutorizaciónAditivo

**Contexto.** La pestaña de análisis de aditivos consulta tres mercados. La UE
(Anexo II, < 8 ms) y el Codex (tabla curada, < 1 ms) son diccionarios locales
consultados por clave exacta. **Estados Unidos no**: cada celda dispara una
búsqueda en vivo contra el eCFR y **hasta tres lecturas con `glm-5.2`**, medidas
en 15–36 s con p95 ≈ 36 s.

Existe una caché (`cache_llm`, clave `ecfr:{término}|{categoría}`, TTL 90 días),
pero no hace el trabajo de una base de datos: es **fría** —la primera consulta
de cada celda paga los 36 s—, **opaca** —un blob JSON que no se puede listar ni
filtrar— y **no admite curaduría**: una corrección del especialista del CITE se
pierde al vencer el TTL. En `agroscout.db` no hay hoy ninguna entrada con
prefijo `ecfr:`.

**Decisión.** Introducir el puerto `AutorizaciónAditivo` con cascada de tres
niveles, **sin modificar `AnalizadorAditivos` ni el tipo `EvaluacionMercado`**:

- **N1 `aditivo_mercado`** — el veredicto precalculado, por clave exacta.
- **N2 `aditivo_seccion_us`** — el mapa curado aditivo → sección del 21 CFR.
- **N3 el agente del eCFR** — sin cambios, solo para huecos, y su resultado se
  persiste en N1 tras pasar el grounding.

El almacén es **relacional, no vectorial**.

**Por qué relacional.** La clave es un código exacto —número E/INS más categoría
de alimento—, no un texto parecido a otro. Una búsqueda por similitud devuelve
siempre *lo más cercano*, y en una tabla regulatoria el aditivo más cercano a
E200 es una respuesta equivocada con buena pinta. Eso contradice el principio 1
(*nada se inventa*). Lo vectorial entra donde el problema **sí** es de
similitud: mapear las 8.322 categorías de OFF a las 58 del Anexo II (§6.5), y
solo produciendo categorías marcadas como deducidas, que degradan el veredicto a
`SI_CONDICIONADO`.

**Por qué es viable precalcularlo.** El universo está acotado por el propio
código: **35 aditivos** con término de búsqueda (`TERMINO_EN`) × **95 términos
de alimento** (`MAPA`) = **≤ 3.325 celdas**, y un aditivo fuera de `TERMINO_EN`
ya devuelve `SIN_DATO` sin consultar. Además, las secciones de cobertura
`GENERAL` —GRAS por buenas prácticas, sin lista de alimentos— dan un veredicto
que **no depende del alimento**: una fila con `categoria_ue = NULL` en vez de 95.

**Consecuencias positivas:**

- La columna de EE. UU. pasa de 15–36 s a la latencia de las otras dos.
- El coste de la pestaña deja de ser proporcional al uso: es un lote que se corre
  una vez y se reingesta cuando cambia la norma.
- Aparece un lugar donde el especialista del CITE **puede corregir una celda** y
  que la corrección persista, con `validado_por` como trazabilidad.
- El corpus regulatorio se vuelve consultable: «todos los aditivos con veredicto
  `NO` en US» pasa a ser una consulta SQL.
- Curar N2 recorta el peor caso del agente de 3 llamadas al modelo a 1, incluso
  para lo que nunca llegue a precalcularse.

**Consecuencias negativas y mitigaciones:**

- **La norma cambia y la tabla no se entera.** Es el modo de fallo serio, y el
  mismo que ADR-004 resuelve con el canario: reingesta periódica del título 21
  desde bulkdata comparando `content_hash`, y `verificado_en` visible en la
  tarjeta. Una celda vieja se enseña con su fecha, no se esconde.
- **Coste inicial del lote.** Acotado y conocido: ≤ 3.325 lecturas, bastantes
  menos con el colapso de `GENERAL`. Se corre por aditivo, no de una vez.
- **Dos caminos regulatorios conviviendo** con la etapa 5 (§6.6). Se declara como
  decisión abierta en vez de forzar una unificación prematura.

**Alternativas descartadas:**

- *Subir el TTL de la caché de LLM.* No arregla el arranque en frío, no permite
  listar ni corregir, y una caché con TTL de un año es una tabla mal hecha.
- *Un índice vectorial sobre el corpus del eCFR.* Ya existe `vectores/regulatorio.lance`
  y su límite está documentado: el corpus RAG de 734 pasajes **no tenía la parte
  172**, que es justo donde está §172.120. Recuperar por similitud sobre texto
  normativo devuelve secciones plausibles, no la aplicable.
- *Dejar que el agente resuelva siempre y presupuestarlo.* Es lo que ADR-004 ya
  descartó para el dato comercial, por las mismas razones: insostenible con los
  topes y sin trazabilidad determinista.

**Relación con ADRs previos.** Extiende ADR-004 a la dimensión regulatoria y no
modifica ninguno anterior. El principio 5 de v2 —*la confianza del dato depende
de su origen, no de su forma*— es el que autoriza que una fila de tabla curada y
una lectura del agente convivan en la misma pantalla con distinto `origen`.

---

## 13. Roadmap

### 13.1 Shelf Radar (v2)

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

### 13.2 AutorizaciónAditivo (v2.1)

Pista independiente: no comparte código con Shelf Radar y puede correr en
paralelo.

| Fase | Alcance | Días |
|---|---|---|
| **R0** | **`aditivo_seccion_us`: las 35 secciones, curadas y revisadas a ojo** | **1** |
| R1 | DDL de `aditivo_mercado` + adaptador N1 delante del agente (no toca `AnalizadorAditivos`) | 2 |
| R2 | Volcado de UE y CODEX a la tabla · P16 en verde | 1 |
| R3 | Job por lotes de US: el agente llena N1 con grounding · P17 en verde | 3 |
| R4 | Canario de reingesta del título 21 + `verificado_en` visible en la tarjeta | 2 |
| R5 | Gate vectorial de categoría sobre los 58 códigos del Anexo II (§6.5) | 3 |

**Camino crítico: R0→R2.** R0 solo es un día y ya recorta el peor caso del
agente de 3 llamadas al modelo a 1, sin esperar a nada más. Con R2 cerrado, dos
de los tres mercados se sirven de tabla y la pestaña deja de depender de la red
para dos tercios de cada fila.

**Diferido a fase 2/3** (heredado de v1, actualizado):

- LB + 2-3 réplicas API (MVP: 1 nodo)
- Object storage (S3/R2) + CDN (MVP: snapshot local)
- mistral-embed (MVP: bge-m3 CPU)
- Ingesta regulatoria completa: eCFR completo · EFSA · Codex · INACAL
- Alertas y retiros: openFDA `food/enforcement` (US) + RASFF (UE) — señal de riesgo de exportación, distinta de la norma
- Shelf Radar tiers C/D en producción: Scrapling + Bright Data de pago
- Promoción con muestreo sistemático (MVP: manual)

---

## 14. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Adaptador roto por rediseño de tienda | pérdida silenciosa de cobertura | canario diario con aserciones + `sweep_attempts` visible |
| Bloqueo por comportamiento | tienda cae del scope | rate limit conservador, UA identificado, circuit breaker |
| Bloqueo por política (ToS) | no se puede scrapear | tier P2/P3 → no se consulta; se declara o se licencia |
| Sesgo de cobertura (solo se mide donde es fácil) | conclusiones torcidas | `coverage_pct` por país; nunca promediar países con cobertura desigual |
| Gate de categoría mal calibrado | ruido en el catálogo | métrica `gate_discarded_total` vigilada; golden set en CI |
| ODbL de OFF | restricción al distribuir dataset | vender obras producidas (informes), no bases de datos |
| Cero histórico de Shelf Radar hasta 2028 | MIM sin base propia | OFF sostiene tendencias; captura arranca ya |
| **Celda regulatoria obsoleta** (la FDA modifica el título 21 y la tabla no se entera) | se publica una autorización que ya no rige | reingesta periódica desde bulkdata comparando `content_hash`; `verificado_en` visible en la tarjeta |
| **Sección mal curada en `aditivo_seccion_us`** | veredicto sistemáticamente equivocado para ese aditivo | 35 filas revisables a ojo; el `grounding()` sigue corriendo sobre la sección curada, así que una sección que no menciona el aditivo no produce celda |
| **Precalcular oculta la incertidumbre** (una celda vieja parece tan firme como una fresca) | falsa confianza en la pantalla | `origen` y `verificado_en` van a la tarjeta; una celda curada a mano no se pinta igual que una traída del eCFR hace un minuto |
| **Categoría resuelta por vector** (§6.5) | `SI` apoyado en una categoría adivinada | `cat.deducida` degrada a `SI_CONDICIONADO` con la nota al pie; ya está en código |

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
