<template>
  <div class="login-container">
    <div class="glass-panel login-card animate-fade-in">
      <div class="logo-area">
        <h1>AgroScout <span class="highlight">IA</span></h1>
        <p class="subtitle">CITEagroindustrial Chavimochic</p>
      </div>
      
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="input-group">
          <label for="email">Correo Electrónico</label>
          <input 
            type="email" 
            id="email" 
            v-model="email" 
            placeholder="usuario@cite.gob.pe" 
            required
          />
        </div>
        
        <div class="input-group">
          <label for="password">Contraseña</label>
          <input 
            type="password" 
            id="password" 
            v-model="password" 
            placeholder="••••••••" 
            required
          />
        </div>
        
        <button type="submit" class="btn-primary login-btn" :disabled="isLoading">
          <span v-if="!isLoading">Ingresar al Sistema</span>
          <span v-else>Validando...</span>
        </button>
        
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api, CLAVE_TOKEN, CLAVE_USUARIO } from '../api.js'

const email = ref('')
const password = ref('')
const errorMsg = ref('')
const isLoading = ref(false)
const emit = defineEmits(['login-success'])

const handleLogin = async () => {
  if (!email.value || !password.value) return
  
  isLoading.value = true
  errorMsg.value = ''
  
  try {
    // El backend hace de proxy del password grant de Supabase y conserva la
    // misma forma de request y response que en S1, así que este componente no
    // necesita ninguna clave de Supabase.
    const res = await api.login(email.value, password.value)

    if (!res.ok) {
      if (res.status === 401) throw new Error('Credenciales inválidas')
      throw new Error('Error al conectar con el servidor')
    }

    const data = await res.json()
    localStorage.setItem(CLAVE_TOKEN, data.access_token)
    localStorage.setItem(CLAVE_USUARIO, data.user)
    emit('login-success')
    
  } catch (error) {
    errorMsg.value = error.message
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 40px;
  text-align: center;
}

.logo-area {
  margin-bottom: 40px;
}

.logo-area h1 {
  font-size: 2rem;
  margin-bottom: 8px;
  letter-spacing: -0.5px;
}

.highlight {
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.subtitle {
  color: var(--text-muted);
  font-size: 0.9rem;
  margin: 0;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 8px;
}

.input-group label {
  font-size: 0.85rem;
  color: var(--text-muted);
  font-weight: 500;
}

.login-btn {
  margin-top: 10px;
  padding: 14px;
}

.error-msg {
  color: #DC2626;
  font-size: 0.9rem;
  margin-top: 10px;
  background: rgba(220, 38, 38, 0.1);
  padding: 8px;
  border-radius: 6px;
  border: 1px solid rgba(220, 38, 38, 0.2);
}
</style>
