<template>
  <div class="app-wrapper">
    <Login v-if="!isAuthenticated" @login-success="isAuthenticated = true" />
    
    <div v-else class="main-content">
      <nav class="navbar glass-panel">
        <div class="logo">AgroScout <span class="highlight">IA</span></div>
        <div class="tabs">
          <button
            :class="['tab-btn', { activa: vista === 'consulta' }]"
            @click="vista = 'consulta'"
          >
            Consulta
          </button>
          <button
            :class="['tab-btn', { activa: vista === 'alertas' }]"
            @click="vista = 'alertas'"
          >
            Alertas de retiro
          </button>
          <button
            :class="['tab-btn', { activa: vista === 'promociones' }]"
            @click="vista = 'promociones'"
          >
            Promociones
          </button>
        </div>
        <div class="user-info">
          <span>{{ userEmail }}</span>
          <button @click="logout" class="logout-btn">Salir</button>
        </div>
      </nav>

      <template v-if="vista === 'consulta'">
        <Search v-if="!currentResult" @search-result="handleResult" />

        <div v-if="currentResult">
          <TokenUsage :ejecucion-id="currentResult.ejecucion_id" />
          <Result :result="currentResult" @reset="currentResult = null" />
        </div>
      </template>

      <!-- S6.7. Se monta aqui en vez de con vue-router: la SPA no lo usa y
           meter una dependencia de enrutado por una segunda pantalla seria
           desproporcionado. Cuando llegue el panel de S8 tocara replantearlo. -->
      <AlertasRetiro v-else-if="vista === 'alertas'" />

      <!-- S7.6: el 20 % que revisa una persona. -->
      <Promociones v-else-if="vista === 'promociones'" />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import Login from './components/Login.vue'
import Search from './components/Search.vue'
import Result from './components/Result.vue'
import TokenUsage from './components/TokenUsage.vue'
import AlertasRetiro from './components/AlertasRetiro.vue'
import Promociones from './components/Promociones.vue'
import { CLAVE_TOKEN, CLAVE_USUARIO } from './api.js'

const isAuthenticated = ref(false)
const userEmail = ref('')
const currentResult = ref(null)
const vista = ref('consulta')

const cerrarSesion = () => {
  isAuthenticated.value = false
  currentResult.value = null
  vista.value = 'consulta'
}

onMounted(() => {
  const token = localStorage.getItem(CLAVE_TOKEN)
  if (token) {
    isAuthenticated.value = true
    userEmail.value = localStorage.getItem(CLAVE_USUARIO) || 'Usuario'
  }
  // El token de Supabase vive ~1 h. Cuando caduca, el cliente API lo detecta en
  // el primer 401 y avisa: la sesión se cierra sola en vez de dejar la interfaz
  // fallando sin explicación a mitad de la demo.
  window.addEventListener('agroscout:sesion-caducada', cerrarSesion)
})

onUnmounted(() => {
  window.removeEventListener('agroscout:sesion-caducada', cerrarSesion)
})

const logout = () => {
  localStorage.removeItem(CLAVE_TOKEN)
  localStorage.removeItem(CLAVE_USUARIO)
  cerrarSesion()
}

const handleResult = (data) => {
  currentResult.value = data
}
</script>

<style scoped>
.app-wrapper {
  width: 100%;
}

.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 40px;
  margin-bottom: 40px;
  border-radius: 0;
  border-left: none;
  border-right: none;
  border-top: none;
}

.logo {
  font-size: 1.5rem;
  font-weight: 700;
}

.highlight {
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.tabs {
  display: flex;
  gap: 8px;
}

.tab-btn {
  background: transparent;
  color: var(--text-muted);
  border: 1px solid transparent;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: inherit;
}

.tab-btn.activa {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  color: inherit;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 0.9rem;
  color: var(--text-muted);
}

.logout-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.2);
}
</style>
