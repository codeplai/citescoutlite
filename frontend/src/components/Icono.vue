<!--
  El juego de iconos de la casa. Uno solo, de trazo, grosor 1,75.

  ## Por qué existe

  Antes había tres juegos conviviendo: emoji a color en los titulares
  (🚨 💰 🗺️ 🔍 ⏱️), caracteres Unicode sueltos en el menú lateral (⌕ ⚠ ⇪ ☰ ◔ ⏻)
  y flechas de texto en los enlaces (→ ↗). Los tres tienen el mismo problema y
  cada uno lo agrava a su manera:

  - **No son iconos, son texto.** Su forma la elige la fuente del sistema, así
    que ⌕ sale como una lupa en macOS, como un cuadrado vacío en varios
    Windows y como nada en un Linux sin la fuente de símbolos. El menú de
    navegación no puede depender de qué tipografías tenga instaladas quien
    mira.
  - **El emoji trae color propio.** 🚨 es rojo pase lo que pase, y ese rojo
    compite con el rojo que en este sistema significa «alerta crítica». Cuando
    todo grita, el grito deja de informar.
  - **El lector de pantalla los lee.** «🗺️ Mapa comercial» se anuncia como
    «mapa del mundo mapa comercial». El icono decorativo tiene que callarse.

  ## Cómo se usa

      <Icono nombre="buscar" />                  decorativo: aria-hidden
      <Icono nombre="externo" titulo="Abre en otra pestaña" />   con nombre accesible

  Si un icono lleva `titulo`, se anuncia como imagen con ese texto. Si no,
  desaparece para el lector de pantalla y el significado lo pone el texto que
  va al lado. La regla es simple: **un icono nunca es la única forma de saber
  qué hace un control**.
-->
<template>
  <svg
    :width="tamano"
    :height="tamano"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.75"
    stroke-linecap="round"
    stroke-linejoin="round"
    :role="titulo ? 'img' : undefined"
    :aria-hidden="titulo ? undefined : 'true'"
    :focusable="false"
    class="icono"
  >
    <title v-if="titulo">{{ titulo }}</title>
    <!-- eslint-disable-next-line vue/no-v-html -- `trazos` sale del mapa
         literal de abajo; nunca lleva contenido de servidor. -->
    <g v-html="trazos" />
  </svg>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  nombre: { type: String, required: true },
  tamano: { type: [Number, String], default: 18 },
  /** Nombre accesible. Sin él, el icono es decorativo y se oculta. */
  titulo: { type: String, default: '' },
})

/**
 * Los trazos, en una tabla. Nombres en español porque el resto del código lo
 * está y `nombre="warning"` dentro de una plantilla en español obliga a
 * traducir mentalmente en cada uso.
 */
const TRAZOS = {
  // -- Navegación -----------------------------------------------------
  buscar: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>',
  alerta:
    '<path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  promover: '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/>',
  lista:
    '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  medidor: '<path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/>',
  encendido: '<path d="M12 2v10"/><path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>',

  // -- Acciones -------------------------------------------------------
  externo:
    '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  descargar: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M21 21H3"/>',
  refrescar:
    '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
  salir:
    '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  filtro: '<path d="M3 5h18"/><path d="M7 12h10"/><path d="M11 19h2"/>',
  copiar:
    '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',

  // -- Veredicto y estado ---------------------------------------------
  check: '<path d="m5 13 4 4L19 7"/>',
  equis: '<path d="M18 6 6 18M6 6l12 12"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 17h.01"/>',
  reloj: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  candado:
    '<rect x="3" y="11" width="18" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
  imagen:
    '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="1.6"/><path d="m21 15-4.5-4.5L7 21"/>',
  documento:
    '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/>',

  // -- Movimiento -----------------------------------------------------
  'chevron-abajo': '<path d="m6 9 6 6 6-6"/>',
  'chevron-arriba': '<path d="m18 15-6-6-6 6"/>',
  'chevron-izq': '<path d="m15 18-6-6 6-6"/>',
  'chevron-der': '<path d="m9 18 6-6-6-6"/>',
  sube: '<path d="M12 19V6"/><path d="m6 12 6-6 6 6"/>',
  baja: '<path d="M12 5v13"/><path d="m6 12 6 6 6-6"/>',
}

const trazos = computed(() => {
  const t = TRAZOS[props.nombre]
  if (t) return t
  // Un icono que no existe se ve —un cuadrado— en vez de desaparecer sin
  // ruido: un hueco silencioso en una barra de navegación tarda semanas en
  // detectarse.
  if (import.meta.env.DEV) console.warn(`[Icono] no existe «${props.nombre}»`)
  return '<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 3"/>'
})
</script>

<style scoped>
.icono {
  flex: none;
  /* Alinea con la línea base del texto que acompaña, en vez de colgar del
     borde superior de la caja. */
  vertical-align: -0.15em;
}
</style>
