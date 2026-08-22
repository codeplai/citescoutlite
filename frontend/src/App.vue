<template>
  <!-- El login no lleva panel: no hay adónde navegar todavía. -->
  <router-view v-if="$route.meta.publica" />

  <div v-else class="panel">
    <!--
      Saltar al contenido. Con seis entradas de menú, quien navega con teclado
      o lector de pantalla tenía que recorrerlas enteras en cada cambio de
      pantalla antes de llegar a los datos.
    -->
    <a href="#contenido" class="saltar no-imprimir">Saltar al contenido</a>

    <aside class="lateral no-imprimir">
      <div class="logo">AgroScout <span class="highlight">IA</span></div>

      <nav class="menu" aria-label="Secciones">
        <div v-for="grupo in menu" :key="grupo.nombre" class="grupo">
          <p :id="`grupo-${idGrupo(grupo.nombre)}`" class="grupo-titulo">
            {{ grupo.nombre }}
          </p>
          <!--
            `aria-labelledby` ata cada bloque a su rótulo: sin esto, un lector
            de pantalla lee seis enlaces seguidos y «Costes» no se distingue de
            una pantalla de operación. La distinción importa: el grupo de
            administración solo lo ve un admin.
          -->
          <div
            class="grupo-entradas"
            role="group"
            :aria-labelledby="`grupo-${idGrupo(grupo.nombre)}`"
          >
            <RouterLink
              v-for="ruta in grupo.entradas"
              :key="ruta.name"
              :to="{ name: ruta.name }"
              class="entrada"
              active-class="activa"
            >
              <Icono :nombre="ruta.meta.icono" :tamano="17" />
              {{ ruta.meta.titulo }}
            </RouterLink>
          </div>
        </div>
      </nav>

      <div class="pie">
        <p class="correo" :title="sesion.email">{{ sesion.email }}</p>
        <p v-if="sesion.rol" class="rol">{{ sesion.rol }}</p>
        <button class="salir" @click="cerrarSesion">
          <Icono nombre="salir" :tamano="15" />Salir
        </button>
      </div>
    </aside>

    <main id="contenido" class="contenido" tabindex="-1">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import Icono from './components/Icono.vue'
import { menuPara } from './router/index.js'
import { asegurarPerfil, hayToken, salir, sesion } from './sesion.js'
import { olvidarConsulta } from './vistas/estado_consulta.js'

const route = useRoute()
const router = useRouter()

const menu = computed(() => menuPara(sesion.rol))

/**
 * «Administración» → «administracion», para usarlo como id de HTML.
 *
 * El `normalize('NFD')` separa cada letra de su tilde y el rango de marcas
 * combinantes se lleva las tildes sueltas. Sin esto el id llevaría `ó` y la
 * referencia desde `aria-labelledby` dependería de que el navegador y el
 * lector de pantalla normalicen la cadena igual, cosa que no está garantizada.
 */
const idGrupo = (nombre) =>
  nombre
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')

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
/**
 * El chrome de la aplicación.
 *
 * ## Por qué la barra lateral es oscura
 *
 * Antes era la misma superficie translúcida que las tarjetas de contenido, con
 * `backdrop-filter` incluido. Eso tenía dos consecuencias: el borde entre
 * «dónde estoy» y «qué estoy mirando» quedaba en un borde de 1px del mismo
 * color que los demás, y el menú heredaba el fondo de lo que hubiera detrás,
 * así que su contraste cambiaba de pantalla en pantalla.
 *
 * Un raíl de tinta resuelve las dos: la navegación deja de ser una tarjeta más
 * y su contraste ya no depende del contenido. Es además lo que hace todo panel
 * institucional, y aquí la familiaridad vale más que la originalidad.
 */

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
  gap: 26px;
  padding: 22px 0;
  background: var(--oscuro);
  color: #B9C4BF;
}

.logo {
  padding: 0 20px 2px;
  font-size: 1.125rem;
  font-weight: 750;
  letter-spacing: -0.02em;
  color: #fff;
}

/* Lo único que queda del gradiente de marca en el cuerpo de la aplicación es
   este acento plano. Un degradado de dos colores recortado sobre tres letras
   se lee como un artefacto, no como una firma. */
.highlight {
  color: var(--verde-claro);
}

.menu {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 22px;
  overflow-y: auto;
}

.grupo-entradas {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.grupo-titulo {
  margin: 0 0 8px;
  padding: 0 20px;
  font-size: 0.655rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--oscuro-rotulo);
}

/*
  El estado activo se dice de tres formas a la vez: barra verde a la izquierda,
  fondo un punto más claro y texto en blanco. Con una sola —el color— quien no
  distinga el verde del gris no sabría en qué pantalla está, y la barra
  lateral es justo el sitio donde eso importa.

  Los 3px de borde los llevan TODAS las entradas, transparentes en las
  inactivas: si solo lo llevara la activa, el texto se desplazaría 3px al
  cambiar de pantalla.
*/
.entrada {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 9px 20px;
  border-left: 3px solid transparent;
  color: var(--oscuro-texto);
  text-decoration: none;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background-color 0.15s, color 0.15s;
}

.entrada:hover {
  color: #fff;
  background: var(--oscuro-hover);
  text-decoration: none;
}

.entrada.activa {
  color: #fff;
  background: var(--oscuro-activo);
  border-left-color: var(--verde);
  font-weight: 600;
}

/* Sobre tinta, el anillo verde del sistema se pierde. Aquí el foco va en
   claro. */
.entrada:focus-visible,
.salir:focus-visible {
  outline: 2px solid var(--verde-claro);
  outline-offset: -2px;
}

.pie {
  border-top: 1px solid #1D2723;
  margin: 0 20px;
  padding-top: 16px;
  font-size: 0.8rem;
  color: var(--oscuro-texto);
}

.correo {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rol {
  margin: 2px 0 12px;
  font-size: 0.655rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--verde-claro);
}

/*
  Salir dejó de ser rojo. Cerrar sesión no es destructivo —no se pierde nada
  que no vuelva al entrar— y pintarlo del color de «alerta crítica» gastaba el
  rojo del sistema en el control más inocuo de la pantalla. Ahora es un botón
  neutro sobre el raíl, y el rojo queda libre para lo que de verdad lo
  necesita.
*/
.salir {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  font-family: inherit;
  font-size: 0.82rem;
  font-weight: 600;
  background: transparent;
  color: var(--oscuro-texto);
  border: 1px solid #27352F;
  padding: 8px 12px;
  border-radius: var(--r-xs);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s, border-color 0.15s;
}

.salir:hover {
  background: var(--oscuro-hover);
  border-color: #37443F;
  color: #fff;
}

/* Se ve solo con el tabulador, y entonces se ve del todo. */
.saltar {
  position: absolute;
  left: -9999px;
  z-index: 100;
  padding: 10px 18px;
  background: var(--verde);
  color: #fff;
  font-weight: 600;
  border-radius: 0 0 var(--r-sm) 0;
  text-decoration: none;
}

.saltar:focus {
  left: 0;
  top: 0;
}

.contenido {
  flex: 1;
  min-width: 0;   /* sin esto, una tabla ancha empuja la barra lateral */
  padding: 32px 40px 72px;
  /* El salto de foco desde «Saltar al contenido» no debe dibujar un recuadro
     alrededor de media pantalla: el destino ya se nota porque la vista salta. */
  outline: none;
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
    padding: 12px 16px;
  }

  .logo { padding: 0; }
  .menu { flex-direction: row; overflow-x: auto; gap: 8px; }
  .grupo { display: flex; align-items: center; gap: 4px; }
  .grupo-entradas { flex-direction: row; }
  .grupo-titulo { display: none; }

  /* En horizontal, un borde a la izquierda no señala nada: pasa abajo. */
  .entrada {
    border-left: 0;
    border-bottom: 3px solid transparent;
    padding: 8px 12px;
    white-space: nowrap;
    border-radius: var(--r-xs) var(--r-xs) 0 0;
  }

  .entrada.activa { border-bottom-color: var(--verde); }

  .pie {
    border-top: none;
    margin: 0;
    padding-top: 0;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .correo, .rol { display: none; }
  .salir { width: auto; }
  .contenido { padding: 24px 20px 48px; }
}
</style>
