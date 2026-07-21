<template>
  <div class="token-container animate-fade-in" v-if="tokens !== null">
    <div class="glass-panel token-card">
      <div class="token-info">
        <span class="icon">🪙</span>
        <div class="details">
          <h4>Consumo de Tokens (LLM)</h4>
          <p class="total-tokens"><strong>{{ tokens }}</strong> tokens totales utilizados en esta consulta</p>
          <div class="token-split">
            <span class="split-badge in">📥 Entrada (Prompt): <strong>{{ tokensEntrada }}</strong></span>
            <span class="split-badge out">📤 Salida (Completion): <strong>{{ tokensSalida }}</strong></span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  ejecucionId: {
    type: String,
    default: null
  }
})

const tokens = ref(null)
const tokensEntrada = ref(0)
const tokensSalida = ref(0)

watch(() => props.ejecucionId, async (newId) => {
  if (!newId) {
    tokens.value = null
    return
  }
  
  try {
    const res = await fetch(`http://localhost:8001/ejecucion/${newId}/tokens`)
    if (res.ok) {
      const data = await res.json()
      tokens.value = data.total_tokens
      tokensEntrada.value = data.tokens_entrada
      tokensSalida.value = data.tokens_salida
    }
  } catch (e) {
    console.error("Error fetching tokens", e)
  }
}, { immediate: true })
</script>

<style scoped>
.token-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 20px 20px 20px;
}

.token-card {
  padding: 16px 24px;
  background: rgba(16, 185, 129, 0.1);
  border-color: rgba(16, 185, 129, 0.2);
}

.token-info {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon {
  font-size: 2rem;
}

.details h4 {
  margin: 0 0 4px 0;
  color: #34D399;
  font-size: 0.95rem;
}

.details p {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.85rem;
  margin-bottom: 8px;
}

.token-split {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.split-badge {
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(255,255,255,0.8);
  border: 1px solid rgba(0,0,0,0.05);
  color: var(--text-main);
}

.split-badge.in {
  border-color: rgba(59, 130, 246, 0.3); /* Blue for input */
}

.split-badge.out {
  border-color: rgba(16, 185, 129, 0.3); /* Green for output */
}
</style>
