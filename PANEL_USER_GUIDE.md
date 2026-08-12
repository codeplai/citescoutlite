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
