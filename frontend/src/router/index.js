/**
 * S8.1 - Rutas del panel.
 *
 * La SPA venía navegando con un `ref` llamado `vista` y una cadena de
 * `v-else-if`. Con tres pestañas se aguantaba; el panel de S8 trae seis
 * pantallas más y ese patrón tiene dos problemas que no se arreglan añadiendo
 * ramas: **no hay URL** —no se puede enlazar una pantalla ni volver con el
 * botón de atrás— y **recargar te devuelve siempre al principio**.
 *
 * ## El menú vive aquí, no en la barra lateral
 *
 * Cada ruta declara en `meta` su título y si es de administración, y la barra
 * lateral se dibuja recorriendo el router. Así una pantalla nueva se añade en
 * un solo sitio y es imposible que aparezca en el menú sin ruta, o al revés.
 */

import { createRouter, createWebHistory } from 'vue-router'

import Login from '../components/Login.vue'
import { asegurarPerfil, hayToken } from '../sesion.js'

// Las tres pantallas de dentro se cargan bajo demanda: quien solo consulta
// precios no tiene por qué descargar el panel de promociones.
export const rutas = [
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: { publica: true },
  },
  {
    path: '/consulta',
    name: 'consulta',
    component: () => import('../vistas/ConsultaVista.vue'),
    meta: { titulo: 'Consulta', grupo: 'Operación', icono: '⌕' },
  },
  {
    path: '/alertas',
    name: 'alertas',
    component: () => import('../components/AlertasRetiro.vue'),
    meta: { titulo: 'Alertas de retiro', grupo: 'Operación', icono: '⚠' },
  },
  {
    // Mirar la cola puede hacerlo cualquiera del equipo; promover y rechazar
    // exigen admin, y eso lo decide el backend en cada acción. La ruta no se
    // marca de administración porque cerraría la lectura a quien sí debe leer.
    path: '/promociones',
    name: 'promociones',
    component: () => import('../components/Promociones.vue'),
    meta: { titulo: 'Promociones', grupo: 'Operación', icono: '⇪' },
  },
  { path: '/', redirect: { name: 'consulta' } },
  { path: '/:resto(.*)*', redirect: { name: 'consulta' } },
]

export const router = createRouter({
  history: createWebHistory(),
  routes: rutas,
})

/** Las rutas que se enseñan en el menú, agrupadas y filtradas por rol. */
export function menuPara(rol) {
  const grupos = new Map()
  for (const ruta of rutas) {
    if (!ruta.meta?.titulo) continue
    if (ruta.meta.admin && rol !== 'admin') continue
    const grupo = ruta.meta.grupo || 'Operación'
    if (!grupos.has(grupo)) grupos.set(grupo, [])
    grupos.get(grupo).push(ruta)
  }
  return [...grupos].map(([nombre, entradas]) => ({ nombre, entradas }))
}

router.beforeEach(async (destino) => {
  if (destino.meta.publica) {
    // Con sesión abierta, el login no tiene nada que ofrecer.
    return hayToken() ? { name: 'consulta' } : true
  }

  if (!hayToken()) {
    // `volverA` para que, tras entrar, se vuelva a donde se quería ir. Sin
    // esto, caducar la sesión en Promociones te deja en Consulta y hay que
    // volver a navegar a mano.
    return { name: 'login', query: { volverA: destino.fullPath } }
  }

  if (destino.meta.admin) {
    const { rol } = await asegurarPerfil()
    if (rol !== 'admin') return { name: 'consulta' }
  }

  return true
})

export default router
