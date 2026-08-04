# Plan · Precio de góndola por producto de la tabla comercial

**Fecha:** 2026-08-03 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)
**Objetivo:** llenar `ProductoEnMercado.precio_rango`, la columna que hoy sale
"sin dato" en las 200 filas del mapa comercial.
**No confundir con** el precio de materia prima, que ya está resuelto
(`PrecioMateriaPrima`, MIDAGRI · SISAP): eso es a cuánto está el kilo de palta,
esto es a cuánto vende su guacamole una marca.

---

## 0. Lo que hay que saber antes de decidir

Todo lo de esta sección está **medido**, no supuesto.

### 0.1 · Hay un defecto que hay que arreglar primero

`DescubrimientoSnapshot.descubrir()` devuelve las 200 primeras coincidencias **en
orden de índice**, y el índice de LanceDB va ordenado por `id`, que es el código
de barras. Los códigos que empiezan por `0` son de EE. UU./Canadá, así que
**copan el resultado siempre**:

| Insumo | Registro de marca de los 200 que enseña la tabla |
|---|---|
| arándano · palta · espárrago · mango · quinua | **100 % EE. UU./Canadá** |

Pero el snapshot **no** es así:

| | Snapshot completo (29.054) |
|---|---|
| EE. UU./Canadá | 56,0 % |
| Alemania · Francia · Reino Unido · España | 20,1 % |
| **Latinoamérica** | **613 (2,11 %)** |
| **Perú** | **38 (0,13 %)** |

**Hay 613 productos latinoamericanos que la tabla nunca ha enseñado.** Para un
CITE peruano, presentar un mapa comercial que es 100 % estadounidense por un
artefacto de ordenación es un problema **hoy**, sin que tenga nada que ver con
los precios.

### 0.2 · Cuántos productos de la región hay por insumo

| Insumo | En el snapshot | LATAM | Perú |
|---|---|---|---|
| quinua | 9.127 | **257** | **28** |
| arándano | 5.877 | **225** | 5 |
| mango | 11.124 | **163** | 3 |
| palta | 3.218 | 24 | 1 |
| espárrago | 902 | 8 | 1 |

Los 38 peruanos incluyen `Camposol Hass Avocado`, `Gloria Mango`,
`Inca Sur Kiwigen` y una familia entera de `Chef Quinoa` — que tiene código
peruano pero se vende en Francia e Italia: **son SKU de exportación**.

### 0.3 · Las fuentes de precio, ya sondeadas

| Fuente | Resultado medido |
|---|---|
| Open Prices, moneda PEN | **5 precios** de 285.726 en toda la base mundial |
| Open Prices, por código de barras | **3 %** de 100 códigos · 0/20 en espárrago, mango y quinua |
| API de Mercado Libre Perú | **HTTP 403**: la búsqueda pública se cerró |
| Portal de datos abiertos del Estado | no resuelve por DNS desde la máquina de la demo |

---

## 1. La pregunta que el plan tiene que responder primero

No es *"¿cómo consigo precios?"*. Es **¿precios de qué productos?**, y hay tres
respuestas incompatibles entre sí:

**A. De los productos que la tabla enseña hoy** (estadounidenses y europeos).
Es lo más fácil de casar —tienen código de barras y hay fuentes— pero es lo
menos útil: a una mipyme de Chavimochic no le dice nada cuánto cuesta una barra
de arándano en un supermercado de Ohio.

**B. De productos peruanos en góndola peruana.** Es lo que de verdad quiere el
CITE. Pero solo hay **38 productos peruanos** en el snapshot, y varios son de
exportación. La cobertura sería testimonial.

**C. De la categoría, no del SKU.** No "este yogur cuesta S/ 4,20" sino
"los yogures con arándano en Lima están entre S/ 3,50 y S/ 6,00". Se pierde el
detalle por fila y se gana algo que sí se puede sostener con una muestra pequeña.

Mi lectura: **A es un callejón, B es lo correcto pero no da volumen, y C es lo
que hace útil a B.** El plan de abajo hace B+C y deja A fuera.

---

## 2. Plan propuesto

### TIER 0 · Arreglar el sesgo de orden (1,5 h) · **prerrequisito**

Sin esto, cualquier trabajo de precios se hace sobre el conjunto equivocado.

- Ordenar el resultado de `descubrir()` por relevancia y no por el índice.
  Criterio propuesto, en este orden: **el insumo en el nombre** > región del
  registro GS1 (Perú → LATAM → resto) > tiene marca > el insumo en ingredientes.
- Exponer la región en `ProductoEnMercado` (`region_marca: str | None`), derivada
  del prefijo GS1. Es un dato que ya está en el código de barras y hoy se tira.
- Un `filtro_region` opcional en el puerto, para poder pedir "solo LATAM".

**Gate:** para quinua, el mapa enseña ≥ 20 productos de marca latinoamericana en
la primera página, frente a los 0 de hoy. Sin tocar el snapshot ni reindexar.

**Esto tiene valor aunque el resto del plan no se haga nunca.**

---

### TIER 1 · Medir la tasa de acierto antes de construir nada (3 h)

El error a evitar es montar un scraper y descubrir después que casa el 2 %.

- Tomar los **38 productos peruanos** y los ~250 LATAM más relevantes.
- Buscarlos a mano en los catálogos web de **Plaza Vea, Tottus, Wong y Metro**,
  y en **Mercado Libre Perú**.
- Anotar, por cada uno: ¿está?, ¿publican el EAN?, ¿el precio es visible sin
  iniciar sesión?

**Salida:** un `COBERTURA-PRECIOS-GONDOLA.md` con la tasa de acierto real, en el
formato del de MIDAGRI.

**Gate de decisión:** si el acierto por EAN es **< 30 %**, TIER 2 no se hace y se
salta a TIER 3. Este número decide el resto del plan y cuesta 3 h averiguarlo.

---

### TIER 2 · Adaptador de nivel 2 · solo si TIER 1 lo justifica (8 h)

Es el `NivelDescubrimiento.API_LICENCIADA` que el puerto ya declara.

- **Mercado Libre Perú**: registrar aplicación y usar la API oficial. Es trámite,
  no ingeniería, y evita el scraping.
- El emparejamiento va **por EAN**, nunca por nombre. Un "Palta Hass 1 kg"
  casado por parecido de texto con `OFF:7751262003744 Camposol Hass Avocado` es
  justo el tipo de dato inventado que P04 persigue: **si no hay EAN, no hay
  precio**.
- Snapshot fechado en `datasets/precios-gondola/`, como todo lo demás. Nada de
  red en tiempo de consulta.

**Gate:** ≥ 30 % de los productos peruanos con precio y EAN verificado; 0 casados
por nombre.

---

### TIER 3 · Precio por categoría, con su intervalo (5 h) · **el que yo haría**

Cuando el SKU exacto no se encuentra, sigue siendo cierto y útil decir en qué
rango se mueve la categoría.

- Muestra manual de **~30 productos por insumo** en góndola peruana, anotando
  formato y precio.
- Modelo `RangoPrecioCategoria`: insumo · formato (mermelada, yogur, snack…) ·
  P25–P75 en S/ · tamaño de la muestra · fecha · dónde se tomó.
- En el informe va **junto al bloque de materia prima**, no en la tabla: la
  columna por fila sigue diciendo "sin dato", porque por fila seguimos sin
  saberlo.

**Gate:** ≥ 3 formatos por insumo con n ≥ 10 cada uno. Un rango con n = 2 no se
publica: se declara la muestra al lado del número o el número no vale.

---

### TIER 4 · Devolver a la comunidad (2 h) · opcional

Open Prices es colaborativo y tiene **5 precios peruanos**. Los que se levanten
en el TIER 3 se pueden aportar. No resuelve nada este año, pero es la única vía
por la que dentro de dos años esto deje de ser un problema — y para un CITE
público, aportar a un bien común es defendible en un CDR.

---

## 3. Lo que NO recomiendo

**Scrapear los supermercados peruanos.** Rompe con cada cambio de maquetación,
obliga a revisar los términos de uso de cada sitio, y —lo que lo mata— **los
retailers no publican el EAN**, así que el emparejamiento tendría que ser por
nombre. Un precio casado por parecido de texto es peor que ninguno: parece un
dato y no lo es.

**Nielsen / Euromonitor / Kantar.** Es el dato bueno. Cuesta lo que cuesta, y
esa decisión es de presupuesto, no de ingeniería. Si aparece, entra por el mismo
puerto de nivel 2 sin tocar nada más.

---

## 4. Resumen y coste

| Tier | Qué | Horas | ¿Depende de? |
|---|---|---:|---|
| **0** | Arreglar el sesgo de orden + región de marca | 1,5 | — |
| **1** | Medir la tasa de acierto real | 3 | T0 |
| **2** | Mercado Libre por EAN | 8 | T1 ≥ 30 % |
| **3** | Rango de precio por categoría | 5 | T1 |
| 4 | Aportar a Open Prices | 2 | T3 |

**Camino corto (T0 + T1 + T3): 9,5 h** y da algo publicable y honesto.
**Camino largo (todo): 19,5 h.**

Nada de esto entra en el MVP de la semana 4. El TIER 0 sí debería, porque es un
defecto de lo que ya se enseña, no una función nueva.

---

## 5. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| R1 | TIER 1 sale con acierto bajísimo y T2 no se hace | Es el propósito del gate: 3 h para no gastar 8 |
| R2 | El rango por categoría se lee como precio del producto | Va en bloque aparte, con el n y la fecha al lado, y la columna por fila sigue en "sin dato" |
| R3 | La muestra manual del T3 envejece | Lleva fecha y se declara; se rehace en una tarde |
| R4 | Arreglar el orden cambia el golden set de S2 | El golden set mide búsqueda (etapa 2a), no el mapa (2b). Verificar, no suponer |

---

## 6. La frase para el CDR

Mientras esto no exista, la afirmación honesta sigue siendo la de ahora:

> El precio en góndola no lo tenemos para ningún producto, y no es una
> limitación del plan contratado. Lo hemos medido: Open Prices tiene 5 precios
> en soles de 285.726, y la API pública de Mercado Libre se cerró. Lo que sí
> tenemos es el precio de la materia prima, oficial y actualizado, que es con el
> que se costea una formulación.

Y con el TIER 0 hecho, se puede añadir algo que hoy no es cierto:

> El mapa prioriza los productos de la región cuando los hay.
