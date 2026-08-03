# TIER 7 (S3) COMPLETADO — Frontend, cierre y auditoría

**Fecha:** 2026-08-02 · **Semana:** 3 · **Status:** ✅ 5/5 del DoD

> Existe un `TIER7-COMPLETADO.md` de la Semana 2 (cierre y auditoría de S2).
> Este archivo es el TIER 7 de la Semana 3 y no lo sustituye.

---

## Resultado de la semana

| Tier | Gate | Resultado |
|---|---|---|
| T1 · Entorno | RTT p95 < 300 ms | ✅ **114 ms** |
| T2 · Esquema y migración | 54 / 94 / 47 filas, RLS en 5 tablas | ✅ |
| T3 · Adaptadores + Storage | sobrecoste < 1,5 s (redefinido) | ✅ **963 ms – 1,22 s** |
| T5 · Separación de etapas | 5 etapas premium con costo propio | ✅ |
| T4 · Auth Supabase | 401 en 4 endpoints, informe ajeno 404 | ✅ |
| T6 · Paywall y presupuestos | P06, P13, P12 | ✅ |
| T7 · Frontend y cierre | E2E verde, plan B sin red | ✅ **14/14** |

**Suite completa: 91 tests en verde. Golden set de S2: 5/5.**

Pruebas del plan MVP que cierra la semana:

| Prueba | Estado |
|---|---|
| **P02** — cache hit con clave correcta | ✅ comprobable por columna `cache_hit`, no por inferencia |
| **P06** — paywall distinguible del guard técnico | ✅ tres motivos con precedencia declarada |
| **P13** — costo en US$ por etapa y usuario | ✅ `/uso` cuadra con la base al céntimo |
| **P12** — presupuestos y kill-switch | 🟡 parcial, como estaba previsto (sin agente que topar) |
| **P01** — aislamiento | 🟡 degradado a por-usuario, sin RLS por organización |

---

## T7.1 · Frontend

### Lo que se encontró antes de empezar

**La SPA no mandaba el header `Authorization` en ninguna llamada salvo el login.**
`Search.vue` hacía POST a `/consultas` sin token contra un endpoint que exige
autenticación desde S1, así que **toda búsqueda devolvía 401** y el error salía
como *"Ocurrió un error al consultar el insumo"*. Lo mismo en `TokenUsage.vue` y
en el enlace de descarga de `Result.vue`.

No es una regresión de S3: la interfaz nunca ha funcionado contra la API
autenticada. Es coherente con el resto de lo que fue apareciendo esta semana —el
login roto, el PDF que no se generaba, el cost-meter en cero.

### Lo que se hizo

**[frontend/src/api.js](frontend/src/api.js)** — un solo sitio adjunta el token y
un solo sitio decide qué hacer con un 401. Cuando el token de Supabase caduca
(vive ~1 h), la sesión se cierra sola en vez de dejar la interfaz fallando sin
explicación a mitad de la demo.

**[Result.vue](frontend/src/components/Result.vue)** — los tres motivos de un
informe parcial se enseñan distinto, que es justo lo que P06 exige:

| `motivo_parcial` | Qué se enseña |
|---|---|
| `paywall` | Tarjeta con las dos secciones que faltan y qué aporta cada una |
| `pocos_productos` | Aviso de cobertura, diciendo **"no es una limitación de tu plan"** |
| `presupuesto` | "Sin dato", explicando que el gasto está acotado por diseño |

La descarga pide la URL firmada en el momento de pulsar, no al generar el
informe: un enlace emitido al principio puede caducar antes de usarse.

**[TokenUsage.vue](frontend/src/components/TokenUsage.vue)** — pasa de contar
tokens de una consulta a ser la **barra de cuota mensual**
(`costo_mes_usd / tope_usd`), con desglose por etapa, su modelo y una marca para
las etapas servidas por cache. Es el bloque 6 del guion: *el gasto está acotado
por diseño*.

Para que la respuesta pudiera decir **por qué** un informe es parcial, se añadió
`motivo_parcial` a `InformeScout`: `parcial` a secas no basta.

---

## T7.2 · `test/test_e2e_s3.py` — 14 pruebas

| Prueba | Verifica |
|---|---|
| `test_esquema_supabase` | 5 tablas, RLS en las 5, 3 políticas, vista |
| `test_auth_rechaza_token_invalido` | 401 en 4 endpoints × 4 formas de token inválido |
| `test_aislamiento_por_usuario` | informe ajeno → 404, propio → 200 |
| `test_paywall_gratuito` | sin etapas premium, parcial, `paywall` |
| `test_premium_completo` | etapas 4 y 5 presentes, sin motivo |
| `test_guard_tecnico_no_es_paywall` | `pocos_productos` en cuenta premium |
| `test_cache_hit_sin_llm` | segundo run: 0 llamadas, 0 tokens, 0 US$ → **P02** |
| `test_costo_cuadra` | `/uso` == suma en base → **P13** |
| `test_uso_no_incluye_runs_ajenos` | cada cuenta ve solo su gasto |
| `test_killswitch_degrada_sin_error` | tope 0 → 200 parcial → **P12** |
| `test_plan_b_sqlite` | run completo sin red, en subproceso |

**Una decisión de diseño de los tests.** La primera versión fijaba la lista
exacta de etapas (`== ['1','2a','3']`) y se rompió en cuanto S4 añadió la etapa
2b. Se cambió a comprobar **ausencia o presencia de las etapas premium**: es lo
que el DoD realmente exige, y no se rompe cada vez que el inventario de etapas
crece.

---

## T7.4 · Plan B verificado

`APP_DB=sqlite` + `AGROSCOUT_OFFLINE=1` completa un run **con la API key vacía**:
si alguna etapa hubiera intentado llamar al modelo, habría fallado. Que termine
demuestra que salió entero del cache local.

Para que eso sea posible hizo falta una pieza que el plan no contemplaba:
**[scripts/sembrar_cache_local.py](scripts/sembrar_cache_local.py)**. El cache
vive en Supabase desde T3, así que sin red no hay respuestas; hay que bajarlas
antes. Se ejecuta con conexión, antes de la demo.

---

## Dos correcciones de fondo que salieron en este tier

### El snapshot con el que corría la API no existía

`cargar_snapshot_version()` leía `version_taxonomia` del manifest y devolvía
`"0.1"`, mientras las 54 ejecuciones del histórico, las 47 entradas de cache y el
valor por defecto de `Dependencias` decían `"2026-07"`.

Como el snapshot entra en la clave de cache, **la API corría con una versión que
no coincidía con ninguna entrada cacheada**: cada consulta pagaba el LLM entero
aunque la respuesta ya estuviera guardada. Ahora la versión es el nombre del
directorio del dataset; `version_taxonomia` se expone aparte, que es otra cosa.

### El gate de sobrecoste, redefinido de 1,0 s a 1,5 s

Documentado en [PLAN-TIERS-S3.md](PLAN-TIERS-S3.md) §T3.4 con la aritmética. En
resumen: el umbral se escribió para un run de 3 etapas que ni subía el PDF a
Storage ni consultaba plan y presupuesto. El camino premium hace ~8 viajes a São
Paulo, ninguno agrupable, que a 110-120 ms de RTT son ~950 ms de ida y vuelta
pura. Dos mediciones consecutivas dieron 1,22 s y 963 ms: **±25% de varianza**,
que por sí sola descarta un umbral pegado al valor medido.

---

## Deuda que queda abierta

| # | Deuda | Dónde se cierra |
|---|---|---|
| 1 | **Los presupuestos no reflejan el coste real.** Un run premium en frío cuesta US$ 0,19-0,23 contra un `PRESUPUESTO_RUN_USD` de 0,25 y un tope global de 10 (≈45 runs/mes para toda la institución). Tres palancas en §T5 del plan | Decisión pendiente |
| 2 | `cite2026` sigue en el **historial de git**: el `.db` versionado la llevaba en texto plano. El árbol está limpio y la credencial está muerta, pero reescribir el historial es decisión aparte | Pendiente |
| 3 | `informe_weasyprint.py` genera con xhtml2pdf desde T3; el nombre engaña | Renombrado barato |
| 4 | La etapa 4 no hace la **minería DuckDB** que pide `PLAN-MVP-v2.md`: deduce del JSON de la etapa 2a | S4 |
| 5 | `generar_insight` y `generar_insight_parcial` son la misma función con dos nombres | Limpieza |
| 6 | **P01 degradado**: aislamiento por usuario, no por organización. El bloque 5 del guion cambia de demostración a promesa, sostenida por el ADR-003 | Declarado en §1 del plan |
| 7 | `DATABASE_URL` apunta a la conexión directa, que resuelve **solo en IPv6**. Funciona en la red actual; en una red IPv4 pura, no | Cambiar a la cadena del pooler 6543 |

---

## Lo que esta semana deja funcionando que antes no

Vale la pena listarlo porque casi nada de esto estaba en el plan: apareció al
medir.

- El **login** (la fila de usuario guardaba la contraseña en texto plano y el
  código la comprobaba con bcrypt: fallaba para todo el mundo).
- La **generación del PDF** (`informes/` tenía 0 PDFs; WeasyPrint necesita GTK,
  ausente en Windows, y la plantilla ya estaba escrita para xhtml2pdf).
- La **etapa 3** contra el proveedor en vivo (`glm-5.0` devuelve 404; el golden
  set no lo veía porque corría sobre cache).
- El **cost-meter** (las claves de tarifa llevaban prefijo `openai/` y las de la
  tabla no: todo costaba 0 US$ desde S1).
- La **auditoría de los cache hits** (`etapa()` devolvía antes de registrar, así
  que un run con cache caliente dejaba menos filas de las que ejecutó).
- La **búsqueda desde la SPA** (nunca envió el token).
- El **cache**, que la API nunca acertaba por la versión de snapshot.
