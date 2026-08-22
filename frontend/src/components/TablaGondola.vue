<!--
  Una góndola: a cuánto se vende hoy y dónde.

  Existe como componente porque hay TRES —Perú, Alemania y Suiza— y son casi
  idénticas. Copiadas, la primera vez que alguien afinase una de ellas quedarían
  discrepando, y como el entregable es justo la comparación entre mercados, se
  leería mal sin que nada fallara.

  Lo que cambia entre mercados va por props (título, subtítulo, cómo se llaman
  las tiendas); lo que no cambia —el orden, los «sin dato», el EAN repetido, la
  ficha nutricional— vive aquí una sola vez.

  ## Por qué ahora hay dos vistas

  Esto era una tabla de ocho columnas, y tres seguidas en la misma pantalla. Ocho
  columnas obligan a leer en horizontal un dato —el precio— que es lo único que
  se viene a buscar, y con nombres de producto de 60 caracteres la primera
  columna se comía la mitad del ancho.

  **Tarjetas** es ahora la vista por defecto: el precio manda en cuerpo grande,
  la conversión va debajo en pequeño, y el mismo EAN en otra tienda se compara
  DENTRO de la tarjeta en vez de ser una nota al pie que obliga a buscar la otra
  fila a ojo.

  **Tabla** sigue estando, a un clic, y no es un resto del pasado: es la vista
  densa que se imprime y se audita, con las ocho columnas alineadas. Las dos
  leen exactamente los mismos datos.
-->
<template>
  <!--
    La sección se pinta SIEMPRE, aunque no haya ofertas.

    Antes se ocultaba entera con `v-if="ofertas.length"`, por una razón buena:
    una tabla vacía con cabeceras se lee como un fallo de carga. Pero el
    remedio tenía un coste peor, y se pagó dos veces depurando: si no hay nada,
    **«este mercado no tiene ofertas» y «esto se rompió» se ven exactamente
    igual**, que es no ver nada. La primera vez la causa fue una caché con el
    esquema viejo; la segunda, una API sin reiniciar. En los dos casos el
    síntoma en pantalla fue el mismo: ausencia muda.

    La salida no es enseñar una tabla vacía —eso sigue leyéndose como error—
    sino declarar la ausencia en una línea. Es el principio de la casa aplicado
    a la propia interfaz: el dato o es real, o dice que no está.
  -->
  <section class="gondola superficie imprimible">
    <div class="gondola-cabecera">
      <h2>{{ titulo }}</h2>
      <span class="gondola-n">
        <b class="num">{{ ofertas.length }}</b>
        {{ ofertas.length === 1 ? 'oferta' : 'ofertas' }}
      </span>

      <div
        v-if="ofertas.length"
        class="conmutador no-imprimir"
        role="group"
        :aria-label="`Forma de ver ${titulo}`"
      >
        <button type="button" :aria-pressed="vista === 'grid'" @click="vista = 'grid'">
          <Icono nombre="imagen" :tamano="14" />Tarjetas
        </button>
        <button type="button" :aria-pressed="vista === 'tabla'" @click="vista = 'tabla'">
          <Icono nombre="lista" :tamano="14" />Tabla
        </button>
      </div>
    </div>

    <!-- Cómo se obtuvo, que no es igual en los tres mercados y cambia lo que
         vale la cifra. Va arriba y no en el pie por eso. -->
    <p class="gondola-sub">{{ subtitulo }}</p>

    <!--
      No dice por qué está vacío, y es deliberado: desde aquí no se distingue
      «se consultó y no había» de «no se consultó» —el interruptor del servidor,
      un término que la etapa 1 no supo traducir—. Afirmar una de las dos sería
      inventar. Lo que sí se afirma es que se miró y esto es lo que hay.
    -->
    <p v-if="!ofertas.length" class="gondola-vacia">
      Sin ofertas para este insumo en esta consulta.
    </p>

    <!-- ================= Tarjetas ================= -->
    <!--
      Sin zona de packshot. El diseño la lleva, pero `OfertaComercial` no trae
      URL de imagen de ninguna tienda: una fila de recuadros grises vacíos sería
      justo el ruido que este rediseño retira de las columnas sin dato.
    -->
    <div v-else-if="vista === 'grid'" class="rejilla">
      <article v-for="o in ofertas" :key="o.fuente_url + o.tienda" class="oferta">
        <header class="oferta-cabecera">
          <a
            class="oferta-nombre recorte-2"
            :href="o.fuente_url"
            target="_blank"
            rel="noopener"
            :title="o.nombre"
          >{{ o.nombre }}</a>
          <span class="oferta-tienda">{{ o.tienda }}</span>
        </header>

        <!--
          El precio nativo manda y la conversión va debajo. Al revés —soles
          grandes, euros en pequeño— se pierde el único dato que la tienda
          publica de verdad: el resto es aritmética nuestra.
        -->
        <div class="oferta-precio">
          <template v-if="tienePrecio(o)">
            <span class="precio-grande">{{ enOrigen(o) }}</span>

            <template v-if="!esLocal(o)">
              <!-- La tasa, su fecha y su fuente viajan en el title: una cifra
                   convertida sin ellas no es auditable, y en un informe de CITE
                   hay que poder responder «¿con qué tipo de cambio?» meses
                   después. -->
              <span
                v-if="o.precio_pen !== null && o.precio_pen !== undefined"
                class="precio-conv"
                :title="detalleConversion(o)"
              >
                ≈ S/ {{ o.precio_pen.toFixed(2) }}
                <!--
                  Y de dónde sale la tasa, **a la vista** y no solo en el title.
                  El euro y el dólar los publica el BCRP y son citables en un
                  informe; el franco suizo NO tiene serie en el BCRP, así que
                  sus soles vienen de un agregador comercial. Mezclar las dos
                  procedencias sin distinguirlas es lo que este informe evita en
                  todo lo demás: el hover no vale, porque no existe al imprimir
                  ni en un móvil.
                -->
                <span v-if="!esOficial(o)" class="chip chip--no-consultado chip-tasa">
                  tasa no oficial
                </span>
              </span>
              <span v-else class="sin-dato">sin conversión a soles</span>
            </template>
          </template>
          <span v-else class="sin-dato">precio sin dato</span>
        </div>

        <!--
          El mismo EAN en otra tienda, comparado aquí dentro. Antes era un chip
          «también en otra tienda» y una nota al pie: para saber la diferencia
          había que localizar la otra fila a ojo y restar mentalmente.
        -->
        <p v-if="comparacion(o)" class="oferta-compara" :class="comparacion(o).sentido">
          <Icono :nombre="comparacion(o).sentido === 'caro' ? 'sube' : 'baja'" :tamano="13" />
          <span>
            <b>{{ comparacion(o).texto }}</b>
            que en {{ comparacion(o).tienda }} ({{ comparacion(o).precioOtro }})
          </span>
        </p>

        <dl class="oferta-datos">
          <div>
            <dt>Stock</dt>
            <!-- Stock vacío = la tienda no lo publica, o dio una cifra
                 centinela. Nunca cero: cero sí sería un dato. -->
            <dd v-if="o.stock !== null && o.stock !== undefined" class="num">{{ o.stock }}</dd>
            <dd v-else class="sin-dato">sin dato</dd>
          </div>
          <div>
            <dt>EAN</dt>
            <dd v-if="o.ean" class="codigo">{{ o.ean }}</dd>
            <dd v-else class="sin-dato">sin dato</dd>
          </div>
        </dl>

        <div class="oferta-acciones">
          <!--
            Ingredientes y alérgenos: de qué está hecho.

            La lista de ingredientes NO la publica ninguna cadena peruana. Se
            buscó por cinco vías —especificaciones del API, el grupo
            «Componentes del Producto», la descripción, el HTML de la ficha y
            OpenFoodFacts por EAN— y el dato vive en el envase físico, no en la
            web. «Sin dato» es la respuesta correcta, no un fallo del extractor.

            Lo que sí llega es el alérgeno declarado, que Makro publica. Se
            enseña con su propio botón y no dentro de la ficha nutricional
            porque es una advertencia de seguridad alimentaria: hay que verla
            sin tener que abrir nada.
          -->
          <button v-if="o.ingredientes" class="btn-ficha" @click="composicionAbierta = o">
            Ingredientes
          </button>
          <button
            v-else-if="o.alergenos"
            class="btn-ficha btn-ficha--alergeno"
            title="La tienda no publica los ingredientes, pero sí el alérgeno declarado"
            @click="composicionAbierta = o"
          >
            <Icono nombre="alerta" :tamano="13" />Alérgenos
          </button>
          <span v-else class="sin-dato">ingredientes sin dato</span>

          <!-- Dos estados, no tres: o la tienda publica la tabla o no. Aquí no
               cabe el «ninguno» que sí tiene la columna de aditivos del mapa,
               porque una ficha sin tabla nutricional no significa que el
               producto no tenga nutrientes. -->
          <button v-if="o.nutricion" class="btn-ficha" @click="nutriAbierta = o">
            Nutrición
          </button>
        </div>

        <!--
          Análisis regulatorio, **partiendo de la lista de ingredientes**.

          Aquí no hay columna de aditivos previa de la que colgarse —el mapa
          comercial sí la tiene—, así que la condición es tener `ingredientes`:
          sin lista no hay nada que leer y el botón sería un enlace a una
          pestaña vacía.

          Que la lista exista no garantiza que traiga aditivos, y está bien: la
          pestaña dirá «esta etiqueta no declara ninguno», que es información.
          Lo que no puede pasar es ofrecer análisis donde no hay ni etiqueta.
        -->
        <a
          v-if="o.ingredientes && ejecucionId"
          class="oferta-analizar"
          :href="urlAnalisis(o)"
          target="_blank"
          rel="noopener"
          :title="`Autorización de los aditivos de ${o.nombre} en EE. UU., Codex y UE · consume saldo del plan`"
        >
          <span class="punto" aria-hidden="true"></span>
          Analizar <Icono nombre="externo" :tamano="13" />
        </a>
        <p v-else class="oferta-sin-analisis">
          {{ o.ingredientes ? 'sin informe asociado' : 'sin ingredientes · nada que analizar' }}
        </p>
      </article>
    </div>

    <!-- ================= Tabla ================= -->
    <div v-else class="tabla-scroll">
      <table class="tabla gondola-tabla">
        <thead>
          <tr>
            <th>Producto</th><th>Tienda</th><th class="num">Precio</th>
            <th class="num">Stock</th><th>EAN</th>
            <th>Ingredientes</th>
            <th>Análisis</th>
            <th>Nutrición</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="o in ofertas"
            :key="o.fuente_url + o.tienda"
            :class="{ comparable: esComparable(o) }"
          >
            <td class="col-producto">
              <a :href="o.fuente_url" target="_blank" rel="noopener" :title="o.nombre">
                <span class="recorte-2">{{ o.nombre }}</span>
              </a>
              <!-- El EAN es lo único que identifica el MISMO producto en dos
                   tiendas: el nombre cambia de una a otra. Marcarlo es lo que
                   convierte la lista en una comparación. -->
              <span
                v-if="esComparable(o)"
                class="chip chip-comparable"
                title="El mismo producto está en otra tienda de esta tabla"
              >también en otra tienda</span>
            </td>
            <td>{{ o.tienda }}</td>

            <!--
              Tres estados, y el del medio es el que importa fuera de Perú.

              Antes esta celda pintaba solo `precio_pen` y caía a «sin dato»
              cuando venía null. Con Perú daba igual —la conversión es la
              identidad y nunca es null—, pero para un precio en euros sin tasa
              del BCRP se estaba TIRANDO un precio que sí se había leído: el
              backend conserva `precio` y `moneda` a propósito para este caso.
              Un hueco donde hay dato es peor que no tener la columna.
            -->
            <td class="num precio">
              <template v-if="o.precio_pen !== null && o.precio_pen !== undefined">
                <span v-if="esLocal(o)">S/ {{ o.precio_pen.toFixed(2) }}</span>
                <template v-else>
                  <span class="precio-origen">{{ enOrigen(o) }}</span>
                  <span class="precio-conv-tabla" :title="detalleConversion(o)">
                    ≈ S/ {{ o.precio_pen.toFixed(2) }}
                  </span>
                  <span
                    v-if="!esOficial(o)"
                    class="chip chip--no-consultado chip-tasa"
                    :title="detalleConversion(o)"
                  >tasa no oficial</span>
                </template>
              </template>
              <template v-else-if="tienePrecio(o)">
                <span class="precio-origen">{{ enOrigen(o) }}</span>
                <span class="sin-dato">sin conversión</span>
              </template>
              <span v-else class="sin-dato">sin dato</span>
            </td>

            <td class="num">
              <span v-if="o.stock !== null && o.stock !== undefined">{{ o.stock }}</span>
              <span v-else class="sin-dato">sin dato</span>
            </td>
            <td>
              <span v-if="o.ean" class="codigo">{{ o.ean }}</span>
              <span v-else class="sin-dato">sin dato</span>
            </td>

            <td>
              <button v-if="o.ingredientes" class="btn-ficha" @click="composicionAbierta = o">
                Ver lista
              </button>
              <button
                v-else-if="o.alergenos"
                class="btn-ficha btn-ficha--alergeno"
                title="La tienda no publica los ingredientes, pero sí el alérgeno declarado"
                @click="composicionAbierta = o"
              >
                <Icono nombre="alerta" :tamano="13" />alérgenos
              </button>
              <span v-else class="sin-dato">sin dato</span>
            </td>

            <td>
              <a
                v-if="o.ingredientes && ejecucionId"
                class="enlace-analisis"
                :href="urlAnalisis(o)"
                target="_blank"
                rel="noopener"
                :title="`Autorización de los aditivos de ${o.nombre} en EE. UU., Codex y UE · consume saldo del plan`"
              >
                <span class="punto" aria-hidden="true"></span>
                Analizar <Icono nombre="externo" :tamano="12" />
              </a>
              <span v-else-if="o.ingredientes" class="sin-dato">sin informe</span>
              <span v-else class="sin-dato">sin ingredientes</span>
            </td>

            <td>
              <button v-if="o.nutricion" class="btn-ficha" @click="nutriAbierta = o">
                Ver tabla
              </button>
              <span v-else class="sin-dato">sin dato</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ================= Fichas ================= -->
    <!--
      Composición y nutrición son dos diálogos con el mismo esqueleto. Se
      superponen a toda la pantalla, no solo a esta sección: un fondo que
      cubriera media página deja lo de detrás pulsable, y con tres góndolas
      seguidas eso es un tercio de la pantalla en cada caso.
    -->
    <div
      v-if="composicionAbierta"
      class="modal-fondo no-imprimir"
      @click.self="composicionAbierta = null"
    >
      <div class="modal superficie" role="dialog" aria-modal="true" tabindex="-1"
           :aria-label="composicionAbierta.nombre">
        <header class="modal-cabecera">
          <div class="modal-titulo">
            <h4>{{ composicionAbierta.nombre }}</h4>
            <p class="modal-sub">
              {{ composicionAbierta.tienda }} ·
              <a :href="composicionAbierta.fuente_url" target="_blank" rel="noopener">
                ver ficha en la tienda <Icono nombre="externo" :tamano="12" />
              </a>
            </p>
          </div>
          <button class="modal-cerrar" aria-label="Cerrar" @click="composicionAbierta = null">
            <Icono nombre="equis" :tamano="17" />
          </button>
        </header>

        <div class="modal-cuerpo">
          <section v-if="composicionAbierta.ingredientes">
            <h5>Ingredientes</h5>
            <p class="composicion-texto">{{ composicionAbierta.ingredientes }}</p>
          </section>

          <!-- Se dice que faltan, en vez de omitir la sección. Un apartado
               ausente se lee como «no se miró»; esto declara que se miró. -->
          <section v-else>
            <h5>Ingredientes</h5>
            <p class="matiz">
              La tienda no publica la lista de ingredientes en su ficha. No se
              completa desde otra fuente: el dato está en el envase, y atribuir
              a este producto los ingredientes de otro parecido sería inventar.
            </p>
          </section>

          <section v-if="composicionAbierta.alergenos">
            <h5>Alérgenos declarados</h5>
            <p class="alergenos-texto">{{ composicionAbierta.alergenos }}</p>
          </section>
        </div>

        <footer class="modal-pie">
          Leído de la ficha de {{ composicionAbierta.tienda }} en el momento de
          la consulta.
        </footer>
      </div>
    </div>

    <div v-if="nutriAbierta" class="modal-fondo no-imprimir" @click.self="nutriAbierta = null">
      <div class="modal superficie" role="dialog" aria-modal="true" tabindex="-1"
           :aria-label="nutriAbierta.nombre">
        <header class="modal-cabecera">
          <div class="modal-titulo">
            <h4>{{ nutriAbierta.nombre }}</h4>
            <p class="modal-sub">
              {{ nutriAbierta.tienda }} ·
              <a :href="nutriAbierta.fuente_url" target="_blank" rel="noopener">
                ver ficha en la tienda <Icono nombre="externo" :tamano="12" />
              </a>
            </p>
          </div>
          <button class="modal-cerrar" aria-label="Cerrar" @click="nutriAbierta = null">
            <Icono nombre="equis" :tamano="17" />
          </button>
        </header>

        <div class="modal-cuerpo">
          <!-- La base va primero y destacada: sin ella, «210,6 kcal» no se
               puede comparar con nada. Podría ser de 30 g o de 60 g. -->
          <p class="nutri-porcion">
            Valores por porción de
            <strong>{{ nutriAbierta.nutricion.porcion || 'tamaño no declarado' }}</strong>
            <span v-if="nutriAbierta.nutricion.porciones_envase">
              · {{ nutriAbierta.nutricion.porciones_envase }} porciones por envase
            </span>
          </p>

          <dl class="nutri-tabla">
            <template v-for="f in filasNutri" :key="f.etiqueta">
              <dt>{{ f.etiqueta }}</dt>
              <dd class="num">{{ f.valor }}</dd>
            </template>
          </dl>

          <p v-if="nutriAbierta.nutricion.alergenos" class="alergenos-texto">
            <strong>Alérgenos declarados:</strong>
            {{ nutriAbierta.nutricion.alergenos }}
          </p>

          <!-- La advertencia de la propia tienda sobre sus cifras. Va a la
               vista y no en letra pequeña: presentar como medido algo que la
               ficha marca como teórico sería lo contrario de lo que hace este
               informe. -->
          <p v-if="nutriAbierta.nutricion.nota" class="nutri-nota">
            <Icono nombre="info" :tamano="15" />
            La tienda declara: «{{ nutriAbierta.nutricion.nota }}»
          </p>
        </div>

        <footer class="modal-pie">
          Leído de la ficha de {{ nutriAbierta.tienda }}. No se ha recalculado
          ni completado con otras fuentes.
        </footer>
      </div>
    </div>

    <!-- ================= Pies ================= -->
    <!-- Sin ofertas no hay tiendas que listar, y «Cadenas consultadas: .» es
         peor que no decir nada: parece un fallo de plantilla. -->
    <p v-if="ofertas.length" class="gondola-pie">
      {{ etiquetaTiendas }}: {{ tiendas.join(', ') }}.
      <template v-if="nComparables">
        <strong>{{ nComparables }}</strong>
        {{ nComparables === 1 ? 'producto aparece' : 'productos aparecen' }}
        en más de una tienda; la diferencia de precio por el mismo código de
        barras va dentro de cada tarjeta.
      </template>
    </p>

    <!-- El pie de la tasa solo aparece si en esta tabla hay alguna: no se
         avisa de un problema que esta tabla no tiene. -->
    <p v-if="fuentesNoOficiales.length" class="gondola-pie gondola-tasa">
      <Icono nombre="info" :tamano="15" />
      <span>
        El BCRP no publica tipo de cambio para {{ monedasNoOficiales.join(', ') }}.
        Los importes en soles de esas filas se han convertido con
        {{ fuentesNoOficiales.join(', ') }} y
        <strong>no son cifras oficiales</strong>: el precio de la izquierda, el
        que publica la tienda, sí lo es.
      </span>
    </p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import Icono from './Icono.vue'

const router = useRouter()

const props = defineProps({
  titulo: { type: String, required: true },
  // Lista vacía = no se consultó ese mercado, o no había nada. La sección se
  // pinta igual y declara la ausencia en una línea.
  ofertas: { type: Array, default: () => [] },
  subtitulo: { type: String, required: true },
  // «Cadenas consultadas» en Perú —se sabe cuáles se preguntaron— frente a
  // «Tiendas encontradas» en Alemania, donde el agente trae lo que halla. No es
  // cosmético: decir «consultadas» de una lista que no se eligió sería falso.
  etiquetaTiendas: { type: String, default: 'Tiendas' },
  // El run del que salen estas ofertas. Sin él no se puede abrir el análisis:
  // el backend relee los ingredientes del informe, no los recibe del cliente.
  // Vacío = la acción de análisis se apaga en vez de dar enlaces rotos.
  ejecucionId: { type: String, default: '' },
})

const vista = ref('grid')

/**
 * La URL de la pestaña de análisis de una oferta.
 *
 * La oferta se identifica por su `fuente_url` y no por un índice de la lista:
 * un índice se rompe en cuanto la tabla se reordene o se filtre, y el enlace
 * pasaría a abrir el análisis de otro producto sin que nada avise.
 */
const urlAnalisis = (oferta) =>
  router.resolve({
    name: 'analisis-oferta',
    params: { ejecucionId: props.ejecucionId },
    query: { url: oferta.fuente_url },
  }).href

const MONEDA_LOCAL = 'PEN'

const SIMBOLOS = { PEN: 'S/', EUR: '€', USD: 'US$', GBP: '£', CHF: 'CHF' }

const nutriAbierta = ref(null)
// Estado propio y no reutilizando `nutriAbierta`: son dos fichas distintas
// —composición y nutrición— y compartir la variable obligaría a preguntar de
// cuál se trata en cada uso. Además pueden abrirse desde la misma tarjeta.
const composicionAbierta = ref(null)

const tiendas = computed(() => [...new Set(props.ofertas.map((o) => o.tienda))].sort())

// EAN que aparece en más de una tienda. Es lo que hace que esto sea una
// comparación y no una lista: el nombre del producto cambia de una tienda a
// otra, el código de barras no.
const eansRepetidos = computed(() => {
  const cuenta = new Map()
  for (const o of props.ofertas) {
    if (!o.ean) continue
    cuenta.set(o.ean, (cuenta.get(o.ean) ?? 0) + 1)
  }
  return new Set([...cuenta].filter(([, n]) => n > 1).map(([ean]) => ean))
})

const esComparable = (oferta) =>
  Boolean(oferta.ean) && eansRepetidos.value.has(oferta.ean)
const nComparables = computed(() => eansRepetidos.value.size)

const tienePrecio = (o) => o.precio !== null && o.precio !== undefined
const esLocal = (o) => (o.moneda || MONEDA_LOCAL).toUpperCase() === MONEDA_LOCAL

/** El precio tal como lo publica la tienda, con el símbolo de su moneda. */
const enOrigen = (o) => {
  if (!tienePrecio(o)) return ''
  const moneda = (o.moneda || '').toUpperCase()
  // Con el código ISO cuando no se conoce el símbolo: 'CHF 4,99' se entiende,
  // '4,99' a secas no dice en qué se paga.
  return `${SIMBOLOS[moneda] ?? moneda} ${o.precio.toFixed(2)}`.trim()
}

/**
 * La comparación con el mismo EAN en otra tienda, resuelta aquí.
 *
 * Se compara sobre `precio_pen` y no sobre el precio nativo: dentro de una
 * misma tabla la moneda suele coincidir, pero no está garantizado, y restar
 * euros a francos daría un número con pinta de válido.
 *
 * Si el EAN está en tres tiendas se enseña **la más barata de las otras**: es
 * la que responde a «¿lo puedo conseguir más barato?», que es la pregunta que
 * trae a alguien a esta tabla.
 *
 * El porcentaje se calcula sobre el precio de la otra tienda, no sobre el
 * propio: «12 % más caro que en Metro» se lee respecto a Metro.
 */
const comparacion = (o) => {
  if (!esComparable(o)) return null
  if (o.precio_pen === null || o.precio_pen === undefined) return null

  const otras = props.ofertas.filter(
    (x) =>
      x !== o &&
      x.ean === o.ean &&
      x.precio_pen !== null &&
      x.precio_pen !== undefined,
  )
  if (!otras.length) return null

  const otro = otras.reduce((a, b) => (a.precio_pen <= b.precio_pen ? a : b))
  const delta = o.precio_pen - otro.precio_pen
  // Dos tiendas al mismo precio: no hay nada que comparar, y decir «0 % más
  // caro» sería ruido con forma de dato.
  if (Math.abs(delta) < 0.005) return null

  const pct = (delta / otro.precio_pen) * 100
  return {
    sentido: delta > 0 ? 'caro' : 'barato',
    tienda: otro.tienda,
    precioOtro: esLocal(otro) ? `S/ ${otro.precio_pen.toFixed(2)}` : enOrigen(otro),
    texto:
      `S/ ${Math.abs(delta).toFixed(2)} más ${delta > 0 ? 'caro' : 'barato'}` +
      ` (${delta > 0 ? '+' : '−'}${Math.abs(pct).toFixed(1)} %)`,
  }
}

/**
 * Si la tasa con la que se convirtió esa fila es la del banco central.
 *
 * `adaptadores/tipo_cambio.py` etiqueta la fuente: 'BCRP · <nombre de la
 * serie>' cuando la publica el banco, y 'exchangerate-api.com (no oficial)'
 * cuando cae al respaldo. Se mira ese prefijo y no una lista de monedas
 * porque quien decide es el backend: el día que el BCRP publique el franco,
 * basta con añadir la serie allí y esta tabla deja de marcarlo sola.
 */
const esOficial = (o) => /^BCRP/.test(o.conversion?.fuente ?? '')

// Las filas convertidas con una tasa que no es del BCRP. Se agregan para el
// pie: repetir la explicación entera en cada fila la volvería ruido, y el chip
// de la celda ya dice cuáles son.
const filasNoOficiales = computed(() =>
  props.ofertas.filter(
    (o) =>
      o.precio_pen !== null &&
      o.precio_pen !== undefined &&
      !esLocal(o) &&
      !esOficial(o),
  ),
)

const monedasNoOficiales = computed(() =>
  [
    ...new Set(
      filasNoOficiales.value.map((o) => (o.moneda || '').toUpperCase()).filter(Boolean),
    ),
  ].sort(),
)

const fuentesNoOficiales = computed(() =>
  [...new Set(filasNoOficiales.value.map((o) => o.conversion?.fuente).filter(Boolean))].sort(),
)

/** Con qué se convirtió. Sin esto la cifra en soles no es citable. */
const detalleConversion = (o) => {
  const c = o.conversion
  if (!c) return 'Convertido a soles'
  const partes = [`1 ${c.moneda_origen} = ${c.tasa} PEN`]
  if (c.fecha_tasa) partes.push(`tasa del ${c.fecha_tasa}`)
  if (c.fuente) partes.push(c.fuente)
  return partes.join(' · ')
}

// Orden fijo, el de una etiqueta nutricional. Se recorre siempre igual aunque
// falten campos, para que dos productos se puedan comparar leyendo en paralelo;
// los que la tienda no publica no se pintan, en vez de salir a cero.
const CAMPOS_NUTRI = [
  ['calorias', 'Calorías'],
  ['proteinas', 'Proteínas'],
  ['carbohidratos', 'Carbohidratos'],
  ['azucares', 'Azúcares'],
  ['grasas', 'Grasas'],
  ['sodio', 'Sodio'],
]

const filasNutri = computed(() => {
  const n = nutriAbierta.value?.nutricion
  if (!n) return []

  const filas = CAMPOS_NUTRI.filter(([clave]) => n[clave]).map(([clave, etiqueta]) => ({
    etiqueta,
    valor: n[clave],
  }))

  // Lo que la ficha traía y no estaba previsto, con su nombre original. Se
  // enseña en vez de tirarlo: una etiqueta desconocida sigue siendo un dato.
  for (const [etiqueta, valor] of Object.entries(n.otros ?? {})) {
    filas.push({ etiqueta, valor })
  }
  return filas
})
</script>

<style scoped>
.gondola { padding: 22px; }

.gondola-cabecera {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.gondola-cabecera h2 {
  margin: 0;
  font-size: 1.1875rem;
  font-weight: 750;
}

.gondola-n {
  font-size: 0.82rem;
  color: var(--texto-atenuado);
}

.gondola-n b { color: var(--tinta); }

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

.conmutador button[aria-pressed='true'] {
  background: var(--superficie);
  color: var(--tinta);
  box-shadow: var(--sombra);
}

.gondola-sub {
  margin: 0 0 18px;
  max-width: 96ch;
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--texto-atenuado);
}

.gondola-vacia {
  margin: 0;
  padding: 24px 0;
  text-align: center;
  font-size: 0.9375rem;
  color: var(--texto-sin-dato);
}

/* ---------------------------------------------------------------- *
 *  Tarjetas
 * ---------------------------------------------------------------- */

.rejilla {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: 14px;
}

.oferta {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  background: var(--superficie);
  transition: border-color 0.15s;
}

.oferta:hover { border-color: var(--borde-fuerte); }

.oferta-cabecera {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.oferta-nombre {
  font-size: 0.875rem;
  font-weight: 650;
  line-height: 1.35;
  color: var(--tinta);
  text-decoration: none;
  min-height: 2.7em;
}

.oferta-nombre:hover { color: var(--verde-texto); }

.oferta-tienda {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--texto-sin-dato);
}

.oferta-precio {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.precio-grande {
  font-size: 1.5rem;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: var(--tinta);
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
}

.precio-conv {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  font-size: 0.78rem;
  color: var(--texto-atenuado);
  font-variant-numeric: tabular-nums;
}

.chip-tasa {
  font-size: 0.62rem;
  padding: 1px 7px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 700;
}

.oferta-compara {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 0;
  padding: 8px 10px;
  border-radius: var(--r-xs);
  font-size: 0.75rem;
  line-height: 1.4;
  background: var(--superficie-sutil);
  border: 1px solid var(--borde-suave);
}

/* Rojo y verde, pero con flecha delante: la dirección se ve también en gris. */
.oferta-compara.caro   { color: var(--critico); }
.oferta-compara.barato { color: var(--verde-texto); }
.oferta-compara span   { color: var(--texto-atenuado); }
.oferta-compara b      { color: inherit; }

.oferta-datos {
  display: flex;
  gap: 18px;
  margin: 0;
  padding-top: 10px;
  border-top: 1px solid var(--borde-suave);
}

.oferta-datos dt {
  font-size: 0.62rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--texto-sin-dato);
  margin-bottom: 2px;
}

.oferta-datos dd {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--tinta);
  text-align: left;
}

.oferta-datos dd.sin-dato { font-weight: 400; color: var(--texto-sin-dato); }

.oferta-acciones {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
  align-items: center;
}

.oferta-analizar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin: 2px -14px -14px;
  padding: 9px;
  text-decoration: none;
  font-size: 0.78rem;
  font-weight: 650;
  background: var(--aviso-fondo);
  border-top: 1px solid var(--aviso-borde);
  color: var(--aviso-texto);
}

.oferta-analizar:hover { background: #F8EDD6; color: var(--aviso-texto); }

.punto {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--aviso);
  flex: none;
}

.oferta-sin-analisis {
  margin: 2px 0 0;
  font-size: 0.68rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #A8B2AD;
  text-align: center;
}

/* ---------------------------------------------------------------- *
 *  Tabla
 * ---------------------------------------------------------------- */

.col-producto { max-width: 260px; }

.col-producto a {
  font-weight: 600;
  color: var(--tinta);
  text-decoration: none;
}

.col-producto a:hover { color: var(--verde-texto); }

.chip-comparable {
  display: inline-block;
  margin-top: 4px;
  font-size: 0.62rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 700;
}

/* La fila con EAN repetido lleva un filo verde a la izquierda: se localiza sin
   leer el chip, que es lo que hace falta para comparar dos filas lejanas. */
.gondola-tabla tr.comparable td:first-child {
  box-shadow: inset 3px 0 0 var(--verde);
}

.precio { white-space: nowrap; }

.precio-origen {
  display: block;
  font-weight: 700;
  color: var(--tinta);
}

.precio-conv-tabla {
  display: block;
  font-size: 0.78rem;
  color: var(--texto-atenuado);
}

.btn-ficha {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 5px 10px;
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

/* El alérgeno es seguridad alimentaria: es el único botón de ficha que lleva
   color, y lo lleva por eso. */
.btn-ficha--alergeno {
  border-color: var(--critico-borde);
  background: var(--critico-fondo);
  color: var(--critico);
}

.btn-ficha--alergeno:hover {
  border-color: var(--critico);
  color: var(--critico);
}

.enlace-analisis {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.75rem;
  font-weight: 650;
  padding: 5px 10px;
  border-radius: var(--r-xs);
  border: 1px solid var(--aviso-borde-suave);
  background: var(--aviso-fondo);
  color: var(--aviso-texto);
  text-decoration: none;
  white-space: nowrap;
}

.enlace-analisis:hover { background: #F8EDD6; color: var(--aviso-texto); }

/* ---------------------------------------------------------------- *
 *  Fichas
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
  max-width: 560px;
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

.modal-sub { margin: 0; font-size: 0.78rem; color: var(--texto-sin-dato); }

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

.modal-cerrar:hover { background: var(--lienzo); color: var(--tinta); }

.modal-cuerpo {
  overflow-y: auto;
  padding: 18px 22px;
  display: grid;
  gap: 18px;
}

.modal-cuerpo h5 {
  margin: 0 0 8px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.composicion-texto {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--texto);
}

.matiz {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--texto-sin-dato);
}

.alergenos-texto {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-xs);
  font-size: 0.85rem;
  background: var(--critico-fondo);
  border: 1px solid var(--critico-borde);
  color: var(--critico);
}

.nutri-porcion {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-xs);
  font-size: 0.82rem;
  background: var(--verde-tinte);
  border: 1px solid var(--verde-borde);
  color: var(--verde-texto);
}

/* Dos columnas: etiqueta a la izquierda, valor alineado a la derecha, para
   poder comparar dos fichas abiertas en dos pestañas leyendo en paralelo. */
.nutri-tabla {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0;
  margin: 0;
}

.nutri-tabla dt,
.nutri-tabla dd {
  padding: 8px 0;
  border-bottom: 1px solid var(--borde-suave);
  margin: 0;
  font-size: 0.85rem;
}

.nutri-tabla dt { color: var(--texto-atenuado); }
.nutri-tabla dd { font-weight: 650; color: var(--tinta); }

.nutri-nota {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-xs);
  font-size: 0.8rem;
  line-height: 1.5;
  background: var(--aviso-fondo);
  border: 1px solid var(--aviso-borde);
  color: var(--aviso-texto);
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
 *  Pies
 * ---------------------------------------------------------------- */

.gondola-pie {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 16px 0 0;
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--texto-atenuado);
}

.gondola-pie strong { color: var(--tinta); }

.gondola-tasa {
  padding: 11px 13px;
  border-radius: var(--r-xs);
  background: var(--aviso-fondo);
  border: 1px solid var(--aviso-borde);
  color: var(--aviso-texto);
}

.gondola-tasa strong { color: var(--aviso-texto); }

@media (max-width: 760px) {
  .conmutador { margin-left: 0; }
  .modal-fondo { padding: 0; align-items: flex-end; }
  .modal { max-width: none; max-height: 92vh; border-radius: var(--r-lg) var(--r-lg) 0 0; }
}
</style>
