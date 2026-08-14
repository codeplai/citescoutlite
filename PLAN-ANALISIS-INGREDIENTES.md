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

> ⚠️ **Corregido el 2026-08-14, en T6.** Aquí ponía que «solo 32 aditivos distintos
> aparecen en todo el snapshot». **Era un artefacto de la medición, no un hecho del
> snapshot:** `aditivos()` solo puede contar lo que su tabla sabe reconocer, así que se
> estaba midiendo la cobertura del reconocedor y presentándola como contenido del índice.
>
> Se destapó al probar los casos de referencia de punta a punta: `acido1.pptx` y
> `acido2.pptx` van del **ácido sórbico** y del **EDTA**, y la tabla no tenía ninguno de
> los dos — una etiqueta que los declarara salía «sin aditivos». Al añadirlos aparecieron
> en **574 filas que antes se veían vacías** (E 200: 234 · E 386: 185 · E 385: 155) y el
> recuento pasó de 32 a **35**.
>
> El argumento sigue en pie —el universo está acotado por el reconocedor, y la curación no
> es un problema abierto— pero **el número es un suelo, no un total**. Cada patrón que se
> añada puede destapar cientos de filas.

**35 aditivos distintos son reconocibles hoy**, y con ellos la cobertura por fila:

| Semilla | Filas con **todos** sus aditivos cubiertos |
|---|---|
| Top 10 | 7.862 — 54,0 % |
| Top 20 | 12.278 — 84,3 % |
| **Todos los reconocibles** | **14.593 — 100 %** |

Esto solo dimensiona **la curación de Codex**. US y UE no tienen tope: el agente y el Anexo
II responden por cualquier aditivo, incluido lo que llegue en el futuro por Alemania, Suiza
o Perú.

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

### T1 · Agente regulatorio para EE. UU. — ✅ HECHO (2026-08-14)

El tier que responde al encargo: buscar en vivo, como agente.

**Se construyó distinto de como estaba escrito aquí, y por una razón medida.** El plan
decía «descarga la sección por la API `versioner`». El `robots.txt` de `ecfr.gov` dice:

```
  # Don't index developer tool links
  Disallow: /api/renderer/v1/content/
  Disallow: /api/versioner/v1/full/
```

Ese es justo el endpoint del texto. Y la página que ve una persona
(`ecfr.gov/current/title-21/...`), que sí está permitida, **es una SPA**: las dos secciones
de prueba devuelven el mismo shell de 10.595 bytes y cero texto de la norma. D-6 vale aquí
igual que para la FAO, así que se buscó otra vía y la hay:

| Pieza | Fuente | robots |
|---|---|---|
| **Ranking** (en vivo) | `ecfr.gov/api/search/v1/results` | permitido |
| **Texto** (una vez) | `govinfo.gov/bulkdata/ECFR/title-21/` — 21,7 MB, 8.406 secciones | permitido |

**El ranking se pregunta; el texto se tiene.** El agente sigue siendo agente donde importa
—la búsqueda en vivo es lo que encuentra §172.120— y deja de pagar una descarga por
consulta para releer un texto que no cambia.

- **T1.1** ✅ [adaptadores/corpus_ecfr.py](adaptadores/corpus_ecfr.py) +
  [etl/ingerir_ecfr.py](etl/ingerir_ecfr.py). Ingesta con canarios: un XML truncado parsea
  sin lanzar, así que la descarga no se da por buena hasta comprobar §182.3089 y §172.120.
  **Cobertura conseguida: parte 172 → 153 secciones, 182 → 85, 184 → 215.** El corpus RAG
  anterior tenía 336 secciones en total y **ninguna de la 172**.
- **T1.2** ✅ [adaptadores/agente_ecfr.py](adaptadores/agente_ecfr.py). Búsqueda
  entrecomillada (sin comillas, `calcium disodium EDTA` trae cientos de secciones con
  «calcium»; con comillas, 29), deduplicada y ponderada por parte.
- **T1.3** ✅ Grounding duro. Y **la cita no la escribe el modelo**: `referencia_texto` y
  `referencia_url` se construyen desde el id de sección con el que se pidió el documento,
  así que citar una norma inexistente es imposible por construcción, no por comprobación.
  El modelo devuelve una *lectura* (`LecturaSeccion`) y el veredicto lo decide
  `_veredicto()` en código revisable.
- **T1.4** ✅ `check_rate_limit` + `tenacity`, como el agente comercial.
- **T1.5** ✅ [tests/test_t1_agente_ecfr.py](tests/test_t1_agente_ecfr.py) — 37 tests puros
  y de corpus + 3 de gate marcados `integracion`.

**Un fallo que encontró el propio gate.** La primera ordenación agrupaba por parte: todas
las «de aditivos» antes que las demás. Medido, estaba mal —

```
parte 172  §172.878   score  9.3   White mineral oil    <- 1.ª
parte 172  §172.878   score  9.0   White mineral oil    <- duplicada
parte 182  §182.3089  score 31.5   Sorbic acid          <- la buena, 3.ª
```

— una sección de 9,3 adelantaba a una de 31,5 por estar en la parte 172, y las repetidas
se comían el presupuesto de lecturas. Ahora el peso de parte **multiplica** al score en vez
de sustituirlo, y se deduplica antes.

> **Gate T1 — correcto salvo la latencia:**
> ✅ ácido sórbico → §182.3089, `SI`/BPM sin cifra · EDTA → **§172.120**, `SI`/**220 ppm**,
> alimento «Cucumbers pickled». Ambas URL son las que citan los PPTX.
> ✅ Grounding: 3 tests dedicados al falso positivo (cifra plausible que la norma no dice).
> ❌ **`p95 < 8 s` NO se cumple, y el número estaba mal puesto en este plan.**

**La latencia, medida sobre 5 aditivos (2026-08-14):**

| Aditivo | Tiempo | Sección | Veredicto |
|---|---|---|---|
| potassium sorbate | 14,5 s | §182.3640 | SI · BPM |
| calcium disodium EDTA | 20,9 s | §172.120 | SI · 220 ppm |
| sorbic acid | 22,4 s | §182.3089 | SI · BPM |
| sodium benzoate | 31,7 s | §184.1733 | SI · BPM |
| xanthan gum | 35,9 s | §172.695 | SI · BPM |

**p95 ≈ 36 s.** Y el `< 8 s` no era alcanzable el día que se escribió: el reparto del tiempo
es búsqueda ~1 s + corpus 0 s + **el resto es la llamada al modelo**, y
[agente.py:99-111](casos_de_uso/agente/agente.py#L99-L111) ya tenía medido que glm-5.2 tarda
15-42 s y **no escala con el tamaño de la entrada** porque razona antes de responder. El
gate se puso sin mirar esa medición que ya estaba en el repo.

*Nota de lo que sí salió bien en esa tabla:* los 5 aditivos aciertan la sección correcta a
la primera —§182.3640, §184.1733 y §172.695 son las que les tocan—, así que la ordenación
corregida generaliza más allá de los dos casos de referencia.

**Gate T1 rebaseado: p95 < 40 s en frío, < 1 s en caliente.** Y las tres mitigaciones son
arquitectónicas, no de este tier:

1. **Caché (T4.3, D-3)** — la segunda consulta del mismo par no llama al modelo.
2. **Concurrencia entre aditivos (T4.2)** — un producto con 5 aditivos debe evaluarlos en
   paralelo. En serie serían ~150 s; en paralelo, ~36 s. Es el cambio que más se nota y
   pertenece al motor, no al agente.
3. **Job con progreso (T5.3)** — ya estaba previsto: «streaming o *job* si el frío pasa de
   10 s». Con 36 s medidos, deja de ser opcional.

### T2 · Anexo II de la UE: ingesta única — ✅ HECHO (2026-08-14)

- **T2.1** ✅ [adaptadores/corpus_anexo_ii.py](adaptadores/corpus_anexo_ii.py) +
  [etl/ingerir_anexo_ii.py](etl/ingerir_anexo_ii.py). **2.177 filas de la Parte E, 116
  categorías, 14.590 usos, 1 sola fila sin expandir.**
- **T2.2** ✅ pero **en JSON local, no en Postgres** — ver más abajo.
- **T2.3** ✅ [adaptadores/evaluador_ue.py](adaptadores/evaluador_ue.py), con los tres
  estados y un cuarto que el plan no tenía: `indeterminado`.
- **T2.4** ✅ CELEX y fecha de ingesta viajan en el artefacto y en la cita.
- **T2.5** ✅ [tests/test_t2_anexo_ii.py](tests/test_t2_anexo_ii.py) — 34 tests.

**El hallazgo que reordena el tier: el veredicto vive en la sexta columna.** La Parte E
tiene `Nº categoría | Nº E | Denominación | Dosis | Notas | **Restricciones**`, y esa
última decide. Medido sobre las 14.590 filas: 52,0 % sin restricción · 31,1 % «solo …» ·
6,2 % «… excepto …» · 1,2 % ambas · 9,4 % otras. **Casi el 40 % restringe por alimento.**

El caso 1 lo demuestra. E 200 *sí* aparece en la categoría 04.2.4.1 con 1.000 mg/kg, y aun
así `acido1.pptx` concluye `NO*`. La razón está en la restricción completa:

> «solo preparados de fruta y verdura, incluidos los preparados a base de algas, las salsas
> a base de frutas y el áspic, **excepto el puré**, la mousse, la compota, las ensaladas y
> los productos similares en conserva»

Un parser que se quedara en «E 200 está en 04.2.4.1 → autorizado» daría la respuesta
**contraria** a la correcta.

**Dónde el sistema se planta.** La cláusula dice «puré»; la matriz es «pulpa». Que una
pulpa sea un «producto similar» es un juicio de tecnólogo —el que hizo el PPTX, y
probablemente acertado— pero un juicio. El evaluador devuelve `SI_CONDICIONADO` con la
dosis y la frase entera, no `NO`. Cablear sinónimos (pulpa→puré) inventaría equivalencias
regulatorias sin validar; pasárselo al modelo sería peor, porque aquí no falta *lectura*
—el texto son dos líneas— sino criterio. Lo que sí se resuelve solo es la coincidencia
literal: «compota» está en la cláusula, y ahí sí sale `NO_CONDICIONADO`.

**Los rangos, y por qué no se expanden con aritmética.** 444 filas traen `E 200-203` o
`E 338-452` en vez de un número. No son intervalos: `range(338, 453)` inventaría 114
aditivos e incluiría el E 400 (ácido algínico) dentro de «fosfatos». Se derivan **del
propio documento**: miembro es el aditivo de la Parte B (321 pares E→nombre) cuyo número
cae dentro y cuyo nombre es consistente con la denominación del rango. Los 5 rangos que
afectan al snapshot (E 200-203, E 210-213, E 220-228, E 280-283, E 338-452) derivan bien y
son gate. Fuera de ahí falla **por defecto** —siglas («TBHQ»), familias sin raíz común
(«Ribonucleótidos» / «Ácido guanílico») y dos erratas del propio Diario Oficial
(`E 341 "Fost*atos"`, `E 355-228` con inicio > fin)—, que es el sentido correcto en el que
equivocarse: sale `SIN_DATO`, no autorizado de más.

**Un fallo silencioso que encontró la verificación.** El primer parser de la Parte C
troceaba por offsets, y la porción del último grupo se tragaba la sección siguiente
(«Otros aditivos que pueden regularse», que lista el E 200-203). Resultado: **el Grupo IV
pasaba de 7 miembros a 117 y el ácido sórbico salía como polialcohol**, heredando su
autorización en 117 categorías. Ahora se recorre el DOM en orden. Hay test de regresión.

> **Gate T2:** ✅ E 200 en **04.2.4.1** a 1.000 mg/kg con la exclusión de purés entera y
> veredicto condicionado, no `SI` · ✅ E 385 en 04.2.2.4 → `NO_CONDICIONADO`, que es el
> caso 2 · ✅ **cobertura 31/32 = 96,9 %** de los aditivos del snapshot (gate ≥ 90 %) ·
> ✅ consulta **< 8 ms** (gate < 50 ms) · ✅ 34 tests.

**La limitación declarada: esto es la foto de 2011.** `CELEX:32011R1129` es el reglamento
que *rellenó* el Anexo II, no su consolidado de hoy. El único aditivo del snapshot sin
cobertura es el **E 960 (glucósidos de esteviol)**, que la UE autorizó meses después con el
Reglamento (UE) 1131/2011; el propio `acido1.pptx` cita el 2018/98, que tampoco está. Lo
que no está sale `SIN_DATO`, **nunca «no autorizado»**: distinguir «la UE lo prohíbe» de
«nuestra copia es de 2011» es la diferencia entre un dato y un error. Arreglo pendiente:
ingerir `CELEX:02008R1333-<fecha>`, que en la sonda devolvió 404 en la forma probada.

**Desviación de T2.2: artefacto JSON en `data/ue/`, no Postgres.** El Anexo II es dato de
*referencia*, no de ejecución: no necesita transacciones ni escritura concurrente, necesita
leerse rápido y poder diferenciarse cuando la norma cambie. Un fichero hace las dos cosas
mejor y deja el tier **testable sin base de datos** — la misma razón por la que el corpus
del eCFR es un fichero. La tabla `efsa_regulations` sigue vacía a propósito; si T4 la
necesita para la caché, ahí sí hay ya dependencia de Postgres.

### T3 · Codex: 32 celdas curadas — 🟡 CÓDIGO HECHO, DATO BLOQUEADO (2026-08-14)

El único tier manual, y lo es por decisión de D-6, no por pereza.

- **T3.1** ✅ [data/codex/gsfa_aditivos.csv](data/codex/gsfa_aditivos.csv) — 33 filas
  (los 31 números E distintos de los 32 aditivos del snapshot, más E 200 y E 385 de los
  casos de referencia), con INS, frecuencia y las columnas del veredicto en blanco.
- **T3.2** ⛔ **Bloqueado: lo tiene que hacer una persona.** Ver abajo.
- **T3.3** ✅ [adaptadores/corpus_codex.py](adaptadores/corpus_codex.py) — cargador con
  validación dura y `EvaluadorCodex`.
- **T3.4** ✅ [tests/test_t3_codex.py](tests/test_t3_codex.py) — 21 tests.

**Por qué T3.2 no lo puede hacer un agente.** Se agotaron las cuatro rutas:

| Ruta | Resultado |
|---|---|
| `fao.org/gsfaonline/*` | **403** de Cloudflare. Las fichas usan `?id=`, que el `robots.txt` de la FAO veta con `Disallow: /*?id=*` |
| Web Unlocker de Bright Data | **rechaza**: «not available for immediate residential (no KYC) access mode **in accordance with robots.txt**» |
| Enlace `sh-proxy` al PDF de la CXS 192 | **403** |
| `workspace.fao.org/.../CXS_192e.pdf` directo | **200, pero es una página de login de SharePoint** |

La segunda zanja el asunto: hay un proveedor de pago negándose a saltarse ese
`robots.txt`. Y rellenar las celdas «de memoria» produciría 96 valores plausibles, no
verificables y con aspecto de curados — exactamente el dato contra el que se construyó el
grounding de T1 y por el que T2 no cablea sinónimos. **No se hizo.**

**Lo que sí se construyó: que el código no deje colar una fila sin respaldo.** Cada fila
declara su `estado`:

- `VERIFICADO` — alguien abrió el GSFA, leyó categoría y límite, y anotó URL y fecha. Es
  el único que da un `SI` limpio.
- `SECUNDARIA` — el dato viene de un documento interno, no del GSFA. **Nunca da `SI` a
  secas**: se degrada a `SI_CONDICIONADO` y la nota dice de dónde salió.
- `PENDIENTE` — nadie lo ha mirado. Devuelve `SIN_DATO`, nunca «no autorizado».

El cargador **falla ruidosamente** si una fila dice estar resuelta y le falta la URL, la
cita, el `verificado_por` o la fecha (D-5). Se valida al cargar, no al consultar: así el
error sale cuando alguien edita la tabla, que es cuando se puede arreglar.

> **Gate T3: 2/33 resueltas, y las dos como fuente secundaria.**
> ✅ Caso 1 — E 200, cat. 04.1.2.8, 1.000 mg/kg, de `acido1.pptx`.
> ✅ Caso 2 — E 385, cat. 04.2.2.4, 365 mg/kg, `SI_CONDICIONADO` (el asterisco del deck),
> de `acido2.pptx`.
> ⛔ Las 31 restantes en `PENDIENTE` → `SIN_DATO`. **El gate «32/32 con veredicto y URL»
> queda abierto y solo lo cierra una persona con el GSFA delante.**

**Cuánto trabajo humano queda:** 31 filas × 3 datos (categoría, límite, URL) ≈ 4 h con el
GSFA abierto. El CSV ya trae identificado cada aditivo con su número INS, que es la llave
de búsqueda del GSFA, así que la tarea es mecánica: buscar, leer, pegar, poner
`estado=VERIFICADO`. En cuanto una fila se rellena, la pantalla la recoge sin tocar código.

### T4 · Motor, caché y categoría — ✅ HECHO (2026-08-14)

- **T4.1** ✅ ya venía de T1. Un cambio: `matriz_gsfa` → **`matriz_ue`**, porque el nombre
  mentía (ver abajo).
- **T4.2** ✅ [casos_de_uso/analizar_aditivos_mercados.py](casos_de_uso/analizar_aditivos_mercados.py).
- **T4.3** ✅ caché con TTL de 90 días, **reusando el puerto `CacheLLM` que ya existe** en
  vez de crear tabla y migración: la forma (`clave: str → dict`) es exactamente la que hace
  falta, y así funciona igual con el adaptador de SQLite y con el de Postgres.
- **T4.4** ✅ [etl/mapear_categoria.py](etl/mapear_categoria.py).
- **T4.5** ✅ ya venía de T1.
- **T4.6** ✅ [tests/test_t4_analizador.py](tests/test_t4_analizador.py) — 23 tests.

**La corrección de nombre que destapó T4.4: son dos vocabularios, no uno.** El Codex y la
UE comparten la raíz de la numeración y **divergen en la hoja**. El `04.1.2.8` que cita
`acido1.pptx` es un código del GSFA y **no existe** entre las 116 categorías del Anexo II.
Llamar `matriz_gsfa` a un campo que guarda un código europeo habría hecho que alguien lo
cruzara con la tabla del Codex tarde o temprano. Hoy solo se deriva el código de la UE,
que es el único que consume alguien; cuando el Codex necesite el suyo irá en campo propio.

**El mapeo, y por qué la unidad es el segmento.** `categoria` trae 3.854 valores distintos
solo entre las filas con aditivo. Lo que salva la situación es que no son etiquetas sino
rutas de taxonomía —`Snacks, Sweet snacks, Biscuits`—, así que se mapea el **segmento**:

| Unidad | Cobertura de las 14.572 filas |
|---|---|
| top 40 cadenas exactas | 35,2 % |
| top 40 segmentos | 56,1 % |
| **113 segmentos (lo implementado)** | **61,0 %** |

Y hay techo: **2.991 filas (20,5 %) no tienen categoría utilizable** —vacía o `undefined`—,
así que el máximo alcanzable es 79,5 %, no 100 %.

**La regla que hereda el asterisco.** Que «Snacks, Sweet snacks» sea la categoría 15.1 es
una lectura razonable, no un hecho. Por eso **una categoría deducida nunca sostiene un `SI`
limpio**: se degrada a `SI_CONDICIONADO` y la nota dice de qué segmento salió. Solo se toca
el veredicto limpio — un `NO` no se afloja a «quizá» por no estar seguros de la categoría,
porque aflojar un «no autorizado» es justo lo contrario de lo que conviene.

**Concurrencia: el número que arregla T1.** Un producto lleva entre 1 y 9 aditivos. En
serie, con los 15-36 s medidos del agente, un producto de 5 aditivos son ~3 minutos. Los
aditivos se evalúan **todos a la vez**, así que el producto cuesta lo que su aditivo más
lento (~36 s). Hay test que falla si la ejecución vuelve a ser secuencial.

**Qué se cachea y qué no.** Solo EE. UU., que es lo único caro; la UE y el Codex son
diccionarios en memoria y cachearlos añadiría invalidación para ahorrar microsegundos. La
clave es el par **(aditivo, matriz)**, no el producto: dos productos con sorbato en
mermelada comparten respuesta. Y **`SIN_DATO` no se cachea** — suele venir de un timeout, y
guardarlo 90 días convertiría un tropiezo de un minuto en una celda vacía un trimestre.

> **Gate T4:** ✅ **61,0 %** de las filas con aditivo obtienen `matriz_ue` (gate ≥ 60 %) ·
> ✅ ninguna categoría deducida devuelve `SI` a secas · ✅ segunda consulta **< 100 ms** sin
> volver a llamar al agente · ✅ 113/113 entradas del mapa apuntan a códigos que existen ·
> ✅ 23 tests.

**Un fallo que encontró la prueba de punta a punta:** «acido citrico» aparecía en
`no_reconocidos` **después de haberse reconocido**, porque el nombre canónico («Ácido
cítrico») se comparaba con tildes contra un texto sin ellas. La pestaña habría dicho a la
vez que conocía el ingrediente y que no. Ahora la comparación usa el mismo plegado que el
reconocedor, y hay test de regresión.

### T5 · API — ✅ HECHO (2026-08-14)

- **T5.0** ✅ *no estaba en el plan y bloqueaba todo lo demás* — ver abajo.
- **T5.1** ✅ `GET /api/analisis-aditivos/{ejecucion_id}/{producto_id}` en
  [api/analisis.py](api/analisis.py), montado en [api/main.py:69](api/main.py#L69) **fuera
  del `if USA_SUPABASE`**: lee `etapas_ejecucion`, que existe en las dos ramas, y los tres
  corpus son ficheros locales. La pestaña tiene que funcionar también en la demo del plan B.
- **T5.2** ✅ 404 / 200-con-lista-vacía.
- **T5.3** 🔄 **resuelto de otra forma que el plan**: acotando, no encolando. Ver abajo.
- **T5.4** ✅ evento `analisis_aditivos_consultado` (hubo que darlo de alta en la lista
  cerrada `EVENTOS`) y contador `llamadas_agente`.
- **T5.5** ✅ [tests/test_t5_api_analisis.py](tests/test_t5_api_analisis.py) — 12 tests.

**T5.0: `ProductoEnMercado` no llevaba `categoria`, y sin ella T4 no tiene entrada.** El
adaptador del snapshot **ya la leía** —está en `_COLUMNAS` y se usa para filtrar por
insumo— pero no la pasaba al contrato, así que se perdía al salir de la consulta. Con el
campo ausente, `mapear_categoria` no recibe nada y **las tres tarjetas salen condicionadas
o sin dato en todos los productos**: el veredicto depende del par (aditivo × categoría) y
de la categoría no llegaba ni una letra. Añadido como campo opcional, retrocompatible.

**El cliente no es fuente de verdad.** El endpoint recibe **dos identificadores**, no una
lista de aditivos. Podría haber recibido `{"aditivos": [...], "categoria": "..."}` de la
SPA y ahorrarse una consulta, y sería un error: quien manda la lista decide el resultado, y
el informe dejaría de decir lo que dice el snapshot para decir lo que le mandaron. Los
aditivos se releen de `etapas_ejecucion.salida_json`, que es la evidencia auditable del run.
Hay test que lo fija pasando parámetros maliciosos y comprobando que se ignoran.

**T5.3, resuelto acotando en vez de encolando.** `AgenteECFR.evaluar` prueba hasta 3
candidatas con 60 s cada una: **peor caso 180 s**, que no cabe en una petición HTTP —la
pasarela corta y el usuario se queda sin nada habiendo pagado las tres lecturas—. Se pone
un techo de **45 s por aditivo** (holgado sobre los 36 s del p95 de T1); al agotarse, *ese*
mercado sale `SIN_DATO` diciendo que se agotó el tiempo y **los otros dos se entregan
igual**. Es el principio del ADR: degradar a «sin dato», nunca a error. Un *job* con
WebSocket sigue siendo lo correcto si la demo enseña productos de 8 aditivos en frío, pero
con la concurrencia de T4 y la caché el caso normal cabe de sobra en una petición, y una
cola es mucha maquinaria para un problema que ahora mismo no se tiene.

> **Gate T5:** ✅ producto sin aditivos → 200, nunca 404 · ✅ producto ajeno o inexistente →
> 404, nunca 403 (un 403 confirmaría que el id existe) · ✅ el filtro por dueño va **en el
> `where`**, con test que lo verifica por lectura del SQL · ✅ 12 tests ·
> ✅ **p95 en caliente medido tras T6: 6,6 ms** (gate < 500 ms).

**La medición del camino caliente** (2026-08-14, tras montar la pantalla). Producto de 5
aditivos = 15 celdas, caché llena, 0 llamadas al agente, 60 peticiones:

```
mediana 5,6 ms · p95 6,6 ms · máx 6,7 ms
```

Setenta y cinco veces por debajo del gate, y era esperable: en caliente esto son un acierto
de caché y dos diccionarios en memoria. Lo que cuesta es el frío, y de eso responde el
techo de 45 s.

**Lo que NO quedó wireado, y conviene saberlo:** el coste *por tokens* de las llamadas del
agente no llega al cost-meter de S8. `agente_ecfr` llama a litellm directamente, sin pasar
por el ejecutor que contabiliza. Lo que sí se registra es **`llamadas_agente`**, el número
de llamadas que de verdad se pagaron (las de caché no cuentan), que es el dato sin el cual
el cost-meter no puede ni empezar a atribuir. Cerrar el circuito es trabajo de F2.

### T6 · Pantalla — ✅ HECHO (2026-08-14)

- **T6.1** ✅ columna **Análisis** en [Result.vue](frontend/src/components/Result.vue), con
  los mismos tres estados que la columna de aditivos. Va como `<a href>` y no como
  `<button>`: abre pestaña de verdad, así que tiene que responder a Ctrl+clic y al botón
  central, y eso solo lo da un enlace real.
- **T6.2** ✅ ruta `/analisis/:ejecucionId/:productoId`, **sin `titulo` en `meta`** para que
  no salga en el menú lateral: aquí no se llega navegando, se llega desde una fila.
- **T6.3** ✅ [AnalisisIngredientes.vue](frontend/src/vistas/AnalisisIngredientes.vue) con
  las tres tarjetas paralelas, la cita literal de cada norma y la nota del asterisco.
- **T6.4** ✅ cada tarjeta dice **de dónde salió y cuándo**.
- **T6.5** ✅ límite interno y bloque de conclusiones, más un pie de «hasta dónde llega
  esto» que declara las tres limitaciones (eCFR en vivo, UE congelada en 2011, Codex a
  medio curar).

Compila y va en su propio *chunk* diferido: 8,26 kB de JS + 4,23 kB de CSS, que solo
descarga quien abre la pestaña.

**El gate destapó dos fallos, y el segundo era grave.**

**(1) El lector de etiquetas no conocía los aditivos de los PPTX.** Ver la corrección de
§1.4: `ADITIVOS` no tenía ni ácido sórbico ni EDTA, así que los dos casos de referencia
salían «sin aditivos» y la pestaña no se podía ni abrir. Añadidos E 200, E 203, E 385 y
E 386 → **574 filas del snapshot que antes salían vacías** ahora tienen análisis.

**(2) Falso negativo sistemático en EE. UU. por el término de categoría.** El caso 2 daba
`NO*` donde el PPTX dice `SÍ`. La nota del propio agente lo explicaba: había encontrado las
filas correctas —`Cabbage, pickled` y `Cucumbers pickled`— pero se le consultaba por
`pickled vegetable`, que **no está literalmente** en la tabla, y el modelo respondía
`OTROS_ALIMENTOS`. Es estructural: el mapeo de T4.4 produce nombres de *categoría* y el
eCFR lista *alimentos concretos*, así que toda consulta genérica iba a fallar igual.

Arreglado en el prompt, no en el mapeo: se le dice al modelo que el alimento consultado
puede venir como categoría y que un alimento concreto de la sección que pertenezca a ella
cuenta como `ALIMENTO_NOMBRADO`, copiando **el nombre concreto**. El grounding sigue
mordiendo —ese nombre tiene que aparecer literalmente— y la tarjeta enseña cuál se aplicó,
así que la deducción taxonómica queda a la vista de quien lee. Medido después:

```
calcium disodium EDTA × pickled vegetable → SI · 220 ppm · §172.120 · «Cabbage, pickled»
calcium disodium EDTA × pickled cucumbers → SI · 220 ppm · §172.120 · «Cucumbers pickled»
sorbic acid           × fruit puree       → SI · BPM     · §182.3089
```

> **Gate T6:** ✅ compila y carga diferido · ✅ ningún botón muerto (tres estados) · ✅ toda
> referencia es enlace a la fuente oficial · ✅ caso 2 reproduce el `SÍ` con 220 ppm del
> PPTX · ⚠️ **caso 1 no reproduce el `NO*` europeo del deck, a propósito** — ver abajo.

**La discrepancia deliberada, dicha en voz alta.** En el caso 1 la UE sale `SÍ*` con 1.000
mg/kg y la restricción entera delante («…excepto el puré…»), donde `acido1.pptx` concluye
`NO*`. El deck dio el paso de considerar la pulpa un «producto similar» al puré; el sistema
no lo da (T2, D-4). **No es que falle: es que se niega a firmar un juicio de tecnólogo de
alimentos.** Pone delante la cifra, la cláusula y la fuente, que es con lo que el autor del
PPTX decidió, y deja decidir. Si se quisiera que concluyera `NO*`, haría falta una tabla de
equivalencias de formas comerciales validada por alguien que responda de ella — y eso es
una decisión de producto, no un arreglo de código.

---

### T6 · Pantalla — plan original

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

### T7 · Honestidad, validador y auditoría — ✅ HECHO (2026-08-14)

- **T7.1** ✅ pie de «hasta dónde llega esto» en la pantalla, con las tres limitaciones
  nombradas (eCFR en vivo, UE congelada en 2011, Codex a medio curar) y los ingredientes
  sin clasificar de esa etiqueta.
- **T7.2** ✅ [casos_de_uso/validar_analisis.py](casos_de_uso/validar_analisis.py) — P-ADI,
  cinco reglas. **Y no solo en test: corre en cada respuesta del endpoint.**
- **T7.3** ✅ [etl/sondar_urls_regulatorias.py](etl/sondar_urls_regulatorias.py).
- **T7.4** ✅ [REGULATORY_METHODOLOGY.md](REGULATORY_METHODOLOGY.md) reescrito (v3.0).
- **T7.5** ✅ [tests/test_t7_validador.py](tests/test_t7_validador.py) — 21 tests.

**P-ADI encontró un fallo en el código propio, y en el mercado que se presumía más
verificable.** `EvaluadorUE` componía la cita así:

```python
cita = f"{uso.entrada} — {uso.denominacion}: {uso.dosis_texto}"
```

Eso produce «E 440 — Pectinas: quantum satis»: una cadena **montada con puntuación propia
que no aparece en ninguna parte del Anexo II**. Tenía aspecto de cita literal y era un
resumen. P-ADI-2 la rechazó sobre una mermelada real. Arreglado guardando `texto_fila` —la
fila del documento tal como se lee, sus seis celdas— en la ingesta. Tras el arreglo, ese
caso pasó de 4 celdas verificadas + 2 fallos a **6 verificadas + 0 fallos**.

**Tres resultados por celda, no dos.** P-ADI distingue *comprobada*, *fallida* y **no
verificable**. Las del Codex son no verificables por definición —su fuente es una persona—
y devolver «correcto» sobre una celda que no se ha podido mirar daría por auditado lo que
nadie auditó. Lo mismo en la sonda de URLs: **viva, muerta y opaca**. La primera pasada
marcó como muertas las dos citas del Codex, y era un error de la sonda: la FAO devuelve 403
a las máquinas y abre sin problema en un navegador. Etiquetarlo como un 404 habría hecho
borrar una cita buena.

**Se hace cumplir, no solo se anota.** Una celda que falla P-ADI-2 **se degrada a
`SIN_DATO`** antes de salir por el endpoint, con la nota de por qué. Registrar el fallo en
el log y enseñar la celda igual sería quedarse a medias: quien lee la pantalla no ve el log.

> **Gate T7:** ✅ P-ADI en verde sobre cuatro análisis reales (pulpa, encurtidos, mermelada,
> refresco): **0 fallos**, 16 celdas verificadas contra la fuente · ✅ corre en cada
> petición y cuesta **3,3 ms** (p95 total 9,9 ms, gate < 500 ms) · ✅ 21 tests ·
> ✅ el documento de metodología no contiene ninguna cifra que el sistema no pueda
> demostrar, y las tres se reproducen con un comando.

**Lo que decía la v2.0 de la metodología y era falso:** «4100+ regulaciones de 5 fuentes»,
un job semanal `corpus_ingest` con su historial, y un apartado de estadísticas de uso. Las
seis tablas del corpus estaban **a cero**. La v3.0 lo dice en su §7, con el conteo real,
en vez de borrarlo y hacer como si nunca se hubiera prometido.

---

### T7 · Honestidad, validador y auditoría — plan original

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

| Tier | Entrega | Horas | Estado |
|---|---|---|---|
| T1 | Agente eCFR (US) en vivo | 6,0 | ✅ 2026-08-14 |
| T2 | Ingesta del Anexo II (UE) | 6,0 | ✅ 2026-08-14 |
| T3 | Codex curado (32 celdas) | 4,0 | 🟡 código ✅ · dato ⛔ humano |
| T4 | Motor, caché y categoría | 6,0 | ✅ 2026-08-14 |
| T5 | API | 2,5 | ✅ 2026-08-14 |
| T6 | Columna + pestaña | 5,0 | ✅ 2026-08-14 |
| T7 | Honestidad y validador | 3,5 | ✅ 2026-08-14 |
| | **Total** | **33,0 h** | |

> **T4.1 se adelantó a T1.** El contrato
> ([dominio/analisis_aditivos.py](dominio/analisis_aditivos.py)) no podía esperar: el agente
> del eCFR produce `EvaluacionMercado` y sin el tipo no había dónde ponerlo. Lleva ya las
> invariantes de D-2 y D-5 como validadores de pydantic —un veredicto sin cita literal no se
> puede ni construir— y el cálculo de `limite_interno`, con sus tres reglas (ppm ≡ mg/kg,
> BPM no vota, quien prohíbe tampoco).

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
