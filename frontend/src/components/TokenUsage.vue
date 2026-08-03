<template>
  <div class="uso-container animate-fade-in" v-if="uso">
    <div class="glass-panel uso-card">
      <div class="cabecera">
        <div>
          <h4>Consumo del mes · plan {{ uso.plan }}</h4>
          <p class="cifras">
            <strong>${{ uso.costo_mes_usd.toFixed(4) }}</strong> de ${{ uso.tope_usd.toFixed(2) }}
            · {{ uso.runs }} {{ uso.runs === 1 ? 'consulta' : 'consultas' }}
          </p>
        </div>
        <span v-if="uso.kill_switch_activo" class="kill-switch">
          ⏸️ Gasto global detenido
        </span>
      </div>

      <!-- El gasto está acotado por diseño: la barra lo enseña, no lo cuenta. -->
      <div class="barra" role="progressbar" :aria-valuenow="porcentaje" aria-valuemin="0" aria-valuemax="100">
        <div class="relleno" :class="nivel" :style="{ width: porcentaje + '%' }"></div>
      </div>

      <div v-if="etapas.length" class="desglose">
        <span class="titulo-desglose">Última consulta:</span>
        <span v-for="etapa in etapas" :key="etapa.etapa" class="etapa" :class="{ cacheada: etapa.cache_hit }">
          <strong>{{ etapa.etapa }}</strong>
          <span class="modelo">{{ modeloCorto(etapa.modelo) }}</span>
          <span class="costo">{{ etapa.cache_hit ? 'cache' : '$' + etapa.costo_usd.toFixed(4) }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { api, NoAutorizado } from '../api.js'

const props = defineProps({
  ejecucionId: {
    type: String,
    default: null
  }
})

const uso = ref(null)

const etapas = computed(() => uso.value?.ultimo_run?.etapas || [])

const porcentaje = computed(() => {
  if (!uso.value?.tope_usd) return 0
  return Math.min(100, (uso.value.costo_mes_usd / uso.value.tope_usd) * 100)
})

const nivel = computed(() => {
  if (porcentaje.value >= 90) return 'agotado'
  if (porcentaje.value >= 60) return 'alto'
  return 'normal'
})

// 'openai/glm-5.2' -> 'glm-5.2'. El prefijo es del enrutado de litellm y no
// significa nada para quien lee el informe.
const modeloCorto = (modelo) => (modelo || '—').split('/').pop()

watch(() => props.ejecucionId, async () => {
  try {
    uso.value = await api.uso()
  } catch (error) {
    if (!(error instanceof NoAutorizado)) console.error(error)
    uso.value = null
  }
}, { immediate: true })
</script>

<style scoped>
.uso-container {
  max-width: 1000px;
  margin: 0 auto;
  padding: 0 20px 20px 20px;
}

.uso-card {
  padding: 16px 24px;
}

.cabecera {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.cabecera h4 {
  margin: 0 0 4px 0;
  font-size: 0.95rem;
  text-transform: capitalize;
}

.cifras {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.kill-switch {
  font-size: 0.8rem;
  padding: 4px 10px;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #EF4444;
  white-space: nowrap;
}

.barra {
  height: 8px;
  border-radius: 4px;
  background: rgba(100, 116, 139, 0.18);
  overflow: hidden;
  margin: 12px 0;
}

.relleno {
  height: 100%;
  border-radius: 4px;
  transition: width 0.4s ease;
}

.relleno.normal { background: #10B981; }
.relleno.alto { background: #F59E0B; }
.relleno.agotado { background: #EF4444; }

.desglose {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  font-size: 0.78rem;
}

.titulo-desglose {
  color: var(--text-muted);
}

.etapa {
  display: inline-flex;
  gap: 6px;
  align-items: baseline;
  padding: 3px 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.etapa.cacheada {
  opacity: 0.65;
  border-style: dashed;
}

.etapa .modelo {
  color: var(--text-muted);
}

.etapa .costo {
  font-variant-numeric: tabular-nums;
}
</style>
