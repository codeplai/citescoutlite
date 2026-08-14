<!--
  T6 — La pestaña de análisis regulatorio.

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
-->
<template>
  <div class="analisis">
    <!-- Portada: lo mismo que la diapositiva 1 de los PPTX. -->
    <header class="portada glass-panel">
      <p class="volver">
        <RouterLink :to="{ name: 'consulta' }">‹ Volver a la consulta</RouterLink>
      </p>
      <p class="eyebrow">Análisis de ingredientes · Panorama regulatorio</p>
      <h1>{{ analisis?.producto_nombre || 'Análisis de ingredientes' }}</h1>
      <p class="subtitulo">
        Autorización de los aditivos declarados en la etiqueta para mercados de
        exportación — <strong>Estados Unidos</strong>,
        <strong>Codex Alimentarius</strong> y <strong>Unión Europea</strong>.
      </p>
      <p v-if="analisis?.matriz" class="matriz">
        <span class="etiqueta">Matriz alimentaria</span>
        {{ analisis.matriz }}
        <span v-if="analisis.matriz_ue" class="codigo">
          → categoría UE {{ analisis.matriz_ue }} (deducida)
        </span>
        <span v-else class="sin-dato">categoría no mapeada</span>
      </p>
    </header>

    <!-- Cargando. La espera se explica porque puede llegar a 45 s. -->
    <div v-if="cargando" class="glass-panel estado">
      <div class="hilandero" />
      <p><strong>Consultando las tres fuentes…</strong></p>
      <p class="matiz">
        El eCFR de EE. UU. se consulta en vivo y tarda entre 15 y 40 segundos.
        El Anexo II de la UE y la tabla del Codex son locales e instantáneos.
      </p>
    </div>

    <!--
      El estado de error dice **qué** ha pasado y **qué hacer**, no solo que
      algo falló.

      La primera versión ponía «No se pudo completar el análisis» de encabezado
      y debajo el detalle del backend, que para un 500 era… «No se pudo
      completar el análisis». La misma frase dos veces y ninguna pista: para
      diagnosticarlo había que entrar al servidor a leer el log.
    -->
    <div v-else-if="error" class="glass-panel estado error">
      <p><strong>{{ error.titulo }}</strong></p>
      <p class="matiz">{{ error.explicacion }}</p>
      <p v-if="error.quehacer" class="matiz quehacer">{{ error.quehacer }}</p>
      <p v-if="error.tecnico" class="tecnico">{{ error.tecnico }}</p>
      <button class="btn-primary" @click="cargar">Reintentar</button>
    </div>

    <!--
      Sin aditivos NO es un error ni un hueco: es una etiqueta limpia, y para
      quien formula eso es información. Es el 49,8 % del snapshot.
    -->
    <div v-else-if="!analisis.aditivos.length" class="glass-panel estado">
      <p><strong>Esta etiqueta no declara ningún aditivo reconocible.</strong></p>
      <p class="matiz">
        No hay nada que autorizar, así que no hay veredicto que dar. Se reconocen
        los aditivos por su nombre en el texto de la etiqueta; que no aparezca
        ninguno no descarta que el producto lleve otros con nombres que este
        sistema todavía no reconoce.
      </p>
    </div>

    <template v-else>
      <!-- Un bloque por aditivo, cada uno con sus tres tarjetas. -->
      <section v-for="ad in analisis.aditivos" :key="ad.nombre" class="aditivo glass-panel">
        <div class="cabecera-aditivo">
          <p class="eyebrow">
            <span v-if="ad.ins">INS {{ ad.ins }}</span>
            <span v-if="ad.e_number">· {{ ad.e_number }}</span>
            <span v-if="ad.funcion">· {{ ad.funcion }}</span>
          </p>
          <h2>{{ ad.nombre }}</h2>
        </div>

        <div class="tarjetas">
          <article
            v-for="ev in ad.evaluaciones"
            :key="ev.mercado"
            class="tarjeta"
            :class="clase(ev.autorizado)"
          >
            <div class="veredicto">{{ VEREDICTO[ev.autorizado] }}</div>
            <h3 class="mercado">{{ MERCADO[ev.mercado] }}</h3>

            <div class="campo">
              <span class="etiqueta">Límite máximo</span>
              <strong>{{ limite(ev) }}</strong>
            </div>

            <div class="campo">
              <span class="etiqueta">Referencia normativa</span>
              <a :href="ev.referencia_url" target="_blank" rel="noopener">
                {{ ev.referencia_texto }} ↗
              </a>
            </div>

            <div v-if="ev.categoria_alimento" class="campo">
              <span class="etiqueta">Categoría aplicada</span>
              <span>{{ ev.categoria_alimento }}</span>
            </div>

            <!--
              La cita literal. Es lo que separa esto de una opinión: el
              fragmento de la norma del que sale el número, comprobado contra
              el documento antes de publicarse.
            -->
            <blockquote v-if="ev.cita_literal" class="cita">
              «{{ ev.cita_literal }}»
            </blockquote>

            <p v-if="ev.nota" class="nota">{{ ev.nota }}</p>

            <!-- T6.4: de dónde salió y cuándo. -->
            <p class="procedencia">
              {{ ORIGEN[ev.origen] || ev.origen }} ·
              {{ fecha(ev.verificado_en) }}
            </p>
          </article>
        </div>

        <!-- Paso 6 de la metodología: el límite más estricto entre los que autorizan. -->
        <p v-if="ad.limite_interno !== null" class="limite-interno">
          <strong>Límite interno sugerido: {{ ad.limite_interno }} mg/kg.</strong>
          Es el más estricto de los mercados que autorizan el aditivo; adoptarlo
          permite una sola formulación para los tres destinos.
        </p>
        <p v-else class="limite-interno vacio">
          Ningún mercado con cifra numérica: no hay límite interno que adoptar.
        </p>
      </section>

      <!-- Conclusiones: la diapositiva 3. -->
      <section class="glass-panel conclusiones">
        <h2>Conclusiones y recomendaciones</h2>
        <ol>
          <li v-if="autorizan.length">
            <strong>Autorizan el uso:</strong>
            {{ autorizan.map(m => MERCADO[m]).join(', ') }}. Revisar el límite de
            cada uno en las tarjetas de arriba.
          </li>
          <li v-if="analisis.mercados_que_prohiben?.length" class="grave">
            <strong>Reformulación obligatoria para
            {{ analisis.mercados_que_prohiben.map(m => MERCADO[m]).join(', ') }}.</strong>
            Alguno de los aditivos no está cubierto para este producto: hay que
            retirarlo o buscar alternativa antes de exportar a ese mercado.
          </li>
          <li v-if="resumen.condicionadas">
            <strong>{{ resumen.condicionadas }} de {{ resumen.celdas }} celdas van
            condicionadas (*).</strong>
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
      <footer class="glass-panel alcance">
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
            <strong>{{ analisis.no_reconocidos.length }} ingredientes sin
            clasificar</strong> en esta etiqueta: {{ analisis.no_reconocidos.slice(0, 12).join(', ') }}<span
              v-if="analisis.no_reconocidos.length > 12">…</span>. No se han
            analizado; que no aparezcan arriba no significa que no estén
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
      quehacer: `Comprueba que el backend está levantado y que responde en ${BASE}. `
        + 'Si la SPA y la API están en máquinas distintas, revisa VITE_API_URL.',
      tecnico: detalle,
    }
  }
  if (status === 404 && /not found/i.test(detalle)) {
    // FastAPI responde así cuando la RUTA no existe; el 404 nuestro trae otro
    // texto. Distinguirlos importa: uno es un backend viejo y el otro un id malo.
    return {
      titulo: 'El servidor no conoce este endpoint',
      explicacion: 'La ruta /api/analisis-aditivos no está montada en la API que responde.',
      quehacer: 'Reinicia el backend: es la versión anterior, de antes de que '
        + 'existiera esta pantalla.',
      tecnico: detalle,
    }
  }
  if (status === 404) {
    return {
      titulo: props.ofertaUrl
        ? 'Esa oferta no está en este informe'
        : 'Ese producto no está en este informe',
      explicacion: 'El informe no existe, no es tuyo, o la fila no forma parte '
        + 'de su mapa comercial.',
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
    quehacer: 'El detalle completo está en el log del backend. Si se repite '
      + 'con todos los productos, probablemente falte algún corpus: '
      + '`python -m etl.ingerir_ecfr` y `python -m etl.ingerir_anexo_ii`.',
    tecnico: `HTTP ${status}`,
  }
}

const resumen = computed(() => analisis.value?.resumen ?? {})

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

const clase = (veredicto) => ({
  SI: 'si',
  SI_CONDICIONADO: 'si-cond',
  NO: 'no',
  NO_CONDICIONADO: 'no-cond',
  SIN_DATO: 'sin',
}[veredicto])

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
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

const cargar = async () => {
  cargando.value = true
  error.value = null
  try {
    analisis.value = props.ofertaUrl
      ? await api.analisisOferta(props.ejecucionId, props.ofertaUrl)
      : await api.analisisAditivos(props.ejecucionId, props.productoId)
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
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 20px 60px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.portada { padding: 24px 28px; }
.volver { margin: 0 0 12px; font-size: 0.85rem; }
.volver a { color: var(--text-muted); text-decoration: none; }
.volver a:hover { color: var(--primary-color); }

.eyebrow {
  margin: 0;
  font-size: 0.74rem;
  letter-spacing: 0.09em;
  text-transform: uppercase;
  color: var(--primary-color);
  font-weight: 600;
}

.portada h1 { margin: 6px 0 10px; font-size: 1.7rem; color: var(--text-main); }
.subtitulo { margin: 0 0 14px; color: var(--text-muted); line-height: 1.6; }

.matriz {
  margin: 0;
  padding-top: 12px;
  border-top: 1px solid var(--card-border);
  font-size: 0.9rem;
}
.matriz .codigo { color: var(--primary-color); font-weight: 600; }

.etiqueta {
  display: block;
  font-size: 0.68rem;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 3px;
}

.estado { padding: 40px 28px; text-align: center; }
.estado.error { border-color: rgba(220, 53, 69, 0.4); }
.matiz { color: var(--text-muted); font-size: 0.88rem; line-height: 1.6; margin: 8px auto 0; max-width: 620px; }
.quehacer { color: var(--text-main); font-weight: 500; }
.tecnico {
  margin: 12px auto 16px;
  max-width: 620px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.05);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.76rem;
  color: var(--text-muted);
  word-break: break-word;
}

.hilandero {
  width: 28px; height: 28px; margin: 0 auto 14px;
  border: 3px solid var(--card-border);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: girar 0.9s linear infinite;
}
@keyframes girar { to { transform: rotate(360deg); } }

.aditivo { padding: 22px 24px; }
.cabecera-aditivo { margin-bottom: 16px; }
.cabecera-aditivo h2 { margin: 4px 0 0; font-size: 1.25rem; color: var(--text-main); }

/*
  Tres columnas iguales. La comparación entre mercados es la pregunta de esta
  pantalla, y en paralelo se hace de un vistazo; apiladas obligarían a
  desplazarse para comparar dos, que es justo lo que se viene a hacer.
*/
.tarjetas {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
@media (max-width: 900px) {
  .tarjetas { grid-template-columns: 1fr; }
}

.tarjeta {
  border: 1px solid var(--card-border);
  border-top-width: 4px;
  border-radius: 12px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.6);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* El color dice el veredicto antes de leerlo; el texto lo confirma. Nunca solo
   el color: quien no distinga verde de rojo tiene que poder leer 'SÍ' y 'NO'. */
.tarjeta.si       { border-top-color: var(--success); }
.tarjeta.si-cond  { border-top-color: #E0A800; }
.tarjeta.no       { border-top-color: #DC3545; }
.tarjeta.no-cond  { border-top-color: #E0A800; }
.tarjeta.sin      { border-top-color: var(--text-muted); }

.veredicto { font-size: 1.5rem; font-weight: 700; line-height: 1; }
.tarjeta.si .veredicto      { color: var(--success); }
.tarjeta.si-cond .veredicto { color: #B98700; }
.tarjeta.no .veredicto      { color: #DC3545; }
.tarjeta.no-cond .veredicto { color: #B98700; }
.tarjeta.sin .veredicto     { color: var(--text-muted); font-size: 1.05rem; }

.mercado {
  margin: 0;
  font-size: 0.8rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-main);
}

.campo { font-size: 0.87rem; }
.campo a { color: var(--primary-color); word-break: break-word; }

.cita {
  margin: 0;
  padding: 8px 10px;
  border-left: 3px solid var(--card-border);
  background: rgba(0, 0, 0, 0.03);
  font-size: 0.8rem;
  line-height: 1.5;
  color: var(--text-muted);
  font-style: italic;
}

.nota { margin: 0; font-size: 0.8rem; line-height: 1.5; color: var(--text-muted); }

.procedencia {
  margin: auto 0 0;
  padding-top: 8px;
  border-top: 1px dashed var(--card-border);
  font-size: 0.72rem;
  color: var(--text-muted);
}

.limite-interno {
  margin: 16px 0 0;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(45, 151, 102, 0.08);
  font-size: 0.88rem;
  line-height: 1.6;
}
.limite-interno.vacio { background: rgba(0, 0, 0, 0.03); color: var(--text-muted); }

.conclusiones, .alcance { padding: 22px 24px; }
.conclusiones h2 { margin: 0 0 12px; font-size: 1.15rem; }
.conclusiones ol { margin: 0; padding-left: 22px; }
.conclusiones li { margin-bottom: 10px; line-height: 1.65; font-size: 0.92rem; }
.conclusiones li.grave strong { color: #DC3545; }

.alcance h3 { margin: 0 0 10px; font-size: 0.95rem; }
.alcance ul { margin: 0; padding-left: 20px; }
.alcance li {
  margin-bottom: 8px;
  font-size: 0.82rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.sin-dato { color: var(--text-muted); font-style: italic; }
</style>
