# Semana 4: Plan en TIERS — Mapa comercial, honestidad del dato y ensayo

**Fecha:** 2026-08-02 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)
**Modelo:** el mismo de S1, S2 y S3 — 7 tiers secuenciales con gate numérico
**Calendario nominal:** Lun 10 – Vie 14 de agosto 2026 · **≈36 h de código**
**Cierra:** la última semana del alcance comprometido (`PLAN-MVP-v2.md` §7). CDR el 2026-08-28.

**Estado previo:** S2 cerrada (29.054 productos, P03 verde) · S3 planificada en
[PLAN-TIERS-S3.md](PLAN-TIERS-S3.md) (Supabase, paywall, presupuestos, sin multi-tenant).

---

## 0. Lo que dice el snapshot hoy (medido, no supuesto)

La etapa 2b promete *"país · marca · presentación · rango de precio · canal · URL ·
fecha"*. Antes de diseñarla conviene mirar qué hay realmente en las 29.054 filas de
`datasets/2026-07/productos_merged.json`:

| Campo del mapa comercial | Cobertura real | Estado |
|---|---|---|
| `url` | **29.054 / 29.054 — 100 %** | ✅ listo |
| `fecha_dato` | **29.054 / 29.054 — 100 %** | ✅ listo |
| `nombre` | 29.054 — 100 % | ✅ listo |
| `marca` | **23.811 — 82,0 %** | ✅ usable, 18 % en `null` |
| `pais` | 28.927 — 99,6 % | ⚠️ **inservible tal cual** (ver abajo) |
| `categoria` | 24.020 — 82,7 % | ✅ |
| **`presentacion`** | **0 %** | ❌ no existe en el snapshot |
| **`precio`** | **0 %** | ❌ no existe en el snapshot |
| **`canal`** | **0 %** | ❌ no existe en el snapshot |

Tres hallazgos que mandan sobre el plan de la semana:

**1. El campo `pais` tiene 1.578 valores distintos** para lo que en realidad son ~100
países. Es la columna `countries` de OFF sin normalizar:

```
United States (9.986) · en:United States (1.633) · en:us (1.005)
United States, World (852) · en:united-states (785)   → los cinco son el mismo país
```

Un "mapa comercial por país" agrupando por esta columna produce basura en pantalla.
Normalizar a ISO-3166 es **T2.1** y es prerrequisito de la etapa 2b, no un pulido.
Hay además mojibake de codificación (`Espa�a`), que se ve en la demo.

**2. `presentacion`, `precio` y `canal` no están en el snapshot y no se pueden
recuperar del disco.** El ETL de S2 proyectó el CSV de OFF a **9 campos** y descartó
`quantity`, `packaging` y `stores` en el momento de la descarga
([cargar_off_bulk.py:135-146](etl/cargar_off_bulk.py#L135)). El export original
(`~/off_export.csv.gz`, ~9 GB) **ya no está en disco**. Recuperarlos por la vía del
export completo es volver a pagar la tarea con más varianza de todo el proyecto (§10
de `PLAN-MVP-v2.md`) por un campo cosmético.

**Decisión propuesta (D-S4-1):** no se re-descargan 9 GB. `presentacion` se recupera
por la **API v2 de OFF, por código de barras, solo para los productos que la demo
enseña** (top-30 por insumo + golden set ≈ 150-300 llamadas, minutos). Los demás quedan
en `null` declarado. Es coherente con el criterio del MVP: *cero valores inventados;
todo dato con fuente + url + fecha, o `null`*.

**3. El precio sigue siendo el hueco, y ahora está cuantificado.** Nunca se integró
Open Prices. T1.2 lo mide con una muestra real de 100 códigos de barras; ese número
—no una estimación— es el que se dice en voz alta en el bloque 2 del guion. Si sale
~0 %, el bloque cambia de *"aquí están los precios"* a **"aquí está el hueco, medido,
y esto es exactamente lo que llena el nivel 3 del puerto"**, que es un argumento mejor
para pedir presupuesto en el CDR.

---

## 1. Alcance de la semana

**Entra** (`PLAN-MVP-v2.md` §7 semana 4, sin multi-tenant y sobre Supabase):

1. Normalización de país y enriquecimiento acotado de presentación.
2. Entidad `ProductoEnMercado` + tabla `catalogo_comercial` con **procedencia por
   campo** (fuente + url + fecha), no por fila.
3. Puerto `DescubrimientoComercial` con la **cascada completa en la interfaz**: N1 real,
   N2 y N3 como stubs declarados que se registran en la auditoría.
4. **Etapa 2b** en el DAG, dentro de `etapa()`: informe gratuito = 1 · 2 · 2b · 3.
5. **P04** (campo sin dato = `null`) y **P05** (cada afirmación con cita a un dato
   entregado) como validadores automáticos, no como promesa.
6. Etapas 4 y 5 sobre datos reales → **P07** y **P08** degradados.
7. Panel mínimo, CI y ensayo del guion de 15 min.

**No entra:** agente (P11), cuarentena, MIM completo (P10), cola `procrastinate` (P09
pleno), deck PPTX, minería DuckDB de formulación, OCR de DIGESA. Se presentan como
diseño decidido en los ADR (§8 de `PLAN-MVP-v2.md`).

### Estado de las 13 pruebas al cerrar S4

| | Prueba | Estado |
|---|---|---|
| P01 | Aislamiento | 🟡 por usuario (multi-tenant fuera por decisión de S3) |
| P02 | Cache hit con clave correcta | ✅ S3 |
| P03 | Búsqueda p95 < 2 s | ✅ S2 (66 ms GPU / 176 ms CPU) |
| P04 | Campo sin dato = `null` | ✅ **S4 · T6** |
| P05 | Cada afirmación con cita | ✅ **S4 · T6** |
| P06 | Paywall ≠ guard técnico | ✅ S3 |
| P07 | Formulación | 🟡 **S4** sin minería DuckDB |
| P08 | Regulación con citas | 🟡 **S4** sobre los 734 pasajes de S2 |
| P09 | Informe como job | 🟡 PDF síncrono <15 s |
| P10 | MIM | ⬜ diseño |
| P11 | Agente | ⬜ diseño |
| P12 | Presupuestos | 🟡 S3, sin run de agente que topar |
| P13 | Cost-meter | ✅ S3 |

**Resultado: 10/13 con 4 degradados declarados** — exactamente lo comprometido en §7.

---

## 2. Estructura de TIERS

```
TIER 1: Medición y decisiones (Lun 10, mañana)                 → 3 h
  ├─ T1.1 Cobertura comercial del snapshot (§0, reproducible)
  ├─ T1.2 Sonda Open Prices sobre 100 códigos de barras
  ├─ T1.3 Decidir D-S4-1: enriquecimiento acotado vs 9 GB
  └─ T1.4 Congelar el contrato ProductoEnMercado

TIER 2: Normalización y enriquecimiento (Lun 10 – Mar 11)      → 6 h
  ├─ T2.1 countries OFF → ISO-3166 (1.578 → ~100)
  ├─ T2.2 Arreglar mojibake de codificación
  ├─ T2.3 presentacion por API v2 de OFF (top-30 x insumo)
  └─ T2.4 precio desde Open Prices, si T1.2 > 0

TIER 3: catalogo_comercial en Supabase (Mar 11)                → 5 h
  ├─ T3.1 dominio/producto_en_mercado.py con procedencia por campo
  ├─ T3.2 Tabla + índices + RLS + manifest de cobertura
  └─ T3.3 Proyección ETL desde el snapshot

TIER 4: Puerto DescubrimientoComercial (Mié 12)                → 5 h
  ├─ T4.1 puertos/descubrimiento_comercial.py
  ├─ T4.2 N1 snapshot (real)
  ├─ T4.3 N2 API licenciada y N3 agente: stubs declarados
  └─ T4.4 nivel_maximo_costo desde el entitlement de S3

TIER 5: Etapa 2b en el DAG (Mié 12 – Jue 13)                   → 5 h
  ├─ T5.1 casos_de_uso/etapas/mapear_comercio.py dentro de etapa()
  ├─ T5.2 Informe gratuito 1 · 2 · 2b · 3
  └─ T5.3 Mapa en el PDF y en Result.vue

TIER 6: P04 y P05 — honestidad del dato (Jue 13)               → 6 h
  ├─ T6.1 Validador "campo sin dato = null"        → P04
  ├─ T6.2 Validador "cada afirmación cita un id"   → P05
  └─ T6.3 Etapas 4 y 5 sobre datos reales          → P07/P08

TIER 7: Panel, CI, ensayo y cierre (Vie 14)                    → 6 h
  ├─ T7.1 Panel mínimo (historial, costo, informes, mapa)
  ├─ T7.2 CI: golden set de 30 + contratos + smoke test premium
  ├─ T7.3 Ensayo cronometrado del guion + plan B
  └─ T7.4 TIER7-S4-COMPLETADO.md y DoD final

TOTAL: ~36 h. T2 es el tier con más varianza (red).
```

---

## 🎯 TIER 1 · Medición y decisiones

**Duración:** 3 h · **Riesgo:** bajo · **Bloquea:** todo lo demás

### T1.1 · Cobertura comercial (45 min)

`scripts/cobertura_comercial.py` reproduce la tabla de §0 y **la escribe en
`manifest.json`**. Los números de §0 ya están medidos; el script los vuelve
auditables y detecta regresiones cuando el snapshot cambie.

### T1.2 · Sonda de Open Prices (1 h)

```python
# scripts/sonda_open_prices.py
# 100 códigos de barras al azar del snapshot (estratificado por los 5 insumos)
# GET https://prices.openfoodfacts.org/api/v1/prices?product_code=<barcode>
# Salida: % con al menos un precio, mediana de antigüedad del precio, países.
```

**Gate T1.2:** el porcentaje queda **escrito en el manifest y en el guion**. No es un
gate de "tiene que dar X": es un gate de "el número existe y se dice en voz alta".

### T1.3 · D-S4-1 (30 min)

Decidir y registrar en el ADR: enriquecimiento acotado por API (recomendado, §0-2) o
re-descarga del export. Si se eligiera la re-descarga, **arranca ya el lunes** y T2.3
se mueve al jueves.

### T1.4 · Contrato congelado (45 min)

```python
# dominio/producto_en_mercado.py
class Procedencia(BaseModel):
    fuente: str                 # 'OFF' | 'USDA' | 'OpenPrices'
    url: HttpUrl
    fecha: date

class CampoConFuente[T](BaseModel):
    valor: T | None
    procedencia: Procedencia | None   # None si y solo si valor is None

class ProductoEnMercado(BaseModel):
    insumo: str
    producto_id: str
    nombre: CampoConFuente[str]
    marca: CampoConFuente[str]
    pais_iso: CampoConFuente[str]        # ISO-3166 alpha-2
    presentacion: CampoConFuente[str]    # '500 g', '1 L'
    precio_rango: CampoConFuente[str]    # casi siempre None: es el hueco
    canal: CampoConFuente[str]           # casi siempre None
    url: HttpUrl
    fecha_dato: date
```

La invariante `valor is None ⇔ procedencia is None` es lo que **P04 verifica en T6.1**.
Que la procedencia sea **por campo y no por fila** es lo que permite decir en la demo
*"la marca viene de OFF con esta URL y esta fecha; el precio no viene de ningún sitio,
por eso está vacío"*.

### DoD de TIER 1

- [ ] Tabla de cobertura de §0 reproducida por script y volcada al `manifest.json`
- [ ] % de precio en Open Prices **medido sobre 100 códigos** y anotado
- [ ] D-S4-1 decidida y escrita
- [ ] `ProductoEnMercado` congelado; `contratos/` regenerado

---

## 🌍 TIER 2 · Normalización y enriquecimiento

**Duración:** 6 h · **Riesgo:** medio (red) · **Depende de:** T1

### T2.1 · `etl/normalizar_paises.py`

De 1.578 variantes a ISO-3166 alpha-2. Reglas, en orden:

1. Prefijo `en:` fuera → `en:us` → `us`, `en:united-states` → `united-states`.
2. Guiones a espacios, minúsculas, sin tildes.
3. Diccionario de alias ES/EN/FR/DE (`estados unidos`, `états-unis`, `deutschland`…).
4. Multivalor (`United States, World`) → **lista** de códigos; `world` se descarta.
5. Sin correspondencia → `null` **y se registra en un reporte**, nunca se adivina.

**Gate T2.1:** ≥ 95 % de las 29.054 filas con al menos un ISO válido · **0 filas con
`en:` crudo** · el reporte de no mapeados tiene ≤ 200 variantes distintas y se revisa a
ojo.

### T2.2 · Mojibake (30 min)

`Espa�a` viene de leer el CSV con la codificación equivocada. Se corrige en la
normalización, no re-descargando. **Gate:** 0 filas con `�` en `marca`, `nombre`
o `pais`.

### T2.3 · `etl/enriquecer_presentacion.py`

```
GET https://world.openfoodfacts.org/api/v2/product/{barcode}
    ?fields=code,quantity,product_quantity,packaging,stores
```

Solo para los productos que la demo enseña: top-30 por insumo + golden set ≈ 150-300
llamadas. Rate-limit cortés (1 req/s, user-agent identificado), resultado cacheado en
`datasets/2026-07/enriquecimiento_off.json` con su fecha de consulta.

**Gate T2.3:** ≥ 80 % de los enriquecidos con `quantity` real; el resto `null`. Cero
inferencias del tipo "si el nombre dice 500g entonces la presentación es 500 g".

### T2.4 · Precio (condicional)

Solo si T1.2 dio > 0 %. Mismo patrón: valor + fuente + url + fecha, o `null`.

### DoD de TIER 2

- [ ] ≥ 95 % de filas con ISO válido; 0 con `en:` crudo; reporte de no mapeados
- [ ] 0 caracteres de reemplazo en los campos de texto
- [ ] Enriquecimiento cacheado en el snapshot con su fecha
- [ ] `manifest.json` actualizado y SHA256 recalculados (procedimiento de S2-T7.2)
- [ ] Golden set sigue **5/5**

---

## 🗃️ TIER 3 · `catalogo_comercial` en Supabase

**Duración:** 5 h · **Riesgo:** bajo · **Depende de:** T2, y de S3-T2

```sql
create table public.catalogo_comercial (
  id            bigserial primary key,
  insumo        text not null,
  producto_id   text not null,          -- 'OFF:00000036'
  nombre        text not null,
  marca         text,
  pais_iso      text,                   -- alpha-2 o null
  presentacion  text,
  precio_rango  text,
  canal         text,
  url           text not null,
  fecha_dato    date not null,
  procedencia   jsonb not null,         -- {campo: {fuente,url,fecha}}
  snapshot_version text not null,
  creado_en     timestamptz not null default now(),
  unique (producto_id, snapshot_version)
);
create index on public.catalogo_comercial (insumo, pais_iso);
alter table public.catalogo_comercial enable row level security;
-- Catálogo de referencia, no dato de usuario: lectura para authenticated.
create policy p_catalogo_lectura on public.catalogo_comercial
  for select to authenticated using (true);
```

`etl/proyectar_catalogo.py` vuelca el snapshot normalizado a la tabla y **escribe en el
manifest el % de `null` por campo**, que es el número que se enseña en el bloque 2.

### DoD de TIER 3

- [ ] Filas cargadas == productos de los 5 insumos del snapshot
- [ ] **0 filas** con un valor no nulo cuya `procedencia` esté vacía (invariante de T1.4)
- [ ] % de `null` por campo en el manifest: se espera ~18 % marca, ~100 % precio y canal
- [ ] RLS activo; la anon key no lee la tabla

---

## 🪜 TIER 4 · Puerto `DescubrimientoComercial`

**Duración:** 5 h · **Riesgo:** bajo · **Depende de:** T3

El objetivo de este tier **no es traer más datos**: es que la arquitectura del ADR-001
quede demostrada aunque el agente no exista. La cascada entera vive en la interfaz.

```python
# puertos/descubrimiento_comercial.py
class NivelDescubrimiento(IntEnum):
    SNAPSHOT = 1        # real
    API_LICENCIADA = 2  # stub declarado
    AGENTE_WEB = 3      # stub declarado

class DescubrimientoComercial(Protocol):
    def descubrir(self, insumo: str, nivel_maximo: NivelDescubrimiento
                  ) -> ResultadoDescubrimiento: ...
```

- **N1** (`adaptadores/descubrimiento_snapshot.py`): consulta `catalogo_comercial`.
- **N2 y N3** (`descubrimiento_stub.py`): devuelven vacío y **registran una fila en
  `etapas_ejecucion`** con `modelo='stub'`, `costo_usd=0` y una salida
  `{"disponible": false, "motivo": "nivel no disponible en este MVP", "roadmap": "ADR-001 §2.3"}`.
- `nivel_maximo` sale del **entitlement de S3** (`Entitlement.nivel_maximo_costo`):
  gratuito → 1, premium → 2. El 3 no lo alcanza nadie en el MVP.

Que el stub deje rastro en la auditoría es la diferencia entre *"esto está diseñado"* y
*"esto está diseñado y aquí está la fila que lo prueba"*, que es lo que se enseña en el
bloque 2 del guion.

### DoD de TIER 4

- [ ] Run gratuito → solo N1; premium → N1 + fila de N2 declarada no disponible
- [ ] `nivel_maximo=3` → 3 filas, 2 declaradas, **HTTP 200**, nunca excepción
- [ ] Costo de los stubs == 0,00 y no cuentan contra la cuota
- [ ] Test que fija el contrato del puerto (el agente de F4 lo implementará contra él)

---

## 🗺️ TIER 5 · Etapa 2b en el DAG

**Duración:** 5 h · **Riesgo:** bajo · **Depende de:** T4, y de S3-T5

### T5.1 · La etapa

`casos_de_uso/etapas/mapear_comercio.py`, invocada por `etapa()` con `num_etapa='2b'`
—valor ya legal en el `check` del esquema de S3— entre la búsqueda y el insight. Sin
LLM: es una consulta a `catalogo_comercial` a través del puerto, así que su
`costo_usd` es 0 y su duración debe ser de milisegundos.

### T5.2 · Composición

```
gratuito:  1 · 2 · 2b · 3
premium:   1 · 2 · 2b · 3 · 4 · 5
```

El insight de la etapa 3 pasa a recibir **también** el mapa comercial: los países y
marcas reales son material de cita para P05.

### T5.3 · Presentación

Tabla en el PDF y en `Result.vue`: país · marca · presentación · precio · URL · fecha.
Las celdas vacías se pintan como **"sin dato"** con un tooltip que dice de dónde
vendría — no se ocultan ni se rellenan con guiones. Es el gesto visual del bloque 2.

### DoD de TIER 5

- [ ] Run gratuito → **4 filas** en `etapas_ejecucion`: `'1','2','2b','3'`
- [ ] Run premium → **6 filas**
- [ ] Mapa de "arándano" con **≥ 5 países ISO distintos** y ≥ 10 marcas
- [ ] Duración de 2b **< 300 ms**; `costo_usd = 0`
- [ ] Las URLs de la tabla abren el producto real en el navegador (verificado a mano en 10)
- [ ] Golden set **5/5** y suite sin regresión

---

## 🔍 TIER 6 · P04 y P05 — honestidad del dato

**Duración:** 6 h · **Riesgo:** medio · **Depende de:** T5

Este es el tier que sostiene el argumento entero de la demo. Los dos validadores son
**código que corre en cada run**, no una revisión manual.

### T6.1 · P04 — campo sin dato = `null`

`casos_de_uso/validadores/sin_inventos.py`: recorre la salida de 2b y del insight y
falla si encuentra un valor no nulo que sea un no-dato disfrazado — `""`, `"N/A"`,
`"n/a"`, `"desconocido"`, `"-"`, `"sin datos"`, `"None"`, `0` en un rango de precio— o
un valor sin procedencia.

**Gate:** un test que **inyecta** `"N/A"` en `marca` y exige que el validador falle. Un
validador que nunca ha fallado no está probado.

### T6.2 · P05 — cada afirmación con su cita

El contrato de la etapa 3 pasa de `resumen: str` a:

```python
class Afirmacion(BaseModel):
    texto: str
    citas: list[str]      # ids de productos entregados a la etapa, >= 1

class InsightDeMercado(BaseModel):
    cobertura: Literal["baja","media","alta"]
    afirmaciones: list[Afirmacion]
    formatos_comunes: list[str]
    nota_regulatoria: str | None
```

El validador comprueba que **todo id citado esté en el conjunto entregado** a la etapa.
Un id inventado por el modelo es un fallo duro, no una advertencia.

**Gate:** test con una cita inventada → falla; los 5 casos del golden set → **0
afirmaciones sin cita** y **0 citas fuera del conjunto**.

### T6.3 · Etapas 4 y 5 sobre datos reales → P07/P08

Las etapas separadas en S3-T5 reciben ahora datos reales: la formulación trabaja sobre
los ingredientes del snapshot (sin minería DuckDB — degradación declarada de P07) y el
dossier regulatorio cita los **734 pasajes de eCFR y DIGESA** indexados en S2.

Deuda de S2 que hay que decir en voz alta: **el eCFR no cubre los insumos piloto** (es
Title 21 sobre aditivos). Para arándano, palta, espárrago, mango y quinua la fuente son
las NTS peruanas y el Codex. El dossier debe **declarar el alcance de su corpus** en
lugar de sugerir una cobertura que no tiene.

### DoD de TIER 6

- [ ] Validador P04 con test de inyección que falla como debe
- [ ] Validador P05 con test de cita inventada que falla como debe
- [ ] Golden set: 0 afirmaciones sin cita, 0 citas fuera del conjunto
- [ ] Dossier con ≥ 3 citas verificables al corpus y su alcance declarado
- [ ] `contratos/` regenerado

---

## 🖥️ TIER 7 · Panel, CI, ensayo y cierre

**Duración:** 6 h · **Depende de:** todo

### T7.1 · Panel mínimo

Lo que exigen P09, P12 y P13 y nada más (D8): historial de consultas, costo por consulta
y por mes con la barra de cuota de S3, listado de informes con URL firmada, y la tabla
del mapa comercial. Sin gráficos de tendencias: eso es el MIM y es roadmap.

### T7.2 · CI

```yaml
# .github/workflows/ci.yml
- Golden set de 30 productos para el MATCH (el del extractor no aplica sin agente)
- Validación de todos los contratos con model_json_schema()
- Smoke test del DAG premium completo con APP_DB=sqlite y AGROSCOUT_OFFLINE=1
- Suites de S2 (18) + S3 (10) + S4
```

El smoke test corre **offline y en SQLite** a propósito: la CI no debe depender de
Supabase ni del LLM.

### T7.3 · Ensayo

Guion de 15 min cronometrado, con las dos cuentas demo, **incluido el bloque 5 en su
versión de S3** (aislamiento por usuario, no RLS entre organizaciones). Verificar el
plan B: `APP_DB=sqlite` + `AGROSCOUT_OFFLINE=1` completa los 5 insumos sin red.

### T7.4 · Cierre

`TIER7-S4-COMPLETADO.md` con el formato de S2: gates obtenidos, deuda abierta y la
matriz 13/13 con los degradados nombrados uno por uno.

### DoD de TIER 7

- [ ] Panel con las 4 vistas
- [ ] CI verde en un runner limpio
- [ ] Guion ensayado **≤ 15 min** con las 2 cuentas
- [ ] Plan B verificado con los 5 insumos sin red
- [ ] **10/13** con los 4 degradados declarados por escrito

---

## 3. Matriz de cierre de la semana

| Gate | Número exacto | Tier |
|---|---|---|
| Cobertura comercial | 8 campos medidos y en el manifest | T1 |
| Precio en Open Prices | % medido sobre 100 códigos | T1 |
| Normalización de país | ≥ 95 % con ISO · 0 con `en:` crudo | T2 |
| Codificación | 0 caracteres de reemplazo | T2 |
| Enriquecimiento | ≥ 80 % de los mostrados con `quantity` real | T2 |
| Procedencia | 0 valores no nulos sin fuente | T3 |
| Cascada | 3 niveles, 2 declarados, 200 siempre | T4 |
| Etapas | gratuito 4 filas · premium 6 filas | T5 |
| Mapa | ≥ 5 países ISO y ≥ 10 marcas para arándano | T5 |
| Latencia de 2b | < 300 ms, costo 0 | T5 |
| **P04** | test de inyección falla como debe | T6 |
| **P05** | 0 citas fuera del conjunto en el golden set | T6 |
| CI | verde en runner limpio, sin red | T7 |
| Guion | ≤ 15 min cronometrado | T7 |

---

## 4. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| **R1** | **El export de 9 GB ya no está en disco** y `presentacion`/`canal` se perdieron en la proyección de S2 | D-S4-1: enriquecimiento por API acotado a lo que se enseña (~300 llamadas). No re-descargar |
| **R2** | **1.578 variantes de país.** Si T2.1 se subestima, el mapa comercial sale ilegible el viernes | Es T2.1, primer tier de código de la semana, con gate del 95 % |
| **R3** | **El precio saldrá casi todo `null`** | Ya está previsto: se mide en T1.2 y se convierte en el argumento del bloque 2 en vez de esconderse |
| **R4** | **P05 obliga a cambiar el contrato de la etapa 3** (`resumen: str` → `afirmaciones: list`), lo que toca prompt, PDF y SPA | Hacerlo en T6.2 con el prompt ya estabilizado por S3-T5, no antes |
| **R5** | **El eCFR no cubre los insumos piloto** (deuda de S2) | El dossier declara el alcance de su corpus. No se compra corpus nuevo en la semana del ensayo |
| **R6** | S4 depende de que S3 esté cerrada (entitlement, Supabase, etapas 4 y 5 separadas) | T1-T2 no dependen de S3: si S3 se desborda, se adelantan y se retrasa T3 |

---

## 5. Calendario

| Día | Tiers | Horas |
|---|---|---|
| **Lun 10** | T1 completo · T2.1-T2.2 | 7 |
| **Mar 11** | T2.3-T2.4 · T3 completo | 8 |
| **Mié 12** | T4 completo · T5.1 | 7 |
| **Jue 13** | T5.2-T5.3 · T6 completo | 8 |
| **Vie 14** | T7 completo | 6 |

Cierra el **viernes 14**, con **dos semanas de margen** hasta el CDR del 2026-08-28.
Ese margen es el colchón de los degradados: si P07 o P08 quedan flojos, hay tiempo de
subirlos sin tocar el alcance comprometido.

**Orden de sacrificio si la semana se desborda:**

1. T2.4 precio desde Open Prices — si T1.2 dio ~0 %, ni se intenta
2. T2.3 enriquecimiento de presentación — `presentacion: null` es coherente con el
   discurso; simplemente hay una columna vacía más
3. T7.1 panel — reducir a historial y costo
4. **No se sacrifica T6.** Sin P04 y P05 automáticos, *"cero valores inventados"* vuelve
   a ser una afirmación de palabra, y es justo lo que el CITE puede pinchar en vivo

---

## 6. Después de S4

El CDR del **2026-08-28** con 10/13. Lo diferido está en `PLAN-MVP-v2.md` §8 y §11:
F4 (cola, agente, cuarentena, presupuestos plenos) y F5 (MIM, taxonomía CITE, deck
PPTX). El puerto de T4 y la columna `'2b'` del esquema de S3 son los dos ganchos por
donde entra F4 sin reescribir nada.
