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
 *
 * ## `meta.icono` es un nombre, no un carácter
 *
 * Hasta el rediseño aquí vivían caracteres Unicode sueltos —`⌕ ⚠ ⇪ ☰ ◔ ⏻`— y
 * la barra lateral los pintaba como texto. El resultado dependía de las
 * fuentes instaladas en cada máquina: lupa en unas, cuadrado vacío en otras.
 * Ahora es el nombre de un trazo de `components/Icono.vue`, que se dibuja
 * igual en todas partes y no arrastra color propio.
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
    meta: { titulo: 'Consulta', grupo: 'Operación', icono: 'buscar' },
  },
  {
    path: '/alertas',
    name: 'alertas',
    component: () => import('../components/AlertasRetiro.vue'),
    meta: { titulo: 'Alertas de retiro', grupo: 'Operación', icono: 'alerta' },
  },
  {
    // Mirar la cola puede hacerlo cualquiera del equipo; promover y rechazar
    // exigen admin, y eso lo decide el backend en cada acción. La ruta no se
    // marca de administración porque cerraría la lectura a quien sí debe leer.
    path: '/promociones',
    name: 'promociones',
    component: () => import('../components/Promociones.vue'),
    meta: { titulo: 'Promociones', grupo: 'Operación', icono: 'promover' },
  },
  {
    // S8.3. Primera ruta que exige rol de administrador para LEER. Hasta ahora
    // el rol solo cerraba acciones (promover, rechazar); la auditoría dice
    // quién hizo qué y a qué hora, y eso es información sobre las personas que
    // operan el sistema, no sobre los datos.
    //
    // El guard es comodidad, no seguridad: quien fuerce la URL solo consigue
    // que /api/auditoria le devuelva 403.
    path: '/auditoria',
    name: 'auditoria',
    component: () => import('../components/Auditoria.vue'),
    meta: { titulo: 'Auditoría', grupo: 'Administración', icono: 'lista', admin: true },
  },
  {
    // S8.2. El desglose enseña cuánto ha gastado cada usuario, así que es de
    // administración; cada uno ve lo suyo en la propia pantalla de consulta.
    path: '/costos',
    name: 'costos',
    component: () => import('../components/Costos.vue'),
    meta: { titulo: 'Costes', grupo: 'Administración', icono: 'medidor', admin: true },
  },
  {
    // S8.5 y S8.9. Aquí se detiene el gasto de todo el mundo y se cambia el
    // plan de cualquiera: de las tres de administración, la que más importa
    // que no aparezca en el menú de un operador.
    path: '/control',
    name: 'control',
    component: () => import('../components/Control.vue'),
    meta: { titulo: 'Presupuestos y control', grupo: 'Administración',
            icono: 'encendido', admin: true },
  },
  {
    // T6. Sin `titulo` en `meta`, y por eso **no sale en el menú lateral**:
    // aquí no se llega navegando, se llega desde una fila concreta del mapa
    // comercial. Una entrada de menú abriría la pantalla sin producto que
    // analizar.
    //
    // El id del producto va como parámetro de ruta y no como query porque es
    // parte de la identidad de la página: esta URL se pega en un correo para
    // que otra persona vea exactamente el mismo análisis.
    path: '/analisis/:ejecucionId/:productoId',
    name: 'analisis',
    component: () => import('../vistas/AnalisisIngredientes.vue'),
    props: true,
  },
  {
    // T8. La misma pantalla para una fila de las tablas de góndola.
    //
    // Ruta aparte y no un parámetro más porque la oferta se identifica por su
    // **URL de origen**, y una URL dentro de un segmento de ruta obliga a
    // codificar barras y dos puntos: acaba siendo ilegible y frágil. Como query
    // sale limpia y se puede pegar en un correo igual de bien.
    path: '/analisis-oferta/:ejecucionId',
    name: 'analisis-oferta',
    component: () => import('../vistas/AnalisisIngredientes.vue'),
    props: (ruta) => ({
      ejecucionId: ruta.params.ejecucionId,
      ofertaUrl: ruta.query.url || '',
    }),
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
