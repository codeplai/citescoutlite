<template>
  <!-- El login no lleva panel: no hay adónde navegar todavía. -->
  <router-view v-if="$route.meta.publica" />

  <div v-else class="panel">
    <aside class="lateral">
      <div class="logo">AgroScout <span class="highlight">IA</span></div>

      <nav class="menu">
        <div v-for="grupo in menu" :key="grupo.nombre" class="grupo">
          <p class="grupo-titulo">{{ grupo.nombre }}</p>
          <RouterLink
            v-for="ruta in grupo.entradas"
            :key="ruta.name"
            :to="{ name: ruta.name }"
            class="entrada"
            active-class="activa"
          >
            <span class="icono" aria-hidden="true">{{ ruta.meta.icono }}</span>
            {{ ruta.meta.titulo }}
          </RouterLink>
        </div>
      </nav>

      <div class="pie">
        <p class="correo" :title="sesion.email">{{ sesion.email }}</p>
        <p v-if="sesion.rol" class="rol">{{ sesion.rol }}</p>
        <button @click="cerrarSesion" class="salir">Salir</button>
      </div>
    </aside>

    <main class="contenido">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { menuPara } from './router/index.js'
import { asegurarPerfil, hayToken, salir, sesion } from './sesion.js'
import { olvidarConsulta } from './vistas/estado_consulta.js'

const route = useRoute()
const router = useRouter()

const menu = computed(() => menuPara(sesion.rol))

const cerrarSesion = () => {
  salir()
  // El resultado de la consulta vive en memoria, fuera de los componentes: si
  // no se borra aquí, quien entre después en el mismo navegador se encuentra
  // la búsqueda de la persona anterior.
  olvidarConsulta()
  router.push({ name: 'login' })
}

const alCaducar = () => {
  olvidarConsulta()
  router.push({ name: 'login', query: { volverA: route.fullPath } })
}

onMounted(() => {
  // El guard solo pide el perfil en rutas de administración, y hoy no hay
  // ninguna. La barra lateral lo necesita igual para saber qué enseñar.
  if (hayToken()) asegurarPerfil()

  // El token de Supabase vive ~1 h. Cuando caduca, el cliente API lo detecta
  // en el primer 401 y avisa: la sesión se cierra sola en vez de dejar la
  // interfaz fallando sin explicación a mitad de la demo.
  window.addEventListener('agroscout:sesion-caducada', alCaducar)
})

onUnmounted(() => {
  window.removeEventListener('agroscout:sesion-caducada', alCaducar)
})
</script>

<style scoped>
.panel {
  display: flex;
  min-height: 100vh;
  align-items: stretch;
}

/* Fija y con scroll propio: el menú tiene que seguir accesible en pantallas
   largas como la cola de promociones, que son de cientos de filas. */
.lateral {
  position: sticky;
  top: 0;
  align-self: flex-start;
  height: 100vh;
  width: 230px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 28px;
  padding: 24px 16px;
  box-sizing: border-box;
  background: var(--card-bg);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-right: 1px solid var(--card-border);
}

.logo {
  font-size: 1.3rem;
  font-weight: 700;
  padding: 0 8px;
}

.highlight {
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.menu {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
}

.grupo-titulo {
  margin: 0 0 8px 8px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

/* Mismo lenguaje visual que las pestañas que sustituye: realce en verde de
   marca sobre fondo claro, no blancos translúcidos. */
.entrada {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 8px;
  border: 1px solid transparent;
  color: var(--text-muted);
  text-decoration: none;
  font-size: 0.92rem;
  transition: all 0.2s;
}

.entrada:hover {
  color: var(--text-main);
  background: rgba(45, 151, 102, 0.06);
}

.entrada.activa {
  background: rgba(45, 151, 102, 0.12);
  border-color: var(--card-border);
  color: var(--primary-hover);
  font-weight: 600;
}

.icono {
  width: 1.1em;
  text-align: center;
  font-size: 1rem;
}

.pie {
  border-top: 1px solid var(--card-border);
  padding: 16px 8px 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.correo {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rol {
  margin: 2px 0 12px;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--primary-hover);
}

.salir {
  width: 100%;
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
  padding: 7px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.salir:hover {
  background: rgba(239, 68, 68, 0.2);
}

.contenido {
  flex: 1;
  min-width: 0;   /* sin esto, una tabla ancha empuja la barra lateral */
  padding: 32px 40px;
  box-sizing: border-box;
}

@media (max-width: 900px) {
  .panel { flex-direction: column; }

  .lateral {
    position: static;
    width: 100%;
    height: auto;
    flex-direction: row;
    align-items: center;
    gap: 16px;
    border-right: none;
    border-bottom: 1px solid var(--card-border);
  }

  .menu { flex-direction: row; overflow-x: auto; }
  .grupo { display: flex; align-items: center; gap: 6px; }
  .grupo-titulo { display: none; }
  .pie { border-top: none; padding: 0; display: flex; align-items: center; gap: 12px; }
  .rol { display: none; }
  .contenido { padding: 24px 20px; }
}
</style>
