# S8 AUDITORÍA PREVIA: Panel CITE Completo

**Fecha:** 2026-08-11
**Estado:** 🔍 AUDITORÍA PRE-EJECUCIÓN
**Rama:** `main` limpia · último commit `a81895e S7.10: manual de operacion de la promocion`

---

> ## ▶️ ESTADO DE EJECUCIÓN
>
> | Fase | Estado |
> |---|---|
> | 0 · Desbloqueo | ✅ **Cerrada** (2026-08-11) |
> | 1 · Esqueleto del panel | ⬜ Pendiente |
> | 2 · Auditoría transversal | ⬜ Pendiente |
> | 3 · Kill-switch y planes | ⬜ Pendiente |
> | 4 · Cost-meter | ⬜ Pendiente |
> | 8 · Documentación | ⬜ Pendiente |
>
> **Tests: de 15 fallos + 5 errores a 1 fallo. 267 pasan.** El único que queda
> está bloqueado por la credencial de ModelArts, no por código.
>
> ### Lo que se sembró
>
> - Dos cuentas en `auth.users` y sus perfiles
>   ([scripts/crear_usuarios_demo.py](scripts/crear_usuarios_demo.py), ya existía).
> - `demo-premium@cite.gob.pe` nombrado admin
>   ([scripts/nombrar_admin.py](scripts/nombrar_admin.py), nuevo).
> - Histórico portado: **82 ejecuciones, 188 etapas, 60 entradas de caché**
>   ([etl/migrar_sqlite_a_supabase.py](etl/migrar_sqlite_a_supabase.py), revisado).
> - **25 ofertas en `staging_agente`**
>   ([scripts/sembrar_staging_demo.py](scripts/sembrar_staging_demo.py), nuevo).
>   Sintéticas y con URL en `ejemplo.pe`: ninguna atribuida a una tienda real,
>   y borrables de un golpe con `--limpiar`.
> - Bucket privado de informes
>   ([scripts/crear_bucket_informes.py](scripts/crear_bucket_informes.py), nuevo).
> - Verificación de punta a punta
>   ([scripts/verificar_panel_s8.py](scripts/verificar_panel_s8.py), nuevo).
>
> ### Los once defectos que aparecieron al ejecutar
>
> Ninguno se veía leyendo el código: todos estaban tapados por un `try/except`,
> por un test que no llegaba a correr, o por otro fallo anterior.
>
> | # | Dónde | Qué pasaba |
> |---|---|---|
> | 1 | `etl/migrar_sqlite_a_supabase.py` | `ESPERADO` con `{54,94,47}` fijos: **daba ERROR con una migración correcta** |
> | 2 | ídem | No copiaba `motivo_parcial`, `modelo`, `snapshot_version` ni `cache_hit` — justo lo que alimenta 8.2 y 8.8 |
> | 3 | **no existía** | **Nadie escribía `staging_agente`.** B2 de S7, abierto desde S2. Ahora [adaptadores/repositorio_staging.py](adaptadores/repositorio_staging.py) |
> | 4 | `adaptadores/eventos_job.py` | `await cur.scalar(...)` — no existe en psycopg3 |
> | 5 | ídem | `await cur.fetchall(sql, params)` — `fetchall()` no acepta argumentos |
> | 6 | ídem | `async for x in await cur.stream(...)` — `stream()` ya es un generador |
> | 7 | ídem | `json.loads()` sobre una columna `jsonb`, que psycopg3 ya devuelve como dict |
> | 8 | `scripts/start_worker.py` | `async with app.open()` — el asíncrono es `open_async()` |
> | 9 | ídem | `app.worker_defaults(...)` — no existe en procrastinate 3.9 |
> | 10 | ídem | `app.connector()` y `conn.fetchval()` — API de asyncpg, no de psycopg |
> | 11 | ídem | No importaba los módulos de los jobs → **las dos tareas periódicas no existían para el worker** |
>
> Y tres más fuera de esa lista:
>
> - `config/procrastinate_config.py`: los cuatro `@app.on_job_*` **no existen en
>   procrastinate 3.9**, y `setup_event_callbacks()` se llamaba sin `await`.
>   Reescrito como *worker middleware*, que es la forma actual.
> - `casos_de_uso/etapas/mapear_comercio.py`: `interpretado.pais` sobre un
>   modelo que **nunca ha tenido ese campo**. La etapa 2b lanzaba
>   `AttributeError` en cada llamada y `/consultas` devolvía 500. **Roto desde
>   S2 INTEG** (commit `0e0772e`).
> - Storage: el proyecto no tenía **ningún** bucket, así que `/consultas` hacía
>   —y pagaba— todo el trabajo y moría al subir el PDF. Por eso `informes`
>   estaba a 0 mientras `ejecuciones` se llenaba.
>
> Más dos arreglos de entorno: el policy Proactor de asyncio en Windows, que
> impide a psycopg correr en asíncrono
> ([adaptadores/bucle_asincrono.py](adaptadores/bucle_asincrono.py)), y la
> consola cp1252 que sepultaba el log del worker bajo `UnicodeEncodeError`.
>
> ### Verificado corriendo, no leyendo
>
> Job de promoción encolado y procesado por el worker de punta a punta:
> **25 ofertas → 13 promovidas, 5 a revisión manual, 7 rechazadas** por las tres
> reglas activas, en 14 s (SLA 900 s). `eventos_job` con `started`/`completed`
> del job y del worker; `procrastinate_jobs` con el job en `succeeded`.
>
> ### ModelArts habilitado (2026-08-12) — lo que destapó
>
> La credencial se reemplazó y responde **HTTP 200**. Con ella:
>
> - **La suite entera pasa: 268 tests, 0 fallos.** El que quedaba rojo
>   (`test_sobrecoste_estado`) solo esperaba a poder llamar al modelo.
> - **El extractor N3 funciona de verdad.** Sobre una ficha de prueba devuelve
>   una instancia con datos (`precio=24.9`, `stock=42`, `unidad='kg'`) y el
>   grounding check pasa **5 de 5**: ni un valor inventado. **B3 cerrado.**
>
> Y al poder correr el agente completo por primera vez, aparecieron tres cosas
> que el 403 tenía tapadas:
>
> **1. La búsqueda no buscaba tiendas.** La consulta era `f"{insumo} {pais}"` —
> literalmente `"quinua Peru"`— con `topic="general"`. Devolvía Wikipedia (del
> **pueblo** de Quinua, en Ayacucho), un blog de turismo, un vídeo de YouTube,
> un reel y una receta. Cero ofertas. El agente extraía de ahí productos como
> `'Acerca de'` con todo a null, que el grounding rechazaba después: N3 gastaba
> búsqueda y extracciones para no aportar nada.
> **Corregido.** Medido sobre quinua, arándano y cacao: **14 de 15 fichas de
> tienda reales** (Plaza Vea, Metro, Wong, Tottus, Vega y varios productores),
> frente a 0 de 5 antes.
>
> **2. Un `print()` podía tumbar un run ya pagado.** `ejecutar()` imprimía el
> progreso con emojis dentro de su `try`; en consola cp1252 eso lanza
> `UnicodeEncodeError`, el `except` lo recogía y devolvía el run entero como
> `estado='error'` con cero productos. Pasado a `logger`.
>
> **3. El timeout de extracción estaba por debajo de lo que el modelo tarda.**
> Medido: **15,4 s** para 828 caracteres y **41,8 s** para 365 — no escala con
> el tamaño porque glm-5.2 razona antes de responder. Con el límite de 30 s, las
> tres tiendas de una pasada real agotaron el timeout. Subido a 60 s.
>
> ### El renderizado, resuelto sin renderizador (2026-08-12)
>
> El diagnóstico era que las fichas no dan precio a `trafilatura` —Falabella
> devolvía 828 caracteres y el modelo sacaba `nombre='; '`— porque el precio lo
> pinta JavaScript. La salida evidente era meter un navegador (Scrapling está
> como stub sin instalar; Bright Data existe en S5).
>
> **No hizo falta.** El precio *sí* está en el HTML inicial: casi todas las
> plataformas de comercio publican la ficha en `<script type="application/ld+json">`
> con vocabulario `schema.org/Product`, y `trafilatura` la tiraba junto con el
> resto de los `<script>`. Se tiraba la única copia fiable del dato que se venía
> a buscar.
>
> Medido sobre ocho fichas peruanas: **cinco traen nombre, precio y moneda
> exactos**. Nuevo módulo
> [casos_de_uso/agente/datos_estructurados.py](casos_de_uso/agente/datos_estructurados.py),
> que entra **antes** que el modelo:
>
> | | Antes | Después |
> |---|---|---|
> | Ofertas de "quinua" | 0 | **5** |
> | Tiempo | 103 s (3 timeouts) | **9,9 s** |
> | Llamadas al modelo | 3 (pagadas, inútiles) | **0** |
> | Precio | inventado o nulo | exacto, el que publica la tienda |
>
> Es mejor que un navegador en todo lo que importa aquí: exacto en vez de
> interpretado, gratis, instantáneo, y captura páginas de categoría enteras
> (Vega da tres quinuas en una URL). El modelo se queda de respaldo para las
> fichas sin datos estructurados, que es donde de verdad aporta.
>
> **Tres defectos más, encontrados al montarlo:**
>
> 1. **La evidencia no habría servido.** Se guardaban los primeros 6.000
>    caracteres del HTML, pero el JSON-LD empieza en el carácter 202.210 en Vega
>    y en el 134.407 en frutossecosdeperu. El grounding check no habría
>    encontrado nada y la regla `grounding_ok` habría rechazado ofertas buenas.
>    Ahora la evidencia es el nodo JSON del que sale cada oferta.
> 2. **El grounding comparaba números como texto.** Daba por no encontrado un
>    `6.0` contra una página que pone `6`. Ahora compara por valor.
> 3. **El modelo copiaba el ejemplo del esquema.** `ProductoSchema` llevaba un
>    `json_schema_extra` con "Quinua Orgánica Premium, 8.50, Cumbres Andinas";
>    instructor lo manda en la definición de la herramienta y el modelo lo
>    repetía cuando la página no tenía ficha — apareció como oferta encontrada
>    **buscando arándano**. Ejemplo retirado, y ahora una extracción sin nombre
>    o sin precio se descarta antes de entrar en cuarentena.
>
> ### `staging_agente` con datos reales
>
> [scripts/poblar_staging_real.py](scripts/poblar_staging_real.py) corre el
> agente por el camino de producción (`descubrir_n3`) y persiste con el
> repositorio nuevo. Resultado sobre quinua, arándano, cacao, café y maca:
>
> **11 ofertas reales de 7 tiendas distintas, las 11 con grounding en verde.**
> Metro 14,99; Campo Grande con una escalera de 100 g a 3 kg (4,38 → 82,60);
> Fideria 20,00; Frutos Secos 4,50. Antes de esto: 0 filas en tres semanas.
>
> **Suite completa: 268 tests, 0 fallos.**
>
> ### Todo en soles, con la tasa del día (2026-08-12)
>
> Las ofertas de fuera ya no se descartan: se convierten y se etiquetan.
> Adaptador nuevo [adaptadores/tipo_cambio.py](adaptadores/tipo_cambio.py).
>
> **La fuente es el BCRP**, por API abierta. Para un entregable de CITE es la
> citable, por la misma lógica que las regulaciones de S4 se citan contra eCFR
> o DIGESA y no contra un resumen de terceros. Las series se identificaron
> **consultando la API**, no de memoria — y menos mal: el código que parecía el
> del euro (`PD04645PD`) resultó ser `TC Cierre Compra 01:30 PM (S/ por US$)`,
> dólar otra vez.
>
> | Serie | Nombre que devuelve la API | Valor |
> |---|---|---|
> | `PD04640PD` | TC Sistema bancario SBS (S/ por US$) - Venta | 3.387 |
> | `PD04648PD` | TC Euro (S/ por Euro) - Venta | 3.949 |
>
> Se usa el tipo de **venta**: es el que pagaría quien tuviera que comprar esa
> moneda, y sobrestima antes que subestimar. Para monedas que el BCRP no
> publica hay un respaldo (exchangerate-api) **etiquetado como no oficial**,
> para que quien lea el informe distinga una cifra del banco central de una de
> un agregador.
>
> **Tres decisiones de diseño que importan:**
>
> 1. **El precio original no se pisa.** La conversión viaja aparte con su tasa,
>    su fecha y su fuente. Una cifra convertida sin la tasa con la que se
>    convirtió no es auditable: dentro de un mes nadie podría reconstruirla.
> 2. **Se convierte DESPUÉS de extraer y verificar.** Si `conversion_soles`
>    estuviera en `ProductoSchema`, instructor la mandaría en la definición de
>    la herramienta y el modelo se inventaría una tasa. Y el precio convertido
>    **no está en la página**: meterlo en `precio` haría fallar el grounding de
>    toda oferta de fuera.
> 3. **La fecha de la tasa es la del valor publicado, no la de hoy.** El BCRP no
>    publica fines de semana ni feriados. Decir "tipo de cambio del día" cuando
>    es el del viernes sería mentir en un informe.
>
> Resultado: **10 ofertas, las 10 con conversión y procedencia completa.**
> 8 en soles (tasa 1,0), 1 en dólares (BCRP 3.387, del 10-ago) y 1 en pesos
> colombianos (respaldo, marcado no oficial).
>
> ### Un defecto que la conversión destapó
>
> Al hacer visible el origen se vio que la búsqueda de "maca" había traído de
> una tienda colombiana **HARINA DE ARROZ, HARINA DE LENTEJA y HARINA DE SOYA**.
> No era la conversión: una página de categoría publica en su JSON-LD *todos*
> sus productos, y yo los estaba aceptando todos. Añadido
> `corresponde_al_insumo()`, que exige que el nombre contenga el insumo al
> principio de alguna palabra, sin tildes — así 'arandano' casa con 'Arándanos
> rojos' y no con 'Harina de arroz'. Se aplica también al camino del modelo,
> donde colaba un 'Pack Premium CATA- Caja Negra' como café.
>
> Y el lector de números del grounding, que comparaba como texto, ahora reutiliza
> el de `datos_estructurados`: dos parsers distintos para el mismo precio acaban
> discrepando.
>
> **35 tests nuevos** en
> [tests/test_s8_datos_estructurados.py](tests/test_s8_datos_estructurados.py),
> con casos sacados de páginas reales. **Suite: 303 tests, 0 fallos.**
>
> ### El conector VTEX: las cadenas, sin pagar renderizado (2026-08-12)
>
> Quedaba un agujero justo donde más duele: **Wong, Metro, Plaza Vea y Makro**
> —las cadenas que a CITE le importan— son aplicaciones de una sola página y el
> precio lo inyecta JavaScript. Ni JSON-LD, ni microdatos, ni OpenGraph; medido
> en las cuatro. La salida evidente era pagar un servicio que renderice.
>
> No hacía falta. **Las cuatro corren sobre VTEX, que expone un API público de
> catálogo**: sin anti-bot, sin credencial y sin coste.
>
> ```
> GET https://{tienda}/api/catalog_system/pub/products/search?ft={insumo}
> ```
>
> Y da **más** de lo que se sacaría raspando la ficha renderizada:
>
> | Dato | De dónde sale | Qué desbloquea |
> |---|---|---|
> | precio vigente y de lista | `commertialOffer.Price` / `ListPrice` | detectar descuento real |
> | **stock en unidades** | `commertialOffer.AvailableQuantity` | **la regla `stock_minimo`, apagada desde S7 porque ninguna fuente lo daba** |
> | **EAN** | `items[].ean` | comparar el MISMO producto entre cadenas |
> | marca, categoría, unidad | `brand`, `categories`, `measurementUnit` | filtrar y agrupar |
>
> Adaptador nuevo: [adaptadores/catalogo_vtex.py](adaptadores/catalogo_vtex.py),
> enganchado en `descubrir_n3` **antes** del agente. Las cuatro tiendas se
> consultan en paralelo y una caída no cancela a las demás; si el agente falla
> después, las ofertas del catálogo se conservan igual.
>
> **Qué tiendas y por qué.** Se probó una por una. Responden: Wong, Metro, Plaza
> Vea, Makro, Oechsle y Promart. Solo entran las cuatro de alimentación —Oechsle
> es tienda por departamentos y Promart ferretería, y para un insumo
> agroalimentario solo aportarían ruido—. Tottus devuelve 503; Vivanda y Tambo
> no exponen el API.
>
> **Tres cosas que hubo que resolver, y no son detalles:**
>
> 1. **El precio quedaba fuera de la evidencia.** Es el mismo error del JSON-LD,
>    repetido: guardar el nodo recortado a 8.000 caracteres deja fuera
>    `items[].sellers[].commertialOffer`, que va detrás de imágenes y
>    especificaciones. El grounding daba por inventado un precio que la tienda
>    sí publica, y `grounding_ok` habría rechazado la oferta. La evidencia se
>    construye ahora con los campos que respaldan cada valor, no recortando un
>    volcado por donde caiga.
> 2. **99.999 no es stock.** VTEX usa cifras centinela para "hay de sobra".
>    Guardarlas como unidades haría que `stock_minimo` diera por bueno todo, que
>    es peor que no tener el dato. Por encima de 10.000 no se guarda.
> 3. **El buscador de VTEX es generoso.** Para 'arándano' devolvió un
>    *"Smartphone MOTOROLA G17 6.8\" 4GB 128GB **Arándano**"* — arándano es el
>    color del teléfono, y por nombre casa perfecto. Lo delata su categoría:
>    `/Tecnología/Telefonía/`. Se descartan departamentos que no venden comida.
>    La lista es corta a propósito y se equivoca hacia dejar pasar: un champú de
>    maca o una galleta de arándano **sí** son mercado del insumo.
>
> **La moneda la pone la tienda, no la página.** El API no la declara. Se marca
> PEN porque es una propiedad de la cadena —las cuatro son peruanas y venden en
> soles—, y eso va en la tabla de tiendas, a la vista, no escondido en el código
> que mapea campos.
>
> #### Resultado medido, por el camino de producción
>
> `staging_agente` pasó de 0 filas en tres semanas a **129**, todas con
> grounding en verde y todas con conversión a soles:
>
> | | |
> |---|---|
> | ofertas en cuarentena | **129** |
> | grounding en verde | **129 / 129** |
> | con conversión a soles | **129 / 129** |
> | con EAN | 88 / 104 en la primera tanda |
> | con stock real (no centinela) | 81 / 104 |
> | tiendas distintas | 4 cadenas VTEX + 4 de la web abierta |
>
> Pasada limpia sobre un insumo nuevo (kiwicha): **25 ofertas, 25 con grounding
> en verde** — 19 de las cuatro cadenas, 5 por JSON-LD y 1 del modelo.
>
> **Y lo que esto habilita de verdad**: 17 productos aparecen con el **mismo EAN
> en dos o más cadenas**. Eso ya no es una lista de ofertas sueltas, es un mapa
> comercial:
>
> ```
> 7707211637829   Makro S/45.90   |  Plaza Vea S/54.90    (+19,7 %)
> 7752025007023   Metro S/ 8.40   |  Wong      S/ 9.20    (+9,5 %)
> 7759699000152   Plaza Vea S/9.80|  Wong S/9.90 | Metro S/9.90
> ```
>
> **21 tests nuevos** en
> [tests/test_s8_catalogo_vtex.py](tests/test_s8_catalogo_vtex.py), con el nodo
> real de Metro como fixture y sin salir a la red.
> **Suite completa: 324 tests, 0 fallos.**
>
> ### FASE 1 — Esqueleto del panel (2026-08-12)
>
> La SPA navegaba con un `ref` llamado `vista` y una cadena de `v-else-if`. Con
> tres pestañas se aguantaba; con seis pantallas más, no — y el problema no se
> arregla añadiendo ramas: **no había URL**, así que no se podía enlazar una
> pantalla, ni volver con el botón de atrás, y **recargar te devolvía siempre al
> principio**.
>
> #### El hueco que había que tapar primero
>
> **El frontend no tenía forma de saber el rol del usuario.** `/token` devuelve
> token y correo; `/uso`, el plan. El rol no salía por ningún endpoint, así que
> el guard de admin (1.2) no se podía ni escribir. Añadido `GET /api/sesion`,
> que devuelve `{usuario_id, email, rol}`.
>
> Es de lectura y **no autoriza nada**. Lo que devuelve viaja al navegador,
> donde cualquiera lo reescribe desde las herramientas de desarrollo; quien
> decide sigue siendo `requiere_admin` en cada endpoint. Sirve para no enseñar
> una puerta que se va a cerrar en la cara. Por eso mismo **el rol no se guarda
> en `localStorage`**: se vuelve a pedir al servidor en cada sesión, mientras
> que el token y el correo sí se guardan porque hacen falta para reanudar.
>
> #### Lo entregado
>
> | | |
> |---|---|
> | 1.1 vue-router + barra lateral | `src/router/index.js`, `App.vue` reescrito como shell |
> | 1.2 guard de sesión y de admin | `beforeEach`, con `volverA` para no perder el destino |
> | 1.3 las 3 pestañas a rutas | `/consulta`, `/alertas`, `/promociones` |
>
> **El menú se dibuja recorriendo el router**, no con una lista aparte: cada
> ruta declara en `meta` su título, su grupo y si es de administración. Una
> pantalla nueva se añade en un solo sitio, y es imposible que salga en el menú
> sin ruta o al revés. Las fases 2-4 solo tienen que añadir entradas con
> `meta.admin`.
>
> Las tres pantallas se cargan bajo demanda: quien solo consulta precios ya no
> descarga el panel de promociones. El *bundle* de entrada bajó a 98 kB y
> Promociones (9 kB) y Alertas (9 kB) salieron a trozos aparte.
>
> #### Dos cosas que el cambio destapó
>
> 1. **El resultado de la consulta se habría perdido al navegar.** Vivía en
>    `App.vue`, que envolvía las pestañas, así que ir a Alertas y volver lo
>    conservaba. Al pasar Consulta a ser una ruta, su estado se destruye al
>    salir: asomarse a Promociones habría borrado una búsqueda que cuesta
>    dinero y medio minuto. Movido a un módulo aparte, y **se borra al cerrar
>    sesión** para que quien entre después en el mismo navegador no se
>    encuentre la búsqueda de la persona anterior.
> 2. **`volverA` era un redirector abierto.** El destino tras el login viene de
>    la barra de direcciones. Se acota a rutas internas: una sola barra al
>    principio, porque `//evil.pe` es protocolo-relativa y el navegador la
>    trataría como otro dominio.
>
> #### Verificación
>
> - `/api/sesion` contra las dos cuentas reales: premium → `admin`,
>   gratuita → `operador`, sin token → 401.
> - Las seis rutas sirven la SPA (`/`, `/consulta`, `/alertas`,
>   `/promociones`, `/login`, y una inexistente): recargar en cualquiera carga
>   el panel y el router la resuelve. **DoD cumplido.**
> - **4 tests nuevos** en [tests/test_s8_sesion.py](tests/test_s8_sesion.py),
>   centrados en que el rol lo pone el servidor y no la petición.
>   **Suite: 328, 0 fallos.**
>
> **Aviso de despliegue:** el modo historia exige que el servidor estático
> devuelva `index.html` en cualquier ruta. En desarrollo lo hace Vite; en el
> repo no hay configuración de despliegue, así que cuando la haya tendrá que
> llevar el *fallback* o `/promociones` dará 404 al recargar.
>
> ### FASE 2 — Auditoría transversal, 8.3 (2026-08-12)
>
> De las **seis acciones** que 8.3 enumera, dejaba rastro **una**: la promoción
> manual, en `promotion_log` (S7.4). Y ese rastro sirve para promociones, no
> para responder la pregunta de 8.3 —"quién cambió esto y qué había antes"—
> sobre cualquier cosa que se toque desde el panel.
>
> #### B4 era menos grave de lo que parecía
>
> El bloqueador decía "hay dos tablas llamadas `audit_log`". Mirándolas:
>
> - **`public.audit_log`** (Postgres): huérfana del esquema S1, **0 filas**,
>   solo la menciona `create_schema_s1.sql`. Ningún Python la toca. Y su forma
>   —`(evento, tabla, fila_id, detalles)`— no sirve: le falta el antes/después.
> - **`adaptadores/audit_log.py`**: es una **tercera** cosa. Un log técnico en
>   SQLite (`level, component, message`) para el canario y los conflictos de
>   dedup. Lo usan 3 módulos y funciona.
>
> No compiten: una está muerta y la otra es un log operativo con el nombre mal
> puesto. Tabla nueva con nombre inequívoco, `auditoria_panel`, y **la huérfana
> no se toca**: borrar una tabla es del dueño del esquema, no de una migración
> que viene a crear otra cosa. Queda anotado al final de la 009.
>
> #### Tres decisiones de diseño
>
> **1. Solo inserción, con trigger.** Un registro que se puede editar o borrar
> no es una auditoría: es un log. Y la aplicación se conecta como dueña del
> esquema, así que un `revoke` no la detendría. El trigger sí, y deja el motivo
> por escrito:
>
> ```
> update -> auditoria_panel es de solo insercion (se intento UPDATE).
>           Para caducar datos, elimina la particion del mes con drop table.
> ```
>
> **2. Partición por mes — pero no por volumen.** CITE hará miles de filas al
> año, no millones. El motivo es la **retención de un año** que pide S8: con
> particiones, caducar un mes es `drop table` (instantáneo) en vez de un
> `delete` que deja páginas muertas. Se crean 13 meses por delante y hay una
> partición por defecto como red: perder una escritura de auditoría es peor que
> tenerla en el sitio equivocado.
>
> **3. El correo se copia, no se resuelve al leer.** Y el resumen de la oferta
> también. No es duplicar por duplicar: **`staging_agente` tiene un TTL de
> 24 h**, así que una entrada que solo guardara el `staging_id` sería ilegible
> al día siguiente — y la auditoría se conserva un año.
>
> #### La auditoría no tumba la acción que audita
>
> `registrar()` no propaga excepciones. Es incómodo y va en esa dirección a
> propósito: entre "promover y no poder anotarlo" y "no poder promover porque
> la auditoría está caída", lo segundo convierte el fallo de un registro
> accesorio en una caída del panel. El fallo se anota con `error`, no se pierde.
>
> #### Lo entregado
>
> | | |
> |---|---|
> | 2.1 | [009_auditoria_panel.sql](supabase/migraciones/009_auditoria_panel.sql) — aplicada, 14 particiones |
> | 2.2 | [adaptadores/auditoria_panel.py](adaptadores/auditoria_panel.py), enganchado en promover, rechazar y **login** |
> | 2.3 | `GET /api/auditoria` con filtros (acción, correo, rango de fechas) y paginación |
> | 2.4 | `GET /api/auditoria/export.csv`, con los mismos filtros que la tabla |
> | 2.5 | [Auditoria.vue](frontend/src/components/Auditoria.vue) — tabla, detalle antes/después con las claves que cambiaron resaltadas, y paginación |
>
> **Marcador de 8.3, actualizado:**
>
> | Acción | Antes | Ahora |
> |---|---|---|
> | `promotion_manual` | ✅ solo en promotion_log | ✅ con antes/después |
> | `promotion_rejected` | ❌ | ✅ |
> | `login` | ❌ | ✅ |
> | `plan_changed` | ❌ | fase 3 |
> | `kill_switch_toggled` | ❌ | fase 3 |
> | `rule_updated` | ❌ | el editor de 7.2 sigue sin construirse |
> | `export` | ❌ | evento reservado; 8.7 quedó fuera de S8 |
>
> #### Dos cosas que se corrigieron sobre la marcha
>
> 1. **El mismo dato en columnas distintas.** En `promotion_manual` el resumen
>    de la oferta iba en `detalles` y en `promotion_rejected` en `antes`. Ahora
>    `antes`/`despues` son siempre el cambio de estado y `detalles` siempre el
>    contexto. Un rechazo no cambia la fila —sigue en cuarentena hasta que el
>    TTL se la lleve—, así que sus dos columnas van vacías: rellenar un
>    "después" para que no quede en blanco sería afirmar un cambio que no
>    ocurrió.
> 2. **Los tests de S7 escribían en la tabla real.** `_auditoria` es de módulo,
>    así que promover con un repo falso llamaba a la auditoría de verdad con
>    `staging_id` inventados. Hoy no pasaba, pero **por accidente**: los tests
>    no leen `.env`, la conexión falla y `registrar` se lo traga. Ahora el
>    doble se instala siempre.
>
> #### Verificación
>
> - Migración aplicada contra Supabase: 14 particiones, el insert enruta a
>   `auditoria_panel_2026_08`, `update` y `delete` bloqueados, partición por
>   defecto vacía.
> - Recorrido real por la API: login, promover y rechazar dejaron sus tres
>   entradas; filtros por acción, correo parcial y rango de fechas; paginación
>   sin solape.
> - CSV: BOM UTF-8, CRLF, 10 columnas, cabeceras de aviso de corte.
> - Control de acceso en las tres rutas: admin 200, operador **403**, sin token
>   **401**.
> - **35 tests nuevos**: 27 en
>   [test_s8_auditoria.py](tests/test_s8_auditoria.py) y 8 en la clase de
>   auditoría de
>   [test_s7_api_promociones.py](tests/test_s7_api_promociones.py).
>
> ### FASE 3 — Kill-switch y planes, 8.5 y 8.9 (2026-08-12)
>
> **B5 tenía razón: el kill-switch no era un switch.** Lo que había era un
> umbral calculado —`gasto_global_mes >= PRESUPUESTO_GLOBAL_MES_USD`—, sin
> estado persistido, sin forma de accionarlo a mano y, por tanto, sin nada que
> auditar.
>
> #### Por qué una tabla y no otra variable de entorno
>
> Los topes viven en el entorno y está bien: son política, cambian cuando
> cambia el presupuesto del proyecto y tocarlos es un despliegue. El
> kill-switch es lo contrario: **se acciona durante un incidente**, por alguien
> que no tiene acceso al servidor, y después hay que poder responder quién lo
> apagó y cuándo. Nada de eso cabe en una variable de entorno.
>
> `sistema_config` es clave-valor con jsonb porque las fases siguientes van a
> necesitar más ajustes y una columna por ajuste obliga a una migración por
> cada uno. El precio es que Postgres no valida la forma del valor, y por eso
> la valida el adaptador — con `is True`, no con `bool(...)`: un `{"activo":
> "sí"}` escrito a mano contra la base pararía el sistema entero.
>
> #### Dónde encaja en la arquitectura
>
> `Presupuesto` es aritmética sobre topes y no sabe leer una tabla, así que la
> parada llega **como un dato** (`parada_manual`) y la lee `atender_consulta`,
> que ya es la frontera donde se resuelven el entitlement y el contexto. Puerto
> `ConfiguracionSistema` + adaptador `ConfiguracionPostgres`, igual que el
> resto.
>
> Se lee **en cada run, sin caché**: es una lectura indexada de una fila, y un
> kill-switch que tarda un minuto en surtir efecto no es un kill-switch.
>
> **Dos asimetrías deliberadas:**
>
> - **Leer falla a apagado; escribir falla hacia arriba.** Un error de lectura
>   que dejara el sistema parado convertiría una incidencia de base de datos en
>   una caída del servicio. Pero si un administrador pulsa «parar» y no se
>   guarda, tiene que enterarse: un botón que dice haber parado el gasto sin
>   haberlo parado es peor que uno que da error.
> - **`nivel_agotado()` devuelve `'manual'`, pero `motivo_parcial` sigue siendo
>   `'presupuesto'`.** La columna tiene un check de tres valores y `'manual'` lo
>   violaría. Dentro, el nombre propio importa: «se paró el gasto» y «se acabó
>   el presupuesto del mes» no son la misma noticia.
>
> #### El DoD, verificado sobre el sistema real
>
> Con el interruptor encendido, `POST /consultas`:
>
> ```
> HTTP 200  en 2,7 s
> ejecuciones.estado         = parcial
> ejecuciones.motivo_parcial = presupuesto
> etapas ejecutadas          = 0     coste = $0.00     tokens = 0
> ```
>
> Degrada, no falla — el principio del ADR-001. Y el interruptor quedó apagado
> otra vez al terminar.
>
> #### Lo entregado
>
> | | |
> |---|---|
> | 3.1 | [010_sistema_config.sql](supabase/migraciones/010_sistema_config.sql) — aplicada, arranca apagada |
> | 3.2 | `parada_manual` en `Presupuesto`, leída en `atender_consulta`; puerto + adaptador |
> | 3.3 | `GET/PUT /api/admin/kill-switch`, auditado |
> | 3.4 | `GET /api/admin/usuarios` y `PUT /api/admin/usuarios/{id}/plan`, auditado |
> | 3.5 | [Control.vue](frontend/src/components/Control.vue) — semáforo verde/naranja, motivo, confirmación y tabla de planes con el gasto del mes |
>
> `/uso` también se corrigió: calculaba `kill_switch_activo` solo con el umbral
> de gasto, así que con el sistema parado a mano el usuario veía verde — justo
> el caso en que más falta hace saberlo.
>
> **Solo se audita si el estado cambió de verdad.** El panel refresca; si cada
> refresco dejara una entrada, entre ellas se perdería la única que importa: la
> vez que alguien lo apagó. Verificado: tres PUT, dos entradas.
>
> **Marcador de 8.3 tras esta fase:** `kill_switch_toggled` y `plan_changed`
> pasan a ✅. Quedan `rule_updated` (el editor de 7.2 nunca se construyó) y
> `export` (8.7 quedó fuera de S8).
>
> #### Verificación
>
> - Control de acceso en las cuatro rutas: admin 200, operador **403**, sin
>   token **401**. Un operador no acciona el interruptor ni por accidente.
> - Recorrido real: encender, reenviar el mismo estado (sin auditar), apagar;
>   subir y bajar de plan a un usuario y devolverlo a su valor original.
> - Errores: plan inventado **400**, usuario inexistente **404**, uuid
>   malformado **400**, motivo de más de 280 caracteres **422**.
> - **31 tests nuevos** en [test_s8_control.py](tests/test_s8_control.py),
>   incluido el camino completo `atender_consulta` → `Presupuesto`.
>
> ### Lo que queda abierto
>
> **Café ya da ofertas** (5 por cadena, más una de la web abierta): lo resolvió
> el conector, no el renderizado. Lo que sigue sin ceder es el 20 % de tiendas
> propias que se defienden con 403 — ahí sí haría falta N2 / Bright Data, pero
> **como excepción por dominio y no como transporte general**: sobre 24 URL
> medidas solo una se perdía de verdad por anti-bot.
>
> **`stock_minimo` se puede reactivar.** Estaba apagada en `promotion_rules`
> desde S7 porque ninguna fuente daba stock. El API de VTEX lo da, y 81 de 104
> ofertas de la primera tanda traen unidades reales. Es un `update` de una fila
> de reglas, pero conviene hacerlo cuando el panel de promoción esté delante
> para ver el efecto.
>
> **Las ofertas de fuera se conservan.** Convertidas y comparables, pero un mapa
> comercial peruano con maca de Walmart y de una tienda colombiana mezcla
> mercados distintos. Si CITE quiere solo oferta nacional, el sitio natural es
> una regla de `promotion_rules` (S7.2) y no un descarte al ingerir: así queda
> a la vista de quien revisa en vez de desaparecer.
>
> **La cascada sigue sin correr en el flujo principal**: `api/main.py` inyecta
> `DescubrimientoSnapshot`, que no tiene `descubrir_sync`. Conectarla mete red,
> coste y latencia en `/consultas` —y con 60 s por extracción, el techo de 120 s
> de `descubrir_n3` da para dos URL—. Es una decisión de producto, no un cable
> suelto. Queda anotado en el docstring del repositorio nuevo.

---

## 🔴 RESUMEN EJECUTIVO (auditoría previa, 2026-08-11)

S8 pide un panel donde el cliente vea **todo**. El problema no es construir las
pantallas: es que **no hay qué mostrar en ellas**.

De las 36 tablas que hay en Postgres, **27 están a 0 filas**. Y los datos reales
del sistema —82 ejecuciones, 188 etapas, 60 entradas de caché— no están en
Postgres: están en el **SQLite del plan B**, que es precisamente el backend
donde los routers de S6 y S7 ni siquiera se montan
([api/main.py:54-58](api/main.py#L54-L58)).

Peor: con la configuración actual (`APP_DB=supabase` en `.env`) **no se puede
iniciar sesión**. `auth.users` tiene **0 filas**. No hay usuarios, no hay
perfiles, no hay admin. Los endpoints de promoción de S7.6 responderían 403 a
cualquiera que consiguiera un token, porque `rol_de()` devuelve `'operador'`
cuando no encuentra fila en `perfiles`
([api/auth.py:99-102](api/auth.py#L99-L102)).

**Complejidad real: ALTA**, y con el reparto de esfuerzo invertido respecto al
que declara el plan. S8 dice "Frontend (2) + Backend (1)". Lo que hay que hacer
es ~70 % backend: seis de las diez pantallas leen de tablas, endpoints o
instrumentación **que no existen**.

---

## 📊 ESTADO MEDIDO DE LA BASE DE DATOS (2026-08-11)

Consultado contra `db.qjhogpbgahedpblnalvl.supabase.co`. **36 tablas, 7 vistas.**

### Lo que tiene filas

| Tabla | Filas | Sirve a |
|---|---:|---|
| `ingredientes_cite` | 25 | S4 |
| `alert_scores` | 10 | 8.4 (sección 1) |
| `openfda_alerts` | 10 | 8.4 (sección 1) |
| `promotion_rules` | 6 | 8.6 / editor de 7.2 |
| `taxonomia_cite` | 5 | S4 |
| `tendencias_insumo` | 5 | S4 |
| `audit_claims` | 4 | — |
| `presupuesto_config` | 2 | 8.2 (cuotas) |
| `alert_ingest_log` | 2 | 8.4 (frescura) |

### Lo que S8 necesita y está vacío

| Tabla | Filas | Ítem de S8 que se queda sin datos |
|---|---:|---|
| `auth.users` | **0** | **todo el panel: no hay login** |
| `perfiles` | **0** | 8.9 (planes), rol admin de 8.5 y 8.6 |
| `ejecuciones` | 0 | 8.2, 8.7 |
| `etapas_ejecucion` | 0 | 8.2 (desglose por etapa), 8.8 (cache hit) |
| `presupuesto_uso` | 0 | 8.2 (fuente declarada) |
| `eventos_job` | 0 | 8.1 |
| `procrastinate_jobs` | 0 | 8.1 |
| `procrastinate_workers` | 0 | 8.4 (heartbeat) |
| `informes` | 0 | 8.7 |
| `staging_agente` | 0 | 8.6 |
| `promotion_log` / `_validation_log` / `_watermark_log` | 0 | 8.3, 8.6 |
| `ecfr_regulations`, `efsa_regulations`, `codex_standards`, `inacal_nts`, `digesa_directivas` | 0 | 8.4 (frescura de corpus) |
| `audit_log` | 0 | 8.3 — y además es un huérfano, ver B4 |

### Y en paralelo, SQLite (`agroscout.db`)

| Tabla | Filas |
|---|---:|
| `ejecuciones` | **82** |
| `etapas_ejecucion` | **188** |
| `cache_llm` | 60 |
| `usuarios` | 2 |

**Dos fuentes de verdad, y la que tiene datos es la que no soporta las
pantallas nuevas.** Esto no es un detalle de despliegue: decide si el panel de
S8 se construye sobre datos o sobre una maqueta.

---

## 🚧 BLOQUEADORES

### B0 — No hay usuarios en Supabase (afecta **todo**)

`select count(*) from auth.users` → **0**.

`.env.local` guarda `PASSWORD_DEMO_GRATUITA` y `PASSWORD_DEMO_PREMIUM`, así que
las cuentas demo estaban previstas, pero **no existen en la base**. Con
`APP_DB=supabase`, `/token` proxea el password grant de Supabase
([api/main.py:199-210](api/main.py#L199-L210)) y devolvería 401 siempre.

Consecuencia en cadena: `perfiles` vacío → `rol_de()` = `'operador'` →
`requiere_admin` da 403 → **los botones de promover de S7.6 y el kill-switch de
8.5 son inalcanzables**, aunque el código esté bien.

### B1 — Dos backends divergentes (afecta 8.1, 8.2, 8.3, 8.4, 8.7)

| | Postgres (`APP_DB=supabase`) | SQLite (plan B) |
|---|---|---|
| Login | imposible (B0) | 2 usuarios |
| Ejecuciones / etapas | 0 / 0 | 82 / 188 |
| Router de alertas (S6) | montado | **no montado** |
| Router de promociones (S7) | montado | **no montado** |
| Tablas de promoción y alertas | existen | no existen |

Hay que elegir uno **antes** de escribir una línea de panel, y sembrarlo. Si no,
cada pantalla se construirá contra la mitad que tenga a mano.

### B2 — No hay jobs que mostrar (afecta 8.1, y 8.7 por dependencia)

8.1 es "Dashboard de jobs (live progress)". El sistema **no encola ni un solo
job**:

- `grep '\.defer('` en todo el repositorio da **dos** resultados, ambos en
  [scripts/test_job.py](scripts/test_job.py). Ninguno en el camino de producción.
- `/consultas` ejecuta `atender_consulta` **dentro del request**
  ([api/main.py:233](api/main.py#L233)). No es un job.
- Existen tres tareas definidas (`job_agente_run`, `job_mim_etl`,
  `job_informe_pdf`) y dos periódicas registradas —alertas a las 03:00 UTC
  ([config/job_alert_ingest.py:456](config/job_alert_ingest.py#L456)) y promoción
  a las 04:00 ([config/job_promotion_auto.py:202](config/job_promotion_auto.py#L202)).
  **Ninguna se ha ejecutado nunca**: `procrastinate_jobs` = 0,
  `procrastinate_workers` = 0, `eventos_job` = 0.

Y el WebSocket que existe no es el que pide 8.1:

- Es `/ws/run/{run_id}` —uno por ejecución—, no `/ws/jobs` —listado global—.
- **No hace streaming.** Manda el histórico y luego se queda esperando pings
  del cliente ([api/websocket_jobs.py:83-92](api/websocket_jobs.py#L83-L92)).
  El propio código lo dice: *"In production, use PostgreSQL LISTEN/NOTIFY for
  true streaming"*. El "actualiza cada 2 s" de 8.1 no está implementado.

### B3 — El cost-meter apunta a una tabla que nadie escribe (afecta 8.2)

8.2 declara dependencia `presupuesto_uso (S2)`. Esa tabla tiene **0 filas**, y
su único escritor es
[api/middleware_presupuesto.py:104](api/middleware_presupuesto.py#L104) —un
módulo que **no importa nadie**. Es código muerto: `main.py` no lo monta, ningún
endpoint usa `@presupuesto_guard`, ninguna prueba lo toca.

Los costos reales se escriben en `etapas_ejecucion`, desde
[adaptadores/auditoria_postgres.py](adaptadores/auditoria_postgres.py) (0 filas
en Postgres, 188 en SQLite). Ahí están `costo_usd`, `tokens_entrada`,
`tokens_salida`, `etapa`, `modelo` y `cache_hit`: **todo lo que 8.2 pide en su
tabla**, salvo el eje "Tenant", que no existe (ver B7).

Hay que decidir de dónde lee el cost-meter. Mantener las dos tablas es
garantizar que den cifras distintas.

### B4 — No existe audit trail, y hay dos tablas llamadas `audit_log` (afecta 8.3)

1. **`public.audit_log` en Postgres** existe, con esquema
   `(evento, usuario_id, tabla, fila_id, detalles, timestamp)`. Es un **huérfano
   del esquema S1** ([scripts/create_schema_s1.sql:71-79](scripts/create_schema_s1.sql#L71-L79)),
   que sobrevivió a la limpieza de S7 porque no estaba en la lista de borrado.
   **Ningún código Python la escribe ni la lee.** Y no tiene antes/después, que
   es justo lo que 8.3 pide al hacer clic en una fila.
2. **`adaptadores/audit_log.py`** es otra cosa distinta con el mismo nombre:
   SQLite, esquema `(level, component, message, data, timestamp)`, usada por
   `canario_check` y `cobertura_calculator`. Incompatible con la anterior.

De las **seis acciones** que 8.3 enumera, hoy deja rastro **una**:

| Acción de 8.3 | ¿Se registra hoy? |
|---|---|
| `promotion_manual` | ✅ `promotion_log` (S7.4) |
| `plan_changed` | ❌ no existe el endpoint |
| `kill_switch_toggled` | ❌ no existe el switch (B5) |
| `rule_updated` | ❌ el editor de 7.2 nunca se construyó |
| `login` | ❌ el login pasa por Supabase Auth y no se anota |
| `export` | ❌ no existe la exportación (B8) |

La retención de 1 año, la partición por mes y el archivado a S3 que menciona la
tabla de riesgos: **nada de eso está**.

### B5 — El kill-switch no es un switch (afecta 8.5)

8.5 pide un **checkbox** con estado verde/naranja. Lo que hay es un **umbral
calculado**: `gasto_global_mes >= PRESUPUESTO_GLOBAL_MES_USD`
([casos_de_uso/presupuesto.py:77-78](casos_de_uso/presupuesto.py#L77-L78),
expuesto en [api/main.py:389](api/main.py#L389)).

No hay estado persistido, no hay forma de activarlo a mano, y por tanto no hay
nada que auditar. Hace falta una tabla de configuración y que `Presupuesto` la
lea, además del endpoint admin.

Además, el test que propone 8.5 —*"nuevas consultas con nivel=3 devuelven sin
presupuesto disponible"*— está escrito contra un modelo que ya no existe:
`nivel_maximo_costo` murió con el esquema S1. Hoy el equivalente es
`perfiles.plan` → `Entitlement.etapas_permitidas`
([casos_de_uso/politica_suscripcion.py:38-55](casos_de_uso/politica_suscripcion.py#L38-L55)).
Y el comportamiento correcto no es devolver un error: es cerrar el run en
`parcial` con `motivo_parcial='presupuesto'` y responder **200**. Degradar, no
fallar — es el principio del ADR-001 y está documentado en
[casos_de_uso/presupuesto.py:13-17](casos_de_uso/presupuesto.py#L13-L17).

### B6 — No hay observabilidad (afecta 8.8)

8.8 declara dependencia *"Observabilidad (S1), Prometheus queries"*.
**No hay Prometheus.** Ni exporter, ni endpoint `/metrics`, ni la dependencia
en `pyproject.toml`. Las únicas coincidencias de "prometheus" en el repositorio
son comentarios sueltos.

Lo que existe es [/health](api/health.py), que comprueba conexión a Postgres,
Redis y DuckDB. Útil, pero no mide nada de lo que 8.8 pinta:

| SLO de 8.8 | ¿Medible hoy? |
|---|---|
| Etapas 1-3: 99.5 % uptime | ❌ no hay histórico de disponibilidad |
| Agente: 95 % uptime | ❌ ídem, y el agente N3 sigue siendo un stub (B3 de S7) |
| API latencia p95 < 500 ms | ⚠️ hay `etapas_ejecucion.duracion_ms`, pero es por etapa, no por request; falta instrumentar el middleware |
| DB replication lag < 100 ms | ❌ **no hay réplica**: una sola instancia Supabase gestionada |
| Cache hit rate > 80 % | ✅ calculable desde `etapas_ejecucion.cache_hit` |

Uno de cinco es medible tal cual. Pintar los otros cuatro en verde sería peor
que no pintarlos.

### B7 — No existe "tenant" (afecta 8.1, 8.2, 8.3, 8.9)

S8 pide una columna **Tenant** en tres de sus tablas y habla de
"demo-gratuita / demo-premium" como si fueran inquilinos. La única aparición de
`tenant` en todo el repositorio está en
[scripts/create_schema_s1.sql](scripts/create_schema_s1.sql) — el esquema muerto
que se borró de la base en S7.

**El multi-tenant se revirtió en S3.** El eje real es `usuario_id` +
`perfiles.plan` ('gratuito' | 'premium'). Hay que reescribir S8 en esos términos
o el panel prometerá una segmentación que la base no puede dar.

### B8 — 8.7 exporta informes que no existen

- `informes` = 0 filas. El PDF sí se genera
  ([adaptadores/informe_weasyprint.py](adaptadores/informe_weasyprint.py)) y se
  sube al bucket, pero la fila sólo se escribe si el run cierra contra Postgres.
- **No hay una sola línea de CSV en `api/`.** JSON es casi gratis (el informe ya
  es un modelo Pydantic y `/consultas` lo serializa con `model_dump(mode="json")`);
  CSV exige decidir el aplanado de un objeto anidado.
- "Trigger: enqueue job, WebSocket notifica cuando listo" → depende entero de B2.
- El TTL de 24 h existe a medias: `firmar_de_nuevo` firma a **3600 s**
  ([api/main.py:268](api/main.py#L268)).

### B9 — El frontend no aguanta seis pantallas más

- [App.vue](frontend/src/App.vue) son tres pestañas resueltas con `v-if`. S8
  añade seis o siete → una barra de diez botones y ningún enlace compartible.
- **No hay vue-router.** `package.json` tiene tres dependencias: `vue`, `marked`,
  `dompurify`. S6 y S7 dejaron esto anotado por escrito: *"cuando llegue el panel
  de S8 tocará replantearlo"* ([App.vue:43-45](frontend/src/App.vue#L43-L45)).
- **No hay librería de gráficos.** `PromocionesDashboard.vue` los hace a mano con
  flex y CSS, y está bien resuelto. Pero 8.2 pide serie temporal de 30 días +
  reparto por etapa + barras por usuario: la serie temporal ya no se hace con
  divs, hace falta SVG a mano o una dependencia.

---

## 🔍 AUDITORÍA ÍTEM POR ÍTEM

| Ítem | Viable hoy | Nota |
|---|---|---|
| **8.1** Dashboard de jobs | ❌ Bloqueado | B0, B1, B2. No hay jobs, ni worker, ni WS de listado, ni streaming real. |
| **8.2** Cost-meter | ⚠️ Parcial | Fuente equivocada (B3) y a 0 filas (B0/B1). Con los datos en Postgres, los gráficos son directos. Sin eje tenant (B7). |
| **8.3** Audit trail | ❌ Por construir entero | B4. 1 de 6 acciones deja rastro. Tabla huérfana que hay que adoptar o borrar. |
| **8.4** Alertas activas | ⚠️ 1 de 4 secciones | Retiradas ✅ (10 alertas + `AlertasRetiro.vue` ya montado). Corpus ❌ (5 tablas a 0 y sin registro de última ingesta). Cobertura ❌ (`mapa_comercial_metadata` vive en SQLite). Worker ❌ (0 heartbeats). |
| **8.5** Kill-switch UI | ⚠️ Backend por construir | B5. La UI es media hora; la tabla de estado, el guard y el test, no. |
| **8.6** Promovedor manual | ✅ **Ya hecho en S7.6** | [Promociones.vue](frontend/src/components/Promociones.vue) + 6 endpoints + rol admin. Falta sólo el "smart ordering" por precio, cuya regla está apagada por falta de datos. Cola a 0 filas. |
| **8.7** Export en lote | ⚠️ Parcial | B8. JSON es fácil; CSV es una decisión de diseño; el bulk asíncrono depende de B2. |
| **8.8** SLO dashboard | ❌ Bloqueado | B6. 1 SLO de 5 medible, 1 requiere instrumentar, 3 no tienen de dónde salir. |
| **8.9** Planes y entitlements | ⚠️ Casi | `perfiles.plan` y `perfiles.rol` existen y el entitlement **no se cachea**, así que el "efecto inmediato" sale gratis. Falta el endpoint admin, la UI y la auditoría del cambio. |
| **8.10** Documentación | ✅ Sí | Depende de lo que efectivamente se construya. |

---

## 🔁 CONTRADICCIONES DEL DOCUMENTO S8

1. **"Tenant" (8.1, 8.2, 8.3)** — no existe. Revertido en S3. El eje es usuario + plan.
2. **"`nivel_maximo_costo` se recalcula inmediato" (8.9)** — ese campo murió con el esquema S1.
3. **8.6 duplica S7.6**, que ya está entregado. La propia auditoría de S7 lo señaló (§Solapamientos, punto 1).
4. **"E1: 5 %, E2: 10 %…" (8.2)** — las etapas del sistema se llaman `1`, `2a`, `2b`, `3`, `4`, `5`. No hay E1-E5.
5. **"DB replication lag" (8.8)** — no hay réplica. Una sola instancia Supabase gestionada ([PLAN-TIERS-S3](PLAN-TIERS-S3.md)).
6. **"archive a S3 después de 90d" (riesgos)** — no hay bucket configurado para archivado; el único bucket es el de informes.
7. **"5 días · Frontend (2) + Backend (1)"** — el trabajo real es ~70 % backend. Con este reparto, dos personas de frontend se pasarían la semana esperando endpoints.
8. **8.4 depende de "Todas (6, 7, S4)"** — S4 está construido pero con las cinco tablas de corpus a 0 filas: la sección de frescura no tiene qué leer aunque el código funcione.

---

## ❓ DECISIONES — ✅ TOMADAS (2026-08-11)

**D1 — ¿Sobre qué base corre el panel, y con qué datos?**
✅ **Postgres, con siembra completa en la fase 0.** Crear las dos cuentas demo
en `auth.users`, comprobar que el trigger de `perfiles` dispara, nombrar un
admin y portar una muestra representativa de las 82 ejecuciones de SQLite.
Se descartó construir sobre SQLite: obligaría a portar los routers de S6 y S7,
que asumen Postgres y sus tablas, y dejaría la deuda intacta. Se descartó
también sembrar sólo usuarios: ocho de diez pantallas se entregarían vacías.

**D2 — ¿De dónde lee el cost-meter?**
Recomiendo: **`etapas_ejecucion`**, que es donde están los datos y lo que ya
escribe la auditoría. `presupuesto_uso` se queda sólo como registro del guard, o
se borra junto con `middleware_presupuesto.py`. Tener las dos es garantizar dos
cifras distintas para la misma pregunta.

**D3 — ¿Entra vue-router?**
Recomiendo: **sí, ahora.** Es el momento que S6 y S7 dejaron marcado, y diez
pestañas sin URL propia hacen el panel indefendible en una demo.

**D4 — ¿Qué hacemos con 8.8 sin Prometheus?**
✅ **Degradar ahora, instrumentar en S9.** El widget "System Health" se
construye con lo medible hoy —cache hit rate desde `etapas_ejecucion.cache_hit`,
disponibilidad de Postgres desde `/health`, y p95 si se instrumenta el
middleware—. Lo que no tiene fuente se marca **"sin instrumentar"**, nunca en
verde. Prometheus entra en S9, que ya es la semana de CI y carga.

**D5 — ¿Se acepta el recorte de alcance?**
✅ **Sí: núcleo en S8, resto a S9.** Reparto en la sección siguiente.

---

## 🎯 PLAN DE FASES (sujeto a D1-D5)

```
FASE 0 · Desbloqueo (1 día)          ← sin esto todo lo demás es una maqueta
  0.1 Decidir D1-D5
  0.2 Crear las 2 cuentas demo en auth.users; verificar el trigger de perfiles
  0.3 Nombrar el primer admin (update perfiles set rol='admin')
  0.4 Script de siembra: portar ejecuciones + etapas de SQLite a Postgres
  0.5 Fixtures de staging_agente (deuda D2 de S7, sigue abierta)
  0.6 Arrancar un worker de procrastinate una vez, para que haya heartbeat y
      los dos jobs periódicos dejen eventos
  0.7 Verificar login end-to-end contra Supabase        [cierra B0, B1]

FASE 1 · Esqueleto del panel (1 día)                              [B9]
  1.1 vue-router + layout con barra lateral
  1.2 Guard de sesión y guard de admin en el router
  1.3 Migrar las 3 pestañas actuales a rutas
  DoD: navegación por URL; recargar no pierde la página

FASE 2 · Auditoría transversal (1 día)                        [8.3]
  Va ANTES que los dashboards, porque 8.5 y 8.9 escriben en ella.
  2.1 Migración 009: tabla de auditoría del panel con antes/después (jsonb),
      partición por mes, y decidir qué se hace con el audit_log huérfano
  2.2 Helper registrar_auditoria() + engancharlo en promover/rechazar
  2.3 GET /api/auditoria con filtros (usuario, acción, fecha) y paginación
  2.4 Export CSV de auditoría
  2.5 UI: tabla + detalle antes/después
  DoD: las 6 acciones de 8.3 escriben; el export descarga

FASE 3 · Control: kill-switch y planes (0.5 día)          [8.5, 8.9]
  3.1 Migración: sistema_config(clave, valor, actualizado_por, actualizado_en)
  3.2 Presupuesto lee el switch manual → nivel_agotado() lo contempla
  3.3 GET/PUT /api/admin/kill-switch (requiere_admin) → audita
  3.4 GET/PUT /api/admin/usuarios/{id}/plan → audita
  3.5 UI "Presupuestos y Control"
  3.6 Test: switch on → el run cierra 'parcial' con motivo 'presupuesto' y 200
  DoD: el toggle funciona y queda auditado

FASE 4 · Cost-meter (1 día)                                   [8.2]
  4.1 GET /api/costos: serie diaria 30d, desglose por etapa, por usuario,
      cuota del plan y proyección de cierre de mes. Agregación en SQL, no en
      el cliente (es el primer riesgo que lista el propio S8)
  4.2 GET /api/costos/export.csv
  4.3 UI: serie temporal (SVG a mano), barra apilada por etapa, barras por
      usuario, barra de cuota. Mismo lenguaje visual que PromocionesDashboard
  DoD: CSV parseable; el endpoint responde < 500 ms con 30 días

FASE 5 · Jobs en vivo (1 día)                                 [8.1]
  5.1 Decidir el alcance: hoy sólo existen 2 jobs periódicos.
      (a) mover /consultas a job asíncrono — es deuda de S3, ~1 día extra
      (b) el dashboard lista los periódicos y sus eventos
  5.2 GET /api/jobs desde procrastinate_jobs + eventos_job
  5.3 WS /ws/jobs global, con LISTEN/NOTIFY sobre eventos_job
  5.4 UI: tabla, modal de logs, descarga .txt, reconexión a 5 s con fallback
      a polling (segundo riesgo que lista S8)
  DoD: un job periódico lanzado a mano aparece y avanza en vivo

FASE 6 · Alertas y salud (1 día)                          [8.4, 8.8]
  6.1 GET /api/panel/alertas con las 4 secciones. Las que no tienen fuente
      devuelven 'sin_dato' explícito, nunca un 0 que parezca un dato
  6.2 Registro de última ingesta por fuente de corpus (hoy no existe)
  6.3 Heartbeat de worker desde procrastinate_workers
  6.4 GET /api/salud con los SLOs medibles; el resto, 'sin instrumentar'  [D4]
  DoD: 4 tipos de alerta; el widget distingue verde de sin dato

FASE 7 · Export (0.5 día)                                     [8.7]
  7.1 GET /api/informes/{id}/export?formato=json|csv
  7.2 Bulk export: job + WS si la fase 5 lo permite; si no, síncrono con tope
  7.3 Subir la firma del enlace de 3600 s a 24 h
  DoD: el JSON valida contra el modelo; el CSV abre en Excel

FASE 8 · Documentación (0.5 día)                             [8.10]
  8.1 PANEL_USER_GUIDE.md con capturas reales
  8.2 Sección explícita: qué significa "sin dato" y por qué hay tanto
  8.3 Capacitación con CITE (1 h)
```

**Total realista: ~7,5 días**, no 5. Y ~5 de ellos son backend.

---

## ✂️ ALCANCE ACORDADO (D5)

**Se ejecuta en S8** — fases 0, 1, 2, 3, 4 y 8:

| Ítem | Cómo se entrega |
|---|---|
| 8.2 Cost-meter | Completo, leyendo `etapas_ejecucion` (D2) |
| 8.3 Audit trail | Completo, con antes/después y export CSV |
| 8.5 Kill-switch | Completo, con estado persistido y auditado |
| 8.9 Planes | Completo |
| 8.6 Promovedor manual | **Ya entregado en S7.6**; sólo se reubica en el router |
| 8.10 Documentación | Completo |

Seis de diez ítems, y son los que no dependen de infraestructura inexistente.
Son también los cuatro que CITE mira todos los días.

**Pasa a S9** — la semana de CI y carga, donde encajan por dependencias:

- **8.1** (jobs en vivo) — no tiene sentido antes de que existan jobs (B2).
- **8.8** (SLO) — no tiene sentido antes de instrumentar (B6, D4).
- **8.4** y **8.7** — se evalúan al cerrar el núcleo; hoy 8.4 tiene fuente para
  una de sus cuatro secciones y el bulk de 8.7 depende de B2.

---

## ✨ CONCLUSIÓN

**S8 no es ejecutable tal como está escrita**, y el motivo no es distinto al de
S7: la deuda arrastrada. Pero aquí duele más, porque un panel es precisamente lo
que hace visible que las tablas están vacías.

**El punto de partida obligatorio es la fase 0.** No por prolijidad: hoy la
aplicación configurada como está en `.env` **no permite iniciar sesión**. Todo
lo demás —diez pantallas, gráficos, WebSockets— se construiría sobre una puerta
cerrada.

Lo que sí tiene valor propio y se puede empezar en cuanto se resuelva D1:
la tabla de auditoría (8.3), el kill-switch persistido (8.5), los planes (8.9) y
el cost-meter (8.2). Son piezas que quedan bien al margen de cómo se resuelva el
resto, y son las cuatro que CITE va a mirar todos los días.

---

**AUDITORÍA COMPLETA. ESPERANDO D1-D5 PARA ARRANCAR.**
