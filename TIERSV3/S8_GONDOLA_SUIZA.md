# Góndola de Suiza — traspaso para continuar en otra sesión

**Estado:** Perú **hecho y verificado**. Alemania **hecha, por agente**. Suiza
**hecha, por agente** — opción C del §5, decidida y construida el 2026-08-13.
**Escrito:** 2026-08-13
**Sonda de tiendas suizas:** 2026-08-13 — resultados medidos en §3.
**Construida:** 2026-08-13 — ver §5 (la decisión) y §6 (lo que se hizo).
**Para:** quien retome esto sin haber visto la conversación anterior.

> **Si solo lees una cosa:** Suiza va por agente, la tabla se rotula «Suiza», y
> **Migros y Coop no aparecen en ella** —su 403 es del servidor, así que el
> agente tampoco entra—. Lo que la llena son tiendas suizas menores y
> Piccantino. Es una referencia de precio, no una muestra del mercado, y así lo
> dice la propia tabla y el `PANEL_USER_GUIDE.md`.

Este documento **no repite** la arquitectura. Esa está en
[`S8_GONDOLA_ALEMANIA.md`](S8_GONDOLA_ALEMANIA.md) §2 y §3: modelo de dominio,
adaptador, dónde se engancha, cómo se pinta la tabla. **Léelo primero.** Aquí
va solo lo que es distinto en Suiza, que es bastante.

---

## 1. Titular

**Suiza no es Alemania.** Allí las cinco cadenas sondeadas devolvían 403 o no
publicaban precio, y la conclusión fue que solo se llega por agente. Aquí hay
**una tienda que sí publica precio en formato estructurado y gratis**
—Piccantino—, y el extractor del proyecto ya la lee sin tocar una línea.

Pero es **una sola tienda, con cobertura irregular**. No da un mapa del mercado
suizo; da un punto de referencia.

> **Cómo acabó:** se fue igualmente por agente (§5), y el resultado práctico se
> parece más de lo esperado a lo que habría dado Piccantino solo, porque el 403
> de Migros y Coop también frena al agente. Lo que se ganó es alcance sobre
> tiendas suizas menores y no depender de acertar la URL de una categoría; lo
> que no se ganó son las dos cadenas grandes.

---

## 2. Las tiendas que había en `tiendas.xlsx`

El fichero lista 67 tiendas; **tres son suizas**:

| # | Tienda | URL | Nota del fichero |
|---|---|---|---|
| 65 | Farmy | `https://www.farmy.ch` | «mercado online orgánico líder en Suiza» |
| 66 | Piccantino | `https://www.piccantino.ch` | — |
| 67 | Rappn | `https://rappn.ch` | «Comparador/agregador de delivery de supermercados suizos» |

> Ojo con la fila 50: **Eataly estaba listada como Suiza** y es italiana. Ya
> está corregida en el fichero, pero si alguien trabaja con una copia vieja se
> la va a encontrar.

**Faltan las dos que importan.** Migros y Coop no están en el fichero y son
**~70 % del comercio minorista de alimentación suizo**. Un mapa de góndola
suizo sin ellas es como uno peruano sin Wong ni Metro. Se sondearon igualmente
(§3) porque no tenerlas en la lista no las hace menos relevantes.

---

## 3. La sonda — hecha el 2026-08-13

Mismo método que Perú y Alemania: primero endpoint JSON de catálogo, luego
JSON-LD `schema.org/Product` en el HTML crudo, y solo entonces el agente.
Término de búsqueda `Quinoa` (alemán/suizo-alemán).

| Tienda | Resultado | Veredicto |
|---|---|---|
| `farmy.ch` | **el DNS no resuelve** (`getaddrinfo failed`, con y sin `www`) | ⚠️ ver abajo |
| `piccantino.ch` | 200; JSON-LD `Product` con precio CHF y `gtin13` | ✅ **el único camino gratis** |
| `rappn.ch` | 404 en todas las rutas de búsqueda; la raíz da 527 KB con «quinoa» **0 veces** | SPA, nada que raspar |
| `migros.ch` | **403** en todo, incluidas rutas de API (213 KB de página de desafío) | Anti-bot |
| `coop.ch` | **403** hasta en `robots.txt` (770 B) | Anti-bot duro |

Ninguna corre sobre VTEX: el endpoint que salvó a Perú da 404 o 403 en las
cinco.

### 3.1 Farmy: no es anti-bot, es que no resuelve

`farmy.ch` y `www.farmy.ch` fallan en la **resolución DNS**, no en la conexión
ni con un 403. Eso no es un bloqueo de servidor: o el dominio ya no existe, o
el DNS de esta máquina no lo resuelve.

**No se puede distinguir desde aquí, y no conviene darlo por muerto sin
comprobarlo.** Antes de descartarlo:

```
nslookup www.farmy.ch 8.8.8.8      # con un DNS público
curl -I https://www.farmy.ch       # desde otra red
```

Si resuelve en otro sitio, es cosa de red local y hay que repetir la sonda. Si
tampoco, la fila 65 del Excel apunta a una tienda que ya no está y hay que
quitarla — era la que el propio fichero llamaba «líder».

### 3.2 Migros y Coop: 403, y con matices

Migros responde `robots.txt` (513 B) pero **403 en cualquier ruta de producto o
API**, incluidas `/api/onesearch/v1/search` y `/api/products/search`. Coop es
más cerrado todavía: 403 incluso en `robots.txt`.

Son las dos cadenas que darían un mapa de verdad, y las dos están cerradas al
acceso directo. Cualquier plan que las incluya pasa por el agente, con la
misma latencia y coste que Alemania.

### 3.3 Piccantino: el hallazgo

```
GET https://www.piccantino.ch/quinoa
→ HTTP 200, 87 KB
   <script type="application/ld+json"> { "@type": "Product",
       "name": "SO Fröhlich Quinoa, 500 g",
       "sku": ..., "productID": ..., "gtin13": ...,
       "description": "Optimal für eine ausgewogene Ernährung" }
   Precios en el HTML: CHF 5.50, CHF 11.00
```

**Y el extractor que ya existe lo lee sin cambios.** Medido:

```python
from casos_de_uso.agente.datos_estructurados import extraer_productos
extraer_productos(html)
# -> [OfertaEstructurada(producto=ProductoSchema(
#        nombre='SO Fröhlich Quinoa, 500 g', precio=5.5, moneda='CHF', ean=None))]
```

Tres límites, medidos, que hay que tener delante antes de prometer nada:

1. **Es por categoría, no por búsqueda.** `/quinoa` funciona; `/search?q=Quinoa`
   devuelve 200 pero con «quinoa» **0 veces**. Y `/heidelbeeren` (arándanos)
   devuelve 200 con **0 bloques `Product`**. Es decir: la URL de categoría hay
   que acertarla, y no todas las categorías traen JSON-LD.
2. **Un producto por página, no la lista.** La página de categoría lleva un
   solo nodo `Product` —el destacado—; el resto del listado no está en JSON-LD.
   De `/quinoa` sale **1 oferta**, no las que se ven en pantalla.
3. **El EAN se pierde.** El JSON-LD trae `gtin13`, pero
   `datos_estructurados.py` no lee ese campo y devuelve `ean=None`. Es una
   pérdida real: el EAN es lo único que permite emparejar el mismo producto
   entre tiendas y con la tabla peruana. **Arreglarlo es de las tareas más
   baratas y de mayor valor de todo este documento** (§6, punto 1).

`robots.txt` da dos sitemaps —`/de-CH/sitemap-c.xml` y `sitemap-cs.xml`— que
son la vía para descubrir qué categorías existen sin adivinar URLs.

---

## 4. La moneda: franco suizo

**El BCRP no publica serie de franco suizo.** Se barrieron las series
`PD04630PD` … `PD04680PD` —el rango donde viven el dólar (`PD04640PD`) y el
euro (`PD04648PD`)— y **ninguna** menciona Suiza, franco ni CHF.

Consecuencia: CHF cae al respaldo de `tipo_cambio.py`, y **ya funciona hoy sin
tocar nada**:

```
5,50 CHF → Conversion(precio_pen=22.82, tasa=4.149443, moneda_origen='CHF',
                      fecha_tasa='2026-08-13',
                      fuente='exchangerate-api.com (no oficial)')
```

**La etiqueta «(no oficial)» no es un detalle: es la diferencia con Perú y
Alemania.** Las cifras en soles de esas dos tablas salen del banco central y
son citables en un informe de CITE; las suizas saldrían de un agregador
comercial. El adaptador ya lo dice en el campo `fuente`, pero **la interfaz
hoy no lo enseña**, y una columna «S/» que mezcla dos procedencias sin
distinguirlas es justo lo que este proyecto evita en todo lo demás.

Si Suiza entra, hay que enseñar la procedencia de la tasa en la tabla. Es un
requisito, no una mejora.

> ✅ **Hecho** (2026-08-13). Las filas convertidas con una tasa que no es del
> BCRP llevan el chip **«tasa no oficial»** junto al precio, y el pie de la
> tabla nombra la fuente. Se detecta por el prefijo `BCRP` de
> `conversion.fuente` y no por una lista de monedas, así que sirve para
> cualquier moneda que el banco central no publique, no solo para el franco.

> Antes de asumirlo: merece cinco minutos comprobar si el BCRP publica el CHF
> en **otro rango de series** (el barrido cubrió 50 códigos, no el catálogo
> entero). La API acepta `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{serie}/json/{desde}/{hasta}`
> y devuelve el nombre de la serie en `config.series[0].name`.

---

## 5. La decisión — **tomada: opción C**

> **Lo elegido: C, el agente para todo, y la tabla rotulada «Suiza»** como las
> de Perú y Alemania. Está implementado y en verde. Se asumen a sabiendas las
> consecuencias: la consulta pasa a **dos** runs de agente en serie, y cada una
> gasta el doble que antes. La mitigación es `AGROSCOUT_GONDOLA_CH=0`, un freno
> de mano separado del alemán, y no sustituye a conectar el selector de fuentes.
>
> **Lo que se descartó, y conviene no rehacerlo sin motivo nuevo:** la opción A
> (solo Piccantino, gratis). El camino gratis no se pierde del todo —el agente
> pasa primero por `extraer_productos`, así que cuando cae en una ficha con
> JSON-LD la lee sin gastar modelo—, pero la tabla ya no depende de acertar la
> URL de la categoría.
>
> **Y una cosa que la sonda no había medido y ahora se sabe:** el agente
> **tampoco** entra en Migros ni en Coop. El 403 es del servidor, no del método.
> Así que el argumento que más pesaba a favor de C —«cubre las dos cadenas que
> son el 70 % del mercado»— **no se cumple en la práctica**. Lo que C aporta
> frente a A es alcance sobre tiendas suizas menores, no las cadenas grandes.
> Está escrito en la interfaz y en el manual para que nadie lo lea de más.

Igual que en Alemania, el problema no era escribir el conector. Era qué se
promete.

| | Qué da | Qué cuesta |
|---|---|---|
| **A. Solo Piccantino, gratis** | 1 oferta por categoría, con precio real y en segundos | **no es un mapa del mercado suizo**: es una tienda gourmet de nicho. Llamar «Suiza» a eso induce a error |
| **B. Piccantino + agente para Migros/Coop** | el mapa de verdad | minutos por consulta y coste; y `/consultas` es síncrono (deuda de S3) |
| **C. Agente para todo** | consistente con lo que se decida en Alemania | lo mismo, sin la parte gratis |
| **D. Aparcar Suiza** | cero riesgo | ninguna casilla la promete todavía, así que no hay que desdecirse |

**Nota sobre D, que ya no aplica:** cuando se escribió esto, Suiza estaba en
`Search.vue` marcada «en preparación» y no devolvía nada. Ahora la casilla
promete una tabla y la tabla existe, así que aparcarla ya obligaría a
desdecirse en la interfaz y en el manual.

**La lectura que había, y que se cumplió a medias:** la opción A por sí sola
parecía la más peligrosa, porque *parece* la barata y entrega un dato que se
lee como «el precio en Suiza» cuando es «el precio en una tienda gourmet
online». Se fue por C y la tabla se rotula «Suiza»… pero como el agente tampoco
alcanza a Migros ni a Coop, **el riesgo de lectura es casi el mismo**. Por eso
la mitigación no está en el rótulo sino en el subtítulo de la tabla, en la
tarjeta del selector y en el manual, los tres diciendo lo que no es.

---

## 6. Lo que se hizo — **todo esto está construido**

En este orden. Los dos primeros valían aunque Suiza se hubiera aparcado.

1. ✅ **`gtin13` → `ean` en `datos_estructurados.py`.** El extractor recorría el
   JSON-LD y dejaba `ean=None` aunque el nodo trajera el código de barras. Se
   leen `gtin13`/`gtin14`/`gtin12`/`gtin8`/`gtin`, en el `Product` y en la
   `Offer`, y **se descarta lo que no sea un GTIN bien formado** (longitud 8,
   12, 13 o 14): la tabla empareja filas por EAN, así que un `'0'` o un `'N/A'`
   repetido marcaría como el mismo producto dos que no lo son. **Beneficia
   también a Perú y a la web abierta.** 10 tests en
   `tests/test_s8_datos_estructurados.py`.

2. ✅ **Procedencia de la tasa a la vista** (§4). Las filas convertidas con una
   tasa que no es del BCRP llevan el chip **«tasa no oficial»** al lado del
   precio, y la tabla lo explica en el pie con la fuente concreta. Se detecta
   por el prefijo `BCRP` de `conversion.fuente`, no por una lista de monedas:
   el día que el BCRP publique el franco, basta añadir la serie en
   `tipo_cambio.py` y la tabla deja de marcarlo sola.

3. ⬜ **Descubrir categorías por el sitemap de Piccantino.** *No se hizo y ya no
   hace falta para esto:* era la vía de la opción A, que se descartó. Sigue en
   pie si alguna vez se quiere leer Piccantino directamente y sin agente.

4. ✅ **Conector** `adaptadores/catalogo_suiza.py`, con la misma interfaz que
   `CatalogoVTEX` y `CatalogoAlemania` (`buscar()` / `buscar_sync()`), moneda
   `CHF` declarada arriba y `TIENDAS_CONOCIDAS` a la vista. Lleva el test de
   `buscar_sync` desde dentro de un bucle de eventos.

   **Lo que tiene y el conector alemán no: `es_tienda_suiza`.** Se busca en
   alemán, y una búsqueda en alemán devuelve sobre todo tiendas alemanas; sin
   la guarda, la tabla rotulada «Suiza» se habría llenado de `rewe.de` con
   precios en euros. Acota a `.ch` y anota los descartes en el log, que es lo
   que distingue «no se encontró nada» de «se encontró, pero no era suizo».

5. ✅ **Tercera ranura de catálogo en `OfertasGondola`** (`catalogo_ch`, al
   final de la firma). Alemania y Suiza tampoco pueden compartirla entre sí:
   van las dos por agente pero con país y plantilla distintos.

6. ✅ **`de_suiza(insumo, termino)`**, reutilizando `_ordenadas(...)` y con
   procedencia `agente:` —no `piccantino:`, como decía este documento: la fila
   llega por búsqueda web y extracción, igual que la alemana, y el campo existe
   para distinguir eso de una lectura de catálogo—.

7. ✅ **`ofertas_suiza`** en `dominio/mapa_comercial.py`, en `mapear_comercio` y
   como tercera `<TablaGondola>` en `Result.vue`. El componente ya estaba
   extraído de cuando se hizo Alemania, así que la tercera tabla fueron seis
   líneas.

8. ✅ **Interruptor propio, `AGROSCOUT_GONDOLA_CH=0`.** Separado del alemán a
   propósito: con uno solo, apagar el gasto obligaría a renunciar también al
   mercado que sí se quiere mirar.

### 6.2 Lo que enseñó la primera ejecución real (2026-08-13, 3 pasadas)

La tabla salió **vacía** la primera vez, y ninguna de las causas era la que
este documento anticipaba. Ni anti-bot, ni Bright Data, ni la guarda de país
haciendo su trabajo. Vale la pena tenerlas listadas porque son de las que no se
ven leyendo el código:

1. **`trafilatura` tiraba el precio antes de enseñárselo al modelo.** En
   `zwicky.swiss` reducía 74.200 caracteres a 688 y el `8,05 CHF` se quedaba
   fuera; en `green-shop.ch`, 542.560 a 4.565 sin ninguno de sus cinco precios.
   El modelo devolvía `precio=None` **con razón** y la extracción se pagaba
   igual. Es la misma trampa que ya documenta `datos_estructurados.py` —«el
   precio no está en el texto, pero sí en el HTML»—, resuelta allí solo para
   las tiendas con JSON-LD.

   Arreglado con `casos_de_uso/agente/precio_en_html.py`: al texto principal se
   le añaden los fragmentos del HTML donde hay un importe. **Ojo al guardar la
   evidencia**: `html_capturado` tiene que ser el texto compuesto, o el
   grounding de S7 rechaza por inventado el precio que se acaba de rescatar.

2. **`.swiss` no estaba en la guarda de país**, y `zwicky.swiss` se descartaba
   «por no ser de una tienda suiza» siendo la mejor ficha de la pasada. Es un
   TLD restringido de la Confederación: mejor señal de país que `.ch`.

3. **El alemán compone palabras y `corresponde_al_insumo` no lo contemplaba.**
   `'Bio-Weißquinoa - 500 g - Rapunzel'`, extraída con su precio, se tiraba
   porque el filtro buscaba `\bquinoa` y aquí «quinoa» va pegado detrás de
   «Weiß». Ahora el término vale al principio **o al final** de palabra.

4. **Exigir precio vaciaba la tabla.** Se relajó **solo para las góndolas**
   (`ejecutar(exigir_precio=False)`); la cuarentena mantiene el criterio
   estricto. Lo que frena la basura no es el precio sino el filtro por nombre:
   `'dm-drogerie markt - dauerhaft günstig online kaufen'` lo sigue tirando.

Resultado de la tercera pasada, con los cuatro arreglos:

```
CH  green-shop.ch  Bio-Weißquinoa - 500 g - Rapunzel  CHF 7,70 -> S/ 31,95
DE  buxtrade.de    Quinoa                             EUR 3,49 -> S/ 13,97
```

> Y una falsa alarma, para que no se persiga otra vez: el `WeiÃ` que aparece al
> mirar la respuesta desde PowerShell **no es mojibake del dato**. PowerShell
> 5.1 no respeta UTF-8 en `Invoke-RestMethod` si el Content-Type no declara el
> charset. Comprobado en la tubería: el nombre lleva `C3 9F`, que es `ß` bien
> codificado.

### 6.3 Lo que queda abierto

- **El timeout de extracción, 60 s, es ahora la causa principal de descartes.**
  En la última pasada se llevó 2 de 6 páginas, y una era `zwicky.swiss`, la de
  mejor ficha. No se subió a propósito: `descubrimiento_cascada.descubrir_n3`
  envuelve al agente en un `wait_for` de 120 s y procesa hasta 3 URL en serie,
  así que subirlo aquí puede hacer que la cascada se corte antes de tiempo. Es
  una decisión de latencia de `/consultas`, no del agente, y hay que tomarla
  mirando las dos.
- **El selector sigue sin filtrar**, y ahora cuesta el doble: cada consulta
  lanza los dos agentes marque el usuario lo que marque. Es lo más urgente de
  todo S8 y está descrito en `S8_GONDOLA_ALEMANIA.md` §6.
- **Las dos góndolas por agente corren en serie**, no en paralelo, dentro de
  una petición síncrona. Paralelizarlas casi partiría la espera por dos y es un
  cambio acotado a `mapear_comercio`; no se hizo para no tocar la ruta alemana
  en el mismo paso.
- **Francés e italiano.** Se busca solo con `terminos_aleman`. Migros y Coop
  sirven las tres regiones lingüísticas, así que si alguna vez se les entra,
  elegir idioma pasa a ser una decisión de producto.
- **Farmy sigue sin comprobar** (§3.1): si el DNS tampoco resuelve desde otra
  red, hay que quitar la fila 65 de `tiendas.xlsx`.

### 6.1 El término de búsqueda: aquí hay suerte

Alemania obligó a resolver de dónde sale la palabra alemana (§5.1 de su
documento), y eso ya está hecho: `InsumoInterpretado.terminos_aleman`.

**Piccantino.ch es la versión suiza en alemán**, así que **el mismo término
sirve**: `Quinoa`, `Heidelbeeren`. No hace falta un `terminos_frances` ni un
`terminos_italiano` mientras la única tienda sea germanófona.

Eso cambia si entran Migros o Coop, que sirven las tres regiones lingüísticas y
cuyas URL cambian por idioma (`/de/`, `/fr/`, `/it/`). En ese caso, elegir
idioma es una decisión más, no un detalle de implementación.

---

## 7. Ficheros tocados

```
casos_de_uso/agente/datos_estructurados.py   + gtin -> ean                (punto 1)
                                             + exigir_precio             (6.2.4)
casos_de_uso/agente/precio_en_html.py        NUEVO: rescata el precio del
                                             HTML que trafilatura tira   (6.2.1)
casos_de_uso/agente/agente.py                + PLANTILLA_BUSQUEDA_CH, el rescate,
                                             exigir_precio, y el filtro por
                                             nombre con palabras compuestas (6.2.3)
adaptadores/catalogo_suiza.py                NUEVO                        (punto 4)
adaptadores/catalogo_alemania.py             + exigir_precio=False        (6.2.4)
adaptadores/ofertas_gondola.py               + de_suiza(), 3ª ranura      (5, 6)
dominio/mapa_comercial.py                    + ofertas_suiza
casos_de_uso/etapas/mapear_comercio.py       + una llamada
api/main.py                                  + AGROSCOUT_GONDOLA_CH       (punto 8)
frontend/src/components/TablaGondola.vue     chip y pie de «tasa no oficial» (2)
frontend/src/components/Result.vue           3ª <TablaGondola>
frontend/src/components/Search.vue           tarjeta de Suiza: ya no «en
                                             preparación» y ya no gratis
tests/test_s8_precio_en_html.py              NUEVO (32 tests)
tests/test_s8_ofertas_suiza.py               NUEVO (46 tests)
tests/test_s8_ofertas_alemania.py            su `_gondola` inyecta también la
                                             ranura suiza — ver abajo
tests/test_s8_datos_estructurados.py         + los del gtin
PANEL_USER_GUIDE.md                          §3.1
tiendas.xlsx                                 quitar Farmy si confirma que no existe
```

**`api/main.py` sí se tocó**, al contrario de lo que decía este documento: eso
valía para la opción A, que era gratis. Con el agente hace falta el freno de
mano, y separado del alemán.

> ⚠️ **Trampa que se pisó y hay que recordar:** `tests/test_s8_ofertas_alemania.py`
> tiene una clase `TestEtapa2b` que llama a `mapear_comercio`, y la etapa
> consulta **las tres** góndolas con el mismo término alemán. Al añadir Suiza,
> esos cuatro tests pasaron a lanzar el agente suizo de verdad —minutos y gasto
> de modelo en cada pasada de la suite— hasta que su helper `_gondola` empezó a
> inyectar también un doble en `catalogo_ch`. **Cualquier góndola nueva tiene
> que rellenar todas las ranuras en todos los helpers de test, no solo en el
> suyo.**

`casos_de_uso/dependencias.py` no se toca: `de_suiza` es un método más del
mismo `OfertasGondola` que ya se inyecta como `d.ofertas`.

---

## 8. Cómo repetir la sonda

Los dos scripts de la sonda están en el scratchpad de la sesión y se pierden;
esto es lo que hacían, para rehacerlo en diez líneas:

```python
import httpx, re, json
UA = {"User-Agent": "Mozilla/5.0 ... Chrome/126 Safari/537.36",
      "Accept-Language": "de-CH,de;q=0.9"}   # sin esto, más 403

# 1. ¿VTEX?      /api/catalog_system/pub/products/search?ft=Quinoa
# 2. ¿JSON-LD?   buscar <script type="application/ld+json"> con "@type":"Product"
# 3. ¿precio?    re.findall(r'CHF\s?\d+[.,]\d{2}', html)
# 4. ¿DNS?       socket.gethostbyname(host)   <- distingue "caído" de "403"

from casos_de_uso.agente.datos_estructurados import extraer_productos
extraer_productos(r.text)    # el extractor del proyecto, sin escribir nada nuevo
```

El paso 4 es el que evitó dar a Farmy por bloqueada cuando lo que pasa es que
no resuelve.

## 9. Lecturas de apoyo

| Fichero | Para qué |
|---|---|
| `TIERSV3/S8_GONDOLA_ALEMANIA.md` | **La arquitectura entera.** Este documento asume que se ha leído |
| `adaptadores/catalogo_vtex.py` | El conector de referencia; su docstring es el guion del sondeo |
| `casos_de_uso/agente/datos_estructurados.py` | El extractor JSON-LD que ya lee Piccantino |
| `adaptadores/tipo_cambio.py` | Series del BCRP y el respaldo no oficial |
| `PANEL_USER_GUIDE.md` §3.1 y §4 | Qué se le ha prometido a CITE y qué significa «sin dato» |
