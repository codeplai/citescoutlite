# TIER 5 (S3) COMPLETADO — Separación de las etapas 4 y 5

**Fecha:** 2026-08-02
**Semana:** 3 · **Duración:** ~4 h
**Status:** ✅ 6/6 del DoD — **P02 verde**

> Existe un `TIER5-COMPLETADO.md` de la Semana 2 (búsqueda optimizada, gate P03).
> Este archivo es el TIER 5 de la Semana 3 y no lo sustituye.

---

## Por qué este tier no era opcional

`PLAN-MVP-v2.md` §7 ponía esta separación en la **Semana 1** y no se hizo. Hasta hoy,
`InsightDeMercado` era un solo objeto:

```python
class InsightDeMercado(BaseModel):
    cobertura: Literal["baja", "media", "alta"]
    resumen: str
    hipotesis_formulacion: str        # <- "etapa 4"
    verificacion_regulatoria: str     # <- "etapa 5"
    formatos_comunes: list[str]
    citas: list[str]
```

Los dos campos premium salían de **la misma llamada al modelo** que el resumen gratuito.
Con esa forma el paywall no se puede implementar honestamente: el token de la formulación
se paga siempre y "ocultarla" es recortar un string ya generado. Además, el contexto
regulatorio se armaba **fuera** del envoltorio `etapa()`, así que las consultas a openFDA
y al RAG —la parte cara— no se auditaban, no se cacheaban y no tenían costo asignado.

---

## Tareas ejecutadas

### ✅ T5.1 · Tres contratos donde había uno

| Archivo | Etapa | Plan | Contenido |
|---|---|---|---|
| [dominio/insight_mercado.py](dominio/insight_mercado.py) | 3 | gratuito | `cobertura`, `resumen`, `formatos_comunes`, `citas`, `nota_regulatoria` |
| [dominio/hipotesis_formulacion.py](dominio/hipotesis_formulacion.py) | 4 | premium | `hipotesis`, `ingredientes_probables`, `procesos_sugeridos`, `citas` |
| [dominio/dossier_regulatorio.py](dominio/dossier_regulatorio.py) | 5 | premium | `restricciones`, `citas: list[CitaRegulatoria]`, `sin_dato` |

`CitaRegulatoria` lleva `texto`, `fuente`, `url` y `fecha`. No es adorno: es exactamente
lo que diferencia el párrafo gratuito del dossier de pago.

**Decisión sobre D4 — la `nota_regulatoria` gratuita es orientativa y sin corpus.** El
prompt de la etapa 3 le **prohíbe** citar normas, números de artículo o URLs, y le exige
decir que hace falta verificar con la norma vigente. Dos razones:

1. Si el plan gratuito ya trajera fuentes verificables, el dossier premium no añadiría
   nada y el paywall no tendría sustancia.
2. El RAG normativo hace `encode` + búsqueda vectorial en LanceDB. Armar contexto en la
   etapa 3 **y** en la 5 lo ejecutaría dos veces por run premium.

### ✅ T5.2 · Etapa 4 — [casos_de_uso/etapas/formular_hipotesis.py](casos_de_uso/etapas/formular_hipotesis.py)

Ingeniería inversa de la formulación a partir de los productos del snapshot. Al pasar por
`etapa()` obtiene cache, auditoría, modelo y **costo propio**.

El prompt obliga a que cada afirmación se apoye en los productos aportados y a declarar
cuándo los datos no bastan, en vez de rellenar con conocimiento general.

### ✅ T5.3 · Etapa 5 — [casos_de_uso/etapas/verificar_regulacion.py](casos_de_uso/etapas/verificar_regulacion.py)

El armado del contexto regulatorio se movió **dentro** de la etapa. Consecuencias, todas
buscadas:

- entra en la clave de cache → un segundo run idéntico no vuelve a embeber ni a buscar;
- queda en `etapas_ejecucion` con su duración y su costo;
- sin corpus aplicable devuelve `sin_dato=True`, no un error. *Degrada a "sin dato",
  nunca a error*, como manda el ADR.

El prompt prohíbe inventar normas, secciones o URLs y obliga a usar solo lo que venga en
el contexto. **Verificado en vivo:** contra "cáscara de cacao" el dossier respondió *"no
existe norma específica del 21 CFR que regule directamente la cáscara de cacao; aplican
únicamente normas sanitarias generales"* — y citó las dos normas DIGESA que sí estaban en
el corpus.

### ✅ T5.4 · Numeración `TEXT` — adelantada a TIER 3

El `check` de [001_esquema_s3.sql](supabase/migraciones/001_esquema_s3.sql) solo admite
`'1','2a','2b','3','4','5','6'`, así que la renumeración de `int` a `str` hubo que hacerla
en T3 o escribir un shim que luego se borraría. También se adelantó desde aquí el arreglo
del cost-meter (claves de tarifa con prefijo `openai/`), porque estrenar `glm-5.2` con un
medidor que marcaba cero no tenía sentido.

**La etapa 2 es `'2a'`, no `'2'`.** El histórico migrado son búsquedas sobre el snapshot,
que es la definición de `2a` en D6; admitir los dos valores reintroduciría la ambigüedad
que D6 viene a cerrar.

### ✅ Dos composiciones — [casos_de_uso/evaluar_insumo.py](casos_de_uso/evaluar_insumo.py)

```python
async def generar_mapa_comercial(texto, d, usuario_id)  # 1 · 2a · 3
async def generar_dossier(texto, d, usuario_id)         # + 4 · 5
```

Dos composiciones, no una con banderas: el paywall se resuelve componiendo casos de uso,
no filtrando campos de un objeto ya generado (ADR-001 §2.4).

Quien elige entre las dos es **T6.2**, según el entitlement. Hasta entonces la API llama a
`generar_dossier`, que es lo que hacía antes de S3: **T5 cambia cómo se produce el
informe, no quién lo recibe.**

### ✅ El informe recibe tres objetos opcionales

`InformeScout` gana `insight`, `hipotesis` y `dossier`, de modo que la SPA recibe datos
estructurados y no solo markdown (lo que T7.1 necesita para la tarjeta de paywall).

En el informe gratuito, las dos secciones premium no quedan vacías: la plantilla pone el
bloque de paywall.

```
### 🧪 Hipótesis de Formulación e Ingeniería Inversa
_Esta sección requiere el plan premium: la ingeniería inversa de la formulación
no se generó para este informe._

### ⚖️ Dossier Regulatorio
_Esta sección requiere el plan premium: el dossier con citas verificables
no se generó para este informe._

> **Nota regulatoria orientativa.** Los productos que combinan cacao y quinua
> suelen requerir registro sanitario del producto terminado, etiquetado
> nutricional obligatorio y cumplimiento de buenas prácticas de manufactura...
```

---

## DoD de TIER 5

| Ítem | Resultado |
|---|---|
| Run premium → 5 filas `'1','2a','3','4','5'` | ✅ |
| Las 5 con `modelo` no nulo y `costo_usd > 0` en las 4 filas LLM | ✅ |
| Run gratuito → 3 filas; ninguna llamada al modelo de etapa 4 | ✅ |
| Segundo run idéntico → 0 llamadas LLM (**P02**) | ✅ |
| `contratos/` regenerado con los 3 esquemas nuevos | ✅ 7 modelos |
| Golden set de S2 sigue 5/5 | ✅ |

```
run PREMIUM (cache frío)
   etapa=1   deepseek-v4-flash   $0.000262    873 tokens   cache=False
   etapa=2a  sync                $0.000000      0 tokens   cache=False
   etapa=3   glm-5.2             $0.087500   7542 tokens   cache=False
   etapa=4   glm-5.2             $0.103330   8249 tokens   cache=False
   etapa=5   glm-5.2             $0.042790   2822 tokens   cache=False

run PREMIUM repetido → las 4 etapas LLM con cache_hit=True, 0 tokens   ← P02
run GRATUITO         → 3 filas; hipotesis=None, dossier=None
```

Sin regresión: **suite 18/18**, **golden set 5/5**.

---

## El número que hay que resolver antes de TIER 6

**Un run premium en frío cuesta US$ 0,2339.** Contra los topes ya declarados en `.env`:

| Variable | Valor | Runs que permite |
|---|---|---|
| `PRESUPUESTO_RUN_USD` | 0,25 | **1,1** — un solo run consume el 94% del tope |
| `PRESUPUESTO_USUARIO_MES_USD` | 2 | 8,6 al mes por usuario |
| `PRESUPUESTO_GLOBAL_MES_USD` | 10 | **42,8 al mes para toda la institución** |

Esos topes se escribieron cuando la etapa 3 apuntaba a `glm-5.0`. Con aquella tarifa el
mismo run habría costado **US$ 0,0218 — once veces menos**. El salto no lo causan las
etapas nuevas sino el precio por token de `glm-5.2` (0,010/0,020 frente a
0,000539/0,002965).

El motor del coste es el tamaño de la entrada: las etapas 3 y 4 reciben **~6.200 tokens
cada una**, porque se les manda el JSON completo de los 30 productos.

**Tres palancas, por orden de coste-beneficio:**

1. **Etapa 4 a `deepseek-v4-flash`.** Es deducción sobre datos ya dados, no redacción
   fina. Ahorra ~US$ 0,10 por run: el 44% del total.
2. **Recortar el payload de productos** que se manda a 3 y 4 (top-10 en vez de 30, o podar
   campos). Ataca los ~12.500 tokens de entrada.
3. **Subir los topes**, si se decide que la calidad de `glm-5.2` vale ese precio.

Sin una de las tres, el kill-switch de T6.3 salta a los 43 runs y **P12 daría verde por la
razón equivocada**.

---

## Deuda que queda abierta

| # | Deuda | Dónde se cierra |
|---|---|---|
| 1 | Los presupuestos de `.env` no reflejan el coste real (arriba) | Decisión antes de T6.3 |
| 2 | `manifest.json` declara `version_taxonomia = "0.1"` pero todos los datos usan `"2026-07"`. La API corre con `"0.1"`, así que **ningún run acierta en las 47 entradas de cache migradas** y `ejecuciones.snapshot_version` queda sin corresponder a ningún dataset | Una línea, pero decidir cuál de los dos valores es el bueno |
| 3 | La etapa 4 no hace la **minería DuckDB real** que pide `PLAN-MVP-v2.md` §7: deduce solo del JSON de productos de la etapa 2a | S4 |
| 4 | `informe_weasyprint.py` ya no usa WeasyPrint (genera con xhtml2pdf desde T3). El nombre engaña | Renombrado barato en T7 |
| 5 | `generar_insight` y `generar_insight_parcial` son la misma función; se conservan los dos nombres por compatibilidad | Limpieza en T7 |

---

## Estado de la Semana 3

| Tier | Estado |
|---|---|
| T1 · Entorno | ✅ RTT p95 114 ms · JWKS ES256 · bucket privado |
| T2 · Esquema y migración | ✅ 5 tablas + RLS · 54/94/47 |
| T3 · Adaptadores + Storage | ✅ sobrecoste 642 ms |
| **T5 · Separación de etapas** | ✅ **este documento** |
| T4 · Auth Supabase | ⬜ (T4.4 estructuralmente hecho) |
| T6 · Paywall, cuotas, kill-switch | ⬜ |
| T7 · Frontend, cierre, ensayo | ⬜ |

**Lo que T5 desbloquea:** el paywall de T6 ya tiene sobre qué operar. Un run gratuito
ejecuta 3 etapas y uno premium 5, con costo propio cada una y sin generar jamás el token
de la formulación para quien no la paga.
