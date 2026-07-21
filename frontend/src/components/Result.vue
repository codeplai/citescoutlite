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
    
    <div class="glass-panel content-card">
      <div class="markdown-body" v-html="sanitizedHtml"></div>
      
      <div class="actions">
        <a v-if="result.ruta_pdf" :href="'http://localhost:8001/informes/' + result.ejecucion_id" target="_blank" class="btn-primary download-btn">
          Descargar PDF
        </a>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  result: {
    type: Object,
    required: true
  }
})

defineEmits(['reset'])

const sanitizedHtml = computed(() => {
  if (!props.result.markdown_content) return '<p>No hay contenido disponible.</p>'
  const rawHtml = marked(props.result.markdown_content)
  return DOMPurify.sanitize(rawHtml)
})
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
}

.download-btn {
  text-decoration: none;
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
</style>
