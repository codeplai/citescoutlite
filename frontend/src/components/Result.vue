<template>
  <div class="result-container animate-fade-in" v-if="result">
    <div class="header-section">
      <div class="badges">
        <span class="badge" v-if="result.parcial">🔍 Análisis Parcial</span>
        <span class="badge success" v-else>✅ Análisis Completo</span>
        <span class="badge version">v{{ result.snapshot_version }}</span>
        <span class="badge time" v-if="result.elapsedTime">⏱️ {{ result.elapsedTime }}s</span>
      </div>
      <button class="btn-primary reset-btn" @click="$emit('reset')">Nueva Consulta</button>
    </div>

    <!--
      Los tres motivos de un informe parcial se enseñan distinto a propósito.
      Confundirlos es exactamente lo que P06 prohíbe: "no hay datos" y "esto se
      paga" son mensajes opuestos para quien lee el informe.
    -->
    <div v-if="aviso" class="glass-panel aviso" :class="aviso.tipo">
      <span class="aviso-icono">{{ aviso.icono }}</span>
      <div>
        <h4>{{ aviso.titulo }}</h4>
        <p>{{ aviso.texto }}</p>
        <ul v-if="aviso.faltan" class="faltan">
          <li v-for="item in aviso.faltan" :key="item">{{ item }}</li>
        </ul>
      </div>
    </div>

    <!--
      Mapa comercial (etapa 2b, S4). Las cifras salen del objeto estructurado,
      no del markdown: son las que se dicen en voz alta en la demo y tienen que
      cuadrar con la tabla de abajo sin que nadie las cuente a mano.

      Los tres campos vacíos se anuncian aquí ANTES de que se vean en la tabla.
      Que el usuario se encuentre tres columnas vacías y luego lea por qué es
      peor que decírselo primero: lo segundo es una decisión declarada, lo
      primero parece un fallo del informe.
    -->
    <div v-if="mapa" class="glass-panel mapa-panel">
      <h4 class="mapa-titulo">🗺️ Mapa comercial</h4>

      <div class="mapa-cifras">
        <div class="cifra">
          <strong>{{ mapa.productos.length }}</strong><span>productos</span>
        </div>
        <div class="cifra"><strong>{{ nPaises }}</strong><span>países</span></div>
        <div class="cifra"><strong>{{ nMarcas }}</strong><span>marcas</span></div>
      </div>

      <!--
        Precio de la MATERIA PRIMA. Bloque propio, y separado de la tabla de
        productos a propósito: son dos preguntas distintas. A cuánto está el kilo
        de palta se sabe; a cuánto vende su guacamole una marca, no. Ponerlos
        juntos haría creer que el segundo existe y está detrás del plan de pago.
      -->
      <div class="precio-bloque">
        <h5>💰 Precio de la materia prima</h5>

        <div v-if="precios.length" class="precio-lista">
          <div v-for="p in precios" :key="p.producto + p.mercado" class="precio-item">
            <span class="precio-valor">S/ {{ p.precio_soles_kg.toFixed(2) }}</span>
            <span class="precio-unidad">por kg</span>
            <span class="precio-nombre">{{ p.producto }}</span>
            <span
              v-if="p.variacion_pct !== null"
              class="precio-var"
              :class="p.variacion_pct >= 0 ? 'sube' : 'baja'"
            >{{ p.variacion_pct >= 0 ? '▲' : '▼' }} {{ Math.abs(p.variacion_pct).toFixed(1) }} %</span>
            <span v-else class="sin-dato">var. sin dato</span>
          </div>
          <p class="precio-fuente">
            {{ precioReciente.fuente }} · boletín del {{ precioReciente.fecha }} ·
            {{ precioReciente.mercado_nombre }} ·
            <a :href="precioReciente.url_boletin" target="_blank" rel="noopener">ver PDF</a>
          </p>
        </div>

        <p v-else class="matiz">
          El boletín diario de MIDAGRI no publica precio mayorista para
          <strong>{{ mapa.insumo }}</strong>: los mercados de Lima no lo
          comercializan en volumen.
        </p>
      </div>

      <p class="mapa-hueco">
        <strong>El precio de la tabla de abajo sale vacío en todas las filas</strong>,
        y la presentación y el canal ni siquiera se recogen. Es el precio en
        <em>góndola</em> del producto terminado, que no está en el snapshot de datos
        abiertos y que <strong>no se desbloquea con ningún plan</strong>: una sonda
        sobre 100 códigos de barras encontró precio para el 3 %, ninguno en Perú.
        No confundirlo con el precio de materia prima de aquí arriba, que sí lo hay.
      </p>

      <!--
        La tabla se pinta aquí y no desde el markdown: el markdown lleva 25
        filas porque es lo que cabe en un PDF, pero la SPA recibe los 200
        productos y puede recorrerlos. La sección del markdown se quita en
        `markdownSinMapa` para no enseñar las dos.
      -->
      <div class="mapa-tabla-scroll">
        <table class="mapa-tabla">
          <thead>
            <tr>
              <th>Producto</th><th>País</th><th>Marca</th>
              <th>Precio</th><th>Aditivos</th><th>Ingredientes</th>
              <!-- Aditivos e Ingredientes abren la misma ficha, cada uno en su sección. -->
              <th>Análisis</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="fila in filas" :key="fila.id">
              <td class="col-producto">
                <a :href="fila.url" target="_blank" rel="noopener">{{ fila.nombre }}</a>
              </td>
              <!--
                Celda vacía = "sin dato", nunca un guion ni un hueco en blanco.
                Un guion se lee como "no aplica", y estos campos sí aplican:
                simplemente no se conocen.
              -->
              <td v-for="(celda, i) in fila.celdas" :key="i">
                <span v-if="celda">{{ celda }}</span>
                <span v-else class="sin-dato">sin dato</span>
              </td>

              <!--
                Tres estados, no dos. Sin texto de etiqueta es "sin dato"; con
                texto y cero aditivos reconocidos es **ninguno**, que no es un
                hueco sino un producto de etiqueta limpia: para quien formula,
                eso es información, no ausencia de información.
              -->
              <td>
                <button
                  v-if="fila.producto.aditivos.length"
                  class="btn-ficha"
                  @click="abrir(fila.producto, 'aditivos')"
                >
                  {{ fila.producto.aditivos.length }} aditivos
                </button>
                <span v-else-if="fila.producto.ingredientes" class="ninguno">ninguno</span>
                <span v-else class="sin-dato">sin dato</span>
              </td>

              <td>
                <button
                  v-if="fila.producto.ingredientes"
                  class="btn-ficha"
                  @click="abrir(fila.producto, 'ingredientes')"
                >
                  Ver {{ fila.producto.n_ingredientes }} ingredientes
                </button>
                <span v-else class="sin-dato">sin dato</span>
              </td>

              <!--
                Análisis regulatorio (T6). Los mismos tres estados que la
                columna de aditivos, y por el mismo motivo: **sin aditivos no
                hay nada que analizar**, así que un botón ahí sería un botón
                muerto que abre una pestaña vacía. Es el 49,8 % de las filas.

                Va como <a> y no como <button>: abre pestaña de verdad, así que
                tiene que poder abrirse también con el botón central del ratón
                o con Ctrl+clic, y eso solo lo da un enlace real con href.
              -->
              <td>
                <a
                  v-if="fila.producto.aditivos.length && result.ejecucion_id"
                  class="btn-analisis"
                  :href="urlAnalisis(fila.id)"
                  target="_blank"
                  rel="noopener"
                  :title="`Autorización de ${fila.producto.aditivos.length} aditivo(s) en EE. UU., Codex y UE`"
                >Analizar ↗</a>
                <span v-else-if="fila.producto.ingredientes" class="ninguno">
                  sin aditivos
                </span>
                <span v-else class="sin-dato">sin dato</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="paginacion">
        <button class="pag-btn" :disabled="pagina === 1" @click="pagina = 1">« Primera</button>
        <button class="pag-btn" :disabled="pagina === 1" @click="pagina--">‹ Anterior</button>
        <span class="pag-estado">
          Página <strong>{{ pagina }}</strong> de {{ totalPaginas }}
          · productos {{ desde }}–{{ hasta }} de {{ mapa.productos.length }}
        </span>
        <button class="pag-btn" :disabled="pagina === totalPaginas" @click="pagina++">Siguiente ›</button>
        <button class="pag-btn" :disabled="pagina === totalPaginas" @click="pagina = totalPaginas">Última »</button>
      </div>

      <p v-if="nivelesFaltan" class="mapa-niveles">
        Fuentes no consultadas: {{ nivelesFaltan }}
      </p>

      <!--
        Tabla de góndola: a cuánto se vende HOY, tienda por tienda.

        Va debajo de la de OpenFoodFacts y no fundida con ella porque responden
        preguntas distintas. Arriba: qué productos existen y con qué
        composición. Aquí: a qué precio están y dónde. Una fila de arriba es un
        producto; una de aquí es una oferta, y hay productos con varias.
      -->
      <!--
        Las tres góndolas. Van en tablas separadas y no en una sola con columna
        «país»: la lectura útil es «cuánto cuesta aquí FRENTE A cuánto cuesta
        allá», y mezclarlas obligaría a filtrar para leer cualquiera de ellas.

        El subtítulo de cada una dice cómo se obtuvo, y no es el mismo dato:
        Perú sale de un API de catálogo —exacto y completo— y Alemania y Suiza
        de una búsqueda web con extracción por modelo, que es irregular.
        Presentarlas con la misma etiqueta haría creer que valen lo mismo.

        Orden: origen primero, destinos después. No es alfabético ni por
        volumen de datos, es el recorrido de la pregunta que trae aquí a un
        exportador —cuánto vale mi producto aquí, cuánto allá—.
      -->
      <TablaGondola
        titulo="Precio de góndola · Perú"
        :ofertas="ofertasPeru"
        etiqueta-tiendas="Cadenas consultadas"
        subtitulo="Leído del catálogo de cada cadena en el momento de la consulta. Sin revisión humana: es lo que la tienda publica."
      />

      <TablaGondola
        titulo="Precio de góndola · Alemania"
        :ofertas="ofertasAlemania"
        etiqueta-tiendas="Tiendas encontradas"
        subtitulo="Ninguna cadena alemana publica su precio de forma abierta, así que esto se ha buscado y leído ficha a ficha. Sin revisión humana, y la cobertura es irregular: que un producto no salga aquí no significa que no se venda en Alemania."
      />

      <TablaGondola
        titulo="Precio de góndola · Suiza"
        :ofertas="ofertasSuiza"
        etiqueta-tiendas="Tiendas encontradas"
        subtitulo="Buscado y leído ficha a ficha, igual que Alemania. Migros y Coop bloquean el rastreo y no aparecen aquí, así que esto son tiendas suizas menores: es una referencia de precio, no una muestra del mercado. Se busca en alemán, de modo que las fichas en francés e italiano quedan fuera."
      />

      <!--
        Ficha de formulación. Se superpone **solo al panel del mapa**, no a toda
        la página: quien la abre está comparando filas, y oscurecer el informe
        entero para enseñar una etiqueta le quita de la vista justo el contexto
        desde el que preguntó.

        Se cierra con Escape, con la ✕ o pinchando fuera.
      -->
      <div v-if="abierto" class="modal-fondo" @click.self="abierto = null">
      <div class="modal" role="dialog" aria-modal="true">
        <header class="modal-cabecera">
          <div>
            <h4>{{ abierto.nombre }}</h4>
            <p class="modal-sub">
              {{ abierto.marca || 'sin marca' }} ·
              {{ abierto.paises_iso.join(', ') || 'sin país' }} ·
              <a :href="abierto.url" target="_blank" rel="noopener">ver ficha original</a>
            </p>
          </div>
          <button class="modal-cerrar" @click="abierto = null" aria-label="Cerrar">×</button>
        </header>

        <div class="modal-cuerpo">
          <section ref="seccionAditivos" :class="{ destacada: foco === 'aditivos' }">
            <h5>Aditivos <span class="cuenta">{{ abierto.aditivos.length }}</span></h5>
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
              Se reconocen por su nombre en el texto; el número entre paréntesis
              es el del Codex. Un aditivo escrito con un nombre comercial que no
              está en la lista no se detecta.
            </p>
          </section>

          <section ref="seccionIngredientes" :class="{ destacada: foco === 'ingredientes' }">
            <h5>Ingredientes <span class="cuenta">{{ abierto.n_ingredientes }}</span></h5>
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
              Vacío NO es "no tiene". La etiqueta no lo declara en este texto, y
              deducir alergenicidad de un ingrediente sería inventar un dato de
              seguridad alimentaria.
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
        </div><!-- /.modal -->
      </div><!-- /.modal-fondo -->
    </div><!-- /.mapa-panel -->

    <div class="glass-panel content-card">
      <div class="markdown-body" v-html="sanitizedHtml"></div>

      <div class="actions">
        <span v-if="errorDescarga" class="error-descarga">{{ errorDescarga }}</span>
        <button
          v-if="result.ejecucion_id"
          class="btn-primary download-btn"
          :disabled="descargando"
          @click="descargar"
        >
          {{ descargando ? 'Preparando…' : 'Descargar PDF' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, NoAutorizado } from '../api.js'
import TablaGondola from './TablaGondola.vue'

const router = useRouter()

const props = defineProps({
  result: {
    type: Object,
    required: true
  }
})

defineEmits(['reset'])

const descargando = ref(false)
const errorDescarga = ref('')

const AVISOS = {
  paywall: {
    tipo: 'premium',
    icono: '🔒',
    titulo: 'Informe del plan gratuito',
    texto: 'Este análisis incluye el mapa comercial. Con el plan premium se añaden dos secciones que no se han generado para este informe:',
    faltan: [
      'Hipótesis de formulación: ingeniería inversa de ingredientes y procesos a partir de los productos comparables.',
      'Dossier regulatorio: restricciones con citas verificables, cada una con su fuente oficial y enlace.'
    ]
  },
  pocos_productos: {
    tipo: 'tecnico',
    icono: '🔍',
    titulo: 'Cobertura limitada en el snapshot',
    texto: 'La búsqueda encontró dos o menos productos que usen el insumo de forma directa. El informe se emite igual, pero conviene leerlo como orientación: no hay base suficiente para conclusiones firmes. No es una limitación de tu plan.'
  },
  presupuesto: {
    tipo: 'sindato',
    icono: '⏸️',
    titulo: 'Sin dato: presupuesto agotado',
    texto: 'Se alcanzó el tope de gasto configurado, así que algunas etapas no se ejecutaron. Lo que ves está completo hasta donde llegó el análisis; no hay ningún error, el gasto está acotado por diseño.'
  }
}

const aviso = computed(() => AVISOS[props.result.motivo_parcial] || null)

/* --- Mapa comercial (etapa 2b) ------------------------------------------ */

const NIVELES = {
  1: 'snapshot local',
  2: 'API licenciada',
  3: 'agente web'
}

// Un mapa sin productos no se pinta: el markdown ya dice que no se encontró
// ninguno, y un panel con tres ceros se lee como un fallo de carga.
const mapa = computed(() => {
  const m = props.result.mapa
  return m && m.productos && m.productos.length ? m : null
})

const nPaises = computed(() =>
  new Set((mapa.value?.productos ?? []).flatMap(p => p.paises_iso ?? [])).size
)

// Los productos sin marca no cuentan: el snapshot no la trae para el 36 % de
// ellos y contarlos como una marca más inflaría la cifra que se dice en la demo.
const nMarcas = computed(() =>
  new Set((mapa.value?.productos ?? []).map(p => p.marca).filter(Boolean)).size
)

/* --- Góndola: a cuánto se vende hoy, tienda por tienda ------------------- */

// Una lista por mercado y no una sola con columna «país»: la lectura útil es
// «cuánto cuesta aquí frente a cuánto cuesta allá», y mezclarlas obligaría a
// filtrar para leer cualquiera de ellas.
//
// Lista vacía = ese mercado no se consultó, o no había nada. `TablaGondola`
// pinta la sección igual y declara la ausencia en una línea; ocultarla entera
// —que es lo que hacía— convertía cualquier avería en una pantalla idéntica a
// «no hay ofertas», y eso costó dos rondas de depuración.
//
// El resto —el orden por EAN, el chip de repetido, los «sin dato», la ficha
// nutricional— vive dentro del componente, porque es idéntico en los dos
// mercados y duplicarlo aquí acabaría en dos tablas que se comportan distinto.
const ofertasPeru = computed(() => mapa.value?.ofertas_peru ?? [])
const ofertasAlemania = computed(() => mapa.value?.ofertas_alemania ?? [])
const ofertasSuiza = computed(() => mapa.value?.ofertas_suiza ?? [])

// Precio de materia prima. Lista vacía = MIDAGRI no publica precio para este
// insumo; no es lo mismo que "vale cero" ni que "está detrás del paywall".
const precios = computed(() => mapa.value?.precios_materia_prima ?? [])
const precioReciente = computed(() =>
  precios.value.reduce((a, b) => (a.fecha >= b.fecha ? a : b), precios.value[0])
)

const nivelesFaltan = computed(() =>
  (mapa.value?.niveles_no_disponibles ?? [])
    .map(n => `nivel ${n} (${NIVELES[n] ?? 'desconocido'})`)
    .join(', ')
)

/* --- Paginación de la tabla del mapa ------------------------------------- */

// 25 es lo mismo que muestra el PDF: quien compare las dos salidas ve la misma
// primera página en vez de dos recortes distintos del mismo mapa.
const POR_PAGINA = 25

const pagina = ref(1)

// Una consulta nueva reutiliza el componente. Sin esto, buscar un insumo con
// menos productos dejaría la vista en una página que ya no existe.
watch(() => props.result.ejecucion_id, () => { pagina.value = 1 })

const totalPaginas = computed(() =>
  Math.max(1, Math.ceil((mapa.value?.productos.length ?? 0) / POR_PAGINA))
)

const desde = computed(() => (pagina.value - 1) * POR_PAGINA + 1)
const hasta = computed(() =>
  Math.min(pagina.value * POR_PAGINA, mapa.value?.productos.length ?? 0)
)

const filas = computed(() =>
  (mapa.value?.productos ?? [])
    .slice(desde.value - 1, hasta.value)
    .map(p => ({
      id: p.producto_id,
      nombre: p.nombre,
      url: p.url,
      producto: p,
      // El orden es el de las columnas intermedias de la cabecera (País, Marca,
      // Precio, Aditivos). `null` = sin dato; se normaliza aquí para que la
      // plantilla no distinga entre null, cadena vacía y lista vacía.
      celdas: [
        p.paises_iso?.length ? p.paises_iso.join(', ') : null,
        p.marca || null,
        p.precio_rango || null
      ]
    }))
)

/* --- Análisis regulatorio (T6) ------------------------------------------- */

// La URL de la pestaña de análisis, resuelta por el router y no construida a
// mano: si la ruta cambia de forma, esto la sigue. `resolve().href` respeta
// además la base de la SPA, que un literal se saltaría, y codifica el id —que
// viene como `OFF:00000036`— sin que haya que acordarse.
const urlAnalisis = (productoId) => router.resolve({
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

const abrir = async (producto, seccion) => {
  abierto.value = producto
  foco.value = seccion
  await nextTick()
  const destino = seccion === 'aditivos'
    ? seccionAditivos.value
    : seccionIngredientes.value
  destino?.scrollIntoView({ block: 'nearest' })
}

// Cerrar con Escape: un modal del que solo se sale con el ratón estorba a quien
// está recorriendo la tabla con el teclado.
const alPulsarTecla = (e) => { if (e.key === 'Escape') abierto.value = null }
onMounted(() => window.addEventListener('keydown', alPulsarTecla))
onUnmounted(() => window.removeEventListener('keydown', alPulsarTecla))

// Cambiar de página con un modal abierto dejaría en pantalla una ficha que ya
// no está en la tabla de debajo.
watch(pagina, () => { abierto.value = null })

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
.result-container {
  padding: 20px;
  max-width: 1000px;
  margin: 0 auto;
}

.header-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.badges {
  display: flex;
  gap: 10px;
}

.badge {
  background: rgba(15, 23, 42, 0.8);
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid var(--card-border);
}

.badge.success {
  background: rgba(16, 185, 129, 0.2);
  color: #10B981;
  border-color: rgba(16, 185, 129, 0.3);
}

.badge.version {
  background: rgba(56, 189, 248, 0.2);
  color: #38BDF8;
}

.badge.time {
  background: rgba(245, 158, 11, 0.15);
  color: #D97706;
  border-color: rgba(245, 158, 11, 0.3);
}

.reset-btn {
  padding: 8px 16px;
  font-size: 0.9rem;
}

/* --- Avisos de informe parcial ------------------------------------------ */

.aviso {
  display: flex;
  gap: 16px;
  padding: 20px 24px;
  margin-bottom: 20px;
  align-items: flex-start;
}

.aviso-icono {
  font-size: 1.8rem;
  line-height: 1;
}

.aviso h4 {
  margin: 0 0 6px 0;
  font-size: 1rem;
}

.aviso p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.faltan {
  margin: 10px 0 0 0;
  padding-left: 18px;
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--text-main);
}

.faltan li {
  margin-bottom: 6px;
}

.aviso.premium {
  background: rgba(139, 92, 246, 0.1);
  border-color: rgba(139, 92, 246, 0.3);
}

.aviso.premium h4 {
  color: #8B5CF6;
}

.aviso.tecnico {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.3);
}

.aviso.tecnico h4 {
  color: #D97706;
}

.aviso.sindato {
  background: rgba(100, 116, 139, 0.12);
  border-color: rgba(100, 116, 139, 0.3);
}

.aviso.sindato h4 {
  color: #64748B;
}

/* --- Mapa comercial ------------------------------------------------------ */

.mapa-panel {
  padding: 20px 24px;
  margin-bottom: 20px;
  text-align: left;
  /* Ancla del overlay de la ficha: sin esto, `position: absolute` treparía
     hasta el viewport y volvería a tapar la página entera. */
  position: relative;
}

.mapa-titulo {
  margin: 0 0 14px 0;
  font-size: 1rem;
}

.mapa-cifras {
  display: flex;
  flex-wrap: wrap;
  gap: 28px;
  margin-bottom: 14px;
}

.cifra {
  display: flex;
  flex-direction: column;
}

.cifra strong {
  font-size: 1.6rem;
  line-height: 1.1;
  color: var(--primary-color);
}

.cifra span {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

/* --- Precio de materia prima --------------------------------------------- */

.precio-bloque {
  margin: 0 0 14px 0;
  padding: 14px 16px;
  border-radius: 6px;
  border-left: 3px solid #10B981;
  background: rgba(16, 185, 129, 0.08);
}

.precio-bloque h5 {
  margin: 0 0 10px 0;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.precio-item {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px 0;
}

.precio-valor {
  font-size: 1.15rem;
  font-weight: 700;
  color: #059669;
}

.precio-unidad {
  font-size: 0.76rem;
  color: var(--text-muted);
}

.precio-nombre {
  font-size: 0.85rem;
  color: var(--text-main);
}

.precio-var {
  font-size: 0.78rem;
  margin-left: auto;
}

.precio-var.sube { color: #DC2626; }
.precio-var.baja { color: #059669; }

.precio-fuente {
  margin: 10px 0 0 0;
  font-size: 0.76rem;
  color: var(--text-muted);
}

.precio-fuente a { color: var(--primary-color); }

.mapa-hueco {
  margin: 0;
  padding: 12px 14px;
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--text-muted);
  background: rgba(100, 116, 139, 0.12);
  border-left: 3px solid #64748B;
  border-radius: 4px;
}

.mapa-hueco strong {
  color: var(--text-main);
}

.mapa-niveles {
  margin: 10px 0 0 0;
  font-size: 0.82rem;
  font-style: italic;
  color: var(--text-muted);
}

/* --- Tabla paginada del mapa --------------------------------------------- */

.mapa-tabla-scroll {
  margin-top: 16px;
  overflow-x: auto;
}

.mapa-tabla {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.mapa-tabla th {
  text-align: left;
  padding: 8px 10px;
  background: rgba(100, 116, 139, 0.12);
  border-bottom: 2px solid var(--card-border);
  white-space: nowrap;
  font-weight: 600;
}

.mapa-tabla td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--card-border);
  vertical-align: top;
  white-space: nowrap;
}

.mapa-tabla tbody tr:hover {
  background: rgba(100, 116, 139, 0.06);
}

/* El nombre es lo único que puede ser largo; se le deja crecer y se corta. */
.col-producto {
  white-space: normal;
  min-width: 240px;
  max-width: 380px;
}

.mapa-tabla a {
  color: var(--primary-color);
  text-decoration: none;
}

.mapa-tabla a:hover {
  text-decoration: underline;
}

/*
  Atenuada y a la vez visible: el objetivo no es esconder el hueco —sería lo
  contrario de lo que el mapa quiere enseñar— sino que se lea como un hueco
  declarado y no como un dato más de la fila.
*/
.sin-dato {
  display: inline-block;
  font-size: 0.78rem;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(100, 116, 139, 0.14);
  color: var(--text-muted);
}

.paginacion {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--card-border);
}

.pag-btn {
  padding: 5px 12px;
  font-size: 0.82rem;
  border-radius: 6px;
  border: 1px solid var(--card-border);
  background: rgba(100, 116, 139, 0.08);
  color: var(--text-main);
  cursor: pointer;
}

.pag-btn:hover:not(:disabled) {
  background: rgba(100, 116, 139, 0.18);
}

.pag-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.pag-estado {
  margin-left: auto;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.btn-ficha {
  padding: 4px 10px;
  font-size: 0.78rem;
  white-space: nowrap;
  border-radius: 6px;
  border: 1px solid var(--card-border);
  background: rgba(56, 189, 248, 0.12);
  color: var(--primary-color);
  cursor: pointer;
}

.btn-ficha:hover {
  background: rgba(56, 189, 248, 0.24);
}

/*
  El enlace a la pestaña de análisis. Se pinta como acción y no como enlace de
  texto porque compite con el nombre del producto, que también es un enlace: sin
  peso visual propio, la columna entera parecía decoración de la primera.
*/
.btn-analisis {
  display: inline-block;
  padding: 4px 10px;
  border: 1px solid var(--primary-color);
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--primary-color);
  text-decoration: none;
  white-space: nowrap;
}

.btn-analisis:hover {
  background: var(--primary-color);
  color: #fff;
}

/*
  "ninguno" no se pinta como "sin dato": son cosas distintas. Sin texto de
  etiqueta no sabemos nada; con texto y cero aditivos, sabemos que no los lleva.
*/
.ninguno {
  font-size: 0.8rem;
  color: var(--text-main);
}

/* --- Ficha de formulación ------------------------------------------------ */

/*
  `absolute`, no `fixed`: la ficha se superpone al panel del mapa y nada más. El
  resto del informe —el aviso de plan, el insight, el botón de descarga— sigue
  visible y utilizable, que es lo que se espera cuando lo que se consulta es el
  detalle de una fila.

  El radio coincide con el del panel para que el velo no desborde sus esquinas.
*/
.modal-fondo {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.55);
}

.modal {
  width: 100%;
  max-width: 620px;
  /* Del alto del panel, no del viewport: la ficha vive dentro de su caja. */
  max-height: 100%;
  display: flex;
  flex-direction: column;
  text-align: left;
  border-radius: 12px;
  border: 1px solid var(--card-border);
  background: var(--card-bg, #fff);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.4);
}

.modal-cabecera {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--card-border);
}

.modal-cabecera h4 {
  margin: 0 0 4px 0;
  font-size: 1.02rem;
}

.modal-sub {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.modal-sub a {
  color: var(--primary-color);
}

.modal-cerrar {
  margin-left: auto;
  border: none;
  background: none;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: var(--text-muted);
}

.modal-cuerpo {
  padding: 18px 22px;
  overflow-y: auto;
}

.modal-cuerpo section + section {
  margin-top: 20px;
}

/* La sección desde la que se abrió la ficha, para no perderla de vista. */
.modal-cuerpo section.destacada {
  margin-left: -12px;
  padding-left: 9px;
  border-left: 3px solid var(--primary-color);
}

.nota-alcance {
  margin-top: 8px;
  font-size: 0.76rem;
}

.modal-cuerpo h5 {
  margin: 0 0 8px 0;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
}

.cuenta {
  display: inline-block;
  margin-left: 6px;
  padding: 0 7px;
  border-radius: 9px;
  background: rgba(100, 116, 139, 0.16);
  font-size: 0.75rem;
  letter-spacing: 0;
}

.ingredientes-texto {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.7;
  color: var(--text-main);
}

/*
  Dos columnas: una lista de 47 ingredientes en una sola columna obliga a
  desplazarse para verla entera, y lo que se quiere es abarcarla de un vistazo.
  Se reduce a una columna cuando no hay ancho.
*/
.lista-ingredientes {
  margin: 0;
  padding-left: 22px;
  columns: 2;
  column-gap: 24px;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--text-main);
}

.lista-ingredientes li {
  margin-bottom: 3px;
  /* Que un ingrediente no se parta entre las dos columnas. */
  break-inside: avoid;
}

@media (max-width: 560px) {
  .lista-ingredientes {
    columns: 1;
  }
}

.etiquetas {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.etiquetas li {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
  background: rgba(56, 189, 248, 0.14);
  color: var(--primary-color);
}

.etiquetas.alergenos li {
  background: rgba(245, 158, 11, 0.18);
  color: #B45309;
}

.matiz {
  margin: 0;
  font-size: 0.84rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.modal-pie {
  padding: 12px 22px;
  border-top: 1px solid var(--card-border);
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--text-muted);
}

.content-card {
  padding: 40px;
  text-align: left;
}

.actions {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--card-border);
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 16px;
}

.download-btn {
  text-decoration: none;
}

.download-btn:disabled {
  opacity: 0.6;
  cursor: progress;
}

.error-descarga {
  font-size: 0.85rem;
  color: #EF4444;
}

/* Markdown Styles */
:deep(.markdown-body h1) {
  color: var(--primary-color);
  border-bottom: 2px solid rgba(0,0,0,0.1);
  padding-bottom: 10px;
}

:deep(.markdown-body h2) {
  color: var(--primary-hover);
  margin-top: 1.5em;
}

:deep(.markdown-body h3) {
  color: #2A454B;
}

:deep(.markdown-body p),
:deep(.markdown-body li) {
  line-height: 1.7;
  color: var(--text-main);
}

:deep(.markdown-body ul) {
  padding-left: 20px;
}

:deep(.markdown-body code) {
  background: rgba(0,0,0,0.05);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  color: #DC3545;
}

/*
  Tabla del mapa comercial. Hasta S4 el informe no traía ninguna tabla, así que
  no había estilos: la del mapa habría salido sin bordes ni cabecera.
*/
.markdown-body {
  overflow-x: auto;
}

:deep(.markdown-body table) {
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 0.85rem;
}

:deep(.markdown-body th) {
  text-align: left;
  padding: 8px 10px;
  background: rgba(100, 116, 139, 0.12);
  border-bottom: 2px solid var(--card-border);
  white-space: nowrap;
  font-weight: 600;
}

:deep(.markdown-body td) {
  padding: 7px 10px;
  border-bottom: 1px solid var(--card-border);
  vertical-align: top;
}

:deep(.markdown-body tbody tr:hover) {
  background: rgba(100, 116, 139, 0.06);
}

:deep(.markdown-body td a) {
  color: var(--primary-color);
  text-decoration: none;
}

:deep(.markdown-body td a:hover) {
  text-decoration: underline;
}

/*
  Las celdas "sin dato". El informe las escribe en cursiva (`_sin dato_`), que
  es la única cursiva que aparece dentro de la tabla.

  Se pintan atenuadas y a la vez visibles: el objetivo no es esconderlas —eso
  sería justo lo contrario de lo que el mapa quiere enseñar— sino que se lean
  como un hueco declarado y no como un dato más de la fila.
*/
:deep(.markdown-body td em) {
  font-style: normal;
  font-size: 0.78rem;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(100, 116, 139, 0.14);
  color: var(--text-muted);
  white-space: nowrap;
}
</style>
