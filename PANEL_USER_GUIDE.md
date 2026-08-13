# Panel CITE — manual de uso

**Para:** equipo CITE que opera el panel
**Última revisión:** 2026-08-12 (S8)

Este documento explica qué hace cada pantalla del panel, qué significan las
cifras que enseña y —lo que más preguntas genera— **por qué hay tantos huecos
donde pone «sin dato»**. Está pensado para poder operar sin pedir ayuda a
desarrollo.

La promoción de ofertas tiene manual propio y no se repite aquí:
[PROMOTION_PROCEDURES.md](PROMOTION_PROCEDURES.md).

---

## 1. Entrar

El panel vive en el navegador. Se entra con correo y contraseña; la sesión dura
aproximadamente **una hora** y luego se cierra sola. Cuando eso pasa, el panel
te devuelve a la pantalla de entrada y, al volver a entrar, **te lleva a donde
estabas**, no al principio.

Cada pantalla tiene su propia dirección (`/consulta`, `/costos`…), así que se
pueden guardar en favoritos y compartir por correo. Recargar la página no te
saca de donde estás.

---

## 2. Quién ve qué

Hay dos roles, y el panel enseña cosas distintas a cada uno.

| | **Operador** | **Administrador** |
|---|---|---|
| Consulta | ✅ | ✅ |
| Alertas de retiro | ✅ | ✅ |
| Promociones — ver la cola | ✅ | ✅ |
| Promociones — promover o rechazar | ❌ | ✅ |
| Auditoría | ❌ | ✅ |
| Costes | ❌ | ✅ |
| Presupuestos y control | ❌ | ✅ |

Un operador **no ve** el grupo «Administración» en el menú. Si escribe la
dirección a mano, el panel lo devuelve a Consulta y el servidor rechaza la
petición igualmente: el menú es una comodidad, no la cerradura.

> **Para nombrar a alguien administrador** hace falta tocar la base de datos:
> ```sql
> update public.perfiles set rol = 'admin' where email = 'quien@cite.gob.pe';
> ```
> Cambiar **roles** desde el panel todavía no se puede; cambiar **planes**, sí
> (§7). Es una diferencia deliberada: un rol da acceso a datos de otras
> personas, y esa decisión no debería poder tomarse con un clic.

---

## 3. Las pantallas, una a una

El menú está a la izquierda, agrupado:

```
OPERACIÓN            ADMINISTRACIÓN  (solo administradores)
  ⌕  Consulta          ☰  Auditoría
  ⚠  Alertas de retiro ◔  Costes
  ⇪  Promociones       ⏻  Presupuestos y control
```

> **Capturas:** este manual todavía no las lleva. Se toman con el panel
> abierto en `demo-premium@cite.gob.pe`, a 1440 px de ancho, y van una por
> sección (3.1 a 3.6). Hasta entonces cada apartado describe la pantalla con
> el detalle suficiente para seguirla.

### 3.1 Consulta

Escribes un insumo («quinua», «arándano») y el sistema devuelve un informe.
Debajo del resultado aparece lo que ha costado esa consulta en tokens.

Si te vas a otra pantalla y vuelves, **el resultado sigue ahí**. Si recargas la
página, se pierde: el informe vive en memoria, no guardado.

#### Dónde buscar

Encima del cuadro de búsqueda hay cuatro fuentes que se pueden marcar y
desmarcar. No son cuatro versiones de lo mismo: **responden preguntas
distintas**.

| Fuente | Qué responde | Qué cuesta |
|---|---|---|
| **OpenFoodFacts** | *Qué* productos existen y con qué composición. Catálogo global | Instantáneo, sin coste |
| **Ecommerce del Perú** | A cuánto se vende **aquí**. Wong, Metro, Plaza Vea y Makro | Segundos, sin coste |
| **Ecommerce de Alemania** | A cuánto se vende **allá**. Tiendas alemanas abiertas al rastreo, **no las grandes cadenas** — ver abajo | Minutos, **con coste** |
| **Ecommerce de Suiza** | Lo mismo en el segundo destino. Tiendas suizas abiertas al rastreo, **tampoco las grandes** — ver abajo | Minutos, **con coste** |

**El origen y los destinos juntos son el mapa que interesa**: lo que un producto
cuesta aquí y lo que cuesta en Europa. Por separado, cada parte es solo una
lista de precios; juntas responden a dónde conviene exportar.

**Las dos gratuitas vienen marcadas; Alemania y Suiza no.** Es deliberado: son
las que gastan dinero, y una opción cara activada por defecto se acaba pagando
sin que nadie haya decidido pagarla.

No se pueden desmarcar las cuatro: al menos una tiene que quedar.

> **Los precios extranjeros se convierten a soles solos**, y junto a cada oferta
> se guarda la tasa usada, su fecha y su fuente, así que la cifra sigue siendo
> auditable meses después. Ver §4.3.
>
> **Pero el euro y el franco no valen lo mismo como dato.** El euro sale de la
> serie oficial del BCRP (TC Euro venta). **El BCRP no publica tipo de cambio
> del franco suizo**, así que los soles de la tabla suiza se calculan con un
> agregador comercial. Esas filas llevan la marca **«tasa no oficial»** al lado
> del precio y la tabla lo explica en su pie. El precio en francos —el que
> publica la tienda— sí es dato de primera mano; lo que no es oficial es la
> conversión. Si el informe va a citar una cifra suiza, cita los francos.

> ### ⚠️ El selector todavía no filtra, y ahora eso cuesta el doble
>
> Lleva la etiqueta **«vista previa»** al lado por eso. Las cuatro fuentes están
> conectadas al informe:
>
> | Fuente | Estado real |
> |---|---|
> | OpenFoodFacts | **Conectada** (tabla de productos) |
> | Ecommerce del Perú | **Conectada** (tabla de góndola, ver abajo) |
> | Ecommerce de Alemania | **Conectada** (segunda tabla de góndola) |
> | Ecommerce de Suiza | **Conectada** (tercera tabla de góndola) |
>
> Pero la consulta se ejecuta igual marques lo que marques, y **las cuatro se
> lanzan siempre**. Antes eso solo confundía; ahora tiene precio:
>
> - **Cada consulta tarda minutos, no segundos, y desde que existe Suiza son
>   dos búsquedas con agente, una detrás de otra.** Ninguna cadena alemana
>   publica su precio de forma abierta —se comprobaron REWE, Edeka, Alnatura,
>   Kaufland y Lidl— y en Suiza, Migros y Coop devuelven un bloqueo hasta en
>   `robots.txt`, así que esos precios se buscan y se leen ficha a ficha con el
>   agente. Eso es lento por naturaleza, no un fallo.
> - **Y por eso no verás REWE ni Edeka en la tabla.** Las grandes cadenas
>   bloquean el rastreo. Lo que aparece son tiendas alemanas más pequeñas, a
>   menudo de venta directa del productor: en una prueba con arándano
>   («Heidelbeeren») salieron cinco ofertas, todas de granjas online y en
>   formatos de 1 a 8 kg. **Es precio alemán real, pero no es precio de
>   supermercado**, y para comparar con la góndola peruana —que sí es de
>   supermercado— hay que tenerlo presente.
> - **En Suiza pasa lo mismo, y ahí pesa más.** Migros y Coop son en torno al
>   70 % del comercio de alimentación del país y las dos bloquean el acceso, así
>   que la tabla suiza se llena con tiendas menores y con Piccantino, una
>   tienda gourmet online. Léela como **una referencia de precio, no como una
>   muestra del mercado suizo**.
> - **Cada consulta gasta, y ahora gasta el doble.** El agente usa el modelo.
>   Aparece en la pantalla de Costes (§3.5) como cualquier otro gasto.
> - **Desmarcar Alemania o Suiza no evita ni lo uno ni lo otro**, porque el
>   selector no filtra todavía.
>
> Si eso es un problema para una demostración o para el presupuesto del mes,
> díselo a desarrollo (§7): las dos góndolas caras se apagan **por separado** y
> es un cambio de configuración, no de código. Se puede dejar Alemania y quitar
> Suiza, o al revés.

#### La tabla de góndola

Debajo de la tabla de productos de OpenFoodFacts aparece **Precio de góndola ·
Perú**: a cuánto se vende hoy el insumo en Wong, Metro, Plaza Vea y Makro. Y
debajo de ella, **Alemania** y **Suiza**, con las mismas columnas.

La de OpenFoodFacts y las de góndola no son la misma tabla repetida: responden
preguntas distintas. La de arriba dice **qué productos existen** y con qué
composición; las de abajo, **a cuánto están y dónde**. Un producto de arriba
puede corresponder a varias ofertas de abajo.

Y los tres mercados van en tres tablas y no en una con columna «país» porque la
lectura útil es *cuánto cuesta aquí frente a cuánto cuesta allá*: mezclados
habría que filtrar para leer cualquiera de los tres.

| Columna | Qué es |
|---|---|
| Producto | Nombre en la tienda; enlaza a su ficha |
| Tienda | Cadena donde se leyó |
| Precio | En Perú, soles. Fuera, el precio de la tienda y su conversión: «€ 4,99 → S/ 19,71». Si falla el tipo de cambio verás el original y «sin conversión» — el precio no se pierde |
| Stock | Unidades. Vacío = la tienda no lo publica |
| EAN | Código de barras |
| Especificaciones nutricionales | **Ver tabla** abre calorías, proteínas, carbohidratos, azúcares, grasas, sodio y alérgenos |

**Si una fila lleva «tasa no oficial» junto al precio**, la cifra en soles no
viene del BCRP sino de un agregador comercial, porque el banco central no
publica esa moneda. Hoy le pasa a toda la tabla suiza (el franco). El pie de la
tabla lo dice también, con la fuente concreta.

**La columna nutricional dirá «sin dato» en la mayoría de filas, y eso es
correcto.** Sale de lo que cada cadena publica en su ficha, y hoy solo Makro la
trae de forma consistente: sobre una búsqueda de quinua, 4 de 20 ofertas. No se
completa con otras fuentes ni se deduce de productos parecidos — se comprobó
que los códigos de barras peruanos casi no existen en OpenFoodFacts (1 de 16), y
rellenar el hueco con un producto «parecido» sería inventar.

Dentro de la ficha:

- **La porción va primero**, porque los valores están referidos a ella y no a
  100 g. «210,6 kcal» no significa nada sin saber si la ración es de 30 o de
  60 gramos.
- Si la tienda avisa de algo sobre sus propias cifras —Makro declara «Valores
  Nutricionales Teóricos»— **ese aviso se enseña**. Presentar como medido algo
  que la ficha marca como estimado sería lo contrario de lo que hace este
  informe.

**Las filas resaltadas con «también en otra tienda»** son las que se pueden
comparar: el mismo código de barras aparece en más de una cadena, así que la
diferencia de precio es del mismo producto y no de dos parecidos. El nombre
cambia de una cadena a otra; el código de barras no.

> Estas ofertas se leen **en el momento de la consulta** y **no pasan por
> revisión humana**: es lo que la tienda publica en su catálogo. No es lo mismo
> que la cola de Promociones, que sí se revisa antes de entrar al catálogo.
>
> Lo que ya funciona es la pantalla: qué fuentes hay, qué responde cada una,
> qué cuesta y cuáles quedan marcadas.

### 3.2 Alertas de retiro

Retiradas de producto publicadas por openFDA y RASFF, filtrables por severidad
y por ventana de días.

### 3.3 Promociones

La cola de ofertas en cuarentena esperando revisión. Ver la cola puede hacerlo
cualquiera; **promover y rechazar es de administradores**, porque cambian lo
que ve todo el mundo.

Cómo funciona el reparto 80/20, qué reglas se aplican y cómo averiguar por qué
una oferta concreta no entró: [PROMOTION_PROCEDURES.md](PROMOTION_PROCEDURES.md).

### 3.4 Auditoría *(administradores)*

Quién hizo qué en el panel, con **lo que había antes y lo que quedó después**.

Se filtra por acción, por parte del correo de la persona y por rango de fechas.
Al pulsar **Ver** en una fila se abren dos columnas —Antes y Después— con los
campos que cambiaron **resaltados en amarillo**. Debajo, un bloque de
«Contexto» con la información que hace entendible la entrada sin salir de la
pantalla.

Acciones que se registran hoy:

| Acción | Cuándo se anota |
|---|---|
| Inicio de sesión | cada entrada con éxito |
| Promoción manual | al promover una oferta |
| Rechazo manual | al rechazar una oferta |
| Kill-switch | al detener o reanudar el gasto |
| Cambio de plan | al subir o bajar a alguien de plan |

> **Solo se anota lo que cambió de verdad.** Volver a pulsar «premium» sobre
> alguien que ya es premium no deja entrada. Si cada refresco dejara rastro,
> entre el ruido se perdería la única entrada que importa.

**La auditoría no se puede editar ni borrar.** Ni desde el panel ni desde la
base de datos: hay un candado en la propia tabla. Un registro que se puede
cambiar no es una auditoría. Se conserva un año.

**Exportar CSV** descarga exactamente lo que estás viendo, con los mismos
filtros. El fichero abre en Excel con las tildes bien; si alguna vez ves
`CosteÃ±o` en vez de `Costeño`, es que se abrió con la herramienta equivocada,
no que el dato esté mal.

### 3.5 Costes *(administradores)*

En qué se va el dinero, sobre 7, 30, 90 días o un año.

Arriba: **lo gastado este mes**, el número de consultas, la **proyección de
cierre** (a cuánto llegaría el mes al ritmo actual) y el tope global. Debajo,
una barra de cuota con una **marca vertical**: es la proyección. Si la marca
se sale por la derecha, el aviso lo dice con palabras.

Después, cuatro cortes del mismo periodo:

- **Gasto por día.** Los días sin actividad aparecen a cero, no se saltan.
- **Reparto por etapa**, con una tabla debajo que incluye la columna **«De
  caché»**. Es importante: que una etapa cueste $0 **no** significa que no se
  ejecute. Las etapas 4 y 5 se han servido de caché las 80 veces que se han
  pedido — se ejecutan siempre, y por eso no cuestan.
- **Por usuario**, con su plan y sus consultas.
- **Cómo cerraron las consultas** (§4).

> Las cuatro vistas suman lo mismo. Si alguna vez no cuadran, es un fallo:
> avisa a desarrollo.

Cada bloque tiene su botón **CSV**, que descarga esa vista sobre el periodo
que tengas elegido.

### 3.6 Presupuestos y control *(administradores)*

Dos controles.

**El interruptor de gasto (kill-switch).** Un semáforo:

- **Verde — «Gasto permitido».** Todo funciona con normalidad.
- **Naranja — «Gasto detenido».** Alguien lo ha parado a mano.

Detener el gasto **no apaga el sistema**. Las consultas siguen respondiendo,
pero se cierran en «parcial» sin ejecutar ninguna etapa de IA: quien consulte
recibirá un informe con huecos, no un error. Es naranja y no rojo a propósito
— el sistema no está roto, está detenido a conciencia.

Al detenerlo se puede escribir un **motivo** («incidente de coste 12-ago»). Se
enseña al lado del estado para que quien lo vea sepa por qué está parado sin
tener que preguntar. El panel pide confirmación antes, porque el botón afecta a
todo el mundo.

**Los planes.** Una tabla con cada usuario, su rol, sus consultas del mes, su
gasto y un desplegable para cambiarle el plan. El gasto está a la vista a
propósito: cambiar el plan de alguien sin ver lo que consume es decidir a
ciegas.

Cambiar un plan cambia dos cosas: **qué etapas se le ejecutan** y **cuánto
puede gastar al mes**. `gratuito` llega hasta la etapa 3; `premium` hace las
cinco.

---

## 4. «Sin dato»: qué significa y por qué hay tanto

Esta es la sección que hay que leer antes de sacar conclusiones de ninguna
pantalla.

### 4.1 La regla de la casa

**El sistema nunca inventa un dato para rellenar un hueco, y nunca falla por no
tenerlo.** Cuando algo no se puede averiguar, la respuesta es «sin dato» y la
consulta sigue adelante con lo que sí tiene.

Esto es una decisión de arquitectura, no una carencia (ADR-001). La alternativa
—devolver un error, o rellenar con una estimación— sería peor de las dos
maneras: un informe que falla entero porque faltó un precio no sirve, y uno que
enseña un precio inventado sirve para equivocarse.

> **Un 0 y un «sin dato» no son lo mismo**, y el panel los distingue siempre. Un
> 0 significa «se midió y salió cero». Un «sin dato» significa «no se pudo
> mirar». Si alguna pantalla enseña un 0 donde no había fuente, es un fallo:
> avisa.

### 4.2 Por qué una consulta cierra «parcial»

Del histórico completo del sistema (199 consultas):

| Cómo cerró | Cuántas | Qué significa |
|---|---|---|
| **Completa** | 80 | Se ejecutó todo |
| **Pocos productos** | 70 | El catálogo tenía poco de ese insumo |
| **Limitada por plan** | 24 | El usuario es `gratuito`: etapas 4 y 5 no le tocan |
| **Por presupuesto** | 17 | Se alcanzó un tope de gasto, o el kill-switch estaba puesto |
| **Con error** | 8 | Falló algo; queda registrado |

**Que 119 de 199 no sean «completa» no es una avería.** Tres de esos cuatro
motivos son el sistema funcionando como se diseñó: un usuario gratuito *debe*
recibir un informe sin las etapas premium, y un catálogo con poca cobertura de
un insumo *debe* decirlo en vez de rellenar.

El que sí hay que vigilar es **«con error»**. Los demás se explican solos en la
pantalla de Costes.

### 4.3 De dónde vienen los huecos más habituales

- **Precio de un producto.** Muchas tiendas no lo publican en un formato
  legible. Cuando el precio no se pudo leer **de la propia página**, la oferta
  no entra: hay una comprobación que exige que cada cifra aparezca
  literalmente en lo que se capturó. Preferimos una oferta menos a una oferta
  inventada.
- **Etapas 4 y 5** en un usuario gratuito: no es un hueco, es el plan.
- **Alertas de retiro** de un producto peruano: openFDA y RASFF cubren EE. UU.
  y la UE. Un producto que solo se vende en Perú no aparecerá, y eso no
  significa que sea seguro — significa que esas dos fuentes no lo cubren.
- **Stock.** La mayoría de fichas web no lo publican. Las cuatro cadenas
  peruanas (Wong, Metro, Plaza Vea, Makro) sí, y de ahí sale cuando lo hay.

### 4.4 Lo que el panel todavía no enseña

Con nombre y apellidos, para que nadie lo busque:

| | Por qué |
|---|---|
| **Elegir dónde buscar** | El selector de §3.1 está construido pero **no filtra todavía**: la consulta se ejecuta igual marques lo que marques. Desde que Alemania está conectada esto ya no es solo cosmético — ver el aviso de §3.1 |
| **Comparar Perú con Alemania por código de barras** | El mismo producto puede llevar EAN distinto en cada mercado. Dentro de cada tabla las coincidencias sí se marcan; entre las dos tablas, no se promete hasta medir cuántas coinciden de verdad |
| **Trabajos en vivo** (8.1) | Aplazado a S9: hoy solo hay dos trabajos periódicos y no habría gran cosa que enseñar |
| **Semáforo de SLO** (8.8) | Aplazado a S9: hace falta instrumentar primero, y un semáforo sin medición es decorativo |
| **Editor de reglas de promoción** | Nunca se construyó. Las reglas se cambian por SQL (ver PROMOTION_PROCEDURES.md §6) |
| **Exportar informes en bloque** (8.7) | Fuera del alcance de S8 |

---

## 5. Preguntas que van a salir

**«¿Por qué mi consulta salió incompleta?»**
Mira el motivo en la pantalla de Costes → *Cómo cerraron las consultas*, o
pregunta a un administrador. Los cuatro motivos están en §4.2.

**«He detenido el gasto y la gente sigue consultando.»**
Correcto. El interruptor no bloquea el panel: impide gastar. Las consultas
responden con un informe parcial. Si quisieras cerrar el acceso, eso es otra
cosa y hoy no existe.

**«Cambié un plan y no ha pasado nada.»**
Surte efecto en la **siguiente** consulta de esa persona, no en la que tenga
abierta.

**«¿Quién cambió esto?»**
Auditoría, filtrando por acción y fecha. Si la acción está en la tabla de §3.4,
está registrada. Si no aparece, es que esa acción todavía no se audita —no que
no ocurriera.

**«El CSV se ve raro en Excel.»**
Ábrelo con doble clic, no importándolo desde otra herramienta. Los ficheros
llevan la marca que Excel necesita para leer las tildes.

**«Recargo la página y me sale 404.»**
Eso es un problema de cómo está publicado el panel, no del panel. El servidor
tiene que devolver la aplicación en cualquier dirección. Avisa a desarrollo.

---

## 6. Capacitación (1 h)

Guion sugerido para la sesión con CITE:

| Min | Qué |
|---|---|
| 0-5 | Entrar, recorrer el menú, explicar los dos roles |
| 5-15 | Consulta: lanzar una y leer el informe |
| 15-25 | **§4 entera.** Es lo que evita el 80 % de las dudas posteriores |
| 25-35 | Promociones: promover una y rechazar otra |
| 35-45 | Auditoría: buscar las dos acciones que acaban de hacer y abrir el antes/después |
| 45-55 | Costes: leer la cuota y la proyección; exportar un CSV |
| 55-60 | Control: encender el kill-switch, lanzar una consulta, ver que cierra parcial, apagarlo |

El último bloque conviene hacerlo **en vivo**: es la única forma de que quede
claro que detener el gasto no rompe nada, y es justo la duda que aparece cuando
hace falta usarlo de verdad.

---

## 7. Cuándo llamar a desarrollo

- Una consulta cierra **«con error»** más de una vez seguida.
- Las cuatro vistas de Costes **no cuadran** entre sí.
- Un **0** donde esperabas «sin dato», o al revés.
- Recargar una pantalla da **404**.
- El interruptor de gasto **no guarda** el estado.
