# S7 AUDITORÍA PREVIA: Promoción Automática por Muestreo

**Fecha:** 2026-08-10
**Estado:** 🔍 AUDITORÍA PRE-EJECUCIÓN
**Rama:** `main` limpia · último commit `442e26b s6fin`

---

> ## ✅ CIERRE (2026-08-11)
>
> S7 está implementada. Lo que sigue es la auditoría que se hizo antes de
> empezar, conservada porque explica **por qué** cada cosa se hizo como se hizo.
> Los bloqueadores llevan marcado su estado.
>
> | Ítem | Estado |
> |---|---|
> | 7.1 Watermark | ✅ `dominio/watermark.py` |
> | 7.2 promotion_rules | ⚠️ Tabla y reglas sí; **el editor del panel no** |
> | 7.3 Validador | ✅ `casos_de_uso/promocion/validador.py` |
> | 7.4 promotion_log | ✅ Migración 007 |
> | 7.5 Job nocturno | ✅ `config/job_promotion_auto.py`, 04:00 UTC |
> | 7.6 UI manual | ✅ `Promociones.vue` + 6 endpoints + rol admin |
> | 7.7 promotion_source | ✅ Resuelto por D1 (migración 006) |
> | 7.8 Tests edge | ✅ Los 6 casos del plan |
> | 7.9 Dashboard | ✅ `PromocionesDashboard.vue` |
> | 7.10 Documentación | ✅ [PROMOTION_PROCEDURES.md](PROMOTION_PROCEDURES.md) |
>
> **Lo que queda abierto y no depende de código:**
> 1. La credencial de ModelArts da 403 → `staging_agente` vacío → todo corre
>    sobre cero ofertas. Bloquea también las etapas 1 y 3-5.
> 2. Tres de las seis reglas están apagadas por falta de datos (precio
>    histórico por producto, stock en unidades, clasificación de tienda).
> 3. El editor de reglas de 7.2 quedó sin construir: se opera por SQL.
> 4. La UI no se ha visto renderizada en un navegador.

## 🔴 RESUMEN EJECUTIVO (auditoría previa, 2026-08-10)

S7 promueve ofertas **desde** `staging_agente` **hacia** `catalogo_comercial`.

- El origen (`staging_agente`) existe en Postgres pero **tiene 0 filas y ningún código la escribe**.
- El destino (`catalogo_comercial`) **no existe**: ni tabla, ni migración, ni código. Se cortó del MVP por decisión de arquitectura ([dominio/mapa_comercial.py:4-6](dominio/mapa_comercial.py#L4-L6)).

Es decir: hoy S7 promovería **0 filas de la nada a ninguna parte**. Los ítems 7.1, 7.2, 7.3, 7.4 y 7.8 son construibles y testeables en aislamiento; 7.5, 7.6, 7.7 y 7.9 necesitan decisiones previas.

---

## 📊 ESTADO DE LA BASE DE DATOS — ✅ RESUELTO (2026-08-10)

> **Actualización:** las migraciones pendientes ya se aplicaron con
> [scripts/aplicar_migraciones_pendientes.py](scripts/aplicar_migraciones_pendientes.py).
> La BD pasó de **13 a 32 tablas + 6 vistas**. Lo que sigue documenta lo que se
> encontró y lo que se hizo.

### Lo que se encontró

`db.qjhogpbgahedpblnalvl.supabase.co` tenía 13 tablas, y tres de ellas
(`etapas_ejecucion`, `cache_llm`, `informes`) traían el esquema viejo de
`scripts/create_schema_s1.sql`, **incompatible** con el que usa el código:

| Tabla | Esquema S1 encontrado | Lo que el código usa |
|---|---|---|
| `etapas_ejecucion` | `consulta_id` → `consultas`, `resultado_json` | `ejecucion_id`, `costo_usd`, `tokens`, `cache_hit` |
| `cache_llm` | PK `id`, `tokens_in/out`, `ttl_days` | PK `clave_hash`, `respuesta_json` |
| `informes` | `consulta_id`, `pdf_url`, `titulo` | `ejecucion_id`, `usuario_id`, `ruta_storage` |

Como las migraciones usan `create table if not exists`, **habrían pasado en
verde sin alterarlas**, dejando `/consultas` y `/uso` rotos igual. Las 6 tablas
del esquema S1 estaban a 0 filas y sin una sola referencia en el código Python,
así que se eliminaron antes de aplicar 001.

### Migraciones aplicadas

| Migración | Contenido | Estado |
|---|---|---|
| `supabase/migraciones/001_esquema_s3.sql` | perfiles, ejecuciones, etapas_ejecucion, cache_llm, informes + vista `uso_mensual` | ✅ Aplicada |
| `supabase/migraciones/002_cache_hit.sql` | columna `cache_hit` | ✅ Aplicada |
| `supabase/migraciones/003_perfiles_trigger.sql` | trigger de perfil sobre `auth.users` | ✅ Aplicada |
| `supabase/migraciones/005_presupuesto_uso.sql` | presupuesto_uso, presupuesto_config + 2 vistas | ✅ Aplicada |
| `migrations/006_create_regulaciones_s4.sql` | 8 tablas de S4 | ✅ Aplicada |
| `scripts/migration_s6_alertas_tablas.sql` | 6 tablas de S6 + 2 vistas | ✅ Aplicada (con arreglo, ver abajo) |
| esquema de Procrastinate | procrastinate_jobs / _events / _periodic_defers / _workers | ✅ Aplicado |

### Bugs encontrados al aplicar

1. **`migration_s6_alertas_tablas.sql` no era ejecutable.** La vista
   `alertas_criticas_24h` hacía `EXTRACT(DAY FROM o.fecha_emitida - r.fecha_emitida)`,
   pero `fecha_emitida` es `DATE` y en Postgres `date - date` ya devuelve un
   `integer` de días, no un `interval` → `UndefinedFunction`. Corregido a la
   resta directa. **S6 nunca se pudo haber aplicado tal como estaba escrita.**
2. **`scripts/init_procrastinate.py` no creaba nada.** Afirmaba que *"las tablas
   se crean automáticamente al abrir la app"*; es falso, hay que llamar a
   `apply_schema()`. Por eso terminaba en verde con la BD vacía y el worker de S3
   nunca tuvo dónde encolar. Corregido, y con comprobación previa porque
   `apply_schema()` tampoco es idempotente (revienta con `DuplicateObject`).
3. **`config/procrastinate_config.py` ni siquiera importaba.** `@app.task()`
   recibía `max_attempts` y `schedule_in`, que no existen en procrastinate 3.9
   (`TypeError`). Sustituidos por `retry=3`, la forma actual de "1 intento + 3
   reintentos". **Ningún job de S3 llegó a registrarse nunca.**

---

## 🔌 S6 CONECTADO — ✅ (2026-08-10)

S6 estaba construido pero **ninguna de sus líneas podía ejecutarse**. Al
conectarlo salieron seis defectos, todos corregidos y verificados contra la BD:

| # | Defecto | Dónde |
|---|---|---|
| 1 | `conn = pool().connection()` sin `with` devuelve un context manager, no una conexión → `AttributeError` en `.cursor()` | los **4 endpoints** de `api/alertas.py` y las **5** funciones de `job_alert_ingest.py` |
| 2 | Consultaba `s.severity_score`; la columna de `alert_scores` se llama `score` | `api/alertas.py` (4 sitios) |
| 3 | `ORDER BY s.severity_label` sobre un `UNION ALL`: Postgres sólo admite ahí columnas del resultado | `/activas` |
| 4 | Los parámetros iban desordenados respecto a los placeholders (`[limite, severidad]` para `severidad, severidad, limite`) | `/activas` |
| 5 | El `LEFT JOIN` a `alert_scores` no filtraba por `alert_tipo`, así que un id repetido entre fuentes cruzaba scores | `/{alert_id}` |
| 6 | `/criticas` llamaba a `/activas` como función y `dias` llegaba como objeto `Query` | `api/alertas.py` |

Y en el frontend, `AlertasRetiro.vue` estaba escrito para **Vue CLI**: usaba
`process.env.VUE_APP_API_URL` (no existe en el navegador con Vite → *"process is
not defined"*), puerto 8000 en vez de 8001, y `localStorage.getItem("token")`
cuando la clave es `agroscout_token`. Reescrito sobre el cliente de `api.js`, que
es el único sitio que adjunta el token y gestiona el 401.

**Además:** `tavily-python` estaba en `requirements.txt` pero **no en
`pyproject.toml`**, que es lo que usa uv. Como el agente la importa a nivel de
módulo, `api.main` no levantaba en absoluto (`ModuleNotFoundError`). Añadida.

Verificado contra Postgres con datos de prueba: los 4 endpoints responden, el
orden por severidad y el filtro funcionan, el detalle resuelve openFDA y RASFF, y
`/{alert_id}` inexistente da 404. El frontend compila (`npm run build`) y
`app.openapi()` expone las 4 rutas.

**Pendiente de S6:** el job `job_alert_ingest` ya importa el `app` correcto y usa
bien el pool, pero no se ha ejecutado de punta a punta contra las APIs reales de
openFDA y RASFF.

---

### Verificación

Las consultas reales de `api/main.py`, `cache_postgres.py`,
`repositorio_informes_supabase.py` y `suscripciones_postgres.py` ahora resuelven
contra la BD (`uso_mensual`, `ejecuciones`, `etapas_ejecucion` con `cache_hit`,
`informes`, `cache_llm`). Antes fallaban por tabla inexistente.

> **Nota de convención (pendiente):** siguen existiendo dos directorios de
> migraciones (`migrations/` y `supabase/migraciones/`) más un `.sql` suelto en
> `scripts/`. Antes de escribir la de S7 hay que decidir cuál es el canónico.

---

## ✅❌ DEPENDENCIAS DECLARADAS POR S7

| S7 declara | Realidad |
|---|---|
| 7.2 → "DB (S1)" | ✅ Postgres + pool en [adaptadores/db.py](adaptadores/db.py) operativo |
| 7.4 → "staging_agente (S2)" | ⚠️ Tabla existe, **vacía y sin escritor** |
| 7.5 → "procrastinate (S3)" | ❌ **0 tablas `procrastinate_*` en la BD** |
| 7.6 → "UI framework (Vue 3, ya existe en v2)" | ⚠️ Vue 3 existe, pero **sin router y sin panel** |
| 7.5/7.7 → destino `catalogo_comercial` | ❌ **No existe en ninguna parte** |

---

## 🚧 BLOQUEADORES

### B1 — `catalogo_comercial` no existe (afecta 7.5, 7.7, 7.9) — ✅ RESUELTO por D1

> Zanjado el 2026-08-11: la tabla **no se crea**. Promover pasa a ser un cambio
> de estado en `staging_agente`. Ver D1 más abajo. Lo que sigue es el análisis
> que llevó a esa decisión.


No hay tabla, ni migración, ni un solo `INSERT`. Las únicas apariciones son documentación y los SVG de arquitectura. Y hay una decisión explícita en contra:

> *"Lo que la etapa escribe en `etapas_ejecucion.salida_json`. Esa fila **es** la evidencia de procedencia del mapa: por eso el plan pudo cortar la tabla `catalogo_comercial` en Postgres (§0) sin perder nada auditable."*
> — [dominio/mapa_comercial.py:1-6](dominio/mapa_comercial.py#L1-L6)

Mientras tanto [PLAN-MVP-v3.md:125-128](PLAN-MVP-v3.md#L125-L128) y todo S7 la dan por existente. **Las dos cosas no pueden ser ciertas.** O S7 crea la tabla (y se revierte esa decisión), o "promover" significa otra cosa (p. ej. marcar `promoted_at` en staging y que el mapa lo consuma desde ahí).

### B2 — Nadie escribe en `staging_agente` (afecta 7.1, 7.5, 7.6, 7.8)

[adaptadores/descubrimiento_cascada.py:138-153](adaptadores/descubrimiento_cascada.py#L138-L153) arma `staging_items` como una lista de dicts en memoria y la devuelve. El único consumidor cuenta la longitud:

```python
mapa.productos_n3_staging = cascada_metadata.productos_n3_staging   # mapear_comercio.py:88
```

No hay ningún `INSERT INTO staging_agente` en el repositorio. La cuarentena de S2 nunca se persistió.

**Y es más profundo que un `INSERT` que falte.** Tres cosas bloquean la persistencia:

1. **La cascada no se ejecuta en el flujo principal.** `api/main.py` inyecta
   `DescubrimientoSnapshot`, que sólo tiene `descubrir()`. La rama de cascada de
   [mapear_comercio.py:65](casos_de_uso/etapas/mapear_comercio.py#L65) es
   `hasattr(d.descubrimiento, 'descubrir_sync')` → **siempre falsa en producción**.
   `DescubrimientoCascada` sólo se instancia en tests y en el endpoint aparte
   `/api/discovery`.
2. **`usuario_id` no llega.** Existe en `_ejecutar` ([evaluar_insumo.py:73](casos_de_uso/evaluar_insumo.py#L73))
   pero no se propaga a `mapear_comercio` → `descubrir_sync` → `descubrir_n3`.
   La columna es `not null references auth.users(id)`, así que sin propagarlo por
   esas 4-5 firmas no hay INSERT posible.
3. **No habría qué insertar** mientras el extractor siga siendo el stub de B3.

Por eso esto no es "conectar un cable": es diseño, y depende de D1/D2.

### B3 — El agente N3 es un stub (afecta todo lo aguas abajo)

[casos_de_uso/agente/agente.py:144-146](casos_de_uso/agente/agente.py#L144-L146):

```python
# TODO(s2): Implementar llamada real a glm-5.2 con manejo de timeout
# Por ahora, retornar schema dummy para que compile
return schema
```

Devuelve la **clase** `ProductoSchema`, no una instancia con datos. Así que aunque B2 se arreglara, lo que entraría en staging no tendría `precio`, `stock` ni nada validable — y el validador de 7.3 rechazaría el 100%, que es justo el riesgo que S7 lista como hipotético.

### B4 — Procrastinate no estaba instalado en la BD (afecta 7.5) — ✅ RESUELTO

`select count(*) from pg_tables where tablename like 'procrastinate%'` daba **0**: `scripts/init_procrastinate.py` nunca creó nada porque no llamaba a `apply_schema()`, y `config/procrastinate_config.py` fallaba al importar. Ambos corregidos y el esquema aplicado (4 tablas). Ver la sección de estado de la BD.

**Queda pendiente** un bug de wiring que S7.5 copiaría si sigue el patrón de S6:

```python
# config/job_alert_ingest.py:31
from config.job_scheduling import app as procrastinate_app   # ← ImportError silencioso
```

`config/job_scheduling.py` **no define `app`**; el `procrastinate.App` está en [config/procrastinate_config.py:27](config/procrastinate_config.py#L27). El `try/except ImportError` traga el fallo, `PROCRASTINATE_AVAILABLE` queda en `False` y el periodic task de las 03:00 UTC de S6 **nunca se registró**.

### B5 — No hay panel donde colgar la UI (afecta 7.6, 7.9) — ⚠️ PARCIAL

[frontend/src/App.vue](frontend/src/App.vue) era Login → Search → Result. **No hay vue-router**, así que "new page Promociones" sigue sin un sitio propio al que ir.

El dashboard de S6, que estaba desconectado de punta a punta, ya está montado
(2026-08-10): router en `api/main.py`, `AlertasRetiro.vue` en `App.vue` detrás de
una pestaña, y el componente pasando por el cliente de `api.js`. Ver la sección
de S6 más abajo.

**Para S7 sigue en pie la decisión D3:** con dos pantallas, las pestañas de
`App.vue` bastan; a la tercera (Promociones) conviene decidir si entra vue-router
o se espera al panel de S8.

### B6 — No existe rol admin (afecta 7.6)

S7.6 pide *"Botón Promover (admin only)"*. [api/main.py:174-213](api/main.py#L174-L213) verifica el JWT y devuelve el payload; **ningún endpoint chequea rol**. No hay `is_admin`, ni claim de rol, ni tabla de roles. La UI de promoción manual sería operable por cualquier usuario autenticado.

---

## 🔍 AUDITORÍA ÍTEM POR ÍTEM

| Ítem | Viable hoy | Nota |
|---|---|---|
| **7.1** Watermark binario | ✅ Sí | Función pura + tabla de log. Sin dependencias reales. Único cuidado: el hash de `sha256` es determinista entre procesos (a diferencia de `hash()`), el pseudocódigo del plan está bien. |
| **7.2** `promotion_rules` + editor | ⚠️ Backend sí, UI no | Tabla y DSL JSON son directos. El "Panel CITE: UI para editar reglas" choca con B5. |
| **7.3** Validador anti-garbage | ⚠️ Parcial | Ver tabla de reglas abajo: 3 de 5 reglas no tienen datos de entrada. |
| **7.4** `promotion_log` | ✅ Sí | Tabla + índices. El "trigger automático al promover" depende de B1 (¿trigger sobre qué tabla?). |
| **7.5** Job nocturno | ❌ Bloqueado | B1 (destino) + B2/B3 (origen vacío) + B4 (procrastinate). |
| **7.6** UI promoción manual | ❌ Bloqueado | B5 (sin router/panel) + B6 (sin admin) + B2 (nada que listar). |
| **7.7** `promotion_source` en catálogo | ❌ Bloqueado | B1. Además `n1_direct`/`n2_direct` asume que N1/N2 escriben al catálogo, cosa que tampoco ocurre. |
| **7.8** Tests de edge cases | ✅ Sí | Contra el validador de 7.3 con fixtures sintéticas; no necesita BD ni datos reales. |
| **7.9** Dashboard promociones | ❌ Bloqueado | B5. |
| **7.10** `PROMOTION_PROCEDURES.md` | ✅ Sí | Depende de lo que efectivamente se construya. |

---

## ⚖️ LAS REGLAS DE 7.2 vs. LOS DATOS QUE HAY

El DSL propuesto pide cinco cosas. Esto es lo que el sistema puede alimentar hoy:

| Regla | Dato requerido | ¿Existe? |
|---|---|---|
| `price_range.min/max_pct_of_historical` | Precio histórico **por producto** | ❌ Solo hay `tendencias_insumo` y `shelf_facts.duckdb`, agregados **por insumo/trimestre**. No hay serie por oferta. |
| `stock.min_units` | `producto_json->>'stock'` | ⚠️ El campo existe en `ProductoSchema`, pero el extractor es stub (B3) → siempre `null` → rechazo del 100%. |
| `url_validity.check_200_ok` | HTTP GET a `fuente_url` | ✅ Viable, pero mete red en el job. Con rate-limiting ya existe [casos_de_uso/integraciones](casos_de_uso/integraciones/). Ojo al SLA de 15 min. |
| `date_freshness.max_days_old` | `staging_agente.creado_en` | ✅ Existe. Es la única regla enteramente servible hoy. |
| `tienda_class.exclude: [marketplace]` | Clasificación de tienda | ❌ `ProductoSchema` no tiene campo tienda. Solo `fuente_url`; habría que derivar el dominio y clasificarlo (existe `tiendas.xlsx`, no cargado en Postgres). |

**Conclusión:** el validador se puede escribir completo, pero 3 de 5 reglas tendrían que arrancar desactivadas (`activo=false`) o el 80% automático rechazaría todo.

---

## 🔁 SOLAPAMIENTOS Y CONTRADICCIONES

1. **7.6 vs 8.6** — S8.6 "PROMOVEDOR MANUAL DE OFERTAS" repite S7.6 casi literal (listar watermark=false, bulk select, mostrar validation_errors) y se declara dependiente de *"S7 parcial"*. Hay que decidir el reparto o duplicaremos trabajo de UI.
2. **7.9 vs 8.1/8.4** — El dashboard de promociones de S7.9 es un widget del mismo panel que S8 construye entero.
3. **`catalogo_comercial`** — [PLAN-MVP-v3.md](PLAN-MVP-v3.md) la asume; [dominio/mapa_comercial.py](dominio/mapa_comercial.py) documenta que se cortó a propósito. Contradicción abierta desde S2.
4. **20% manual "no es pesado"** — la nota final de S7 dice *"27 offers/noche = ~1 min de review"*. Con `staging_agente` a 0 filas y el agente en stub, el volumen real es 0.

---

## ❓ DECISIONES QUE NECESITO ANTES DE ESCRIBIR CÓDIGO

**D1 — ¿Qué es "promover"?** ✅ **RESUELTO (2026-08-11): opción (b).**

Promover es **marcar la fila en `staging_agente`**, no moverla a otra tabla.
`catalogo_comercial` no se crea: se respeta el corte de §0 documentado en
[dominio/mapa_comercial.py:4-6](dominio/mapa_comercial.py#L4-L6).

```sql
update public.staging_agente
   set promoted_at      = now(),
       no_verificado    = false,
       promotion_source = 'auto_watermark'   -- o 'manual_human'
 where staging_id = ...;
```

Implementado en
[supabase/migraciones/006_promotion_source.sql](supabase/migraciones/006_promotion_source.sql):

- Columna `promotion_source` en `staging_agente`.
- `staging_promotion_source_valido`: sólo `auto_watermark` o `manual_human`.
  S7.7 listaba además `n1_direct` y `n2_direct`, pero por la cuarentena sólo
  pasa N3 — un producto del snapshot o de Bright Data no entra en
  `staging_agente`, así que serían estados imposibles.
- `staging_promocion_coherente`: `promoted_at` y `promotion_source` van juntos
  o no van. Sin esto, el "¿qué % es auto-promovido?" de 7.7 se calcularía sobre
  un campo que puede quedar a null por descuido.
- Vista `staging_promovido`, contraparte de `staging_pendiente`: es de donde el
  mapa comercial debe leer lo ya promovido.

Verificado: los seis estados posibles se aceptan o rechazan como corresponde.

**Consecuencias para el resto del plan:**

| Afectado | Qué cambia |
|---|---|
| 7.5 (job) | El paso "mover a `catalogo_comercial`" es un `UPDATE` sobre staging. Más simple de lo planeado. |
| 7.7 | `promotion_source` vive en `staging_agente`, con dos valores en vez de cuatro. |
| 7.4 (`promotion_log`) | Su FK a `staging_id` ya tiene destino; no hace falta inventar un id de catálogo. |
| S5 (dedup por EAN) | **Sigue asumiendo `catalogo_comercial`.** Cuando se retome, habrá que decidir si deduplica sobre staging promovido. |
| S8.6 | La UI lista y promueve filas de `staging_agente`; no cambia. |

**D2 — ¿Poblamos `staging_agente` de verdad, o trabajamos con fixtures?**
- (a) Arreglar B2 + B3 (persistir la cascada N3 + implementar el extractor glm-5.2). Es trabajo de S2 que quedó abierto, ~1.5 días extra, pero sin él S7 no tiene insumo.
- (b) Sembrar filas sintéticas con un script y dejar S7 verificable end-to-end sobre datos de prueba, documentando la deuda.

**D3 — ¿UI en S7 o toda en S8?** Recomiendo: **backend + API en S7 (endpoints listos y probados), UI entera en S8** con router y panel de una vez. Evita construir dos veces la misma página y no bloquea S7 con B5/B6.

**D4 — ¿Aplicamos las migraciones pendientes de S4 y S6?** ✅ **HECHO** (2026-08-10). Ver la sección de estado de la BD.

**D5 — ¿Instalamos el esquema de procrastinate?** ✅ **HECHO** (2026-08-10). Queda pendiente el import roto de `config/job_alert_ingest.py:31`, que es wiring de S6.

---

## 🎯 PLAN DE FASES PROPUESTO (sujeto a D1-D5)

```
FASE 0 · Desbloqueo (0.5-1 día)
  0.1 Decidir D1 y D2
  0.2 Aplicar migraciones pendientes + esquema procrastinate  [D4, D5]  ✅ HECHO
  0.3 Arreglar import de job_alert_ingest.py:31 y montar api/alertas.py  ✅ HECHO
  0.4 Sembrar staging_agente (fixtures o pipeline real)       [D2]

FASE 1 · Núcleo determinista (1 día)  ← sin bloqueadores, se puede empezar ya
  1.1 watermark(offer_id, seed) + seed semanal + promotion_watermark_log   [7.1]
  1.2 Tests de determinismo y distribución 80/20                           [7.1]

FASE 2 · Reglas y validador (1.5 días)
  2.1 Migración promotion_rules + promotion_log                 [7.2, 7.4]
  2.2 Reglas base pre-pobladas (las no servibles, activo=false) [7.2]
  2.3 Validador + promotion_validation_log                      [7.3]
  2.4 6 casos de edge cases en verde                            [7.8]

FASE 3 · Job de promoción (1.5 días)
  3.1 job_promotion_auto 04:00 UTC + registro en eventos_job    [7.5]
  3.2 promotion_source según lo decidido en D1                  [7.7]
  3.3 Test de SLA (< 15 min)

FASE 4 · API + docs (1 día)
  4.1 Endpoints REST de promoción (listado 20%, promover, rechazar, stats)
  4.2 PROMOTION_PROCEDURES.md                                   [7.10]
  UI queda para S8                                              [D3]
```

---

## ✨ CONCLUSIÓN

**S7 NO es ejecutable tal como está escrita.** El 40% de sus ítems (7.5, 7.6, 7.7, 7.9) depende de infraestructura que no existe.

**Lo que sí se puede empezar hoy sin ninguna decisión previa:** 7.1 (watermark), 7.2 (tablas), 7.3 (validador), 7.4 (promotion_log) y 7.8 (tests). Son ~3 días de los 5, y son la parte con valor propio: quedan como piezas puras y testeables al margen de cómo se resuelva D1.

**Complejidad real:** MEDIA-ALTA — no por S7 en sí (que es simple), sino por la deuda acumulada de S2 (staging sin escritor, agente stub) y por tres semanas de migraciones sin aplicar.

---

**AUDITORÍA COMPLETA. ESPERANDO D1-D5 PARA ARRANCAR.**
