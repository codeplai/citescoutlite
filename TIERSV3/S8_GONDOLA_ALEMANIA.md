# Góndola de Alemania — traspaso para continuar en otra sesión

**Estado:** Perú y Alemania **hechos**. Alemania va **por agente** (opción B del
§5.3: dentro de `/consultas`, asumiendo su latencia y su coste), porque el
sondeo del §5.2 descartó que hubiera precio alemán gratis. Lo que queda abierto
es el §6, y ahora pesa más que antes.
**Escrito:** 2026-08-13
**Revisado contra el código:** 2026-08-13 — los 18 tests de S8 corren verdes, y
las secciones 3, 5, 6 y 7 se corrigieron con lo que se encontró al cotejarlas.
**Sonda de tiendas alemanas:** 2026-08-13 — resultados medidos en §5.2.
**Para:** quien retome esto sin haber visto la conversación anterior.

Este documento es autocontenido. Léelo entero antes de tocar código: la mitad
del trabajo ya está hecho y repetirlo sería tirar tiempo.

---

## 1. Qué se pidió

En el informe de una consulta, debajo de la tabla de productos de
OpenFoodFacts, deben aparecer **dos tablas más de precio de góndola**: una de
Perú y otra de Alemania.

La de **Perú está construida y funcionando**. Esta guía explica cómo, para que
la de Alemania se haga **igual** y no se invente una segunda arquitectura.

---

## 2. Por qué hay dos tablas y no una

No son dos versiones de lo mismo. Responden preguntas distintas y por eso
viven en modelos distintos:

| | `ProductoEnMercado` (tabla de arriba) | `OfertaComercial` (tablas de góndola) |
|---|---|---|
| Fuente | Snapshot de OpenFoodFacts (LanceDB) | Catálogo de una tienda concreta |
| Responde | qué productos existen, con qué composición | a cuánto se vende **hoy** y **dónde** |
| Tiene | aditivos, ingredientes, alérgenos, países | tienda, precio, stock, EAN, fecha de captura |
| Precio | casi siempre vacío | es el motivo de existir |

Y Perú y Alemania van en **dos listas separadas**, no en una sola con columna
`pais`: la lectura útil es «cuánto cuesta aquí **frente a** cuánto cuesta
allá», y mezclarlas obligaría a filtrar para leer cualquiera de las dos.

---

## 3. Lo que ya existe (no rehacer)

### 3.1 Modelo de dominio — `dominio/oferta_comercial.py`

`OfertaComercial` ya sirve para Alemania **sin cambios**. Campos:

```
nombre, tienda, fuente_url
precio, moneda            <- lo que dice la tienda, sin tocar
precio_pen, conversion    <- la conversión, con tasa/fecha/fuente
marca, ean, unidad, categoria, stock
nutricion                 <- EspecificacionNutricional | None
capturado_en, procedencia
```

`EspecificacionNutricional` guarda los valores **como texto**, no como float:
la tienda escribe `'210.6 kcal'` o `'0 mg'`, y la unidad es parte del dato. Un
`0` de sodio no dice si son gramos o miligramos, y decidirlo por nosotros sería
afirmar algo que la ficha no dice.

Todo va referido a la **porción**, no a 100 g, porque es como lo publican las
cadenas peruanas — por eso `porcion` viaja al lado. Sin ella, «210,6 kcal» no
se puede comparar con nada.

**El precio original nunca se pisa.** `precio` + `moneda` son literales de la
tienda; `precio_pen` es la conversión y viaja con `ConversionMoneda` (tasa,
moneda de origen, fecha de la tasa, fuente). Una cifra convertida sin la tasa
con la que se convirtió no es auditable, y el informe de CITE tiene que
aguantar esa pregunta meses después.

### 3.2 Tipo de cambio — `adaptadores/tipo_cambio.py`

**Esto ya está resuelto para el euro y es lo que más tiempo ahorra.**

```python
SERIES_BCRP = {
    "USD": "PD04640PD",   # TC Sistema bancario SBS (S/ por US$) - Venta
    "EUR": "PD04648PD",   # TC Euro (S/ por Euro) - Venta
}
```

Las series se verificaron **consultando la API del BCRP**, no de memoria: el
código que parecía el del euro (`PD04645PD`) resultó ser dólar otra vez. No
las cambies sin volver a comprobarlas.

- Se usa el tipo de **venta**: es el que pagaría quien tuviera que comprar esa
  moneda, y sobrestima antes que subestimar.
- La fecha que se guarda es la del **valor publicado**, no la de hoy: el BCRP
  no publica fines de semana ni feriados, y decir «tipo de cambio del día»
  cuando es el del viernes sería mentir en un informe.
- Para monedas que el BCRP no publica hay un respaldo (open.er-api.com)
  **etiquetado como no oficial**.

Valor de referencia medido: **3,949 S/ por euro** (10-ago-2026).

### 3.3 Adaptador de góndola — `adaptadores/ofertas_gondola.py`

La clase `OfertasGondola` tiene hoy un solo método público, `de_peru(insumo)`.
**Aquí va `de_alemania(insumo)`.**

Sirve **tal cual** para Alemania:

- `_conversion_de(precio, moneda, cambio)` — devuelve `(precio_pen,
  ConversionMoneda)`. Para PEN es la identidad; para EUR llama al BCRP. Hay
  tests de la ruta del euro, pero contra un doble (`CambioFalso`): prueban que
  lo que no es PEN se enruta a `a_soles`, **no** que la serie `PD04648PD`
  responda. Eso lo respalda la medición manual del §3.2, no la suite.
- **Fallar devuelve `[]`**, nunca excepción. Que una tienda alemana no
  responda no puede tumbar un informe cuyo resto no depende de ella
  (ADR-001: degradar a «sin dato», nunca a error).

Y esto **hay que tocarlo antes de reutilizarlo**. No es «calcar `de_peru`»; el
detalle de cada uno está en §5.4:

- `_a_dominio(cruda, cambio, capturado_en)` mapea la oferta al modelo de
  dominio, pero cierra con `procedencia=f"vtex:{cruda.tienda}"` **a fuego**.
  Reutilizarlo etiquetaría cada oferta de REWE como `vtex:REWE`.
- El constructor tiene **una sola ranura de catálogo** (`self._catalogo`), y
  `_catalogo_vtex()` memoiza dentro de ella. Si `de_alemania` la reutiliza, la
  primera llamada decide el conector de las dos.
- El **orden** —por EAN y luego por precio, de modo que el mismo producto en
  dos tiendas cae en filas contiguas— está escrito dentro de `de_peru`. Es lo
  que convierte la lista en una comparación, y las dos tablas tienen que
  compartir esa regla, no copiarla.

> **Lo que este módulo NO hace, y no debe hacer:** escribir en
> `staging_agente`. La cuarentena y el informe son dos caminos con propósitos
> distintos. Si cada consulta de cada usuario metiera decenas de filas en la
> cola de revisión, Promociones —que hoy tiene 5 y es manejable— sería
> inservible en una tarde. La cuarentena se llena desde el job y desde
> `scripts/poblar_staging_real.py`.

### 3.4 Conector de tiendas — `adaptadores/catalogo_vtex.py`

El de Perú. **Alemania necesitará el suyo**, ver §5.

Lo importante que hay que copiar de aquí, no el cómo sino el qué:

- **`buscar_sync()`**: la etapa 2b es síncrona pero corre **dentro** del bucle
  de eventos de la petición. Un `asyncio.run` ahí lanza *«cannot be called
  from a running event loop»*. Se resuelve corriendo la corrutina en un hilo
  aparte con `ThreadPoolExecutor`. **Hay un test que lo comprueba desde dentro
  de un bucle** (`test_buscar_sync_funciona_dentro_de_un_bucle_de_eventos`);
  cópialo.
- **Filtro por insumo** (`corresponde_al_insumo`): el buscador de una tienda es
  generoso. Para «arándano» VTEX devolvió un *Smartphone MOTOROLA G17 6.8"
  Arándano* —arándano es el color del teléfono—. Habrá equivalentes en alemán.
- **Departamentos excluidos**: lo que delata al Motorola no es el nombre sino
  su categoría (`/Tecnología/Telefonía/`). La lista es corta a propósito y se
  equivoca hacia dejar pasar: un champú de maca sí es mercado del insumo.
- ⚠️ **Los dos filtros están escritos en castellano y contra un catálogo
  alemán no casan.** `DEPARTAMENTOS_EXCLUIDOS` solo deja pasar ruido, pero
  `corresponde_al_insumo` **bloquea**: descartaría la respuesta entera. Es el
  §5.1 y va antes que nada.
- **La evidencia se construye con los campos que respaldan cada valor**, no
  recortando un volcado. Este error se cometió **dos veces** (JSON-LD y VTEX):
  al recortar el nodo a N caracteres, el precio quedaba fuera del recorte y el
  grounding daba por inventado un precio que la tienda sí publica.
- **La moneda la pone la tienda, no la página.** El API de VTEX no la declara;
  se marca PEN porque es una propiedad de la cadena. Para Alemania será EUR
  por el mismo motivo, y debe ir **en la tabla de tiendas, a la vista**, no
  escondido en el código que mapea campos.

#### Especificaciones nutricionales — de dónde salen y qué NO funcionó

La columna existe y funciona, pero llegar a ella descartó dos fuentes. No las
vuelvas a intentar sin motivo nuevo:

| Fuente | Resultado medido (2026-08-13) |
|---|---|
| API de OpenFoodFacts por EAN | **1 de 16** códigos peruanos existe en OFF, y ese sin ningún campo nutricional. Inservible |
| Campos del propio nodo VTEX | **Funciona**: `Calorías Por Porción`, `Proteínas Por Porción`, etc. |
| El agente leyendo la ficha | No hizo falta. Cuesta dinero |

Cobertura real de la vía que sí sirve, sobre 5 productos de «quinua» por
cadena:

| Cadena | Con tabla nutricional |
|---|---|
| Makro | **4/5**, tabla completa |
| Plaza Vea | 1/5, y solo la porción |
| Metro | 0/5 |
| Wong | 0/5 |

Es ~25 %, concentrado en una cadena. Se construyó igualmente porque es dato
real de la tienda y «sin dato» es una respuesta legítima aquí.

Detalles del extractor (`_nutricion_de`) que conviene repetir:

- Se compara la etiqueta **sin tildes ni mayúsculas**: las cadenas no escriben
  igual la misma etiqueta y casar por el literal exacto deja fuera datos que sí
  están.
- Lo que acaba en «por porción» y no estaba previsto se guarda en `otros` con
  su nombre original. Una etiqueta desconocida sigue siendo un dato.
- **Solo la porción no cuenta como tabla**: sin ninguna cifra al lado, «60 g»
  no dice nada, y la columna no debe prometer un dato que al abrirlo está
  vacío.
- **La advertencia de la tienda se conserva.** Makro declara «Valores
  Nutricionales Teóricos» y eso se enseña a la vista: presentar como medido
  algo que la ficha marca como estimado sería lo contrario de lo que hace este
  informe.
- La tabla va **también en la evidencia**, por el mismo motivo que el precio:
  si se enseña, tiene que poder comprobarse contra lo que se leyó.

### 3.5 Dónde se engancha

```
casos_de_uso/dependencias.py     ofertas: Any = None
api/main.py                      ofertas = OfertasGondola()  -> Dependencias(ofertas=ofertas)
casos_de_uso/etapas/mapear_comercio.py
                                 ofertas_peru = d.ofertas.de_peru(insumo) if d.ofertas else []
dominio/mapa_comercial.py        ofertas_peru: list[OfertaComercial]
frontend/src/components/Result.vue   sección .gondola con la tabla
```

Va por `d.ofertas` y **no por la cascada** (`DescubrimientoCascada`) a
propósito: no es un nivel de descubrimiento, es una fuente independiente sin
modelo y sin coste. Meterlo en la cascada arrastraría el agente, que tarda
minutos y cuesta dinero.

### 3.6 Frontend — `frontend/src/components/Result.vue`

La sección `.gondola` con la tabla de Perú. Lo que hay que replicar:

- Columnas: Producto, Tienda, Precio, Stock, EAN, **Especificaciones
  nutricionales** (botón «Ver tabla» que abre una ficha, o «sin dato»).
- En la ficha nutricional, la **porción va primero y destacada**, los campos se
  recorren en orden fijo aunque falten —para poder comparar dos productos
  leyendo en paralelo— y los que la tienda no publica **no se pintan a cero**.
- **Celda vacía = «sin dato»**, nunca un guion ni un blanco. Un guion se lee
  como «no aplica», y estos campos sí aplican: simplemente no se conocen.
- ⚠️ La columna de precio pinta **solo `precio_pen`** y cae a «sin dato» si es
  `null`. Con Perú da igual —la conversión es la identidad y nunca es `null`—,
  pero para Alemania es pérdida de dato: §5.4, punto 9.
- Las filas cuyo **EAN aparece en más de una tienda** se marcan con fondo y con
  un chip de texto («también en otra tienda»). El chip va aparte a propósito:
  el color no puede ser el único portador del dato.
- Un pie que dice **qué cadenas se consultaron** y cuántos productos son
  comparables.
- Si la lista viene vacía, la sección **sí se pinta**, con el título y una línea
  que declara la ausencia («Sin ofertas para este insumo en esta consulta»).

  Ojo, porque esto **cambió** y el motivo importa. Antes se ocultaba entera, por
  una razón buena: una tabla vacía con cabeceras se lee como un fallo de carga.
  Pero el remedio salía más caro, y se pagó dos veces depurando: sin nada en
  pantalla, «este mercado no tiene ofertas» y «esto se rompió» son
  indistinguibles. La primera vez la causa fue una caché con el esquema viejo
  (§5.5); la segunda, una API sin reiniciar tras cambiar el modelo de dominio.
  Síntoma idéntico las dos veces: ausencia muda.

  La línea no dice **por qué** está vacío, a propósito: desde el frontend no se
  distingue «se consultó y no había» de «no se consultó» —interruptor del
  servidor, término alemán que la etapa 1 no supo dar—, y afirmar una de las dos
  sería inventar.

### 3.7 El selector de fuentes — `frontend/src/components/Search.vue`

Ya tiene las tres casillas, y la de Alemania ya existe con `clave: 'alemania'`.

**Está marcado «vista previa» porque el selector todavía no filtra**: la
consulta se ejecuta igual marques lo que marques. Conectarlo es trabajo aparte
(§6).

---

## 4. Verificación de que Perú funciona

Consulta real por la API, `POST /consultas {"texto":"quinua"}`:

```
HTTP 200 en 4,18 s
productos OpenFoodFacts : 200
ofertas de góndola      : 20
conversión              : {"tasa": 1.0, "moneda_origen": "PEN", ...}
```

Con el mismo EAN en dos cadenas:

```
742832801140   Metro  S/15.00  |  Wong  S/15.70
```

Las 20 ofertas salen de `POR_TIENDA = 5` por cada una de las cuatro cadenas. El
tope está en `ofertas_gondola.py` y es de presentación —una tabla de cincuenta
filas por cadena deja de leerse—, no un límite del conector.

**18 tests** en `tests/test_s8_ofertas_gondola.py`. Verificados en verde el
2026-08-13 (`uv run pytest tests/test_s8_ofertas_gondola.py`, 5,8 s).

---

## 5. Lo que hay que hacer para Alemania

### 5.1 Antes de nada: el insumo llega en español

**Esto va primero, antes incluso de sondear tiendas.** `de_peru(insumo)` recibe
`interpretado.insumo_normalizado`, que es castellano. Se rompen dos cosas, y la
segunda es silenciosa:

1. `ft=arándano` en `rewe.de` no devuelve nada. Esto se ve enseguida.
2. `corresponde_al_insumo(nombre, insumo)`
   (`casos_de_uso/agente/agente.py`) filtra con
   `re.search(rf"\b{insumo}", nombre)` sin tildes. Contra un catálogo alemán,
   `\bquinua` **no casa con «Quinoa Bio 500g»**: descarta la respuesta entera y
   el log dice «0 ofertas», que se lee exactamente igual que «la tienda no
   tiene el producto». Falla con quinua, que es el ejemplo de todo este
   documento.

`InsumoInterpretado` tiene `sinonimos_busqueda` y `terminos_ingles`; **no tiene
nada en alemán**. Hay que decidir de dónde sale el término antes de escribir
una línea del conector:

| Salida | A favor | En contra |
|---|---|---|
| Campo `terminos_aleman` en la etapa 1 | ya hay un LLM interpretando el insumo; es una línea en el schema | el modelo puede inventarse un término de nicho, y nadie lo comprobaría |
| Tabla fija insumo → término | auditable, sin coste, sin sorpresas | hay que mantenerla; cubre solo lo que se liste |
| Reusar `terminos_ingles` | ya existe, cero trabajo | «quinoa» cuela por casualidad; «blueberry» no encuentra «Heidelbeere» |

Se elija la que se elija, **`corresponde_al_insumo` tiene que recibir el
término con el que se buscó**, no el insumo normalizado. Es un parámetro más,
no una función nueva —y hay que revisar que el cambio no altere la ruta de
Perú, donde término e insumo coinciden.

Y `DEPARTAMENTOS_EXCLUIDOS` hay que rehacerlo en alemán. Ese no bloquea, solo
deja pasar ruido, así que puede ir después de la primera pasada: se sabrá qué
categorías aparecen de verdad en vez de adivinarlas.

### 5.2 La sonda de tiendas alemanas — **hecha el 2026-08-13**

> **Resultado: no hay precio alemán gratis.** Ninguna de las cinco cadenas
> entrega precio sin agente. El detalle está abajo; la consecuencia, en §5.3.

Con Perú se ganó una semana de trabajo al descubrir que las cuatro cadenas
corren sobre **VTEX** y exponen un API público de catálogo:

```
GET https://{tienda}/api/catalog_system/pub/products/search?ft={insumo}
```

Sin anti-bot, sin credencial y sin coste. La salida «evidente» —pagar un
servicio de renderizado— no hizo falta.

Se aplicó el mismo método, buscando `Quinoa` / `Heidelbeeren` (término alemán,
§5.1) y mirando tres cosas en este orden: endpoint JSON de catálogo, JSON-LD
`schema.org/Product` en el HTML crudo, y solo entonces el agente.

**Lo que devolvió cada una:**

| Tienda | HTML de búsqueda | API JSON | Veredicto |
|---|---|---|---|
| `rewe.de` | 403 (251 KB de página de desafío) | **200 y sirve catálogo** | Catálogo sí, **precio no** |
| `edeka.de` | 403 (387 B) | 403 | Anti-bot |
| `alnatura.de` | 200, pero «Quinoa» aparece **0 veces** en el HTML | 404 | SPA pura, nada que raspar |
| `kaufland.de` | 403 | 403 | Anti-bot |
| `lidl.de` | 200, 1,1 MB, sin JSON de producto embebido | 404 | Render por JavaScript |

Ninguna corre sobre VTEX: el endpoint de Perú da 404 o 403 en las cinco.

**El caso REWE merece detalle, porque parece un sí y no lo es.**

```
GET https://shop.rewe.de/api/products?search=Quinoa&objectsPerPage=5
→ HTTP 200   content-type: application/vnd.rewe.fallback+json
   totalResultCount: 67          (377 para Heidelbeeren)
   _embedded.products[].productName    "REWE Bio Quinoa Tricolore 500g"
   _embedded.products[].brand.name     "REWE Bio"
   _embedded.products[]._embedded.categoryPath
                                       "Kochen & Backen/Getreide/Quinoa/"
   _embedded.products[]._links.detail  "/p/rewe-bio-quinoa-tricolore-500g/2695741"
   _embedded.products[]._embedded.articles   []      ← vacío
```

Sin credencial y sin anti-bot, da nombre, marca, categoría y URL. **Pero el
precio vive en `articles`, y `articles` viene vacío.** Eso es lo que anuncia el
`content-type`: `fallback` significa «sin mercado seleccionado». Se probó a
pasarlo —`market=`, `marketCode=`, `wwIdent=`, `serviceTypes=PICKUP`— y sigue
respondiendo `fallback` con `articles` vacío. La ficha del producto, que sí
tendría precio, devuelve **403**.

REWE no es una excepción sino la regla de este mercado: el precio es por tienda
física, y por eso queda detrás de la selección de mercado, que es justo lo que
el API abierto no deja hacer.

> Contraste con Perú, donde sobre 24 URL medidas **solo una** se perdía por
> anti-bot. Alemania es el caso contrario: tres de cinco responden 403 a la
> primera petición, y las dos que abren no publican precio en el HTML.

**Conclusión: no hay atajo.** El precio alemán solo sale por el agente
(`casos_de_uso/agente/agente.py`), que es lo que este plan daba por evitable y
no lo es. **Eso bloquea el código de abajo hasta decidir por dónde va** (§5.3).

Un matiz que puede servir: la mitad barata de REWE —catálogo sin precio— sigue
disponible y es gratis. Basta para decir «este producto se vende en Alemania, en
esta categoría, con esta marca», que no es el precio de góndola prometido pero
tampoco es nada.

### 5.3 La bifurcación — **decidida: opción B**

> **Lo elegido: B, el agente dentro de `/consultas`.** Está implementado y en
> verde. Se asumen a sabiendas las dos consecuencias: la consulta pasa de ~4 s
> a minutos, y cada una gasta modelo. La mitigación es el interruptor
> `AGROSCOUT_GONDOLA_DE=0` (§5.7), que no sustituye al §6.

La sonda dejó el trabajo justo en el escenario que el §5.5 avisaba que había
que hablar antes de programar. El problema no es escribir el conector: es que
`/consultas` es **síncrono** y el navegador espera. Perú añade ~2 s porque son
cuatro peticiones a un API; el agente tarda **minutos** y cuesta dinero por run.

Cuatro salidas, y ninguna es gratis:

| | Qué da | Qué cuesta |
|---|---|---|
| **A. Agente fuera del camino síncrono** | el precio alemán prometido, sin bloquear la consulta | hay que mover `/consultas` a trabajo asíncrono: deuda abierta desde S3, es la opción cara en tiempo |
| **B. Agente dentro de `/consultas`** | lo mismo, ya | minutos de espera con el navegador colgado y coste por consulta; contradice el §5.5 |
| **C. REWE sin precio** | «se vende en Alemania», categoría y marca, gratis y en segundos | **no es precio de góndola**: rompe la promesa del §2 y de la interfaz. Habría que renombrar la tabla y decir en ella qué no trae |
| **D. Aparcar Alemania** | cero riesgo | la casilla del selector sigue prometiendo algo que no existe; hay que decirlo en `Search.vue` y en `PANEL_USER_GUIDE.md` |

**Lo que convenía hacer pasara lo que pasara**, porque no dependía de esta
decisión: los puntos 2, 3, 4 y 9 del §5.4 —ranura de catálogo, procedencia,
orden extraído y la columna de moneda original—. Hechos todos. El 9 además
arregló una pérdida de dato que ya existía en la ruta de fallo de Perú.

### 5.6 Bright Data como reserva ante un 403 — **activo, y con menos efecto del esperado**

**El síntoma que lo motivó.** Consulta de `quinua` el 2026-08-13: Perú devolvió
20 ofertas y Alemania **cero**, para un insumo que allí se vende en cualquier
supermercado. El log dice por qué —el agente abrió tres URL y perdió dos:

```
1. muddanatur.com               → extraída, pero sin precio
2. idealo.de/preisvergleich/…   → 403 Forbidden
3. rewe.de/shop/c/quinoa        → 403 Forbidden
```

No es que el dato no exista: es que no se puede llegar a él. Y explica también
por qué `arandano` sí funcionaba (5 ofertas): hay más tiendas pequeñas abiertas
para ese término. **La cobertura alemana depende de qué encuentre Tavily, y hoy
las grandes se caen todas.**

**Lo construido.** `adaptadores/desbloqueo_brightdata.py`, enganchado en
`AgenteInvestigadorComercial.descargar()`. Solo se dispara **después** de un
bloqueo (403, 429, 503), nunca antes: un 404 no mejora por pasar por un proxy y
cada petición cuesta. 19 tests en `tests/test_s8_desbloqueo.py`.

No reutiliza `adaptadores/bright_data_api.py`, y no por descuido: ese es la
**Scraper API**, que encola un trabajo y espera un webhook. Sirve para el
barrido de N2, que es asíncrono. Aquí hace falta petición y respuesta dentro
del bucle de descarga. Eso es Web Unlocker, que es otro producto.

**Encendido el 2026-08-13.** La zona se llama **`web_api_ai`** (tipo
`unblocker`), no `web_unlocker1`, así que hace falta `BRIGHT_DATA_ZONE` en el
`.env`. Con el nombre mal, cada petición vuelve con HTTP 200 y cero bytes: sin
leer la cabecera `x-brd-err-code: client_10002`, un fallo de zona es idéntico a
una página en blanco. Por eso el módulo la lee y lo dice, una vez por proceso.

### El resultado medido: **el 403 se vence, las ofertas no llegan**

Es la parte importante y conviene no confundirla. Web Unlocker hace su trabajo
—5 de 5 intentos contra REWE, 3-6 s, 113-678 KB— pero eso no se traduce en
ofertas:

| Tienda | Con el proxy | Ofertas extraídas |
|---|---|---|
| `rewe.de` | 113-678 KB, ya sin 403 | **0** — el HTML trae `"price":"unknown"` |
| `edeka.de` | 27 KB | 0 |
| `alnatura.de` | 78.571 B | 0 |
| `idealo.de` | 306 B | 0 |
| `kaufland.de` | 252 B | 0 |

**Porque el 403 nunca fue el obstáculo de fondo.** Cada una tiene el suyo:

- **REWE**: el HTML recuperado dice literalmente `"availability":"unknown"`,
  `"price":"unknown"`. Es el mismo muro del §5.2 —el precio va por `marktId`,
  la tienda física— visto ahora desde el otro lado. Confirmado.
- **Alnatura**: devolvió **78.539 B por fetch directo y 78.571 B por el
  proxy**. Prácticamente el mismo documento: no había nada que desbloquear, la
  página es una SPA y el catálogo lo pinta JavaScript.
- **idealo y Kaufland**: 306 y 252 bytes. El proxy pasa el handshake y detrás
  hay otro muro.

**La zona no renderiza JavaScript**, y eso está probado: `render: true`
devuelve 0 bytes y `browser: true` responde 400. Para las SPA haría falta
**Scraping Browser**, que es otro producto de Bright Data, no esta zona.

### Entonces, ¿para qué sirve lo construido?

Para lo que dice su nombre: que un 403 deje de ser una URL perdida. El agente
elige sus URL de lo que devuelve Tavily, y ahí caen tiendas medianas servidas
desde el servidor que hasta ahora se descartaban enteras. Eso sí se recupera.

Lo que **no** compra es la promesa que motivó todo esto: REWE, Edeka y Alnatura
siguen sin dar precio, y las etiquetas de la interfaz deben seguir sin
nombrarlas (§5.5). Si se quiere ir a por ellas, el camino es Scraping Browser
para las SPA y el `marktId` para REWE —o sea, dos trabajos más, no este—.

**El tope de 3 URL se queda en 3. Decidido, no pendiente.**

`ejecutar()` procesa `resultados_busqueda[:3]` de las cinco que pide a Tavily, y
ahí está el cuello de botella real de la cobertura alemana: en la pasada de
`Quinoa`, una URL se fue en un timeout del modelo y otra no publicaba precio, y
el resultado fue **una** oferta. Se planteó subirlo y **se decidió mantenerlo**
(2026-08-13).

Tiene sentido: cada URL de más son hasta 60 s de extracción en serie
(`TIMEOUT_EXTRACCION`) dentro de una petición síncrona, y una llamada al modelo
que se paga. Con dos góndolas por agente ya encadenadas, subir de 3 a 5
multiplicaría la peor latencia de `/consultas` sin garantía de traer nada: las
URL que se pierden se pierden por timeout y por fichas sin precio, no por falta
de candidatas.

Así que la cobertura alemana es la que es —**una a cinco ofertas de tiendas
medianas, según lo que devuelva Tavily ese día**— y eso es lo que la interfaz
debe seguir prometiendo. Si algún día se quiere más, el camino no es subir este
número: es `/consultas` asíncrono (§5.3, opción A) y entonces el tope deja de
tener el coste que hoy tiene.

**Y hay un límite aparte que conviene mirar.** `ejecutar()` procesa
`resultados_busqueda[:3]`: solo tres URL por consulta. Con dos caídas por 403,
queda una. Subirlo es otra decisión de latencia y coste, no del desbloqueo, y
por eso no se ha tocado aquí.

### 5.7 El interruptor, y por qué existe

```
AGROSCOUT_GONDOLA_DE=0    # apaga la góndola alemana; el resto del informe igual
```

No es una opción de producto, es un freno de mano. Hace falta porque el
selector de fuentes **todavía no filtra** (§6): hoy las tres fuentes se lanzan
en cada consulta marque el usuario lo que marque, así que con la opción B
*todas* las consultas tardan minutos y gastan modelo, también las de quien
nunca pidió precios alemanes.

Sin el interruptor, la única forma de parar ese gasto sería desplegar. Con él,
`de_alemania` devuelve `[]` y el informe degrada igual que cuando el agente
falla (ADR-001).

**Se quita cuando el §6 esté hecho**: entonces la decisión la toma quien
consulta, que es donde tiene que estar.

### 5.4 Después, el código

1. **Conector** `adaptadores/catalogo_alemania.py`, con la tabla de tiendas y
   su moneda a la vista:
   ```python
   TIENDAS_DE = {"www.rewe.de": ("REWE", "EUR"), ...}
   ```
   Con `buscar()` async y `buscar_sync()`, igual que VTEX.

2. **Segunda ranura de catálogo en `OfertasGondola`.** Hoy hay **una sola**,
   `self._catalogo`, y `_catalogo_vtex()` memoiza dentro de ella; si
   `de_alemania` la reutiliza, la primera llamada decide el conector de las
   dos. Hace falta su propia ranura con su getter perezoso:
   ```python
   def __init__(self, catalogo=None, cambio=None, catalogo_de=None):
   ```
   El parámetro nuevo va **al final**: el helper `_gondola()` de los tests
   inyecta `catalogo=` y `cambio=`, y de él cuelgan los 18 tests.

3. **`_a_dominio` necesita el prefijo de procedencia como parámetro.** Hoy
   cierra con `procedencia=f"vtex:{cruda.tienda}"` a fuego, y reutilizarlo
   marcaría cada oferta de REWE como `vtex:REWE`. Es procedencia falsa en el
   único campo que dice de dónde salió la fila, y que existe precisamente
   porque leer un catálogo y raspar una ficha «no cuestan lo mismo ni valen lo
   mismo» (`dominio/oferta_comercial.py`).

4. **El orden, extraído a una función.** Las dos líneas del `sorted(...)` de
   `de_peru` son la regla que convierte la lista en comparación. Copiadas, las
   dos tablas acaban ordenando distinto en cuanto alguien toque una. Es el
   mismo argumento por el que abajo se extrae el componente Vue.

5. **`OfertasGondola.de_alemania(insumo, termino)`** con todo lo anterior. La
   conversión a soles ya funciona: `_conversion_de` con `moneda="EUR"` llama al
   BCRP. La firma lleva el término del §5.1; si se resuelve con una tabla fija,
   puede resolverse dentro del método y quedarse en `de_alemania(insumo)`.

6. **`ofertas_alemania`** en `dominio/mapa_comercial.py`, junto a
   `ofertas_peru`.

7. **`mapear_comercio`**: una línea más, con el mismo patrón defensivo
   (`if d.ofertas is not None`).

8. **`Result.vue`**: segunda sección `.gondola`, debajo de la de Perú. Como va
   a haber dos casi idénticas, **extrae la tabla a un componente**
   (`TablaGondola.vue`) con props `titulo`, `ofertas` y `tiendas`, y úsalo dos
   veces. Copiar y pegar 60 líneas de plantilla se paga en el primer cambio.

9. **Columna de moneda original. No es cosmética: hoy se pierde el precio.**
   La plantilla pinta solo `precio_pen` y cae a «sin dato» si es `null`. El
   backend **sí** conserva `precio` cuando no hay tasa —hay test,
   `test_una_oferta_sin_tasa_conserva_su_precio_original`— y la plantilla lo
   tira. Con Perú no se nota porque la conversión es la identidad y nunca es
   `null`; con Alemania, un BCRP caído borra de la tabla un precio que sí se
   leyó. Hay que poder ver «€ 4,99 → S/ 19,71», y «€ 4,99 · sin conversión»
   cuando falle la tasa.

10. **Especificaciones nutricionales de las tiendas alemanas.** El modelo
    (`EspecificacionNutricional`) y la ficha del frontend ya sirven; lo que
    cambia es de dónde se extraen. Dos cosas a favor y una en contra:

    - **A favor:** la UE obliga por reglamento (1169/2011) a declarar la tabla
      nutricional, así que la cobertura debería ser **mucho mejor que el 25 %
      peruano**. Mídela igual antes de prometer nada.
    - **A favor:** allí se declara **por 100 g**, no por porción. Es más
      comparable. Pero entonces `porcion` vendrá vacío y la ficha dice «Valores
      por porción de…»: hay que **rotular la base** (`por 100 g` frente a `por
      porción`) o se estarán comparando cifras que no son comparables. Es el
      cambio de modelo que sí hace falta: un campo `base`.
    - **En contra:** las etiquetas estarán en alemán (`Brennwert`, `Eiweiß`,
      `Kohlenhydrate`, `Fett`, `Zucker`, `Salz`). `NUTRICION_VTEX` es un mapa
      de etiqueta → campo; hace falta el equivalente alemán. Ojo con `Salz`
      (sal) frente a `Natrium` (sodio): **no son lo mismo**, van con factor
      2,5, y confundirlos da un dato falso.

11. **Tests**, copiando `tests/test_s8_ofertas_gondola.py`. Con una precisión:
    los de conversión con EUR ya existen y pasan, **pero contra `CambioFalso`**.
    Prueban el enrutado de lo no-PEN a `a_soles`, no que `PD04648PD` responda.
    Si quieres una red de verdad sobre el BCRP, es un test aparte y marcado
    como de red. Lo que sí hay que cubrir nuevo: que el término alemán llegue
    al filtro (§5.1), que la procedencia no diga `vtex:` y que las dos listas
    no se pisen la ranura de catálogo.

### 5.5 Cuidado con esto

- **Latencia. Esto ya se disparó**, no es una hipótesis: la sonda del §5.2
  confirmó que Alemania necesita el agente. La consulta está hoy en ~4 s y Perú
  añade ~2 s porque son cuatro peticiones en paralelo a un API; el agente son
  **minutos**, y `/consultas` es síncrono: el navegador espera. No lo metas en
  el camino de la consulta sin resolver antes el §5.3.
- **Comparar Perú con Alemania por EAN es tentador y es más difícil de lo que
  parece.** El mismo producto puede tener EAN distinto por mercado. No
  prometas la comparación cruzada hasta medir cuántos EAN coinciden de verdad.
  Medido en la primera pasada real: **las cinco ofertas alemanas vinieron sin
  EAN**, así que hoy la comparación cruzada no es difícil, es imposible.
- **Las dos tablas no comparan lo mismo, y hay que decirlo.** En la pasada real
  de `arandano`/`Heidelbeeren` no salió ninguna de las tres cadenas que
  prometía la interfaz: REWE, Edeka y Alnatura bloquean el rastreo, así que el
  agente aterriza en tiendas pequeñas de venta directa —granjas online, con
  formatos de 1 a 8 kg—. Es precio alemán real, pero **no es precio de
  supermercado**, y la góndola peruana sí lo es. Las etiquetas de `Search.vue`
  y de `PANEL_USER_GUIDE.md` §3.1 se corrigieron por esto; si algún día entra
  una cadena grande, vuelven a cambiar.
- **No metas las ofertas alemanas en `staging_agente`** por el mismo motivo del
  §3.3.
- **Añadir un campo a una etapa no invalidaba la caché, y por eso la tabla
  alemana no salía.** Vale la pena entenderlo porque es transversal, no de S8.

  `etapa()` cachea por `entrada|modelo|kwargs|etapa|snapshot` y reconstruye lo
  cacheado con `tipo_retorno.model_validate(...)`. Al añadir `terminos_aleman`
  a `InsumoInterpretado`, los insumos ya consultados —había dos guardados,
  `arandano` y `cascara de cacao`— seguían sirviendo su interpretación vieja,
  y pydantic rellenaba el campo nuevo con `[]`. Resultado: `de_alemania`
  devolvía `[]` sin llamar a nadie y **la sección entera no se pintaba**.

  Lo peor no es el fallo, es que era **mudo**: `[]` es también la respuesta
  legítima de «no hay ofertas allí», así que desde la interfaz no se distinguía
  de una búsqueda vacía. Ni un error, ni una línea de log.

  Arreglado en `_generar_clave_cache`: la lista de campos del modelo de salida
  entra en el hash, de modo que cambiar el esquema invalida lo cacheado por sí
  solo. Solo los **nombres**, ordenados: cambiar una descripción no cambia el
  dato y no merece tirar la caché. Hay 7 tests en
  `tests/test_cache_esquema.py`.

  **Si añades un campo a cualquier etapa, esto ya está cubierto.** Lo que no
  cubre es cambiar el *prompt* sin cambiar el esquema: ahí la caché sigue
  sirviendo la respuesta del prompt anterior, y hay que vaciarla a mano.

---

## 6. Trabajo relacionado, aún sin hacer

> **Esto es ahora lo más urgente del documento.** Mientras el selector no
> filtre, cada consulta —de cualquier usuario, marque lo que marque— lanza el
> agente alemán: minutos de espera y gasto de modelo. El interruptor del §5.7
> es un parche, no la solución: apaga Alemania para todos o para nadie.

**Conectar el selector de fuentes.** Hoy no filtra. Hace falta propagar la
selección:

```
POST /consultas {"texto", "fuentes": ["snapshot","peru","alemania"]}
   -> atender_consulta
   -> mapear_comercio
   -> d.ofertas.de_peru / de_alemania  (según lo marcado)
```

Ninguna de esas firmas acepta el parámetro hoy. Cuando se haga, hay que quitar
la etiqueta «vista previa» de `Search.vue` y actualizar
`PANEL_USER_GUIDE.md` §3.1, que hoy avisa explícitamente de que no filtra.

**Y revisar lo que promete el selector.** Alemania está etiquetada «Minutos ·
con coste» en `Search.vue` y en la tabla de fuentes de `PANEL_USER_GUIDE.md`
§3.1, porque cuando se escribió se dio por supuesto el agente. Si la sonda del
§5.2 encuentra un API de catálogo —que es su objetivo—, esas dos etiquetas
quedan mal del lado peor: anuncian un coste que no existe y empujan a no marcar
la casilla. El resultado del sondeo se escribe en los dos sitios, gane lo que
gane.

---

## 7. Ficheros tocados

```
adaptadores/catalogo_alemania.py          NUEVO  conector por agente
adaptadores/desbloqueo_brightdata.py      NUEVO  Web Unlocker ante 403 (§5.6)
adaptadores/ofertas_gondola.py            + de_alemania(), 2ª ranura de catálogo,
                                          prefijo de procedencia, orden extraído
casos_de_uso/agente/agente.py             término de búsqueda parametrizado (§5.1),
                                          plantilla alemana, reserva ante 403
casos_de_uso/etapas/ejecutor.py           la huella del esquema entra en la clave
                                          de caché (§5.5) — cambio transversal
dominio/insumo.py                         + terminos_aleman
adaptadores/redactor_glm.py               la etapa 1 lo pide en el prompt
dominio/mapa_comercial.py                 + ofertas_alemania
casos_de_uso/etapas/mapear_comercio.py    + la llamada a de_alemania
api/main.py                               interruptor AGROSCOUT_GONDOLA_DE (§5.7)
frontend/src/components/TablaGondola.vue  NUEVO  la tabla, usada una vez por mercado
frontend/src/components/Result.vue        usa el componente; ya no lleva tabla propia
frontend/src/components/Search.vue        etiqueta de coste y de tiendas (§5.5)
tests/test_s8_ofertas_alemania.py         NUEVO
tests/test_s8_desbloqueo.py               NUEVO
tests/test_cache_esquema.py               NUEVO
scripts/sembrar_cache_local.py            cuándo hay que resembrar
PANEL_USER_GUIDE.md                       §3.1 (fuentes, coste y aviso) y §4.4
```

`casos_de_uso/dependencias.py` no se toca: `de_alemania` es un método más del
mismo `OfertasGondola` que ya se inyecta como `d.ofertas`.

---

## 7b. Cómo se levanta para usarlo por web

```bash
# 1. API. --reload no es un lujo: sin él, un cambio en un modelo de dominio
#    deja el proceso sirviendo el esquema viejo, la SPA recibe un JSON sin el
#    campo nuevo y la sección no se pinta. Sin error. Pasó, y costó una tarde.
uv run uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# 2. SPA
cd frontend && npx vite --host 0.0.0.0 --port 3000

# frontend/.env.local ya apunta a la IP de esta máquina (VITE_API_URL). Si la
# maquina cambia de red, esa linea hay que actualizarla o la SPA llamara a un
# host que ya no existe.
```

**Antes de dar por buena una prueba en el navegador**, dos comprobaciones que
ahorran el rato que costaron:

1. **¿La API es la de ahora?** Si tocaste un modelo de dominio y arrancaste sin
   `--reload`, no lo es. Reinicia.
2. **¿El informe que estás mirando es nuevo?** `estado_consulta.js` guarda el
   resultado en memoria del proceso para que ir a otra pestaña no borre una
   búsqueda que cuesta dinero. Cambiar de pantalla lo conserva; **solo recargar
   la página lo tira**. Un informe pedido antes de reiniciar la API sigue en
   pantalla y parece actual.

Y cuenta con la latencia: con las góndolas de agente encendidas, una consulta
son **minutos**, no segundos. Si hay que enseñarlo rápido, apágalas con
`AGROSCOUT_GONDOLA_DE=0` y `AGROSCOUT_GONDOLA_CH=0` (§5.7).

## 8. Lecturas de apoyo

| Fichero | Para qué |
|---|---|
| `TIERSV3/S8_AUDITORIA_PREVIA.md` | Historial de S8 y los defectos que costaron tiempo. La sección del conector VTEX explica el sondeo que hay que repetir |
| `PANEL_USER_GUIDE.md` §3.1 y §4 | Qué se le ha prometido a CITE y qué significa «sin dato» |
| `adaptadores/catalogo_vtex.py` | El docstring es el guion del sondeo de Perú |
| `casos_de_uso/agente/datos_estructurados.py` | Extractor JSON-LD ya hecho |
| `PROMOTION_PROCEDURES.md` | Por qué la cuarentena es otro camino |

## 9. Cómo levantar y probar

```
# API
uv run uvicorn api.main:app --host 0.0.0.0 --port 8001
# SPA (frontend/.env.local ya apunta a la IP de la máquina)
cd frontend && npx vite --host 0.0.0.0 --port 3000

# Cuentas demo: las contraseñas están en .env.local (gitignored)
#   demo-premium@cite.gob.pe    admin / premium
#   demo-gratuita@cite.gob.pe   operador / gratuito

# Prueba rápida del adaptador, sin gastar dinero:
uv run python -c "
from dotenv import load_dotenv; load_dotenv()
from adaptadores.ofertas_gondola import OfertasGondola
for o in OfertasGondola().de_peru('quinua'):
    print(o.ean, o.tienda, o.precio_pen, o.nombre[:40])
"

# Suite (excluye el benchmark de red, que depende de la latencia del día):
uv run pytest tests test -q --no-header --deselect test/test_sobrecoste_estado.py
```
