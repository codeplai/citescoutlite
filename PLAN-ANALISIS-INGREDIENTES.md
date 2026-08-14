# PLAN — Análisis de ingredientes por mercado (US · Codex · UE)

**Fecha:** 2026-08-13 · **Estado:** propuesta para desarrollo
**Entrada de diseño:** [validacion_aditivos_mercados.md](validacion_aditivos_mercados.md)
(extracto de `acido1.pptx` y `acido2.pptx`)
**Alcance:** columna nueva en la tabla del mapa comercial → botón por fila → pestaña
de análisis regulatorio del producto en tres mercados de exportación.

---

## 0. Qué se construye, en una frase

Cada fila del mapa comercial gana una columna **Análisis** con un botón que abre una
pestaña nueva; esa pestaña toma los aditivos ya leídos de la etiqueta de ese producto y
responde, aditivo por aditivo y con cita verificable, si está **autorizado en Estados
Unidos, en el Codex y en la Unión Europea**, con qué límite, y cuál es el límite más
estricto que habría que adoptar para formular una sola vez y vender en los tres.

### Las dos decisiones que mandan sobre todo lo demás

**(a) El veredicto no es del aditivo, es del par (aditivo × categoría de alimento).**

Los dos PPTX de referencia lo enseñan dos veces. El ácido sórbico no está prohibido en la
UE: está autorizado, pero la categoría que lo autoriza (04.2.4.1) *excluye purés*, y el
producto era pulpa de maracuyá → `NO*`. El EDTA sale `SÍ` limpio en EE. UU. porque
§172.120 **nombra los pepinos encurtidos**, y `SÍ*` en Codex porque solo hay cobertura por
categoría general. **El asterisco es un estado de datos de primera clase**, no un adorno.

**(b) Esto va por agente y búsqueda en vivo, no por tabla congelada — pero solo donde la
fuente lo permite.**

Se sondearon las tres fuentes el 2026-08-13 (§1.3) y **no se parecen en nada**: una tiene
API de búsqueda, otra es un documento único de 3,4 MB, y la tercera prohíbe el rastreo en
su `robots.txt`. Un solo mecanismo para las tres sería malo para dos de ellas. El plan usa
**tres mecanismos, uno por mercado**, y esa asimetría es el corazón del diseño.

---

## 1. De qué se parte (medido, no estimado)

### 1.1 Lo que ya está construido y sirve

| Pieza | Dónde | Estado |
|---|---|---|
| Lectura de aditivos de la etiqueta | [etl/analizar_ingredientes.py](etl/analizar_ingredientes.py) | ✅ 50 patrones → nombre canónico + nº E |
| Aditivos e ingredientes en el contrato | [dominio/producto_en_mercado.py:51](dominio/producto_en_mercado.py#L51) | ✅ `aditivos`, `lista_ingredientes` |
| Tabla del mapa comercial + modal | [frontend/src/components/Result.vue:100](frontend/src/components/Result.vue#L100) | ✅ 6 columnas, paginada |
| Rutas con URL propia y guard de rol | [frontend/src/router/index.js](frontend/src/router/index.js) | ✅ vue-router |
| Contrato de cita con URL + `sin_dato` | [dominio/dossier_regulatorio.py](dominio/dossier_regulatorio.py) | ✅ |
| **Agente web** (Tavily/Brave + GLM) | [casos_de_uso/agente/agente.py](casos_de_uso/agente/agente.py) | ✅ probado en góndola DE/CH |
| **Grounding check** (el valor tiene que estar literalmente en el HTML) | [casos_de_uso/agente/grounding_check.py](casos_de_uso/agente/grounding_check.py) | ✅ **es la pieza que hace esto defendible** |
| Descargador eCFR contra la API oficial | [adaptadores/descargador_ecfr.py](adaptadores/descargador_ecfr.py) | ✅ código listo, nunca ejecutado en serio |
| Web Unlocker ante 403 | [adaptadores/desbloqueo_brightdata.py](adaptadores/desbloqueo_brightdata.py) | ✅ configurado (`BRIGHT_DATA_ZONE=web_api_ai`) |

**El snapshot da la entrada gratis:** 29.054 productos, **100 % con texto de ingredientes**,
y **14.572 filas (50,2 %) llevan al menos un aditivo reconocido**.

### 1.2 Lo que NO existe, aunque la documentación diga que sí

> ⚠️ **[REGULATORY_METHODOLOGY.md](REGULATORY_METHODOLOGY.md) declara «4100+ regulaciones de
> 5 fuentes» y hoy eso es falso.** Las tablas existen; están vacías.

Conteo contra el Postgres de Supabase, 2026-08-13:

```
ecfr_regulations  0   efsa_regulations  0   codex_standards  0
inacal_nts        0   digesa_directivas 0   regulacion_cita  0
```

Lo único con contenido es el índice RAG `vectores/regulatorio.lance`: **734 pasajes** = 702
eCFR (336 secciones: partes 184, 145, 182, 146, 150) + 32 DIGESA. **Cero Codex, cero UE.**
Y le falta la parte **172** del CFR, que es donde vive medio catálogo de aditivos —
incluido el EDTA del caso 2.

Conclusión: **no hay corpus sobre el que apoyarse.** Hay que ir a buscarlo.

### 1.3 Sonda de las tres fuentes — 2026-08-13

Mismo método que dio el conector alemán: probar antes de diseñar.

| Mercado | Fuente probada | Resultado | Mecanismo que impone |
|---|---|---|---|
| 🇺🇸 **EE. UU.** | `ecfr.gov/api/search/v1/results` | **200, JSON estructurado.** `"calcium disodium EDTA"` → 29 resultados, **el primero es 21 CFR §172.120** | **Agente en vivo** |
| 🇪🇺 **UE** | EUR-Lex `CELEX:32011R1129` | **200, 3,38 MB, 602 tablas.** Contiene `E 200`, la categoría `04.2.4` y `sorbic` | **Ingesta única + consulta local** |
| 🌍 **Codex** | `fao.org/gsfaonline/*` | **403 Cloudflare** (`"Just a moment..."`) con UA de navegador. Bright Data **también lo rechaza**: `robots.txt` trae `Disallow: /*?id=*` y el Web Unlocker exige KYC para saltarlo | **Curación manual — no se rastrea** |

Tres cosas que esta tabla decide:

1. **El agente resuelve justo el agujero que la curación iba a tapar.** La API del eCFR
   encuentra §172.120 como primer resultado; el corpus local no lo tiene y no lo tendrá.
   Para EE. UU., buscar en vivo es estrictamente mejor que cualquier tabla congelada.
2. **Para la UE, un agente sería peor.** El Anexo II es *un solo documento* con 602 tablas.
   Buscarlo con un agente en cada consulta sería pagar una descarga de 3,4 MB y una
   extracción por modelo para releer lo mismo. Se ingiere una vez y se consulta en local:
   determinista, instantáneo y completo.
3. **Codex no se rastrea.** No es que sea difícil: es que la FAO lo prohíbe en su
   `robots.txt` y Bright Data respeta esa prohibición. Forzarlo sería saltarse una regla
   explícita del sitio para publicar sus datos como propios. Se curan a mano los 32
   aditivos, que es lo que sí se puede hacer: una persona abriendo el GSFA en su navegador.

### 1.4 El universo a cubrir es pequeño

De los 50 patrones, **solo 32 aditivos distintos aparecen en todo el snapshot** (18 no
casan nunca). Y la cobertura por fila:

| Semilla | Filas con **todos** sus aditivos cubiertos |
|---|---|
| Top 10 | 7.862 — 54,0 % |
| Top 20 | 12.278 — 84,3 % |
| **Los 32** | **14.572 — 100 %** |

Esto solo dimensiona **la curación de Codex** (32 celdas). US y UE no tienen tope: el
agente y el Anexo II responden por cualquier aditivo, incluido lo que llegue en el futuro
por Alemania, Suiza o Perú.

Los diez primeros: ácido cítrico (E330, 7.124) · ácido ascórbico (E300, 3.079) · lecitina
(E322, 3.065) · goma xantana (E415, 2.435) · pectina (E440, 2.309) · goma guar (E412,
1.344) · sorbato de potasio (E202, 1.159) · glucósidos de esteviol (E960, 1.113) · ácido
málico (E296, 1.073) · citrato de sodio (E331, 1.044).

### 1.5 El punto débil, dicho ahora

`categoria` está al **82,7 %** (24.020 filas) pero con **8.322 valores distintos**: texto
libre de OFF sin normalizar, el mismo problema que tuvo `pais` con sus 1.578 variantes. Y
la categoría es justo de lo que depende el veredicto. No se resuelve mapeando 8.322: se
resuelve con el asterisco (D-4).

---

## 2. Decisiones

| # | Decisión | Por qué |
|---|---|---|
| **D-1** | **Un mecanismo por mercado, no uno solo.** US → agente en vivo · UE → ingesta única del Anexo II · Codex → 32 celdas curadas. | Lo impone la sonda §1.3. Un mecanismo único sería el peor para dos de los tres. |
| **D-2** | **El agente solo puede afirmar lo que consigue citar literalmente de la URL oficial que descargó.** El número del límite y el identificador de sección tienen que aparecer en el documento; si no, la celda sale `SIN_DATO`. | Es `grounding_check.py` aplicado a normativa. Es lo que separa "buscar en la web" de "inventar con estilo", y es la única razón por la que el agente es aceptable aquí. |
| **D-3** | **Caché persistente de veredictos por (aditivo × categoría × mercado)**, con su URL, su fecha y su `origen`. Se consulta antes de salir a la red. | Un agente que repite la misma consulta a la FDA cada vez que alguien abre una fila es lento y caro. La caché **se llena sola** — no es curación previa, es memoria. |
| **D-4** | **La categoría se mapea solo cuando se puede; cuando no, el veredicto lleva asterisco.** `SI` (categoría confirmada) · `SI_CONDICIONADO` · `NO` · `NO_CONDICIONADO` · `SIN_DATO`. | Es el estado que los PPTX ya usan. Con 8.322 categorías libres, la mayoría caerá en `SI_CONDICIONADO`, y **esa es la respuesta correcta**, no una degradación. |
| **D-5** | **Cero celdas sin URL.** Sin `referencia_url` no se pinta veredicto: se pinta `sin dato`. | Promesa P08 del proyecto. |
| **D-6** | **No se rastrea ninguna fuente que lo prohíba en `robots.txt`.** | La FAO lo prohíbe. Ni con Web Unlocker ni con KYC: publicar como propios los datos de un sitio que pidió que no se rastree es un riesgo que no compensa 32 celdas. |
| **D-7** | **Pestaña real del navegador** (`target="_blank"`) a `/analisis/:informeId/:productoId`. | Lo pidió así el encargo y encaja: el usuario compara filas y no puede perder la tabla. Con URL propia el análisis se puede enviar por correo. |
| **D-8** | **[REGULATORY_METHODOLOGY.md](REGULATORY_METHODOLOGY.md) se corrige** con los conteos reales. | Un documento que promete 4.100 citas sobre un corpus vacío es un pasivo: alguien construirá encima. |

---

## 3. Contrato de datos

`dominio/analisis_aditivos.py` (nuevo). Sigue los campos de
[validacion_aditivos_mercados.md §5](validacion_aditivos_mercados.md).

```python
class EvaluacionMercado(BaseModel):
    mercado: Literal["US", "CODEX", "EU"]
    autorizado: Literal["SI", "SI_CONDICIONADO", "NO", "NO_CONDICIONADO", "SIN_DATO"]
    limite_valor: float | None            # None si es BPM o si no hay dato
    limite_unidad: Literal["mg/kg", "ppm", "BPM", "N/A"] | None
    categoria_alimento: str | None        # código GSFA / Anexo II, si se mapeó
    referencia_texto: str                 # "21 CFR § 172.120"
    referencia_url: HttpUrl               # obligatoria (D-5)
    cita_literal: str                     # el fragmento que sostiene el límite (D-2)
    nota: str | None                      # el porqué del asterisco
    origen: Literal["AGENTE_ECFR", "ANEXO_II", "CURADO_CODEX", "CACHE"]
    verificado_en: datetime               # cuándo se comprobó contra la fuente

class AditivoEvaluado(BaseModel):
    nombre: str; ins: str | None; e_number: str | None; funcion: str | None
    evaluaciones: list[EvaluacionMercado]   # exactamente 3, siempre
    limite_interno: float | None            # mín() de los que autorizan
    limite_interno_unidad: str | None

class AnalisisIngredientes(BaseModel):
    producto_id: str; producto_nombre: str
    matriz: str | None                      # categoría tal cual la trae la etiqueta
    matriz_gsfa: str | None                 # código, si se mapeó
    aditivos: list[AditivoEvaluado]
    no_reconocidos: list[str]               # ingredientes sin clasificar
    generado_en: datetime
```

Tres invariantes que fijan los tests:

1. `evaluaciones` tiene **siempre 3 elementos**. Un mercado sin dato es
   `autorizado="SIN_DATO"`, nunca una lista corta: la tarjeta que falta se lee como «no
   aplica» y lo que pasa es «no lo sabemos».
2. **`cita_literal` no vacía en toda evaluación distinta de `SIN_DATO`**, y su contenido
   tiene que aparecer en el documento de `referencia_url`. Es D-2 hecho test.
3. `limite_interno` = `min()` solo sobre mercados con `SI`/`SI_CONDICIONADO` y
   `limite_valor` no nulo. Si EE. UU. es BPM y Codex 1.000 mg/kg, el interno es 1.000.

---

## 4. Tiers

### T1 · Agente regulatorio para EE. UU. — 6 h

El tier que responde al encargo: buscar en vivo, como agente.

- **T1.1** — `adaptadores/agente_ecfr.py`: consulta `ecfr.gov/api/search/v1/results` con
  `"<aditivo en inglés>"` + el término de matriz, ordena por score y se queda con las
  secciones de las partes 170–186 (aditivos) y 100–169 (normas de identidad).
- **T1.2** — Descarga la sección completa por la API `versioner` y extrae con GLM, contra
  `ExtraccionRegulatoria` (instructor): veredicto, límite, unidad, si el producto se nombra
  explícitamente.
- **T1.3** — **Grounding duro (D-2):** el límite extraído y el identificador de sección
  tienen que aparecer literalmente en el texto descargado. Si no, la celda es `SIN_DATO`.
  Reutiliza `GroundingChecker`.
- **T1.4** — Rate-limit y reintentos con el `check_rate_limit` de `integraciones`, como el
  agente comercial.

> **Gate T1:** ácido sórbico → §182.3089 y EDTA → **§172.120** (el que no está en el corpus
> local), ambos con límite y URL. 0 celdas que pasen el grounding con un número que no esté
> en la fuente. p95 < 8 s por aditivo en frío.

### T2 · Anexo II de la UE: ingesta única — 6 h

- **T2.1** — `etl/ingerir_anexo_ii.py`: descarga `CELEX:32011R1129` (3,4 MB) y parsea las
  602 tablas a filas `(e_number, categoria_codigo, categoria_nombre, limite, unidad, nota)`.
- **T2.2** — Persistir en `efsa_regulations` (la tabla **ya existe** y está vacía) más una
  tabla nueva `eu_anexo_ii_uso` para el par aditivo × categoría, que es la unidad real.
- **T2.3** — Consulta local `buscar_uso_ue(e_number, categoria)` con las tres respuestas:
  autorizado en esa categoría · autorizado pero en otras categorías · no autorizado.
- **T2.4** — Guardar la fecha de la versión y el CELEX exacto: la cita tiene que decir de
  qué consolidación salió.

> **Gate T2:** E 200 devuelve la categoría **04.2.4.1** con su nota de exclusión de purés,
> reproduciendo el caso 1 de los PPTX. ≥ 90 % de los 32 aditivos con al menos una entrada.
> Consulta < 50 ms (es local).

### T3 · Codex: 32 celdas curadas — 4 h

El único tier manual, y lo es por decisión de D-6, no por pereza.

- **T3.1** — `data/codex_gsfa_aditivos.csv`: 32 filas con categoría GSFA de referencia,
  límite, URL y `verificado_por` + `fecha_verificacion`.
- **T3.2** — Rellenar consultando el GSFA **a mano, en el navegador** (una persona
  navegando no es un rastreador).
- **T3.3** — Cargador con validación en arranque: falla ruidosamente si falta una URL.

> **Gate T3:** 32/32 con veredicto y URL. Los dos casos de los PPTX reproducidos:
> sorbatos → 1.000 mg/kg en 04.1.2.8; EDTA → 365 mg/kg en 04.2.2.4 con su asterisco de
> categoría general.

### T4 · Motor, caché y categoría — 6 h

- **T4.1** — `dominio/analisis_aditivos.py` (contrato §3).
- **T4.2** — `casos_de_uso/analizar_aditivos_mercados.py`: por cada aditivo y mercado,
  **caché → mecanismo del mercado → `SIN_DATO`**.
- **T4.3** — Tabla `aditivo_mercado_cache` (Postgres) con clave (e_number, categoria_gsfa,
  mercado) y TTL de 90 días. Es D-3: memoria, no curación.
- **T4.4** — `etl/mapear_categoria_gsfa.py`: las **~40 categorías OFF más frecuentes** →
  código GSFA. El resto cae a `None` a propósito y dispara el asterisco (D-4).
- **T4.5** — `limite_interno` en el dominio, con test de unidades (ppm ≡ mg/kg en masa;
  BPM no participa del mínimo).

> **Gate T4:** ≥ 60 % de las 14.572 filas con aditivo obtienen `matriz_gsfa` no nulo.
> Ninguna fila con categoría sin mapear devuelve `SI` a secas. Segunda consulta del mismo
> producto servida de caché en < 100 ms.

### T5 · API — 2,5 h

- **T5.1** — `GET /api/analisis-aditivos/{informe_id}/{producto_id}` en `api/analisis.py`,
  montado como los demás en [api/main.py:61](api/main.py#L61). Recupera el producto del
  informe persistido: **el cliente no es fuente de verdad de lo que se analiza**.
- **T5.2** — 404 si el producto no está en el informe; **200 con `aditivos: []`** si no
  lleva ninguno reconocido — el 49,8 % de las filas, y **no es un error**.
- **T5.3** — Streaming o *job* si el frío pasa de 10 s: el agente de US tarda. Reutiliza
  `websocket_jobs`.
- **T5.4** — Auditoría (`analisis_aditivos_consultado`) y contabilidad de coste por
  consulta con el cost-meter de S8.

> **Gate T5:** p95 < 500 ms en caliente. Producto sin aditivos → 200, nunca 404. Cada
> llamada al agente queda registrada con su coste.

### T6 · Pantalla — 5 h

- **T6.1** — Columna **Análisis** en [Result.vue:104](frontend/src/components/Result.vue#L104),
  con los mismos tres estados que ya usa la columna de aditivos: botón si hay aditivos ·
  «sin aditivos» si la etiqueta está limpia · «sin dato» si no hay etiqueta. **Ningún botón
  muerto.**
- **T6.2** — Ruta `/analisis/:informeId/:productoId`, abierta con `target="_blank"`. Sin
  entrada en el menú lateral: se llega desde la tabla.
- **T6.3** — Vista `AnalisisIngredientes.vue` con la estructura de las diapositivas:
  cabecera (aditivo · INS · E · función · matriz), **tres tarjetas paralelas** con
  veredicto, límite y referencia enlazada, y la nota al pie del asterisco. Un bloque por
  aditivo.
- **T6.4** — Cada tarjeta muestra **de dónde salió y cuándo** (`origen`, `verificado_en`):
  no es lo mismo una cita traída del eCFR hace un minuto que una celda curada en agosto.
- **T6.5** — Cierre: límite interno adoptado y mercados en `NO` como reformulación
  obligatoria.

> **Gate T6:** los dos casos de los PPTX se leen igual que las diapositivas. Toda
> referencia es un enlace que abre la fuente oficial.

### T7 · Honestidad, validador y auditoría — 3,5 h

- **T7.1** — Aviso permanente: qué mecanismo respalda cada columna, que **Codex sale de
  curación manual con fecha**, y que la clasificación final se confirma antes de cada envío.
- **T7.2** — Validador `P-ADI`, en test y no solo en revisión: (a) toda evaluación distinta
  de `SIN_DATO` tiene URL y `cita_literal`; (b) la `cita_literal` aparece en el documento
  de esa URL; (c) ninguna respuesta trae menos de 3 evaluaciones.
- **T7.3** — Sonda semanal de URLs vivas sobre la caché; una cita muerta degrada su celda a
  `SIN_DATO` en vez de seguir mostrándose.
- **T7.4** — Corregir [REGULATORY_METHODOLOGY.md](REGULATORY_METHODOLOGY.md) (D-8).

> **Gate T7:** P-ADI en verde sobre los 32 aditivos × 3 mercados. El documento de
> metodología no contiene ninguna cifra que el sistema no pueda demostrar.

---

## 5. Resumen y orden

| Tier | Entrega | Horas |
|---|---|---|
| T1 | Agente eCFR (US) en vivo | 6,0 |
| T2 | Ingesta del Anexo II (UE) | 6,0 |
| T3 | Codex curado (32 celdas) | 4,0 |
| T4 | Motor, caché y categoría | 6,0 |
| T5 | API | 2,5 |
| T6 | Columna + pestaña | 5,0 |
| T7 | Honestidad y validador | 3,5 |
| | **Total** | **33,0 h** |

**T1, T2 y T3 son independientes entre sí** y se pueden repartir. T4 los necesita a los
tres. **El orden que no se negocia es que T6 va al final**: empezar por la pantalla daría
una pestaña bonita alimentada de `SIN_DATO`, y una demo que se cae en la primera pregunta.

Si hay que recortar, el corte limpio es **T3**: sin Codex, la pestaña sale con dos
columnas reales y una declarada `SIN_DATO`, que es honesto y sigue siendo útil. Lo que no
se puede recortar es **T7.2**: sin el validador de grounding, "búsqueda en fuente oficial"
vuelve a ser palabra.

---

## 6. Lo que este plan NO hace

- **No rastrea el GSFA de la FAO.** Ver D-6. Es una decisión, no una limitación técnica.
- **No usa agente para la UE.** Un documento único de 3,4 MB se ingiere, no se busca 200
  veces.
- **No cubre Perú (INACAL/DIGESA)** aunque haya 32 pasajes indexados: el encargo son tres
  mercados de exportación, y un cuarto sin mecanismo propio abre el mismo hueco otra vez.
- **No analiza ingredientes que no son aditivos.** La columna se llama «Análisis de
  ingredientes» pero lo que se evalúa son los aditivos: fruta, agua y azúcar no tienen
  autorización que consultar. La pantalla lo dice con `no_reconocidos`.
- **No exporta a PPTX/PDF.** Las tres diapositivas son el formato de referencia, no el
  entregable. Si se pide, son ~4 h con
  [informe_weasyprint.py](adaptadores/informe_weasyprint.py), que ya existe.

---

## 7. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| El agente de US extrae un límite que suena bien y no está en la norma | **El más grave del plan** | D-2 con grounding literal + T7.2 como test. Sin cita literal comprobada, la celda es `SIN_DATO` |
| Parsear 602 tablas del Anexo II resulta más sucio de lo que aparenta | T2 se alarga | Acotar a los 32 aditivos del snapshot antes de generalizar; el gate de T2 pide 90 %, no 100 % |
| La FAO cambia de criterio o aparece una vía legítima al GSFA | Oportunidad | Revisar en F2; la caché de D-3 ya tiene el hueco donde encajaría |
| Casi todo cae en `SI_CONDICIONADO` y el asterisco pierde valor | La pantalla no decide nada | Gate de T4 (≥ 60 % con categoría). Si no se alcanza, ampliar el diccionario antes de tocar la pantalla |
| El coste por consulta del agente se dispara con la paginación de 200 filas | Factura | El análisis es **bajo demanda, una fila cada vez** — nunca en lote. Más la caché de D-3 |
| Alguien lee esto como asesoría regulatoria | Serio | T7.1, y el pie de cada tarjeta: se confirma la clasificación antes de cada envío |
