<!--
  05 · El informe completo.

  ## Qué cambia y por qué

  **El sujeto de la pantalla es la consulta, no el sistema.** Antes lo primero
  que se leía era «🗺️ Mapa comercial» como un h4 perdido a media página,
  mientras el titular lo ocupaban tres insignias de estado y el consumo de
  tokens. Ahora arriba está el insumo consultado y sus tres cifras; el estado
  del run baja a chips y el consumo se va al pie, plegado en una línea.

  **El precio ausente se dice una vez.** La columna «Precio» salía vacía en las
  200 filas y la explicación estaba en un párrafo aparte, después de la tabla.
  Una columna vacía repetida doscientas veces se lee como avería; ahora la
  columna no existe en el grid y la razón sube al encabezado del bloque, en
  ámbar de aviso —no de error—, dicha una sola vez.

  **Filtros y dos vistas.** Con 200 productos y sin ningún filtro, la única
  forma de encontrar los que llevan aditivos era pasar ocho páginas leyendo. Se
  filtra en cliente sobre los datos que ya están cargados: no hay ninguna
  llamada nueva al servidor.

  **La tabla y el grid no paginan igual, a propósito.** La tabla mantiene sus
  25 filas por página porque es la vista que se compara con el PDF, que enseña
  esas mismas 25. El grid es para hojear, y ahí ir sumando tarjetas cansa menos
  que saltar de página en página.

  **Un solo control con color: `Analizar`.** Abre el análisis regulatorio, que
  consume saldo del plan. Todo lo demás —cambiar de vista, filtrar, paginar— es
  gratis y va en neutro. Cuando el ámbar aparece, quiere decir que cuesta.
-->
<template>
  <div v-if="result" class="informe animate-fade-in">
    <!-- ================= Cabecera ================= -->
    <header class="cabecera">
      <div class="cabecera-texto">
        <p class="eyebrow">Mapa comercial</p>
        <!--
          Las cifras salen del MISMO objeto que la tabla de abajo, no del
          markdown. El informe en markdown lleva sus propias cifras escritas
          por el modelo, y cuando las dos convivían podía verse 60/5/22 arriba
          y 200/22 abajo en la misma pantalla.
        -->
        <h1 :title="mapa?.insumo || result.insumo">
          {{ mapa?.insumo || result.insumo || 'Informe' }}
        </h1>

        <!-- Sin productos, las tres serían 0/0/0 y eso se lee como avería.
             La sección de abajo explica la ausencia con palabras. -->
        <div v-if="mapa?.productos?.length" class="cifras">
          <span><b class="num">{{ mapa.productos.length }}</b> productos</span>
          <span><b class="num">{{ nPaises }}</b> países</span>
          <span><b class="num">{{ nMarcas }}</b> marcas</span>
        </div>
      </div>

      <div class="cabecera-lado no-imprimir">
        <div class="estado">
          <span class="chip" :class="result.parcial ? 'chip--aviso' : 'chip--limpio'">
            <Icono :nombre="result.parcial ? 'info' : 'check'" :tamano="13" />
            {{ result.parcial ? 'Análisis parcial' : 'Análisis completo' }}
          </span>
          <span v-if="result.snapshot_version" class="chip chip--codigo">
            v{{ result.snapshot_version }}
          </span>
          <span v-if="result.elapsedTime" class="chip chip--codigo">
            {{ result.elapsedTime }} s
          </span>
        </div>

        <div class="acciones-cabecera">
          <button class="btn btn--secundario" @click="$emit('reset')">
            Nueva consulta
          </button>
          <button
            v-if="result.ejecucion_id"
            class="btn btn--secundario"
            :disabled="descargando"
            @click="descargar"
          >
            <Icono nombre="descargar" :tamano="15" />
            {{ descargando ? 'Preparando…' : 'Descargar PDF' }}
          </button>
        </div>
        <p v-if="errorDescarga" class="error-descarga" role="alert">
          {{ errorDescarga }}
        </p>
      </div>
    </header>

    <!--
      Índice pegajoso. El informe completo mide cuatro pantallas y media; sin
      esto, volver del bloque de góndolas al mapa es scroll a ojo.
    -->
    <nav class="indice no-imprimir" aria-label="Secciones del informe">
      <a href="#seccion-mapa">Mapa</a>
      <a href="#seccion-gondolas">Góndolas</a>
      <a href="#seccion-informe">Informe</a>
    </nav>

    <!--
      Los tres motivos de un informe parcial se enseñan distinto a propósito.
      Confundirlos es exactamente lo que P06 prohíbe: "no hay datos" y "esto se
      paga" son mensajes opuestos para quien lee el informe.
    -->
    <div v-if="aviso" class="aviso superficie" :class="`aviso--${aviso.tipo}`">
      <Icono :nombre="aviso.icono" :tamano="19" />
      <div>
        <h4>{{ aviso.titulo }}</h4>
        <p>{{ aviso.texto }}</p>
        <ul v-if="aviso.faltan" class="faltan">
          <li v-for="item in aviso.faltan" :key="item">{{ item }}</li>
        </ul>
      </div>
    </div>

    <template v-if="mapa">
      <!-- ============ Precio de la materia prima ============ -->
      <!--
        Bloque propio, y separado de la tabla de productos a propósito: son dos
        preguntas distintas. A cuánto está el kilo de palta se sabe; a cuánto
        vende su guacamole una marca, no. Ponerlos juntos haría creer que el
        segundo existe y está detrás del plan de pago.
      -->
      <section class="bloque superficie imprimible">
        <div class="bloque-cabecera">
          <h2>Precio de la materia prima</h2>
          <span class="bloque-fuente">MIDAGRI · boletín mayorista</span>
        </div>

        <div v-if="precios.length" class="precios">
          <div v-for="p in precios" :key="p.producto + p.mercado" class="precio">
            <span class="precio-valor num">S/ {{ p.precio_soles_kg.toFixed(2) }}</span>
            <span class="precio-unidad">por kg</span>
            <span class="precio-nombre">{{ p.producto }}</span>
            <!--
              La variación lleva flecha además de color: en gris de impresora,
              «sube» y «baja» tienen que seguir distinguiéndose.
            -->
            <span
              v-if="p.variacion_pct !== null"
              class="precio-var"
              :class="p.variacion_pct >= 0 ? 'sube' : 'baja'"
            >
              <Icono :nombre="p.variacion_pct >= 0 ? 'sube' : 'baja'" :tamano="13" />
              {{ Math.abs(p.variacion_pct).toFixed(1) }} %
            </span>
            <span v-else class="sin-dato">variación sin dato</span>
          </div>

          <p class="precio-fuente">
            {{ precioReciente.fuente }} · boletín del {{ precioReciente.fecha }} ·
            {{ precioReciente.mercado_nombre }} ·
            <a :href="precioReciente.url_boletin" target="_blank" rel="noopener">
              ver PDF <Icono nombre="externo" :tamano="12" />
            </a>
          </p>
        </div>

        <p v-else class="matiz">
          El boletín diario de MIDAGRI no publica precio mayorista para
          <strong>{{ mapa.insumo }}</strong>: los mercados de Lima no lo
          comercializan en volumen.
        </p>
      </section>

      <!-- ============ Mapa comercial ============ -->
      <section id="seccion-mapa" class="bloque superficie imprimible">
        <div class="bloque-cabecera">
          <h2>Productos comparables en el mundo</h2>
          <span class="bloque-fuente">OpenFoodFacts · snapshot</span>

          <div
            v-if="mapa.productos.length"
            class="conmutador no-imprimir"
            role="group"
            aria-label="Forma de ver la lista"
          >
            <button
              type="button"
              :aria-pressed="vista === 'grid'"
              @click="vista = 'grid'"
            >
              <Icono nombre="imagen" :tamano="14" />Tarjetas
            </button>
            <button
              type="button"
              :aria-pressed="vista === 'tabla'"
              @click="vista = 'tabla'"
            >
              <Icono nombre="lista" :tamano="14" />Tabla
            </button>
          </div>
        </div>

        <!--
          Cero productos NO es una avería, y para un insumo peruano es lo
          normal: el snapshot no tiene ni uno con 'rocoto' entre sus 29.054.
          Se dice con palabras en vez de enseñar filtros vacíos y un paginador
          que anuncia «página 1 de 1» sobre una tabla sin filas.

          Y sobre todo: esto ya no apaga las góndolas de abajo. Antes sí, y por
          eso una consulta con 17 ofertas reales de Wong y Metro se veía como
          una pantalla sin nada.
        -->
        <p v-if="!mapa.productos.length" class="vacio" role="status">
          <Icono nombre="info" :tamano="17" />
          <span>
            <strong>OpenFoodFacts no cubre este insumo.</strong>
            El catálogo global es sobre todo europeo y norteamericano, así que
            los insumos peruanos con nombre propio suelen no aparecer. No es un
            fallo de la consulta ni una limitación de tu plan: los precios de
            góndola de más abajo se leyeron igual.
          </span>
        </p>

        <template v-if="mapa.productos.length">
        <!--
          El precio ausente, explicado UNA vez y en el sitio donde el lector se
          va a hacer la pregunta: antes de mirar las filas, no después. En ámbar
          de aviso y no en rojo, porque no es un fallo: es una frontera conocida
          del dato abierto.
        -->
        <p class="hueco">
          <Icono nombre="info" :tamano="17" />
          <span>
            Aquí <strong>no hay precio de góndola</strong>, y no se desbloquea
            con ningún plan: el precio del producto terminado no está en el
            snapshot de datos abiertos — una sonda sobre 100 códigos de barras
            encontró precio para el 3 %, ninguno en Perú. El precio de materia
            prima, que sí existe, está arriba; el de góndola, más abajo.
          </span>
        </p>

        <!-- -------- Filtros -------- -->
        <div class="filtros no-imprimir">
          <span class="rotulo">País</span>
          <button
            v-for="f in filtrosPais"
            :key="f.codigo"
            type="button"
            class="chip chip--accion"
            :aria-pressed="paisFiltro === f.codigo"
            @click="filtrarPais(f.codigo)"
          >
            {{ f.codigo === 'todos' ? 'Todos' : f.codigo }}
            <span class="filtro-n num">{{ f.n }}</span>
          </button>

          <span class="separador" aria-hidden="true"></span>

          <button
            type="button"
            class="chip chip--accion"
            :aria-pressed="soloAditivos"
            @click="alternarAditivos"
          >
            Solo con aditivos
          </button>

          <span class="filtros-cuenta">
            <b class="num">{{ filtrados.length }}</b> de
            <span class="num">{{ mapa.productos.length }}</span> productos
          </span>
        </div>

        <!--
          Filtrar hasta cero no puede dejar la pantalla en blanco: sin esto,
          quien combine «Solo con aditivos» y un país sin ninguno ve un hueco y
          no sabe si filtró de más o si algo reventó.
        -->
        <p v-if="!filtrados.length" class="vacio">
          Ningún producto cumple los dos filtros a la vez.
          <button type="button" class="btn btn--fantasma btn--pequeno" @click="limpiarFiltros">
            Quitar filtros
          </button>
        </p>

        <!-- -------- Vista de tarjetas -------- -->
        <template v-else-if="vista === 'grid'">
          <!--
            Sin zona de imagen. El diseño la lleva, pero el snapshot no trae URL
            de foto para ningún producto: veinticuatro recuadros grises vacíos
            serían exactamente el ruido que este rediseño retira de la columna
            de precio.
          -->
          <div class="rejilla-productos">
            <article v-for="p in visiblesGrid" :key="p.producto_id" class="tarjeta-producto">
              <div class="tp-cuerpo">
                <a
                  class="tp-nombre recorte-2"
                  :href="p.url"
                  target="_blank"
                  rel="noopener"
                  :title="p.nombre"
                >{{ p.nombre }}</a>

                <div class="tp-meta">
                  <span v-if="p.paises_iso?.length" class="tp-pais codigo">
                    {{ p.paises_iso.join(' ') }}
                  </span>
                  <span v-if="p.marca" class="tp-marca recorte-1" :title="p.marca">
                    {{ p.marca }}
                  </span>
                  <span v-else class="sin-dato">sin marca</span>
                </div>

                <div class="tp-etiquetas">
                  <span
                    class="chip"
                    :class="p.aditivos.length ? 'chip--aviso' : 'chip--limpio'"
                  >
                    {{ etiquetaAditivos(p) }}
                  </span>
                  <button
                    v-if="p.ingredientes"
                    type="button"
                    class="tp-ingredientes"
                    @click="abrir(p, 'ingredientes')"
                  >{{ p.n_ingredientes }} ingr.</button>
                  <span v-else class="sin-dato">ingredientes sin dato</span>
                </div>
              </div>

              <!--
                Va como <a> y no como <button>: abre pestaña de verdad, así que
                tiene que poder abrirse también con el botón central del ratón
                o con Ctrl+clic, y eso solo lo da un enlace real con href.
              -->
              <a
                v-if="p.aditivos.length && result.ejecucion_id"
                class="tp-analizar"
                :href="urlAnalisis(p.producto_id)"
                target="_blank"
                rel="noopener"
                :title="`Autorización de ${p.aditivos.length} aditivo(s) en EE. UU., Codex y UE · consume saldo del plan`"
              >
                <span class="punto" aria-hidden="true"></span>
                Analizar <Icono nombre="externo" :tamano="13" />
              </a>
            </article>
          </div>

          <div v-if="restantes > 0" class="cargar-mas no-imprimir">
            <button type="button" class="btn btn--secundario" @click="limite += PASO_GRID">
              Cargar más
            </button>
            <span class="cargar-nota">
              Mostrando {{ visiblesGrid.length }} · quedan
              <span class="num">{{ restantes }}</span>
            </span>
          </div>
        </template>

        <!-- -------- Vista de tabla -------- -->
        <template v-else>
          <div class="tabla-scroll">
            <table class="tabla">
              <thead>
                <tr>
                  <th>Producto</th><th>País</th><th>Marca</th>
                  <!-- Aditivos e Ingredientes abren la misma ficha, cada uno en su sección. -->
                  <th>Aditivos</th><th>Ingredientes</th><th>Análisis</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in visiblesTabla" :key="p.producto_id">
                  <td class="col-producto">
                    <a :href="p.url" target="_blank" rel="noopener" :title="p.nombre">
                      <span class="recorte-2">{{ p.nombre }}</span>
                    </a>
                  </td>

                  <!--
                    Celda vacía = "sin dato", nunca un guion ni un hueco en
                    blanco. Un guion se lee como "no aplica", y estos campos sí
                    aplican: simplemente no se conocen.
                  -->
                  <td>
                    <span v-if="p.paises_iso?.length" class="codigo">
                      {{ p.paises_iso.join(', ') }}
                    </span>
                    <span v-else class="sin-dato">sin dato</span>
                  </td>
                  <td>
                    <span v-if="p.marca">{{ p.marca }}</span>
                    <span v-else class="sin-dato">sin dato</span>
                  </td>

                  <!--
                    Tres estados, no dos. Sin texto de etiqueta es "sin dato";
                    con texto y cero aditivos reconocidos es **ninguno**, que no
                    es un hueco sino un producto de etiqueta limpia: para quien
                    formula, eso es información, no ausencia de información.
                  -->
                  <td>
                    <button
                      v-if="p.aditivos.length"
                      class="btn-ficha"
                      @click="abrir(p, 'aditivos')"
                    >{{ etiquetaAditivos(p) }}</button>
                    <span v-else-if="p.ingredientes" class="chip chip--limpio">sin aditivos</span>
                    <span v-else class="sin-dato">sin dato</span>
                  </td>

                  <td>
                    <button
                      v-if="p.ingredientes"
                      class="btn-ficha"
                      @click="abrir(p, 'ingredientes')"
                    >Ver {{ p.n_ingredientes }}</button>
                    <span v-else class="sin-dato">sin dato</span>
                  </td>

                  <!--
                    Análisis regulatorio (T6). Los mismos tres estados que la
                    columna de aditivos, y por el mismo motivo: **sin aditivos
                    no hay nada que analizar**, así que un botón ahí sería un
                    botón muerto que abre una pestaña vacía. Es el 49,8 % de
                    las filas.
                  -->
                  <td>
                    <a
                      v-if="p.aditivos.length && result.ejecucion_id"
                      class="enlace-analisis"
                      :href="urlAnalisis(p.producto_id)"
                      target="_blank"
                      rel="noopener"
                      :title="`Autorización de ${p.aditivos.length} aditivo(s) en EE. UU., Codex y UE · consume saldo del plan`"
                    >
                      <span class="punto" aria-hidden="true"></span>
                      Analizar <Icono nombre="externo" :tamano="12" />
                    </a>
                    <span v-else-if="p.ingredientes" class="sin-dato">nada que analizar</span>
                    <span v-else class="sin-dato">sin dato</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="paginacion no-imprimir">
            <button class="btn btn--fantasma btn--pequeno" :disabled="pagina === 1" @click="pagina = 1">
              Primera
            </button>
            <button class="btn btn--fantasma btn--pequeno" :disabled="pagina === 1" @click="pagina--">
              <Icono nombre="chevron-izq" :tamano="14" />Anterior
            </button>
            <span class="pag-estado">
              Página <b class="num">{{ pagina }}</b> de <span class="num">{{ totalPaginas }}</span>
              · productos <span class="num">{{ desde }}</span>–<span class="num">{{ hasta }}</span>
              de <span class="num">{{ filtrados.length }}</span>
            </span>
            <button class="btn btn--fantasma btn--pequeno" :disabled="pagina === totalPaginas" @click="pagina++">
              Siguiente<Icono nombre="chevron-der" :tamano="14" />
            </button>
            <button class="btn btn--fantasma btn--pequeno" :disabled="pagina === totalPaginas" @click="pagina = totalPaginas">
              Última
            </button>
          </div>
        </template>

        </template>

        <p v-if="nivelesFaltan" class="niveles">
          <span class="chip chip--no-consultado">no se consultó</span>
          {{ nivelesFaltan }}
        </p>
      </section>

      <!-- ============ Góndolas ============ -->
      <!--
        A cuánto se vende HOY, tienda por tienda. Van debajo de la de
        OpenFoodFacts y no fundidas con ella porque responden preguntas
        distintas. Arriba: qué productos existen y con qué composición. Aquí: a
        qué precio están y dónde. Una fila de arriba es un producto; una de aquí
        es una oferta, y hay productos con varias.

        Tres tablas y no una sola con columna «país»: la lectura útil es «cuánto
        cuesta aquí FRENTE A cuánto cuesta allá», y mezclarlas obligaría a
        filtrar para leer cualquiera de ellas.

        El subtítulo de cada una dice cómo se obtuvo, y no es el mismo dato:
        Perú sale de un API de catálogo —exacto y completo— y Alemania y Suiza
        de una búsqueda web con extracción por modelo, que es irregular.
        Presentarlas con la misma etiqueta haría creer que valen lo mismo.

        Orden: origen primero, destinos después. No es alfabético ni por volumen
        de datos, es el recorrido de la pregunta que trae aquí a un exportador
        —cuánto vale mi producto aquí, cuánto allá—.
      -->
      <div id="seccion-gondolas" class="gondolas">
        <TablaGondola
          titulo="Precio de góndola · Perú"
          :ofertas="ofertasPeru"
          :ejecucion-id="result.ejecucion_id || ''"
          etiqueta-tiendas="Cadenas consultadas"
          subtitulo="Leído del catálogo de cada cadena en el momento de la consulta. Sin revisión humana: es lo que la tienda publica."
        />

        <TablaGondola
          titulo="Precio de góndola · Alemania"
          :ofertas="ofertasAlemania"
          :ejecucion-id="result.ejecucion_id || ''"
          etiqueta-tiendas="Tiendas encontradas"
          subtitulo="Ninguna cadena alemana publica su precio de forma abierta, así que esto se ha buscado y leído ficha a ficha. Sin revisión humana, y la cobertura es irregular: que un producto no salga aquí no significa que no se venda en Alemania."
        />

        <TablaGondola
          titulo="Precio de góndola · Suiza"
          :ofertas="ofertasSuiza"
          :ejecucion-id="result.ejecucion_id || ''"
          etiqueta-tiendas="Tiendas encontradas"
          subtitulo="Buscado y leído ficha a ficha, igual que Alemania. Migros y Coop bloquean el rastreo y no aparecen aquí, así que esto son tiendas suizas menores: es una referencia de precio, no una muestra del mercado. Se busca en alemán, de modo que las fichas en francés e italiano quedan fuera."
        />
      </div>

      <!--
        Ficha de formulación. Se superpone a toda la pantalla y no solo al panel
        del mapa: con el índice pegajoso y las góndolas debajo, un fondo que
        cubriera media página dejaba el resto pulsable por detrás.

        Se cierra con Escape, con la ✕ o pinchando fuera.
      -->
      <div v-if="abierto" class="modal-fondo no-imprimir" @click.self="abierto = null">
        <div
          ref="dialogo"
          class="modal superficie"
          role="dialog"
          aria-modal="true"
          :aria-label="abierto.nombre"
          tabindex="-1"
        >
          <header class="modal-cabecera">
            <div class="modal-titulo">
              <h4>{{ abierto.nombre }}</h4>
              <p class="modal-sub">
                {{ abierto.marca || 'sin marca' }} ·
                {{ abierto.paises_iso.join(', ') || 'sin país' }} ·
                <a :href="abierto.url" target="_blank" rel="noopener">
                  ver ficha original <Icono nombre="externo" :tamano="12" />
                </a>
              </p>
            </div>
            <button class="modal-cerrar" aria-label="Cerrar ficha" @click="abierto = null">
              <Icono nombre="equis" :tamano="17" />
            </button>
          </header>

          <div class="modal-cuerpo">
            <section ref="seccionAditivos" :class="{ destacada: foco === 'aditivos' }">
              <h5>Aditivos <span class="cuenta num">{{ abierto.aditivos.length }}</span></h5>
              <ul v-if="abierto.aditivos.length" class="etiquetas">
                <li v-for="a in abierto.aditivos" :key="a">{{ a }}</li>
              </ul>
              <!--
                Cero aditivos no es un hueco: es un producto de etiqueta limpia.
                Lo que sí hay que decir es hasta dónde llega el reconocimiento.
              -->
              <p v-else class="matiz">
                Ninguno de los aditivos reconocibles aparece en esta etiqueta.
              </p>
              <p class="matiz nota-alcance">
                Se reconocen por su nombre en el texto; el número entre
                paréntesis es el del Codex. Un aditivo escrito con un nombre
                comercial que no está en la lista no se detecta.
              </p>
            </section>

            <section ref="seccionIngredientes" :class="{ destacada: foco === 'ingredientes' }">
              <h5>Ingredientes <span class="cuenta num">{{ abierto.n_ingredientes }}</span></h5>
              <!--
                Numerados y en el orden de la etiqueta, que no es decorativo: en
                una lista de ingredientes el orden es descendente por peso, así
                que el nº 1 es el componente mayoritario.
              -->
              <ol v-if="abierto.lista_ingredientes.length" class="lista-ingredientes">
                <li v-for="(ing, i) in abierto.lista_ingredientes" :key="i">{{ ing }}</li>
              </ol>
              <p v-else class="ingredientes-texto">{{ abierto.ingredientes }}</p>
            </section>

            <section>
              <h5>Alérgenos declarados</h5>
              <ul v-if="abierto.alergenos.length" class="etiquetas alergenos">
                <li v-for="a in abierto.alergenos" :key="a">{{ a }}</li>
              </ul>
              <!--
                Vacío NO es "no tiene". La etiqueta no lo declara en este texto,
                y deducir alergenicidad de un ingrediente sería inventar un dato
                de seguridad alimentaria.
              -->
              <p v-else class="matiz">
                La etiqueta no declara alérgenos en este texto.
                <strong>No significa que el producto no los contenga.</strong>
              </p>
            </section>
          </div>

          <footer class="modal-pie">
            Leído del texto de la etiqueta que publica Open Food Facts. Los
            aditivos se reconocen por su nombre; el número E es el del Codex.
          </footer>
        </div>
      </div>
    </template>

    <!-- ================= El informe redactado ================= -->
    <section id="seccion-informe" class="bloque superficie imprimible imprimible-salto">
      <div class="bloque-cabecera">
        <h2>Informe</h2>
        <span class="bloque-fuente">Redactado sobre los datos de arriba</span>
      </div>
      <!-- `lectura` cambia a serif: esto es texto para leer seguido, no una
           tabla que se escanea. -->
      <div class="markdown-body lectura" v-html="sanitizedHtml"></div>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, NoAutorizado } from '../api.js'
import Icono from './Icono.vue'
import TablaGondola from './TablaGondola.vue'

const router = useRouter()

const props = defineProps({
  result: {
    type: Object,
    required: true,
  },
})

defineEmits(['reset'])

const descargando = ref(false)
const errorDescarga = ref('')

const AVISOS = {
  paywall: {
    tipo: 'plan',
    icono: 'candado',
    titulo: 'Informe del plan gratuito',
    texto: 'Este análisis incluye el mapa comercial. Con el plan premium se añaden dos secciones que no se han generado para este informe:',
    faltan: [
      'Hipótesis de formulación: ingeniería inversa de ingredientes y procesos a partir de los productos comparables.',
      'Dossier regulatorio: restricciones con citas verificables, cada una con su fuente oficial y enlace.',
    ],
  },
  pocos_productos: {
    tipo: 'tecnico',
    icono: 'buscar',
    titulo: 'Cobertura limitada en el snapshot',
    texto: 'La búsqueda encontró dos o menos productos que usen el insumo de forma directa. El informe se emite igual, pero conviene leerlo como orientación: no hay base suficiente para conclusiones firmes. No es una limitación de tu plan.',
  },
  presupuesto: {
    tipo: 'sindato',
    icono: 'info',
    titulo: 'Sin dato: presupuesto agotado',
    texto: 'Se alcanzó el tope de gasto configurado, así que algunas etapas no se ejecutaron. Lo que ves está completo hasta donde llegó el análisis; no hay ningún error, el gasto está acotado por diseño.',
  },
}

const aviso = computed(() => AVISOS[props.result.motivo_parcial] || null)

/* --- Mapa comercial (etapa 2b) ------------------------------------------ */

const NIVELES = {
  1: 'snapshot local',
  2: 'API licenciada',
  3: 'agente web',
}

/**
 * El mapa, si trae ALGO que enseñar.
 *
 * Antes esto era `m.productos.length ? m : null`, y la condición estaba mal
 * puesta: el mapa no es solo el snapshot de OpenFoodFacts. Lleva tres cosas
 * independientes —productos del snapshot, ofertas de góndola y precio de
 * materia prima— y todo el bloque de la plantilla cuelga de este valor, así
 * que cero productos borraba también las góndolas y los precios.
 *
 * Medido con «salsa de rocoto» el 2026-08-24: el backend devolvió
 * `productos: 0` y `ofertas_peru: 17`, y la pantalla no enseñó ninguna de las
 * diecisiete. Las ofertas eran reales, de Wong y Metro, y son justamente el
 * dato que un exportador viene a buscar.
 *
 * Cero productos en el snapshot es además el estado NORMAL para un insumo
 * peruano: el snapshot no tiene ni un producto con 'rocoto' entre sus 29.054.
 * Que eso apagase la pantalla entera convertía «OpenFoodFacts no lo cubre» en
 * «no hay nada», que es falso y además desanima a mirar lo que sí hay.
 *
 * Es el mismo error que `TablaGondola` ya corrigió un nivel más abajo: ocultar
 * una sección vacía hace que una avería y una ausencia se vean idénticas.
 */
const mapa = computed(() => {
  const m = props.result.mapa
  if (!m) return null
  const hayAlgo =
    m.productos?.length ||
    m.ofertas_peru?.length ||
    m.ofertas_alemania?.length ||
    m.ofertas_suiza?.length ||
    m.precios_materia_prima?.length
  return hayAlgo ? m : null
})

const nPaises = computed(
  () => new Set((mapa.value?.productos ?? []).flatMap((p) => p.paises_iso ?? [])).size,
)

// Los productos sin marca no cuentan: el snapshot no la trae para el 36 % de
// ellos y contarlos como una marca más inflaría la cifra que se dice en la demo.
const nMarcas = computed(
  () => new Set((mapa.value?.productos ?? []).map((p) => p.marca).filter(Boolean)).size,
)

/* --- Góndola: a cuánto se vende hoy, tienda por tienda ------------------- */

// Lista vacía = ese mercado no se consultó, o no había nada. `TablaGondola`
// pinta la sección igual y declara la ausencia en una línea; ocultarla entera
// —que es lo que hacía— convertía cualquier avería en una pantalla idéntica a
// «no hay ofertas», y eso costó dos rondas de depuración.
const ofertasPeru = computed(() => mapa.value?.ofertas_peru ?? [])
const ofertasAlemania = computed(() => mapa.value?.ofertas_alemania ?? [])
const ofertasSuiza = computed(() => mapa.value?.ofertas_suiza ?? [])

// Precio de materia prima. Lista vacía = MIDAGRI no publica precio para este
// insumo; no es lo mismo que "vale cero" ni que "está detrás del paywall".
const precios = computed(() => mapa.value?.precios_materia_prima ?? [])
const precioReciente = computed(() =>
  precios.value.reduce((a, b) => (a.fecha >= b.fecha ? a : b), precios.value[0]),
)

const nivelesFaltan = computed(() =>
  (mapa.value?.niveles_no_disponibles ?? [])
    .map((n) => `nivel ${n} (${NIVELES[n] ?? 'desconocido'})`)
    .join(', '),
)

/**
 * «1 aditivo» y no «1 aditivos». Aparece en las 200 tarjetas del mapa y en las
 * 200 filas de la tabla, así que una falta de concordancia aquí no se ve una
 * vez: se ve doscientas.
 */
const etiquetaAditivos = (p) => {
  const n = p.aditivos.length
  if (!n) return 'sin aditivos'
  return n === 1 ? '1 aditivo' : `${n} aditivos`
}

/* --- Filtros -------------------------------------------------------------
 *
 * Se filtra en cliente sobre los productos que ya están en memoria: el mapa
 * llega entero en la respuesta de la consulta, así que no hay ninguna llamada
 * nueva ni ningún gasto asociado a mover estos controles.
 */

const paisFiltro = ref('todos')
const soloAditivos = ref(false)

/**
 * Cuántos productos hay por país.
 *
 * Un producto puede estar en varios países —`paises_iso` es una lista— así que
 * suma en cada uno de los suyos. Por eso la suma de las cuentas por país es
 * mayor que el total, y por eso «Todos» lleva su propia cuenta en vez de ser
 * la suma de las demás.
 */
const filtrosPais = computed(() => {
  const productos = mapa.value?.productos ?? []
  const cuenta = new Map()
  for (const p of productos) {
    for (const iso of p.paises_iso ?? []) {
      cuenta.set(iso, (cuenta.get(iso) ?? 0) + 1)
    }
  }
  return [
    { codigo: 'todos', n: productos.length },
    ...[...cuenta]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([codigo, n]) => ({ codigo, n })),
  ]
})

const filtrados = computed(() =>
  (mapa.value?.productos ?? []).filter(
    (p) =>
      (paisFiltro.value === 'todos' || (p.paises_iso ?? []).includes(paisFiltro.value)) &&
      (!soloAditivos.value || p.aditivos.length > 0),
  ),
)

const filtrarPais = (codigo) => {
  // Volver a pulsar el país activo lo quita: sin esto, la única forma de
  // deseleccionar es acordarse de que existe un chip «Todos».
  paisFiltro.value = paisFiltro.value === codigo ? 'todos' : codigo
}

const alternarAditivos = () => {
  soloAditivos.value = !soloAditivos.value
}

const limpiarFiltros = () => {
  paisFiltro.value = 'todos'
  soloAditivos.value = false
}

/* --- Las dos vistas ------------------------------------------------------ */

const vista = ref('grid')

// 24 entra justo en filas completas con 2, 3, 4 y 6 columnas, que son los
// anchos que da la rejilla entre móvil y pantalla ancha.
const PASO_GRID = 24
const limite = ref(PASO_GRID)

const visiblesGrid = computed(() => filtrados.value.slice(0, limite.value))
const restantes = computed(() => Math.max(0, filtrados.value.length - limite.value))

// 25 es lo mismo que muestra el PDF: quien compare las dos salidas ve la misma
// primera página en vez de dos recortes distintos del mismo mapa. La
// equivalencia solo vale sin filtros, que es como llega la pantalla.
const POR_PAGINA = 25

const pagina = ref(1)

const totalPaginas = computed(() =>
  Math.max(1, Math.ceil(filtrados.value.length / POR_PAGINA)),
)

const desde = computed(() =>
  filtrados.value.length ? (pagina.value - 1) * POR_PAGINA + 1 : 0,
)
const hasta = computed(() =>
  Math.min(pagina.value * POR_PAGINA, filtrados.value.length),
)

const visiblesTabla = computed(() =>
  filtrados.value.slice((pagina.value - 1) * POR_PAGINA, pagina.value * POR_PAGINA),
)

// Filtrar deja la lista más corta: sin esto, filtrar desde la página 5 enseña
// una tabla vacía y el paginador diciendo «página 5 de 1».
watch([paisFiltro, soloAditivos], () => {
  pagina.value = 1
  limite.value = PASO_GRID
})

// Una consulta nueva reutiliza el componente. Sin esto, buscar un insumo con
// menos productos dejaría la vista en una página que ya no existe y con los
// filtros del insumo anterior puestos.
watch(
  () => props.result.ejecucion_id,
  () => {
    pagina.value = 1
    limite.value = PASO_GRID
    limpiarFiltros()
  },
)

/* --- Análisis regulatorio (T6) ------------------------------------------- */

// La URL de la pestaña de análisis, resuelta por el router y no construida a
// mano: si la ruta cambia de forma, esto la sigue. `resolve().href` respeta
// además la base de la SPA, que un literal se saltaría, y codifica el id —que
// viene como `OFF:00000036`— sin que haya que acordarse.
const urlAnalisis = (productoId) =>
  router.resolve({
    name: 'analisis',
    params: { ejecucionId: props.result.ejecucion_id, productoId },
  }).href

/* --- Ficha de formulación ------------------------------------------------ */

// El producto cuyo modal está abierto, o null.
const abierto = ref(null)

// Qué sección se destaca al abrir. Las dos columnas abren la MISMA ficha —
// aditivos e ingredientes son la misma etiqueta leída de dos maneras, y tenerlas
// en modales separados obligaría a cerrar uno para ver el otro— pero cada botón
// lleva a lo suyo.
const foco = ref('ingredientes')
const seccionAditivos = ref(null)
const seccionIngredientes = ref(null)
const dialogo = ref(null)

// Quién tenía el foco antes de abrir, para devolvérselo al cerrar. Sin esto, el
// foco vuelve al principio del documento y hay que recorrer la tabla otra vez
// para seguir donde se estaba.
let focoPrevio = null

const abrir = async (producto, seccion) => {
  focoPrevio = document.activeElement
  abierto.value = producto
  foco.value = seccion
  await nextTick()
  // El foco entra en el diálogo: si se queda fuera, Escape funciona pero el
  // tabulador sigue recorriendo la tabla que hay detrás del fondo oscuro.
  dialogo.value?.focus?.()
  const destino =
    seccion === 'aditivos' ? seccionAditivos.value : seccionIngredientes.value
  destino?.scrollIntoView({ block: 'nearest' })
}

watch(abierto, (ahora) => {
  if (!ahora && focoPrevio) {
    focoPrevio.focus?.()
    focoPrevio = null
  }
})

// Cerrar con Escape: un modal del que solo se sale con el ratón estorba a quien
// está recorriendo la tabla con el teclado.
const alPulsarTecla = (e) => {
  if (e.key === 'Escape') abierto.value = null
}
onMounted(() => window.addEventListener('keydown', alPulsarTecla))
onUnmounted(() => window.removeEventListener('keydown', alPulsarTecla))

// Cambiar de página o de filtro con un modal abierto dejaría en pantalla una
// ficha que ya no está en la tabla de debajo.
watch([pagina, paisFiltro, soloAditivos, vista], () => {
  abierto.value = null
})

/**
 * El informe sin la sección del mapa.
 *
 * El markdown la lleva porque el PDF la necesita escrita, pero aquí la pinta el
 * bloque de arriba con los 200 productos paginados. Sin quitarla se verían las
 * dos: la tabla completa y las 25 filas recortadas del PDF.
 *
 * Se corta por las marcas que escribe InformeWeasyPrint (`<!--MAPA-->`), no por
 * el texto del encabezado: cambiar el título del apartado no debe dejar una
 * tabla duplicada en pantalla.
 */
const markdownSinMapa = computed(() => {
  const md = props.result.markdown_content || ''
  const inicio = md.indexOf('<!--MAPA-->')
  const fin = md.indexOf('<!--/MAPA-->')
  if (inicio === -1 || fin === -1 || fin < inicio) return md
  return md.slice(0, inicio) + md.slice(fin + '<!--/MAPA-->'.length)
})

const sanitizedHtml = computed(() => {
  if (!props.result.markdown_content) return '<p>No hay contenido disponible.</p>'
  const rawHtml = marked(markdownSinMapa.value)
  return DOMPurify.sanitize(rawHtml)
})

/**
 * El bucket es privado. El backend devuelve una URL firmada de una hora y se
 * pide en el momento de descargar: antes esto era un <a href> directo al
 * endpoint, sin token, contra un endpoint que exige autenticación.
 */
const descargar = async () => {
  descargando.value = true
  errorDescarga.value = ''
  try {
    const { url } = await api.urlInforme(props.result.ejecucion_id)
    window.open(url, '_blank')
  } catch (error) {
    if (!(error instanceof NoAutorizado)) {
      errorDescarga.value = 'No se pudo preparar la descarga.'
      console.error(error)
    }
  } finally {
    descargando.value = false
  }
}
</script>

<style scoped>
.informe {
  max-width: 1180px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ---------------------------------------------------------------- *
 *  Cabecera
 * ---------------------------------------------------------------- */

.cabecera {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}

.cabecera-texto { min-width: 0; }

.eyebrow {
  margin: 0 0 4px;
  font-size: 0.69rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--verde-texto);
}

.cabecera h1 {
  margin: 0;
  font-size: 2rem;
  line-height: 1.1;
  /* Un insumo se escribe en minúsculas —«harina de quinua»— y como titular
     queda raro; capitalizar solo la primera letra lo arregla sin tocar el
     dato. */
  text-transform: none;
}

.cabecera h1::first-letter { text-transform: uppercase; }

.cifras {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  margin-top: 8px;
  font-size: 0.9375rem;
  color: var(--texto-atenuado);
}

.cifras b {
  font-size: 1.25rem;
  font-weight: 750;
  color: var(--tinta);
  margin-right: 4px;
}

.cabecera-lado {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}

.estado {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.acciones-cabecera {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.error-descarga {
  margin: 0;
  font-size: 0.78rem;
  color: var(--critico);
}

/* ---------------------------------------------------------------- *
 *  Índice pegajoso
 * ---------------------------------------------------------------- */

.indice {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  gap: 4px;
  padding: 8px 0;
  margin-bottom: -6px;
  background: var(--lienzo);
  border-bottom: 1px solid var(--borde);
}

.indice a {
  padding: 6px 14px;
  border-radius: var(--r-xs);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--texto-atenuado);
  text-decoration: none;
}

.indice a:hover {
  background: var(--superficie);
  color: var(--tinta);
}

/* ---------------------------------------------------------------- *
 *  Avisos
 * ---------------------------------------------------------------- */

.aviso {
  display: flex;
  gap: 12px;
  padding: 16px 18px;
}

.aviso h4 { margin: 0 0 4px; font-size: 0.9375rem; }
.aviso p  { margin: 0; font-size: 0.875rem; color: var(--texto-atenuado); }

.faltan {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 0.85rem;
  color: var(--texto-atenuado);
  display: grid;
  gap: 5px;
}

/* Tres motivos, tres colores, y ninguno es rojo: ninguno de los tres es un
   fallo del sistema. El plan es una frontera comercial (morado), la cobertura
   es una limitación del dato (gris) y el presupuesto es un tope que alguien
   configuró a propósito (ámbar). */
.aviso--plan    { border-color: var(--plan-borde);  background: var(--plan-fondo);  color: var(--plan); }
.aviso--tecnico { border-color: var(--borde);       background: var(--superficie-sutil); color: var(--texto-atenuado); }
.aviso--sindato { border-color: var(--aviso-borde); background: var(--aviso-fondo); color: var(--aviso-texto); }

.aviso--plan h4    { color: var(--plan); }
.aviso--sindato h4 { color: var(--aviso-texto); }

/* ---------------------------------------------------------------- *
 *  Bloques
 * ---------------------------------------------------------------- */

.bloque { padding: 22px; }

.bloque-cabecera {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.bloque-cabecera h2 {
  margin: 0;
  font-size: 1.1875rem;
  font-weight: 750;
}

.bloque-fuente {
  font-size: 0.78rem;
  color: var(--texto-sin-dato);
}

/* Empuja lo que venga después al extremo derecho sin necesitar un div vacío. */
.conmutador {
  margin-left: auto;
  display: flex;
  padding: 3px;
  border-radius: var(--r-md);
  background: #F0F3F1;
  border: 1px solid var(--borde);
  gap: 2px;
}

.conmutador button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-family: inherit;
  font-size: 0.78rem;
  font-weight: 650;
  padding: 6px 12px;
  border-radius: var(--r-xs);
  border: 0;
  background: transparent;
  color: var(--texto-atenuado);
  cursor: pointer;
}

/* `aria-pressed` es a la vez el estado accesible y el selector de estilo: así
   no puede existir un botón que se ve activo y no lo anuncia, ni al revés. */
.conmutador button[aria-pressed='true'] {
  background: var(--superficie);
  color: var(--tinta);
  box-shadow: var(--sombra);
}

/* ---------------------------------------------------------------- *
 *  El hueco de precio, dicho una vez
 * ---------------------------------------------------------------- */

.hueco {
  display: flex;
  gap: 11px;
  align-items: flex-start;
  margin: 0 0 16px;
  padding: 13px 15px;
  border-radius: var(--r-md);
  background: var(--aviso-fondo);
  border: 1px solid var(--aviso-borde);
  font-size: 0.85rem;
  line-height: 1.55;
  color: #6B4A11;
}

.hueco strong { color: var(--aviso-texto); }

/* Ausencia declarada, no avería. En neutro y no en ámbar a propósito: que
   OpenFoodFacts no cubra un insumo peruano es lo esperable, y pintarlo con el
   color de aviso lo convertiría en un problema que el lector creería que tiene
   que resolver. El ámbar queda para lo que sí es una limitación conocida del
   dato —el precio ausente de arriba—. */
.vacio {
  display: flex;
  gap: 11px;
  align-items: flex-start;
  margin: 0;
  padding: 13px 15px;
  border-radius: var(--r-md);
  background: var(--fondo-sutil, #F7F8F7);
  border: 1px solid var(--borde-suave);
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--texto-atenuado);
}

.vacio strong { color: var(--tinta); }
.vacio svg { flex: none; margin-top: 2px; color: var(--texto-sin-dato); }

/* ---------------------------------------------------------------- *
 *  Filtros
 * ---------------------------------------------------------------- */

.filtros {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--borde-suave);
  margin-bottom: 18px;
}

.filtro-n {
  opacity: 0.6;
  font-size: 0.9em;
}

.separador {
  width: 1px;
  height: 22px;
  background: var(--borde);
  margin: 0 4px;
}

.filtros-cuenta {
  margin-left: auto;
  font-size: 0.85rem;
  color: var(--texto-atenuado);
}

.filtros-cuenta b { color: var(--tinta); }

.vacio {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 40px 0;
  margin: 0;
  font-size: 0.9375rem;
  color: var(--texto-atenuado);
}

/* ---------------------------------------------------------------- *
 *  Tarjetas de producto
 * ---------------------------------------------------------------- */

.rejilla-productos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(212px, 1fr));
  gap: 14px;
}

.tarjeta-producto {
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  background: var(--superficie);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  transition: border-color 0.15s;
}

.tarjeta-producto:hover { border-color: var(--borde-fuerte); }

.tp-cuerpo {
  padding: 12px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tp-nombre {
  font-size: 0.82rem;
  font-weight: 650;
  line-height: 1.35;
  color: var(--tinta);
  text-decoration: none;
  /* Dos líneas fijas: sin la altura, una tarjeta de nombre corto y otra de
     nombre largo dejan los chips de abajo a distinta altura y la rejilla se ve
     desordenada aunque cada tarjeta esté bien. */
  min-height: 2.7em;
}

.tp-nombre:hover { color: var(--verde-texto); }

.tp-meta {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.75rem;
  color: var(--texto-atenuado);
  min-width: 0;
}

.tp-pais {
  flex: none;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  background: #F0F3F1;
  color: var(--texto-atenuado);
}

.tp-marca { min-width: 0; }

.tp-etiquetas {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.tp-ingredientes {
  font-family: inherit;
  font-size: 0.72rem;
  color: var(--texto-atenuado);
  background: none;
  border: 0;
  padding: 0;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: var(--borde-fuerte);
  text-underline-offset: 2px;
}

.tp-ingredientes:hover { color: var(--verde-texto); }

/* El único control de la tarjeta con color propio. */
.tp-analizar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-decoration: none;
  font-size: 0.75rem;
  font-weight: 650;
  padding: 8px;
  background: var(--aviso-fondo);
  border-top: 1px solid var(--aviso-borde);
  color: var(--aviso-texto);
}

.tp-analizar:hover { background: #F8EDD6; color: var(--aviso-texto); }

.punto {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--aviso);
  flex: none;
}

.cargar-mas {
  margin-top: 18px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.cargar-nota {
  font-size: 0.8rem;
  color: var(--texto-sin-dato);
}

/* ---------------------------------------------------------------- *
 *  Tabla
 * ---------------------------------------------------------------- */

.col-producto { max-width: 320px; }

.col-producto a {
  font-weight: 600;
  color: var(--tinta);
  text-decoration: none;
}

.col-producto a:hover { color: var(--verde-texto); }

.btn-ficha {
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: var(--r-xs);
  border: 1px solid var(--borde-fuerte);
  background: var(--superficie);
  color: var(--texto);
  cursor: pointer;
  white-space: nowrap;
}

.btn-ficha:hover {
  border-color: var(--verde);
  color: var(--verde-texto);
}

.enlace-analisis {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.78rem;
  font-weight: 650;
  padding: 4px 10px;
  border-radius: var(--r-xs);
  border: 1px solid var(--aviso-borde-suave);
  background: var(--aviso-fondo);
  color: var(--aviso-texto);
  text-decoration: none;
  white-space: nowrap;
}

.enlace-analisis:hover { background: #F8EDD6; color: var(--aviso-texto); }

.paginacion {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.pag-estado {
  font-size: 0.8rem;
  color: var(--texto-atenuado);
  padding: 0 10px;
}

.niveles {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0 0;
  font-size: 0.8rem;
  color: var(--texto-atenuado);
}

/* ---------------------------------------------------------------- *
 *  Precio de materia prima
 * ---------------------------------------------------------------- */

.precios { display: grid; gap: 8px; }

.precio {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
  padding: 10px 0;
  border-bottom: 1px solid var(--borde-suave);
}

.precio-valor {
  font-size: 1.25rem;
  font-weight: 750;
  color: var(--tinta);
}

.precio-unidad {
  font-size: 0.78rem;
  color: var(--texto-sin-dato);
}

.precio-nombre {
  font-size: 0.875rem;
  color: var(--texto);
  flex: 1;
  min-width: 140px;
}

.precio-var {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82rem;
  font-weight: 650;
}

.precio-var.sube { color: var(--critico); }
.precio-var.baja { color: var(--verde-texto); }

.precio-fuente {
  margin: 6px 0 0;
  font-size: 0.78rem;
  color: var(--texto-sin-dato);
}

.matiz {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.55;
  color: var(--texto-atenuado);
}

.gondolas { display: grid; gap: 18px; }

/* ---------------------------------------------------------------- *
 *  Ficha de formulación
 * ---------------------------------------------------------------- */

.modal-fondo {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(15, 21, 18, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal {
  width: 100%;
  max-width: 640px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--sombra-elevada);
}

.modal-cabecera {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px 22px 16px;
  border-bottom: 1px solid var(--borde-suave);
}

.modal-titulo { flex: 1; min-width: 0; }
.modal-titulo h4 { margin: 0 0 3px; font-size: 1rem; line-height: 1.3; }

.modal-sub {
  margin: 0;
  font-size: 0.78rem;
  color: var(--texto-sin-dato);
}

.modal-cerrar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--r-xs);
  border: 1px solid transparent;
  background: transparent;
  color: var(--texto-atenuado);
  cursor: pointer;
}

.modal-cerrar:hover {
  background: var(--lienzo);
  color: var(--tinta);
}

.modal-cuerpo {
  overflow-y: auto;
  padding: 18px 22px;
  display: grid;
  gap: 20px;
}

.modal-cuerpo h5 {
  margin: 0 0 8px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.cuenta {
  margin-left: 6px;
  font-size: 0.9rem;
  color: var(--tinta);
}

/* La sección desde la que se abrió, señalada sin moverla de sitio. */
.destacada {
  margin: -10px -12px;
  padding: 10px 12px;
  border-radius: var(--r-xs);
  background: var(--verde-tinte);
}

.etiquetas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.etiquetas li {
  font-size: 0.78rem;
  padding: 3px 9px;
  border-radius: var(--r-chip);
  background: var(--lienzo);
  border: 1px solid var(--borde);
  color: var(--texto);
}

.alergenos li {
  background: var(--critico-fondo);
  border-color: var(--critico-borde);
  color: var(--critico);
}

.lista-ingredientes {
  margin: 0;
  padding-left: 20px;
  font-size: 0.85rem;
  color: var(--texto);
  display: grid;
  gap: 3px;
}

.ingredientes-texto {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.55;
  color: var(--texto);
}

.nota-alcance {
  margin-top: 8px;
  font-size: 0.75rem;
  color: var(--texto-sin-dato);
}

.modal-pie {
  padding: 12px 22px;
  border-top: 1px solid var(--borde-suave);
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--texto-sin-dato);
  background: var(--superficie-sutil);
}

/* ---------------------------------------------------------------- *
 *  El informe en markdown
 * ---------------------------------------------------------------- */

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  font-family: var(--fuente-ui);
  margin-top: 1.6em;
  margin-bottom: 0.5em;
}

.markdown-body :deep(h1) { font-size: 1.375rem; }
.markdown-body :deep(h2) { font-size: 1.125rem; }
.markdown-body :deep(h3) { font-size: 1rem; }

/* Ancho de medida: por encima de ~75 caracteres el ojo pierde el renglón al
   volver al margen izquierdo. */
.markdown-body :deep(p),
.markdown-body :deep(li) {
  max-width: 74ch;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--fuente-ui);
  font-size: 0.85rem;
  margin: 1em 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--borde-suave);
  text-align: left;
}

.markdown-body :deep(th) {
  font-size: 0.7rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.markdown-body :deep(code) {
  font-family: var(--fuente-codigo);
  font-size: 0.85em;
  background: var(--lienzo);
  padding: 1px 5px;
  border-radius: 4px;
}

.markdown-body :deep(blockquote) {
  margin: 1em 0;
  padding: 2px 0 2px 16px;
  border-left: 3px solid var(--verde-borde);
  color: var(--texto-atenuado);
}

@media (max-width: 760px) {
  .cabecera-lado { align-items: flex-start; }
  .estado { justify-content: flex-start; }
  .filtros-cuenta { margin-left: 0; width: 100%; }
  .conmutador { margin-left: 0; }
  .modal-fondo { padding: 0; align-items: flex-end; }
  .modal { max-width: none; max-height: 92vh; border-radius: var(--r-lg) var(--r-lg) 0 0; }
}
</style>
