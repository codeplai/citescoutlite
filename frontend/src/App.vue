<template>
  <div class="app-wrapper">
    <Login v-if="!isAuthenticated" @login-success="isAuthenticated = true" />
    
    <div v-else class="main-content">
      <nav class="navbar glass-panel">
        <div class="logo">AgroScout <span class="highlight">IA</span></div>
        <div class="user-info">
          <span>{{ userEmail }}</span>
          <button @click="logout" class="logout-btn">Salir</button>
        </div>
      </nav>

      <Search v-if="!currentResult" @search-result="handleResult" />
      
      <div v-if="currentResult">
        <TokenUsage :ejecucion-id="currentResult.ejecucion_id" />
        <Result :result="currentResult" @reset="currentResult = null" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Login from './components/Login.vue'
import Search from './components/Search.vue'
import Result from './components/Result.vue'
import TokenUsage from './components/TokenUsage.vue'

const isAuthenticated = ref(false)
const userEmail = ref('')
const currentResult = ref(null)

onMounted(() => {
  const token = localStorage.getItem('agroscout_token')
  if (token) {
    isAuthenticated.value = true
    userEmail.value = localStorage.getItem('agroscout_user') || 'Usuario'
  }
})

const logout = () => {
  localStorage.removeItem('agroscout_token')
  localStorage.removeItem('agroscout_user')
  isAuthenticated.value = false
  currentResult.value = null
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
