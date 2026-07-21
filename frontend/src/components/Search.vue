<template>
  <div class="search-container animate-fade-in">
    <div class="glass-panel search-card" v-show="!isLoading">
      <h2>Consulta de Insumos</h2>
      <p class="description">Analiza el potencial de cualquier materia prima agrícola</p>
      
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

const query = ref('')
const isLoading = ref(false)
const progress = ref(0)
const loadingText = ref('')
const emit = defineEmits(['search-result'])

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
    const response = await fetch('http://localhost:8001/consultas', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ texto: query.value })
    })
    
    if (!response.ok) throw new Error('Error en la API')
    
    const data = await response.json()
    clearLoadingAnimation()
    
    const elapsedSeconds = ((performance.now() - startTime) / 1000).toFixed(1)
    data.elapsedTime = elapsedSeconds
    
    setTimeout(() => {
      emit('search-result', data)
      isLoading.value = false
    }, 800)
    
  } catch (error) {
    console.error(error)
    alert('Ocurrió un error al consultar el insumo.')
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
  margin-bottom: 30px;
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
