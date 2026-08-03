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

      <p class="mapa-hueco">
        <strong>Presentación, precio y canal salen vacíos en todas las filas.</strong>
        No es un fallo de este informe: esos tres campos no existen en el snapshot
        de datos abiertos. Rellenarlos es el trabajo del nivel 3 de descubrimiento
        comercial, que no está disponible en esta versión.
      </p>

      <p v-if="nivelesFaltan" class="mapa-niveles">
        Fuentes no consultadas: {{ nivelesFaltan }}
      </p>
    </div>

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
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { api, NoAutorizado } from '../api.js'

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

const nivelesFaltan = computed(() =>
  (mapa.value?.niveles_no_disponibles ?? [])
    .map(n => `nivel ${n} (${NIVELES[n] ?? 'desconocido'})`)
    .join(', ')
)

const sanitizedHtml = computed(() => {
  if (!props.result.markdown_content) return '<p>No hay contenido disponible.</p>'
  const rawHtml = marked(props.result.markdown_content)
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
