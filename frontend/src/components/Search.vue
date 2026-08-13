<template>
  <div class="search-container animate-fade-in">
    <div class="glass-panel search-card" v-show="!isLoading">
      <h2>Consulta de Insumos</h2>
      <p class="description">Analiza el potencial de cualquier materia prima agrícola</p>

      <fieldset class="fuentes">
        <legend>
          ¿Dónde buscamos?
          <!-- Marcado mientras la selección no filtre de verdad. Sin esto, en
               una demostración se entiende que ya decide, y quien la vea
               sacaría conclusiones de un filtro que no se aplicó. -->
          <span class="previa" title="La selección todavía no filtra la búsqueda">
            vista previa
          </span>
        </legend>

        <div class="rejilla">
          <!-- Checkbox real dentro de la etiqueta: se navega con el tabulador y
               un lector de pantalla lo anuncia como lo que es. La tarjeta es
               solo la piel. -->
          <label
            v-for="f in FUENTES"
            :key="f.clave"
            class="fuente"
            :class="{ activa: seleccionadas.includes(f.clave) }"
          >
            <input
              type="checkbox"
              :value="f.clave"
              :checked="seleccionadas.includes(f.clave)"
              :disabled="isLoading"
              @change="alternar(f.clave)"
            />
            <span class="marca" aria-hidden="true"></span>
            <span class="cuerpo">
              <span class="nombre">{{ f.nombre }}</span>
              <span class="detalle">{{ f.detalle }}</span>
              <span class="coste" :class="f.tono">{{ f.coste }}</span>
            </span>
          </label>
        </div>
      </fieldset>

      <form @submit.prevent="submitSearch" class="search-form">
        <div class="input-wrapper">
          <input
            type="text"
            v-model="query"
            placeholder="Ej: Cáscara de cacao, mucílago de café..."
            required
            :disabled="isLoading"
          />
          <button type="submit" class="btn-primary" :disabled="isLoading">
            Analizar
          </button>
        </div>
      </form>
    </div>

    <!-- Gran Loading Overlay -->
    <div class="loading-overlay animate-fade-in" v-if="isLoading">
      <div class="glass-panel loading-card">
        <div class="spinner-large"></div>
        <h3>{{ loadingText }}</h3>
        <div class="progress-bar-container">
          <div class="progress-bar" :style="{ width: progress + '%' }"></div>
        </div>
        <p class="progress-text">{{ Math.round(progress) }}%</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api, NoAutorizado } from '../api.js'

/**
 * Dónde se busca. Tres fuentes con papeles distintos, no tres versiones de lo
 * mismo:
 *
 *   snapshot  → el catálogo global (OpenFoodFacts). Dice QUÉ productos existen
 *               y con qué composición. Instantáneo y sin coste.
 *   peru      → el mercado de origen. API público de VTEX: Wong, Metro, Plaza
 *               Vea y Makro. De aquí salen precio vigente, stock y EAN.
 *   alemania  → el mercado de destino. Dice a qué precio se vende allí, que es
 *               la pregunta de un exportador y no la responde ni el catálogo
 *               global ni la góndola peruana.
 *
 * Perú y Alemania juntos son el mapa que interesa: lo que un producto cuesta
 * aquí y lo que cuesta en el primer destino europeo de la quinua y el cacao
 * peruanos. Por separado, cada mitad es solo una lista de precios.
 *
 * Los precios alemanes vienen en euros, y eso ya está resuelto:
 * `adaptadores/tipo_cambio.py` convierte a soles con la serie oficial del BCRP
 * (PD04648PD, TC Euro venta) y guarda la tasa, su fecha y su fuente junto a
 * cada oferta, de modo que las dos columnas del mapa son comparables.
 *
 * El coste va escrito en la tarjeta a propósito. Sin él, «marcar todo» parece
 * siempre la mejor opción, y no lo es: las tiendas alemanas pasan por el
 * agente, que tarda minutos y gasta en un run lo que las otras dos no gastan
 * en un día.
 */
const FUENTES = [
  {
    clave: 'snapshot',
    nombre: 'OpenFoodFacts',
    detalle: 'Catálogo global de productos y composición',
    coste: 'Instantáneo · sin coste',
    tono: 'gratis',
  },
  {
    clave: 'peru',
    nombre: 'Ecommerce del Perú',
    detalle: 'Wong, Metro, Plaza Vea y Makro',
    coste: 'Segundos · sin coste',
    tono: 'gratis',
  },
  {
    clave: 'alemania',
    nombre: 'Ecommerce de Alemania',
    detalle: 'REWE, Edeka y Alnatura · precios en euros',
    coste: 'Minutos · con coste',
    tono: 'caro',
  },
]

const query = ref('')
const isLoading = ref(false)
const progress = ref(0)
const loadingText = ref('')
// Arrancan las dos gratuitas. Alemania se marca a conciencia: es la única que
// cuesta dinero, y una opción cara activada por defecto se acaba pagando sin
// que nadie haya decidido pagarla.
const seleccionadas = ref(['snapshot', 'peru'])
const emit = defineEmits(['search-result'])

/** Marca o desmarca una fuente, sin dejar la búsqueda sin ninguna. */
const alternar = (clave) => {
  const puestas = seleccionadas.value
  if (!puestas.includes(clave)) {
    seleccionadas.value = [...puestas, clave]
    return
  }
  // Quitar la última dejaría un botón «Analizar» que no puede analizar nada.
  // Se ignora el clic en vez de deshabilitar la casilla: deshabilitada, la
  // única pista de por qué no se puede sería que no pasa nada al pulsarla.
  if (puestas.length > 1) {
    seleccionadas.value = puestas.filter((c) => c !== clave)
  }
}

let progressInterval = null
let stageTimeouts = []

const startLoadingAnimation = () => {
  progress.value = 0
  loadingText.value = "Iniciando análisis..."
  
  progressInterval = setInterval(() => {
    if (progress.value < 95) {
      progress.value += (95 - progress.value) * 0.05
    }
  }, 500)

  stageTimeouts.push(setTimeout(() => loadingText.value = "Interpretando características del insumo...", 3000))
  stageTimeouts.push(setTimeout(() => loadingText.value = "Buscando referencias (LanceDB)...", 8000))
  stageTimeouts.push(setTimeout(() => loadingText.value = "Verificando normativas regulatorias...", 15000))
  stageTimeouts.push(setTimeout(() => loadingText.value = "Redactando Insight con Inteligencia Artificial...", 25000))
  stageTimeouts.push(setTimeout(() => loadingText.value = "Preparando informe final...", 35000))
}

const clearLoadingAnimation = () => {
  if (progressInterval) clearInterval(progressInterval)
  stageTimeouts.forEach(clearTimeout)
  progress.value = 100
  loadingText.value = "¡Análisis completado!"
}

const submitSearch = async () => {
  if (!query.value) return
  
  isLoading.value = true
  const startTime = performance.now()
  startLoadingAnimation()
  
  try {
    // api.consultar adjunta el Authorization; antes se llamaba sin cabecera y
    // este endpoint exige token desde S1, así que siempre daba 401.
    const data = await api.consultar(query.value)
    clearLoadingAnimation()
    
    const elapsedSeconds = ((performance.now() - startTime) / 1000).toFixed(1)
    data.elapsedTime = elapsedSeconds
    
    setTimeout(() => {
      emit('search-result', data)
      isLoading.value = false
    }, 800)
    
  } catch (error) {
    console.error(error)
    if (!(error instanceof NoAutorizado)) {
      // Un 401 ya cierra la sesión y lo gestiona App.vue; avisar dos veces sería ruido.
      alert('Ocurrió un error al consultar el insumo.')
    }
    clearLoadingAnimation()
    isLoading.value = false
  }
}
</script>

<style scoped>
.search-container {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}

.search-card {
  padding: 40px;
  text-align: center;
}

.search-card h2 {
  font-size: 2rem;
  margin-bottom: 10px;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.description {
  color: var(--text-muted);
  margin-bottom: 26px;
}

/* -- Selector de fuentes -------------------------------------------------- */

.fuentes {
  border: none;
  margin: 0 auto 24px;
  padding: 0;
  max-width: 600px;
  text-align: left;
}

.fuentes legend {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 0 10px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.previa {
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.14);
  color: #92400E;
  cursor: help;
}

.rejilla {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.fuente {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 12px 12px 12px 11px;
  border: 1px solid var(--card-border);
  border-radius: 10px;
  background: #ffffff;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
}

.fuente:hover { background: rgba(45, 151, 102, 0.04); }

.fuente.activa {
  border-color: var(--primary-color);
  background: rgba(45, 151, 102, 0.07);
}

/* La casilla real se oculta pero sigue ahí: recibe el foco del tabulador y el
   lector de pantalla la anuncia. El recuadro de abajo es solo la piel. */
.fuente input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: 0;
  padding: 0;
}

.fuente input:focus-visible ~ .marca {
  box-shadow: 0 0 0 3px rgba(45, 151, 102, 0.35);
}

.marca {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  flex-shrink: 0;
  border: 1.5px solid #CED4DA;
  border-radius: 4px;
  background: #ffffff;
  transition: all 0.15s;
}

.fuente.activa .marca {
  border-color: var(--primary-color);
  background: var(--primary-color);
}

/* El palito del tick, dibujado con bordes: no hace falta ningún icono. */
.fuente.activa .marca::after {
  content: '';
  display: block;
  width: 4px;
  height: 8px;
  margin: 1px auto 0;
  border: solid #ffffff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.cuerpo { display: flex; flex-direction: column; gap: 2px; min-width: 0; }

.nombre {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.2;
}

.detalle {
  font-size: 0.72rem;
  color: var(--text-muted);
  line-height: 1.3;
}

.coste {
  margin-top: 3px;
  font-size: 0.68rem;
  font-weight: 600;
}

.coste.gratis { color: var(--primary-hover); }
.coste.caro { color: #B45309; }

@media (max-width: 640px) {
  .rejilla { grid-template-columns: 1fr; }
}

.search-form {
  display: flex;
  justify-content: center;
}

.input-wrapper {
  display: flex;
  width: 100%;
  max-width: 600px;
  position: relative;
}

.input-wrapper input {
  flex-grow: 1;
  padding: 16px 20px;
  padding-right: 120px;
  border-radius: 30px;
  font-size: 1.1rem;
  background: rgba(15, 23, 42, 0.8);
  color: #FFFFFF;
}

.input-wrapper input::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.input-wrapper button {
  position: absolute;
  right: 6px;
  top: 6px;
  bottom: 6px;
  padding: 0 24px;
  border-radius: 24px;
}

/* Loading Overlay */
.loading-overlay {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  padding: 40px 0;
}

.loading-card {
  padding: 50px;
  text-align: center;
  width: 100%;
  max-width: 600px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.loading-card h3 {
  color: var(--primary-color);
  font-size: 1.5rem;
  margin: 10px 0;
}

.spinner-large {
  width: 60px;
  height: 60px;
  border: 5px solid rgba(45, 151, 102, 0.2);
  border-radius: 50%;
  border-top-color: var(--primary-color);
  animation: spin 1s ease-in-out infinite;
}

.progress-bar-container {
  width: 100%;
  height: 12px;
  background: rgba(0,0,0,0.05);
  border-radius: 6px;
  overflow: hidden;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
}

.progress-bar {
  height: 100%;
  background: var(--accent-gradient);
  transition: width 0.3s ease-out;
}

.progress-text {
  font-size: 1.2rem;
  font-weight: bold;
  color: var(--text-main);
  margin: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
