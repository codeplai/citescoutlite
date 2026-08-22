<!--
  T6 — La pantalla de análisis regulatorio.

  ## Copia la estructura de los PPTX a propósito

  `acido1.pptx` y `acido2.pptx` resolvieron ya el problema de presentación, y lo
  resolvieron bien: **tres tarjetas paralelas**, una por mercado, con las mismas
  cuatro casillas cada una (veredicto, mercado, límite, referencia). Puestas en
  paralelo, la comparación se hace sola; en una tabla de filas habría que ir y
  volver con la vista para comparar dos mercados.

  Lo que aquí se añade y las diapositivas no tenían: **de dónde salió cada celda
  y cuándo**. No es lo mismo una cita traída del eCFR hace un minuto que una
  celda curada a mano en agosto, y quien decide un envío tiene derecho a saber
  cuál está mirando.

  ## El asterisco es el contenido, no la decoración

  `SÍ*` y `NO*` significan «el aditivo sí, pero de tu categoría no tenemos
  confirmación». Es el estado más frecuente del sistema —la categoría casi
  siempre se deduce de un texto libre— y por eso se pinta distinto del `SÍ`
  rotundo en vez de disimularse. La nota al pie de cada tarjeta dice qué falta
  por confirmar.

  ## Y por eso esto tarda

  La columna de EE. UU. va por agente en vivo contra el eCFR: 15-36 s medidos.
  La espera se cuenta al usuario mientras ocurre, con lo que se está haciendo,
  porque un spinner mudo de 30 segundos se lee como una pantalla rota.

  ## Lo que cambia con el rediseño

  **El veredicto deja de depender del color.** Antes `SÍ`, `SÍ*`, `NO` y
  `SIN DATO` se distinguían por el verde, el ámbar, el rojo y el gris del
  recuadro. Esta pantalla se imprime y se adjunta a un expediente, y en gris de
  impresora los cuatro eran el mismo recuadro. Ahora cada uno lleva su icono
  —tick, información, aspa— y `SIN DATO` lleva además borde discontinuo: la
  forma llega antes que el color, y el color solo refuerza.

  **Un resumen antes del detalle.** Con tres aditivos son nueve celdas, y la
  pregunta que trae aquí a alguien —«¿puedo exportar esto?»— se responde con
  cuatro cifras. Estaban al final, dentro de las conclusiones.

  **Los aditivos se pliegan.** Tres bloques de tres tarjetas son tres pantallas
  de scroll. El primero viene abierto y los demás cerrados, con sus tres
  veredictos ya visibles en la cabecera plegada: para saber si hay que abrirlo
  no hace falta abrirlo.
-->
<template>
  <div class="analisis">
    <!-- Portada: lo mismo que la diapositiva 1 de los PPTX. -->
    <header class="portada">
      <p class="volver no-imprimir">
        <RouterLink :to="{ name: 'consulta' }">
          <Icono nombre="chevron-izq" :tamano="14" />Volver a la consulta
        </RouterLink>
      </p>
      <p class="eyebrow">Análisis de ingredientes · Panorama regulatorio</p>
      <h1>{{ analisis?.producto_nombre || 'Análisis de ingredientes' }}</h1>
      <p class="subtitulo">
        Autorización de los aditivos declarados en la etiqueta para mercados de
        exportación — <strong>Estados Unidos</strong>,
        <strong>Codex Alimentarius</strong> y <strong>Unión Europea</strong>.
      </p>
      <p v-if="analisis?.matriz" class="matriz">
        <span class="rotulo">Matriz alimentaria</span>
        {{ analisis.matriz }}
        <span v-if="analisis.matriz_ue" class="chip chip--codigo">
          categoría UE {{ analisis.matriz_ue }} · deducida
        </span>
        <span v-else class="sin-dato">categoría no mapeada</span>
      </p>
    </header>

    <!-- Cargando. La espera se explica porque puede llegar a 45 s. -->
    <div v-if="cargando" class="estado superficie" aria-live="polite" aria-busy="true">
      <span class="barra"><span class="barra-barrido"></span></span>
      <div>
        <strong>Consultando las tres fuentes…</strong>
        <p class="matiz">
          El eCFR de EE. UU. se consulta en vivo y tarda entre 15 y 40 segundos.
          El Anexo II de la UE y la tabla del Codex son locales e instantáneos.
        </p>
      </div>
    </div>

    <!--
      El estado de error dice **qué** ha pasado y **qué hacer**, no solo que
      algo falló.

      La primera versión ponía «No se pudo completar el análisis» de encabezado
      y debajo el detalle del backend, que para un 500 era… «No se pudo
      completar el análisis». La misma frase dos veces y ninguna pista: para
      diagnosticarlo había que entrar al servidor a leer el log.
    -->
    <div v-else-if="error" class="estado superficie estado--error" role="alert">
      <Icono nombre="info" :tamano="19" />
      <div>
        <strong>{{ error.titulo }}</strong>
        <p class="matiz">{{ error.explicacion }}</p>
        <p v-if="error.quehacer" class="matiz quehacer">{{ error.quehacer }}</p>
        <p v-if="error.tecnico" class="tecnico codigo">{{ error.tecnico }}</p>
        <button class="btn btn--secundario btn--pequeno" @click="cargar">Reintentar</button>
      </div>
    </div>

    <!--
      Sin aditivos NO es un error ni un hueco: es una etiqueta limpia, y para
      quien formula eso es información. Es el 49,8 % del snapshot.
    -->
    <div v-else-if="!analisis.aditivos.length" class="estado superficie estado--limpio">
      <Icono nombre="check" :tamano="19" />
      <div>
        <strong>Esta etiqueta no declara ningún aditivo reconocible.</strong>
        <p class="matiz">
          No hay nada que autorizar, así que no hay veredicto que dar. Se
          reconocen los aditivos por su nombre en el texto de la etiqueta; que
          no aparezca ninguno no descarta que el producto lleve otros con
          nombres que este sistema todavía no reconoce.
        </p>
      </div>
    </div>

    <template v-else>
      <!--
        El resumen, antes del detalle. Cuatro cifras que responden «¿puedo
        exportar esto?» sin leer las nueve celdas.
      -->
      <div class="resumen">
        <div class="resumen-tile">
          <span class="resumen-n num">{{ resumen.aditivos }}</span>
          <span class="resumen-que">aditivos</span>
          <span class="resumen-det">declarados en la etiqueta</span>
        </div>
        <div class="resumen-tile es-si">
          <span class="resumen-n num">{{ nAutorizadas }}</span>
          <span class="resumen-que">autorizados</span>
          <span class="resumen-det">con cifra o BPM</span>
        </div>
        <div class="resumen-tile es-cond">
          <span class="resumen-n num">{{ resumen.condicionadas || 0 }}</span>
          <span class="resumen-que">condicionados</span>
          <span class="resumen-det">categoría sin confirmar</span>
        </div>
        <div class="resumen-tile es-sin">
          <span class="resumen-n num">{{ resumen.sin_dato || 0 }}</span>
          <span class="resumen-que">sin dato</span>
          <span class="resumen-det">de {{ resumen.celdas }} celdas</span>
        </div>
      </div>

      <!-- Un bloque por aditivo, cada uno con sus tres tarjetas. -->
      <section
        v-for="(ad, i) in analisis.aditivos"
        :key="ad.nombre"
        class="aditivo superficie imprimible"
      >
        <!--
          La cabecera es el control de plegado, y lleva los tres veredictos ya
          resumidos: para decidir si hace falta abrirlo no hace falta abrirlo.
        -->
        <button
          class="cabecera-aditivo"
          type="button"
          :aria-expanded="abierto(i)"
          :aria-controls="`aditivo-${i}`"
          @click="alternar(i)"
        >
          <div class="cabecera-texto">
            <p class="eyebrow">
              <span v-if="ad.ins" class="codigo">INS {{ ad.ins }}</span>
              <span v-if="ad.e_number" class="codigo">· {{ ad.e_number }}</span>
              <span v-if="ad.funcion">· {{ ad.funcion }}</span>
            </p>
            <h2>{{ ad.nombre }}</h2>
          </div>

          <div class="mini-veredictos" aria-hidden="true">
            <span
              v-for="ev in ad.evaluaciones"
              :key="ev.mercado"
              class="mini"
              :class="clase(ev.autorizado)"
              :title="`${MERCADO[ev.mercado]}: ${VEREDICTO[ev.autorizado]}`"
            >{{ VEREDICTO[ev.autorizado] }}</span>
          </div>

          <span class="cabecera-accion no-imprimir">
            {{ abierto(i) ? 'Plegar' : 'Desplegar' }}
            <Icono :nombre="abierto(i) ? 'chevron-arriba' : 'chevron-abajo'" :tamano="15" />
          </span>
        </button>

        <div v-show="abierto(i)" :id="`aditivo-${i}`" class="aditivo-cuerpo">
          <div class="tarjetas">
            <article
              v-for="ev in ad.evaluaciones"
              :key="ev.mercado"
              class="tarjeta"
              :class="clase(ev.autorizado)"
            >
              <!--
                El veredicto, con forma antes que color. El icono y el borde
                discontinuo del SIN DATO son lo que sobrevive a una impresora
                en blanco y negro.
              -->
              <div class="veredicto" :class="`veredicto--${clase(ev.autorizado)}`">
                <Icono
                  v-if="ICONO_VEREDICTO[ev.autorizado]"
                  :nombre="ICONO_VEREDICTO[ev.autorizado]"
                  :tamano="14"
                />
                {{ VEREDICTO[ev.autorizado] }}
              </div>

              <h3 class="mercado">{{ MERCADO[ev.mercado] }}</h3>

              <div class="campo">
                <span class="rotulo">Límite máximo</span>
                <strong>{{ limite(ev) }}</strong>
              </div>

              <div class="campo">
                <span class="rotulo">Referencia normativa</span>
                <a :href="ev.referencia_url" target="_blank" rel="noopener">
                  {{ ev.referencia_texto }} <Icono nombre="externo" :tamano="12" />
                </a>
              </div>

              <div v-if="ev.categoria_alimento" class="campo">
                <span class="rotulo">Categoría aplicada</span>
                <span>{{ ev.categoria_alimento }}</span>
              </div>

              <!--
                La cita literal. Es lo que separa esto de una opinión: el
                fragmento de la norma del que sale el número, comprobado contra
                el documento antes de publicarse.

                Va en serif y con `lang="en"`: es texto normativo para leer, no
                interfaz, y está en inglés. Sin el `lang`, un lector de pantalla
                en español lo pronuncia como si fuera castellano.
              -->
              <blockquote v-if="ev.cita_literal" class="cita" lang="en">
                «{{ ev.cita_literal }}»
              </blockquote>

              <p v-if="ev.nota" class="nota">{{ ev.nota }}</p>

              <!-- T6.4: de dónde salió y cuándo. -->
              <p class="procedencia">
                {{ ORIGEN[ev.origen] || ev.origen }} · {{ fecha(ev.verificado_en) }}
              </p>
            </article>
          </div>

          <!-- Paso 6 de la metodología: el límite más estricto entre los que autorizan. -->
          <p v-if="ad.limite_interno !== null" class="limite-interno">
            <strong>Límite interno sugerido: {{ ad.limite_interno }} mg/kg.</strong>
            Es el más estricto de los mercados que autorizan el aditivo;
            adoptarlo permite una sola formulación para los tres destinos.
          </p>
          <p v-else class="limite-interno vacio">
            Ningún mercado con cifra numérica: no hay límite interno que adoptar.
          </p>
        </div>
      </section>

      <!-- Conclusiones: la diapositiva 3. -->
      <section class="superficie conclusiones imprimible">
        <h2>Conclusiones y recomendaciones</h2>
        <ol>
          <li v-if="autorizan.length">
            <strong>Autorizan el uso:</strong>
            {{ autorizan.map((m) => MERCADO[m]).join(', ') }}. Revisar el límite
            de cada uno en las tarjetas de arriba.
          </li>
          <li v-if="analisis.mercados_que_prohiben?.length" class="grave">
            <strong>
              Reformulación obligatoria para
              {{ analisis.mercados_que_prohiben.map((m) => MERCADO[m]).join(', ') }}.
            </strong>
            Alguno de los aditivos no está cubierto para este producto: hay que
            retirarlo o buscar alternativa antes de exportar a ese mercado.
          </li>
          <li v-if="resumen.condicionadas">
            <strong>
              {{ resumen.condicionadas }} de {{ resumen.celdas }} celdas van
              condicionadas (*).
            </strong>
            La autorización existe, pero la cobertura de la categoría exacta de
            este producto no está confirmada. Es el punto donde más
            discrepancias aparecen entre mercados.
          </li>
          <li v-if="resumen.sin_dato">
            <strong>{{ resumen.sin_dato }} celdas sin dato.</strong>
            No significa «no autorizado»: significa que no se ha podido
            comprobar. Hay que mirarlas a mano en la fuente oficial.
          </li>
          <li>
            <strong>Confirmar antes de cada envío.</strong> Verificar la
            clasificación exacta con la que se comercializará el producto y la
            normativa vigente del país de destino. Este análisis es una ayuda a
            la decisión, no un dictamen regulatorio.
          </li>
        </ol>
      </section>

      <!-- Honestidad del método (T7.1 adelantado: sin esto la pantalla miente por omisión). -->
      <footer class="superficie alcance imprimible">
        <h3>Hasta dónde llega esto</h3>
        <ul>
          <li>
            <strong>Estados Unidos:</strong> búsqueda en vivo en el eCFR
            (título 21). Cada cifra se comprueba contra el texto de la sección
            antes de publicarse; si no aparece literalmente, la celda sale sin
            dato.
          </li>
          <li>
            <strong>Unión Europea:</strong> Anexo II del Reglamento (CE)
            1333/2008 según lo fijó el Reglamento (UE) 1129/2011. Las
            modificaciones posteriores a 2011 no están incluidas.
          </li>
          <li>
            <strong>Codex:</strong> tabla curada a mano. El GSFA de la FAO no
            permite consulta automática, así que la cobertura crece a medida que
            se rellena; lo que falta sale como «sin dato», nunca como prohibido.
          </li>
          <li v-if="analisis.no_reconocidos?.length">
            <strong>
              {{ analisis.no_reconocidos.length }} ingredientes sin clasificar
            </strong>
            en esta etiqueta: {{ analisis.no_reconocidos.slice(0, 12).join(', ')
            }}<span v-if="analisis.no_reconocidos.length > 12">…</span>. No se
            han analizado; que no aparezcan arriba no significa que no estén
            regulados.
          </li>
        </ul>
      </footer>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { api, BASE } from '../api.js'
import Icono from '../components/Icono.vue'

/**
 * La misma pantalla sirve a las dos procedencias, y solo cambia de dónde saca
 * los datos: un producto del snapshot (`productoId`) o una oferta de góndola
 * (`ofertaUrl`). Todo lo que se pinta —las tres tarjetas, el asterisco, las
 * conclusiones— es idéntico, porque la pregunta regulatoria es la misma.
 */
const props = defineProps({
  ejecucionId: { type: String, required: true },
  productoId: { type: String, default: '' },
  ofertaUrl: { type: String, default: '' },
})

// El asterisco de los PPTX, tal cual. `SÍ*` no es un `SÍ` con adorno: es un
// tercer estado, y escribirlo igual que el `SÍ` sería perder el dato.
const VEREDICTO = {
  SI: 'SÍ',
  SI_CONDICIONADO: 'SÍ*',
  NO: 'NO',
  NO_CONDICIONADO: 'NO*',
  SIN_DATO: 'SIN DATO',
}

/**
 * El icono de cada veredicto.
 *
 * No es adorno: es la mitad del mensaje. Esta pantalla se imprime y se adjunta
 * a un expediente, y en gris de impresora el verde del SÍ y el ámbar del SÍ*
 * son el mismo gris. Con el tick y el signo de información, no.
 *
 * `SIN_DATO` no lleva icono a propósito: cualquiera que se le ponga —un
 * interrogante, un guion— añade una lectura que no está. Lo distingue el borde
 * discontinuo, que dice «esto está por rellenar» sin afirmar nada.
 */
const ICONO_VEREDICTO = {
  SI: 'check',
  SI_CONDICIONADO: 'info',
  NO: 'equis',
  NO_CONDICIONADO: 'info',
  SIN_DATO: '',
}

const MERCADO = {
  US: 'Estados Unidos',
  CODEX: 'Codex Alimentarius',
  EU: 'Unión Europea',
}

const ORIGEN = {
  AGENTE_ECFR: 'eCFR, consultado en vivo',
  ANEXO_II: 'Anexo II (UE), corpus local',
  CURADO_CODEX: 'GSFA, curado a mano',
  CACHE: 'de caché',
}

const analisis = ref(null)
const cargando = ref(true)
/** `null` o `{titulo, explicacion, quehacer, tecnico}`. */
const error = ref(null)

/**
 * Qué aditivos están desplegados.
 *
 * El primero viene abierto y el resto cerrados: con uno abierto se ve de qué va
 * la pantalla sin tener que pulsar nada, y con todos abiertos vuelven las tres
 * pantallas de scroll que este plegado existe para evitar.
 *
 * Es un Set de índices y no un `abierto` por aditivo porque el nombre no es
 * identificador estable: dos aditivos pueden compartirlo si el reconocedor
 * duplica una entrada.
 */
const desplegados = ref(new Set([0]))
const abierto = (i) => desplegados.value.has(i)

const alternar = (i) => {
  const s = new Set(desplegados.value)
  if (s.has(i)) s.delete(i)
  else s.add(i)
  desplegados.value = s
}

/**
 * De un fallo a algo que se pueda leer y accionar.
 *
 * Cada caso tiene una causa distinta y una salida distinta, y meterlos todos
 * bajo «no se pudo» obliga a quien lo sufre a adivinar. El caso que más veces
 * va a pasar en desarrollo es el 404 del router: la SPA nueva pidiendo a un
 * backend que todavía no tiene montado el endpoint.
 */
function describir(e) {
  const status = e?.status
  const detalle = e?.detalle || e?.message || String(e)

  if (status === undefined) {
    return {
      titulo: 'No se pudo contactar con el servidor',
      explicacion: 'La petición no llegó a salir o no hubo respuesta.',
      quehacer:
        `Comprueba que el backend está levantado y que responde en ${BASE}. ` +
        'Si la SPA y la API están en máquinas distintas, revisa VITE_API_URL.',
      tecnico: detalle,
    }
  }
  if (status === 404 && /not found/i.test(detalle)) {
    // FastAPI responde así cuando la RUTA no existe; el 404 nuestro trae otro
    // texto. Distinguirlos importa: uno es un backend viejo y el otro un id malo.
    return {
      titulo: 'El servidor no conoce este endpoint',
      explicacion: 'La ruta /api/analisis-aditivos no está montada en la API que responde.',
      quehacer:
        'Reinicia el backend: es la versión anterior, de antes de que ' +
        'existiera esta pantalla.',
      tecnico: detalle,
    }
  }
  if (status === 404) {
    return {
      titulo: props.ofertaUrl
        ? 'Esa oferta no está en este informe'
        : 'Ese producto no está en este informe',
      explicacion:
        'El informe no existe, no es tuyo, o la fila no forma parte ' +
        'de su mapa comercial.',
      quehacer: 'Vuelve a la consulta y abre el análisis desde la fila.',
      tecnico: detalle,
    }
  }
  if (status === 401 || status === 403) {
    return {
      titulo: 'Sesión no válida',
      explicacion: 'El servidor rechazó la petición por falta de permisos.',
      quehacer: 'Vuelve a entrar.',
      tecnico: detalle,
    }
  }
  return {
    titulo: 'El análisis falló en el servidor',
    explicacion: detalle,
    quehacer:
      'El detalle completo está en el log del backend. Si se repite ' +
      'con todos los productos, probablemente falte algún corpus: ' +
      '`python -m etl.ingerir_ecfr` y `python -m etl.ingerir_anexo_ii`.',
    tecnico: `HTTP ${status}`,
  }
}

const resumen = computed(() => analisis.value?.resumen ?? {})

/**
 * Celdas autorizadas.
 *
 * Se cuentan aquí y no se derivan de `celdas - sin_dato - prohibiciones`: esa
 * resta da el número correcto hoy, pero se rompería en silencio el día que
 * aparezca un sexto veredicto. Contar lo que se quiere contar no se rompe.
 */
const nAutorizadas = computed(() => {
  let n = 0
  for (const ad of analisis.value?.aditivos ?? []) {
    for (const ev of ad.evaluaciones) {
      if (ev.autorizado === 'SI' || ev.autorizado === 'SI_CONDICIONADO') n += 1
    }
  }
  return n
})

const autorizan = computed(() => {
  const mercados = new Set()
  for (const ad of analisis.value?.aditivos ?? []) {
    for (const ev of ad.evaluaciones) {
      if (ev.autorizado === 'SI' || ev.autorizado === 'SI_CONDICIONADO') {
        mercados.add(ev.mercado)
      }
    }
  }
  return [...mercados]
})

const clase = (veredicto) =>
  ({
    SI: 'si',
    SI_CONDICIONADO: 'si-cond',
    NO: 'no',
    NO_CONDICIONADO: 'no-cond',
    SIN_DATO: 'sin',
  })[veredicto]

/**
 * El límite, distinguiendo los tres casos que NO son lo mismo.
 *
 * `BPM` es un límite real —buenas prácticas, sin cifra—, «no aplica» es que la
 * pregunta no procede, y la ausencia de dato es que no lo sabemos. Escribir los
 * tres como un guion perdería justo la diferencia que importa.
 */
const limite = (ev) => {
  if (ev.limite_unidad === 'BPM') return 'BPM (sin límite numérico)'
  if (ev.limite_unidad === 'N/A') return 'No aplica'
  if (ev.limite_valor === null || ev.limite_valor === undefined) return 'Sin cifra'
  return `${ev.limite_valor} ${ev.limite_unidad || 'mg/kg'}`
}

const fecha = (iso) => {
  if (!iso) return 'sin fecha'
  return new Date(iso).toLocaleDateString('es', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

const cargar = async () => {
  cargando.value = true
  error.value = null
  try {
    analisis.value = props.ofertaUrl
      ? await api.analisisOferta(props.ejecucionId, props.ofertaUrl)
      : await api.analisisAditivos(props.ejecucionId, props.productoId)
    // Cada carga vuelve a dejar solo el primero abierto: si no, cambiar de
    // producto conserva el plegado del anterior y se ve un bloque desplegado
    // que nadie ha abierto.
    desplegados.value = new Set([0])
  } catch (e) {
    // Al log del navegador va el error entero: la pantalla enseña lo legible,
    // pero quien tenga la consola abierta merece la traza completa.
    console.error('Análisis de aditivos:', e)
    error.value = describir(e)
  } finally {
    cargando.value = false
  }
}

onMounted(cargar)
</script>

<style scoped>
.analisis {
  max-width: 1100px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------------------------------------------------------------- *
 *  Portada
 * ---------------------------------------------------------------- */

.portada { padding-bottom: 4px; }

.volver { margin: 0 0 14px; font-size: 0.85rem; }

.volver a {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  text-decoration: none;
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 0.69rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--verde-texto);
}

.portada h1 {
  margin: 0 0 10px;
  font-size: 1.875rem;
  line-height: 1.15;
}

.subtitulo {
  margin: 0;
  max-width: 76ch;
  font-size: 0.9375rem;
  color: var(--texto-atenuado);
}

.matriz {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-wrap: wrap;
  margin: 14px 0 0;
  font-size: 0.875rem;
  color: var(--texto);
}

/* ---------------------------------------------------------------- *
 *  Estados
 * ---------------------------------------------------------------- */

.estado {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 22px;
}

.estado strong { display: block; color: var(--tinta); font-size: 0.9375rem; }

.matiz {
  margin: 6px 0 0;
  max-width: 76ch;
  font-size: 0.85rem;
  line-height: 1.6;
  color: var(--texto-atenuado);
}

.quehacer { color: var(--texto); }

.tecnico {
  margin: 8px 0 12px;
  font-size: 0.75rem;
  color: var(--texto-sin-dato);
  word-break: break-word;
}

.estado--error {
  border-color: var(--critico-borde);
  background: var(--critico-fondo);
  color: var(--critico);
}

.estado--error strong { color: var(--critico); }

.estado--limpio {
  border-color: var(--verde-borde);
  background: #F7FBF9;
  color: var(--verde-texto);
}

.barra {
  flex: none;
  display: block;
  width: 90px;
  height: 4px;
  margin-top: 8px;
  border-radius: 999px;
  background: #EEF1EF;
  overflow: hidden;
}

.barra-barrido {
  display: block;
  width: 33%;
  height: 100%;
  border-radius: 999px;
  background: var(--verde);
  animation: ags-barrido 1.4s ease-in-out infinite;
}

/* ---------------------------------------------------------------- *
 *  Resumen
 * ---------------------------------------------------------------- */

.resumen {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 10px;
}

.resumen-tile {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 14px 16px;
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  background: var(--superficie-sutil);
}

.resumen-n {
  font-size: 1.625rem;
  font-weight: 750;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--tinta);
}

.resumen-que {
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--texto);
}

.resumen-det {
  font-size: 0.72rem;
  color: var(--texto-sin-dato);
}

.resumen-tile.es-si   { background: var(--verde-tinte);  border-color: var(--verde-borde); }
.resumen-tile.es-cond { background: var(--aviso-fondo);  border-color: var(--aviso-borde); }
.resumen-tile.es-sin  { background: var(--lienzo);       border-color: var(--borde-medio); }

.es-si   .resumen-n { color: var(--exito); }
.es-cond .resumen-n { color: var(--aviso); }
.es-sin  .resumen-n { color: #6F7B76; }

/* ---------------------------------------------------------------- *
 *  Aditivo
 * ---------------------------------------------------------------- */

.aditivo { overflow: hidden; }

.cabecera-aditivo {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  padding: 18px 22px;
  font-family: inherit;
  text-align: left;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.cabecera-aditivo:hover { background: var(--superficie-sutil); }

.cabecera-texto { flex: 1; min-width: 0; }

.cabecera-texto .eyebrow {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
  color: var(--texto-sin-dato);
  letter-spacing: 0.06em;
}

.cabecera-texto h2 {
  margin: 2px 0 0;
  font-size: 1.1875rem;
  font-weight: 750;
}

/* Los tres veredictos del bloque plegado. Van en el mismo orden que las
   tarjetas de dentro —EE. UU., Codex, UE— para que abrirlo no obligue a volver
   a situarse. */
.mini-veredictos {
  display: flex;
  gap: 4px;
  flex: none;
}

.mini {
  min-width: 46px;
  text-align: center;
  font-size: 0.7rem;
  font-weight: 750;
  padding: 3px 8px;
  border-radius: var(--r-xs);
  border: 1px solid var(--borde-medio);
  background: var(--lienzo);
  color: #6F7B76;
}

.mini.si       { background: var(--verde-tinte);   border-color: var(--verde-borde-fuerte); color: var(--exito); }
.mini.si-cond,
.mini.no-cond  { background: var(--aviso-fondo);   border-color: var(--aviso-borde);        color: var(--aviso); }
.mini.no       { background: var(--critico-fondo); border-color: var(--critico-borde);      color: var(--critico); }
.mini.sin      { border-style: dashed; }

.cabecera-accion {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--texto-atenuado);
}

.aditivo-cuerpo {
  padding: 0 22px 20px;
  border-top: 1px solid var(--borde-suave);
}

/*
  Tres columnas iguales, siempre. Es lo que hace que la comparación se lea en
  horizontal sin mover la vista, y por eso no se colapsa a dos: dos y una es
  peor que tres estrechas hasta que ya no caben, y ahí se apilan del todo.
*/
.tarjetas {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  padding-top: 20px;
}

.tarjeta {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  background: var(--superficie);
}

/* El tinte del fondo es refuerzo, muy suave a propósito: el que informa es el
   recuadro del veredicto de arriba. */
.tarjeta.si       { border-color: var(--verde-borde); }
.tarjeta.si-cond,
.tarjeta.no-cond  { border-color: var(--aviso-borde); }
.tarjeta.no       { border-color: var(--critico-borde); }
.tarjeta.sin      { border-style: dashed; border-color: var(--borde-fuerte); }

.veredicto {
  align-self: flex-start;
}

.veredicto--si {
  background: var(--verde-tinte);
  border-color: var(--verde-borde-fuerte);
  color: var(--exito);
}

.veredicto--si-cond,
.veredicto--no-cond {
  background: var(--aviso-fondo);
  border-color: var(--aviso-borde);
  color: var(--aviso);
}

.veredicto--no {
  background: var(--critico-fondo);
  border-color: var(--critico-borde);
  color: var(--critico);
}

.veredicto--sin { border-style: dashed; color: #6F7B76; }

.mercado {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
}

.campo {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 0.82rem;
}

.campo strong { color: var(--tinta); font-weight: 650; }

.campo a {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  font-weight: 600;
}

.cita {
  margin: 0;
  padding: 10px 0 10px 14px;
  border-left: 3px solid var(--verde-borde);
  font-family: var(--fuente-lectura);
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--texto);
}

.nota {
  margin: 0;
  padding: 10px 12px;
  border-radius: var(--r-xs);
  font-size: 0.8rem;
  line-height: 1.5;
  background: var(--superficie-sutil);
  border: 1px solid var(--borde-suave);
  color: var(--texto-atenuado);
}

.procedencia {
  margin: auto 0 0;
  padding-top: 10px;
  border-top: 1px solid var(--borde-suave);
  font-size: 0.72rem;
  color: var(--texto-sin-dato);
}

.limite-interno {
  margin: 16px 0 0;
  padding: 13px 15px;
  border-radius: var(--r-md);
  font-size: 0.85rem;
  line-height: 1.55;
  background: var(--verde-tinte);
  border: 1px solid var(--verde-borde);
  color: var(--texto);
}

.limite-interno strong { color: var(--verde-texto); }

.limite-interno.vacio {
  background: var(--superficie-sutil);
  border-color: var(--borde);
  color: var(--texto-sin-dato);
}

/* ---------------------------------------------------------------- *
 *  Conclusiones y alcance
 * ---------------------------------------------------------------- */

.conclusiones,
.alcance {
  padding: 22px;
}

.conclusiones h2 {
  margin: 0 0 14px;
  font-size: 1.1875rem;
  font-weight: 750;
}

.conclusiones ol {
  margin: 0;
  padding-left: 20px;
  display: grid;
  gap: 12px;
  font-size: 0.9375rem;
  line-height: 1.6;
  color: var(--texto-atenuado);
  max-width: 88ch;
}

.conclusiones strong { color: var(--tinta); }

/* La única conclusión con color: la que obliga a reformular antes de exportar
   es la que puede parar un envío. */
.conclusiones .grave strong { color: var(--critico); }

.alcance {
  background: var(--superficie-sutil);
}

.alcance h3 {
  margin: 0 0 12px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.alcance ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 9px;
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--texto-atenuado);
  max-width: 92ch;
}

.alcance strong { color: var(--texto); }

/* ---------------------------------------------------------------- *
 *  Impresión y pantallas estrechas
 * ---------------------------------------------------------------- */

@media print {
  /* Plegado o no, en papel se imprime todo: un expediente con un aditivo
     ausente porque estaba cerrado en pantalla sería un expediente incompleto.
     El `!important` es lo que gana al `display: none` en línea que pone
     `v-show`. */
  .aditivo-cuerpo { display: block !important; }
  .aditivo { break-inside: avoid; }
}

@media (max-width: 900px) {
  .tarjetas { grid-template-columns: 1fr; }

  .cabecera-aditivo { flex-wrap: wrap; }
  .cabecera-texto { flex-basis: 100%; }
  .mini-veredictos { margin-right: auto; }
}
</style>
