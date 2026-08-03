# Semana 4 — versión MVP: 6 tiers básicos

**Fecha:** 2026-08-02 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)
**Reemplaza a:** [PLAN-TIERS-S4.md](PLAN-TIERS-S4.md) (7 tiers, ~36 h), que se conserva
como referencia de lo que se dejó fuera y por qué.
**Calendario nominal:** Lun 10 – Jue 13 de agosto 2026 · **≈22,5 h de código**
**Cierra:** el alcance comprometido de `PLAN-MVP-v2.md` §7. CDR el 2026-08-28.

---

## 0. Qué se quitó y qué cuesta

| Pieza del plan de 36 h | −h | Qué se pierde |
|---|---|---|
| **Tabla `catalogo_comercial` en Supabase** | −5 | Nada visible. La etapa 2b lee del índice LanceDB que ya existe y la procedencia queda auditada en `etapas_ejecucion.salida_json`. Materializar 29 k filas en Postgres para un solo nodo no compra nada |
| **Enriquecer `presentacion` por API de OFF** | −3 | Una columna más en "sin dato". Coherente con el discurso: ya se dice que el precio está vacío |
| **Integrar precio de Open Prices** | −2 | **Medir sí** (T1.2, sigue dentro); **integrar no**. La sonda dirá casi seguro ~0 % |
| **CI en GitHub Actions** | −2,5 | El check verde. Los tests siguen existiendo y corriendo en local, que es donde se corren |
| **Adaptadores stub de N2/N3 con fila propia en la auditoría** | −3 | Los niveles se declaran en el enum y en el informe, no con una fila de auditoría por nivel |
| **P05 en su versión completa** (`resumen: str` → `list[Afirmacion]`) | −3 | ⚠️ **P05 baja de ✅ a 🟡** — ver §1 |

**Total: −18,5 h → de 36 h a 22,5 h.** De 7 tiers a **6**, y de 5 días a 4 con colchón.

Dos simplificaciones que caen solas al hacer estos cortes y que valen más que las horas:

- **La procedencia por campo deja de tener sentido.** Servía para distinguir "la marca
  viene de OFF, el precio de Open Prices, la presentación de la API v2". Cortados el
  precio y la presentación, **cada fila tiene una sola fuente**: su producto de OFF o
  USDA, con una URL y una fecha. El contrato pasa de genéricos `CampoConFuente[T]` a un
  modelo plano (T1.3).
- **No se reindexa nada.** La normalización de país se aplica **al leer**, no
  reescribiendo `vectores/productos.lance`. Se ahorra la reindexación y el riesgo del
  bug de `sys.modules` que costó TIER 4 de S2.

---

## 1. Alcance y estado de las pruebas

**Entra:** normalización de país · contrato `ProductoEnMercado` · puerto
`DescubrimientoComercial` con la cascada en la interfaz · **etapa 2b** en el DAG ·
**P04** como validador que corre en cada run · **P05 en versión mínima** · etapas 4 y 5
sobre datos reales · panel mínimo y ensayo.

**No entra:** agente (P11), cuarentena, MIM (P10), cola `procrastinate` (P09 pleno),
deck PPTX, minería DuckDB, OCR de DIGESA, y los seis recortes de §0.

| | Prueba | Estado al cerrar |
|---|---|---|
| P01 | Aislamiento | 🟡 por usuario (multi-tenant fuera, decisión de S3) |
| P02 | Cache hit | ✅ S3 |
| P03 | Búsqueda p95 < 2 s | ✅ S2 (66 ms GPU / 176 ms CPU) |
| P04 | Campo sin dato = `null` | ✅ **T5.1** |
| P05 | Afirmación con cita | 🟡 **T5.2 — citas a nivel de informe, no por frase** |
| P06 | Paywall ≠ guard técnico | ✅ S3 |
| P07 | Formulación | 🟡 sin minería DuckDB |
| P08 | Regulación con citas | 🟡 sobre los 734 pasajes de S2 |
| P09 | Informe como job | 🟡 PDF síncrono <15 s |
| P10 · P11 | MIM · Agente | ⬜ diseño |
| P12 | Presupuestos | 🟡 S3, sin run de agente que topar |
| P13 | Cost-meter | ✅ S3 |

**Resultado: 10/13 con 5 degradados declarados** (antes 4). El que cambia es **P05**.

> **Lo que hay que poder decir en la demo.** Con P05 mínimo, la frase honesta es *"todo
> producto citado en el informe fue entregado a la etapa por la búsqueda; ningún id es
> inventado"*. Lo que **no** se puede afirmar es *"esta frase concreta se apoya en estos
> dos productos"*. Si en el CDR alguien pregunta exactamente eso, la respuesta es que
> está diseñado y son 3 h de trabajo — es el primer candidato del colchón (§5).

---

## 2. Estructura de TIERS

```
TIER 1: Medición y contrato (Lun 10, mañana)            → 2,5 h
  ├─ T1.1 Cobertura comercial del snapshot → manifest
  ├─ T1.2 Sonda Open Prices sobre 100 códigos (solo medir)
  └─ T1.3 Contrato ProductoEnMercado (plano, una fuente por fila)

TIER 2: Normalización de país (Lun 10, tarde)           → 3,5 h
  ├─ T2.1 countries OFF → ISO-3166 (1.578 → ~100), al leer
  └─ T2.2 Arreglar mojibake de codificación

TIER 3: Puerto DescubrimientoComercial (Mar 11)         → 2 h
  ├─ T3.1 Protocol + enum de 3 niveles
  └─ T3.2 N1 sobre el índice LanceDB existente

TIER 4: Etapa 2b en el DAG (Mar 11)                     → 4,5 h
  ├─ T4.1 mapear_comercio.py dentro de etapa()
  ├─ T4.2 Composición gratuito 1·2·2b·3 / premium +4·5
  └─ T4.3 Tabla en el PDF y en Result.vue con "sin dato"

TIER 5: Honestidad del dato (Mié 12)                    → 5 h
  ├─ T5.1 Validador P04 "campo sin dato = null"
  ├─ T5.2 Validador P05 mínimo sobre las citas existentes
  └─ T5.3 Etapas 4 y 5 sobre datos reales → P07/P08

TIER 6: Panel, ensayo y cierre (Jue 13)                 → 5 h
  ├─ T6.1 Panel mínimo (historial, costo, informes, mapa)
  ├─ T6.2 Ensayo cronometrado del guion + plan B
  └─ T6.3 TIER-S4-COMPLETADO.md y DoD final

TOTAL: ~22,5 h en 4 días. Viernes 14 libre como colchón.
```

---

## 🎯 TIER 1 · Medición y contrato

**Duración:** 2,5 h · **Riesgo:** bajo · **Bloquea:** todo

### T1.1 · Cobertura comercial (45 min)

`scripts/cobertura_comercial.py` mide sobre las 29.054 filas de
`datasets/2026-07/productos_merged.json` y escribe el resultado en `manifest.json`.
Los números ya están medidos (2026-08-02); el script los vuelve auditables:

| Campo | Cobertura |
|---|---|
| `url` · `fecha_dato` · `nombre` | **100 %** |
| `marca` | **82,0 %** (23.811) |
| `categoria` | 82,7 % |
| `pais` | 99,6 %, pero con **1.578 variantes** → T2 |
| `presentacion` · `precio` · `canal` | **0 % — no existen en el snapshot** |

El ETL de S2 proyectó el CSV de OFF a 9 campos y descartó `quantity`, `packaging` y
`stores` en la descarga ([cargar_off_bulk.py:135-146](etl/cargar_off_bulk.py#L135)), y
el export original (~9 GB) ya no está en disco. **No se re-descarga:** esos tres campos
quedan en `null` declarado, que es exactamente el hueco que el nivel 3 del puerto llena.

### T1.2 · Sonda de Open Prices (1 h)

```python
# scripts/sonda_open_prices.py
# 100 códigos de barras al azar, estratificados por los 5 insumos
# GET https://prices.openfoodfacts.org/api/v1/prices?product_code=<barcode>
# Salida: % con al menos un precio · antigüedad mediana · países
```

**Solo mide; no integra.** El porcentaje se escribe en el manifest y se dice en voz alta
en el bloque 2 del guion. Si sale ~0 %, el bloque pasa de *"aquí están los precios"* a
**"aquí está el hueco, medido"**, que para pedir presupuesto en el CDR funciona mejor.

### T1.3 · Contrato (45 min)

```python
# dominio/producto_en_mercado.py
class ProductoEnMercado(BaseModel):
    insumo: str
    producto_id: str                 # 'OFF:00000036'
    nombre: str
    marca: str | None                # 18 % en null
    paises_iso: list[str]            # ISO-3166 alpha-2; [] si no se pudo mapear
    presentacion: str | None = None  # siempre None en el MVP
    precio_rango: str | None = None  # siempre None en el MVP: es el hueco
    canal: str | None = None         # siempre None en el MVP
    fuente: Literal["OFF", "USDA"]   # una sola fuente por fila
    url: HttpUrl
    fecha_dato: date
```

Los tres campos que siempre son `None` **se quedan en el modelo a propósito**: son lo
que la tabla enseña como "sin dato" y el gancho por donde entra el agente en F4.

### DoD de TIER 1

- [ ] Tabla de cobertura reproducida por script y volcada al `manifest.json`
- [ ] % de precio en Open Prices medido sobre **100 códigos** y anotado
- [ ] `ProductoEnMercado` congelado; `contratos/` regenerado

---

## 🌍 TIER 2 · Normalización de país

**Duración:** 3,5 h · **Riesgo:** bajo · **Depende de:** T1

Sin esto el mapa por país sale ilegible: `United States` (9.986), `en:United States`
(1.633), `en:us` (1.005), `United States, World` (852) y `en:united-states` (785) son
el mismo país.

### T2.1 · `etl/normalizar_paises.py`

Función pura `normalizar(countries: str) -> list[str]`, aplicada **al leer**. No
reescribe el snapshot ni el índice LanceDB. Reglas, en orden:

1. Quitar prefijo `en:` → `en:us` → `us`, `en:united-states` → `united-states`
2. Guiones a espacios, minúsculas, sin tildes
3. Diccionario de alias ES/EN/FR/DE (`estados unidos`, `états-unis`, `deutschland`…)
4. Multivalor (`United States, World`) → lista; `world` se descarta
5. Sin correspondencia → **no se adivina**: fuera de la lista y al reporte

**Gate T2.1:** ≥ **95 %** de las 29.054 filas con al menos un ISO válido · **0 filas con
`en:` crudo** · reporte de no mapeados con ≤ 200 variantes, revisado a ojo.

### T2.2 · Mojibake (30 min)

`Espa�a` viene de leer el CSV con la codificación equivocada. Se corrige en la misma
función, no re-descargando. **Gate:** 0 caracteres `�` en `marca`, `nombre` y `pais`.

### DoD de TIER 2

- [ ] ≥ 95 % con ISO válido; 0 con `en:` crudo; reporte de no mapeados
- [ ] 0 caracteres de reemplazo en los campos de texto
- [ ] Test unitario con los 5 alias de Estados Unidos → todos `US`
- [ ] Golden set sigue **5/5**

---

## 🪜 TIER 3 · Puerto `DescubrimientoComercial`

**Duración:** 2 h · **Riesgo:** bajo · **Depende de:** T2

El objetivo **no es traer más datos**: es que la cascada del ADR-001 esté en la
interfaz aunque el agente no exista.

```python
# puertos/descubrimiento_comercial.py
class NivelDescubrimiento(IntEnum):
    SNAPSHOT       = 1   # real en el MVP
    API_LICENCIADA = 2   # no disponible en el MVP
    AGENTE_WEB     = 3   # no disponible en el MVP

class DescubrimientoComercial(Protocol):
    def descubrir(self, insumo: str, nivel_maximo: NivelDescubrimiento
                  ) -> list[ProductoEnMercado]: ...
```

`adaptadores/descubrimiento_snapshot.py` implementa **solo N1**: consulta el índice
LanceDB existente filtrando por insumo (hasta 200 filas), aplica el normalizador de T2 y
proyecta a `ProductoEnMercado`. Los niveles 2 y 3 **no tienen adaptador**: el resultado
de la etapa lleva `niveles_no_disponibles: [2, 3]` y el informe lo imprime como una
línea. Es la versión barata de la misma afirmación.

### DoD de TIER 3

- [ ] `descubrir("arándano", nivel_maximo=1)` devuelve ≥ 50 productos en < 300 ms
- [ ] `nivel_maximo=3` devuelve lo mismo y declara `[2, 3]` — **nunca lanza excepción**
- [ ] Test que fija el contrato del puerto (contra él se escribirá el agente en F4)

---

## 🗺️ TIER 4 · Etapa 2b en el DAG

**Duración:** 4,5 h · **Riesgo:** bajo · **Depende de:** T3, y de S3-T5

### T4.1 · La etapa

`casos_de_uso/etapas/mapear_comercio.py`, invocada por `etapa()` con `num_etapa='2b'`
—valor ya legal en el `check` del esquema de S3— entre la búsqueda y el insight. **Sin
LLM:** su `costo_usd` es 0 y su duración se mide en milisegundos. Como pasa por
`etapa()`, queda cacheada y auditada como cualquier otra, y su `salida_json` es la
evidencia de procedencia que ya no necesita tabla propia.

### T4.2 · Composición

```
gratuito:  1 · 2 · 2b · 3
premium:   1 · 2 · 2b · 3 · 4 · 5
```

El insight de la etapa 3 recibe **también** el mapa: los países y marcas reales son
material de cita.

### T4.3 · Presentación

Tabla en el PDF y en `Result.vue`: país · marca · presentación · precio · URL · fecha.
Las celdas vacías se pintan **"sin dato"**, no se ocultan ni se rellenan con guiones. Es
el gesto visual del bloque 2 del guion.

### DoD de TIER 4

- [ ] Run gratuito → **4 filas** en `etapas_ejecucion`: `'1','2','2b','3'`
- [ ] Run premium → **6 filas**
- [ ] Mapa de "arándano" con **≥ 5 países ISO distintos** y ≥ 10 marcas
- [ ] Duración de 2b **< 300 ms** y `costo_usd = 0`
- [ ] 10 URLs de la tabla abiertas a mano: todas resuelven al producto real

---

## 🔍 TIER 5 · Honestidad del dato

**Duración:** 5 h · **Riesgo:** medio · **Depende de:** T4

El tier que sostiene el argumento de la demo. Los validadores son **código que corre en
cada run**, no una revisión manual.

### T5.1 · P04 — campo sin dato = `null` (2,5 h)

`casos_de_uso/validadores/sin_inventos.py` recorre la salida de 2b y del insight y falla
si encuentra un no-dato disfrazado: `""`, `"N/A"`, `"n/a"`, `"desconocido"`, `"-"`,
`"sin datos"`, `"None"`, o un `0` en un rango de precio.

**Gate:** un test que **inyecta** `"N/A"` en `marca` y exige que el validador falle. Un
validador que nunca ha fallado no está probado.

### T5.2 · P05 mínimo (1 h)

`InsightDeMercado` **ya tiene** `citas: list[str]`. La versión mínima valida que **todo
id citado esté en el conjunto entregado a la etapa**: un id inventado por el modelo es
fallo duro, no advertencia.

**Gate:** test con una cita inventada → falla · los 5 casos del golden set → **0 citas
fuera del conjunto** y **≥ 1 cita por informe**.

No se parte el resumen en `list[Afirmacion]`: eso arrastra prompt, PDF y SPA, son 3 h
más y es lo primero que sube si sobra el viernes (§5).

### T5.3 · Etapas 4 y 5 sobre datos reales (1,5 h)

Las etapas separadas en S3-T5 reciben datos reales: la formulación trabaja sobre los
ingredientes del snapshot (sin minería DuckDB — degradación declarada de P07) y el
dossier cita los **734 pasajes** de eCFR y DIGESA indexados en S2.

Deuda de S2 que hay que decir en voz alta: **el eCFR no cubre los insumos piloto** (es
Title 21, aditivos). Para arándano, palta, espárrago, mango y quinua la fuente son las
NTS peruanas y el Codex. El dossier **declara el alcance de su corpus** en vez de
sugerir una cobertura que no tiene.

### DoD de TIER 5

- [ ] P04 con test de inyección que falla como debe
- [ ] P05 con test de cita inventada que falla como debe
- [ ] Golden set: 0 citas fuera del conjunto, ≥ 1 cita por informe
- [ ] Dossier con ≥ 3 citas verificables y su alcance declarado
- [ ] `contratos/` regenerado

---

## 🖥️ TIER 6 · Panel, ensayo y cierre

**Duración:** 5 h · **Depende de:** todo

### T6.1 · Panel mínimo (2 h)

Lo que exigen P09, P12 y P13 y nada más (D8): historial de consultas, costo por consulta
y por mes, listado de informes y la tabla del mapa comercial. Sin gráficos de
tendencias: eso es el MIM y es roadmap.

### T6.2 · Ensayo (2 h)

Guion de 15 min cronometrado con las dos cuentas demo, **con el bloque 5 en su versión
de S3** (aislamiento por usuario, no RLS entre organizaciones). Verificar el plan B:
`APP_DB=sqlite` + `AGROSCOUT_OFFLINE=1` completa los 5 insumos sin red.

Las suites (S2: 18 · S3 · S4) se corren **en local**, que es donde se van a correr. Sin
CI en GitHub Actions: el check verde no entra a la demo.

### T6.3 · Cierre (1 h)

`TIER-S4-COMPLETADO.md` con el formato de S2: gates obtenidos, deuda abierta y la matriz
13/13 con **los 5 degradados nombrados uno por uno**.

### DoD de TIER 6

- [ ] Panel con las 4 vistas
- [ ] Suites en verde en local
- [ ] Guion ensayado **≤ 15 min** con las 2 cuentas
- [ ] Plan B verificado con los 5 insumos sin red
- [ ] **10/13** con los 5 degradados declarados por escrito

---

## 3. Matriz de cierre

| Gate | Número exacto | Tier |
|---|---|---|
| Cobertura comercial | 8 campos medidos y en el manifest | T1 |
| Precio en Open Prices | % medido sobre 100 códigos | T1 |
| Normalización de país | ≥ 95 % con ISO · 0 con `en:` crudo | T2 |
| Codificación | 0 caracteres de reemplazo | T2 |
| Puerto | `nivel_maximo=3` declara `[2,3]` y no lanza | T3 |
| Etapas | gratuito 4 filas · premium 6 filas | T4 |
| Mapa | ≥ 5 países ISO y ≥ 10 marcas para arándano | T4 |
| Latencia de 2b | < 300 ms, costo 0 | T4 |
| **P04** | test de inyección falla como debe | T5 |
| **P05** | 0 citas fuera del conjunto en el golden set | T5 |
| Guion | ≤ 15 min cronometrado | T6 |

---

## 4. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| **R1** | **1.578 variantes de país.** Si T2.1 se subestima, el mapa sale ilegible | Es el primer tier de código, con gate del 95 % y test de los 5 alias de EE. UU. |
| **R2** | **`presentacion`, `precio` y `canal` van vacíos.** Tres de las siete columnas de la tabla | Es la decisión de §0, no un accidente: se enseñan como "sin dato" y se explica que ese es el trabajo del nivel 3 |
| **R3** | **P05 degradado** puede quedarse corto si el CDR pregunta por el respaldo de una frase concreta | Respuesta preparada (§1) y 3 h de colchón el viernes para subirlo |
| **R4** | **El eCFR no cubre los insumos piloto** (deuda de S2) | El dossier declara el alcance de su corpus. No se compra corpus nuevo en la semana del ensayo |
| **R5** | S4 depende de que S3 esté cerrada (etapas 4/5 separadas, entitlement) | T1, T2 y T3 **no dependen de S3**: si S3 se desborda, se adelantan y solo se retrasa T4 |

---

## 5. Calendario

| Día | Tiers | Horas |
|---|---|---|
| **Lun 10** | T1 · T2 | 6 |
| **Mar 11** | T3 · T4 | 6,5 |
| **Mié 12** | T5 | 5 |
| **Jue 13** | T6 | 5 |
| **Vie 14** | — colchón | — |

**Si sobra el viernes**, en este orden:

1. **Subir P05 a la versión completa** (`list[Afirmacion]`, 3 h) — es el único degradado
   que se puede cerrar dentro de la semana
2. Enriquecer `presentacion` por la API v2 de OFF para los ~300 productos de la demo (3 h)
3. CI en GitHub Actions (2,5 h)

**Si la semana se desborda**, el orden de sacrificio es: T6.1 panel → reducir a historial
y costo. **No se sacrifica T5**: sin P04 automático, *"cero valores inventados"* vuelve a
ser una afirmación de palabra, y es justo lo que el CITE puede pinchar en vivo.

---

## 6. Después

CDR el **2026-08-28** con 10/13 y dos semanas de margen. Lo diferido está en
`PLAN-MVP-v2.md` §8 y §11: F4 (cola, agente, cuarentena, presupuestos plenos) y F5 (MIM,
taxonomía CITE, deck PPTX). El puerto de T3 y la columna `'2b'` del esquema de S3 son
los dos ganchos por donde entra F4 sin reescribir nada; la tabla `catalogo_comercial`
que aquí se corta es lo primero que F4 necesitará, y su DDL está en
[PLAN-TIERS-S4.md](PLAN-TIERS-S4.md) §T3 listo para usar.
