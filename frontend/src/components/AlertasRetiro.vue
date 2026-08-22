<!--
  11 · Vigilancia de retiros (FDA + RASFF).

  ## De tarjetas de colores a filas comparables

  La versión anterior pintaba cada alerta como una tarjeta con encabezado
  🚨, tres tarjetas de estadística con gradiente morado y rosa, y la severidad
  en un emoji de círculo de color. Tres problemas, y el tercero es el grave:

  1. **Las tarjetas no se comparan.** Lo que se hace en esta pantalla es
     ordenar por gravedad y decidir qué mirar primero. Con seis tarjetas de
     alto variable, «cuál es peor» exige leerlas todas.
  2. **El gradiente morado no significa nada.** Estaba en la cabecera, en el
     botón y en la barra de score, o sea en los tres sitios donde el color
     tenía que estar diciendo la severidad.
  3. **La severidad iba solo en color.** 🔴🟠🟡🟢 es color puro: quien no
     distinga rojo de naranja no puede ordenar la lista, y en gris de
     impresora los cuatro círculos son el mismo círculo.

  Ahora cada alerta es una fila de altura fija con una **barra de severidad a
  la izquierda** y el rótulo en versalitas al lado. El color refuerza; el que
  informa es el rótulo. La escala completa —crítica, alta, media, baja— va de
  rojo a oliva pasando por naranja y ocre, que es un eje y no cuatro colores
  sueltos.
-->
<template>
  <div class="alertas">
    <header class="cabecera">
      <div>
        <p class="eyebrow">Vigilancia</p>
        <h1>Alertas de retiro</h1>
        <p class="entradilla">
          Retiradas y notificaciones de la FDA (Estados Unidos) y del RASFF
          (Unión Europea) sobre productos alimentarios.
        </p>
      </div>

      <!--
        Los contadores salen de /estadisticas/resumen y son GLOBALES, no los de
        la página filtrada. Rellenarlos desde /activas —que es lo que hacía una
        versión anterior— hacía que filtrar por «crítica» cambiara el total de
        críticas, que es justo la cifra que no debe moverse al filtrar.
      -->
      <dl class="contadores">
        <div>
          <dt>Críticas</dt>
          <dd class="cifra critica">{{ estadisticas.alertas_criticas }}</dd>
        </div>
        <div>
          <dt>Activas · 90 días</dt>
          <dd class="cifra alta">{{ estadisticas.alertas_activas_90d }}</dd>
        </div>
        <div>
          <dt>Totales</dt>
          <dd class="cifra">{{ estadisticas.total_alertas }}</dd>
        </div>
      </dl>
    </header>

    <p v-if="estadisticas.ultima_actualizacion" class="actualizado">
      Última actualización del corpus:
      <strong>{{ formatearFecha(estadisticas.ultima_actualizacion) }}</strong>
    </p>

    <!-- ================= Filtros ================= -->
    <div class="filtros no-imprimir">
      <span class="rotulo">Severidad</span>
      <!--
        Chips y no un desplegable: son cinco opciones excluyentes y con el chip
        se ve cuál está puesta sin abrir nada. Cada uno lleva su punto de
        color, que aquí sí es legítimo porque el texto va al lado.
      -->
      <button
        v-for="s in SEVERIDADES"
        :key="s.valor"
        type="button"
        class="chip chip--accion"
        :aria-pressed="filtroSeveridad === s.valor"
        @click="ponerSeveridad(s.valor)"
      >
        <span class="punto" :class="`punto--${s.valor || 'todas'}`" aria-hidden="true"></span>
        {{ s.nombre }}
      </button>

      <span class="separador" aria-hidden="true"></span>

      <label class="campo-en-linea">
        <span class="rotulo">Días</span>
        <select v-model.number="filtroDias" @change="cargarAlertas">
          <option :value="7">Últimos 7 días</option>
          <option :value="30">Últimos 30 días</option>
          <option :value="90">Últimos 90 días</option>
        </select>
      </label>

      <label class="campo-en-linea">
        <span class="rotulo">Máximo</span>
        <select v-model.number="filtroLimite" @change="cargarAlertas">
          <option :value="25">25 alertas</option>
          <option :value="50">50 alertas</option>
          <option :value="100">100 alertas</option>
          <option :value="200">200 alertas</option>
        </select>
      </label>

      <span class="cuenta">
        <b class="num">{{ alertas.length }}</b> visibles
      </span>

      <button type="button" class="btn btn--secundario btn--pequeno" @click="cargarAlertas">
        <Icono nombre="refrescar" :tamano="14" />Actualizar
      </button>
    </div>

    <!-- ================= Estados ================= -->
    <!--
      Los tres estados de la lista se ven distintos entre sí. Antes «cargando»,
      «sin resultados» y «error» compartían el mismo hueco silencioso, y la
      diferencia entre «no hay alertas» y «la API no responde» era invisible.
    -->
    <div v-if="cargando" class="estado superficie" aria-live="polite" aria-busy="true">
      <span class="barra"><span class="barra-barrido"></span></span>
      Consultando el corpus de alertas…
    </div>

    <div v-else-if="error" class="estado superficie estado--error" role="alert">
      <Icono nombre="info" :tamano="18" />
      <div>
        <strong>No se pudo cargar la lista de alertas</strong>
        <p>
          Los contadores de arriba pueden ser de una carga anterior. Pulsa
          Actualizar; si se repite, el motivo está en el log de la API.
        </p>
      </div>
    </div>

    <div v-else-if="!alertas.length" class="estado superficie">
      <Icono nombre="check" :tamano="18" />
      <div>
        <strong>Ninguna alerta con estos filtros</strong>
        <p>
          No es lo mismo que «no hay riesgo»: es que en los últimos
          {{ filtroDias }} días no hay ninguna notificación de la severidad
          seleccionada.
        </p>
      </div>
    </div>

    <!-- ================= Lista ================= -->
    <div v-else class="lista">
      <article
        v-for="alerta in alertas"
        :key="alerta.alert_id"
        class="alerta"
        :class="`sev-${alerta.severity_label}`"
      >
        <!-- La barra de severidad. Es un elemento propio y no un `border-left`
             para que ocupe el alto completo de la fila aunque la descripción
             sea de una sola línea. -->
        <div class="alerta-barra" aria-hidden="true"></div>

        <div class="alerta-sev">
          <span class="sev-rotulo">
            {{ NOMBRE_SEV[alerta.severity_label] || alerta.severity_label }}
          </span>
          <span class="sev-fuente codigo">{{ alerta.fuente.toUpperCase() }}</span>
        </div>

        <div class="alerta-cuerpo">
          <h2 :title="alerta.producto_nombre">{{ alerta.producto_nombre }}</h2>
          <!--
            El texto del riesgo viene de la fuente y está en inglés. `lang="en"`
            para que un lector de pantalla en español no lo pronuncie como si lo
            fuera; sin esto, «Listeria monocytogenes detected» sale ininteligible.
          -->
          <p class="alerta-desc recorte-2" lang="en" :title="alerta.riesgo_texto">
            {{ alerta.riesgo_texto }}
          </p>
        </div>

        <div class="alerta-riesgo">
          <span class="rotulo">Riesgo</span>
          <span class="riesgo-valor">{{ capitalizarPrimera(alerta.riesgo_categoria) }}</span>
          <span class="riesgo-meta">
            {{ alerta.pais_origen }} · hace {{ alerta.dias_desde }} días
          </span>
        </div>

        <!--
          El score va con su medidor. `role="img"` con etiqueta porque la barra
          sola no se puede leer, y la cifra ya está al lado en texto: la barra
          es para comparar de un vistazo entre filas.
        -->
        <div v-if="alerta.severity_score" class="alerta-score">
          <span class="score-cifra num">{{ alerta.severity_score.toFixed(1) }}</span>
          <span
            class="score-barra"
            role="img"
            :aria-label="`Severidad ${alerta.severity_score.toFixed(1)} sobre 5`"
          >
            <span
              class="score-relleno"
              :style="{ width: (alerta.severity_score / 5) * 100 + '%' }"
            ></span>
          </span>
        </div>
        <div v-else class="alerta-score">
          <span class="sin-dato">sin score</span>
        </div>

        <div class="alerta-acciones no-imprimir">
          <button
            type="button"
            class="btn btn--secundario btn--pequeno"
            @click="mostrarDetalle(alerta)"
          >
            Detalles
          </button>
          <a :href="alerta.url_oficial" target="_blank" rel="noopener" class="enlace-fuente">
            Fuente oficial <Icono nombre="externo" :tamano="12" />
          </a>
        </div>
      </article>
    </div>

    <!-- ================= Detalle ================= -->
    <div v-if="alertaSeleccionada" class="modal-fondo no-imprimir" @click.self="cerrarDetalle">
      <div
        class="modal superficie"
        role="dialog"
        aria-modal="true"
        tabindex="-1"
        :aria-label="alertaSeleccionada.producto_nombre"
      >
        <header class="modal-cabecera">
          <div class="modal-titulo">
            <span
              class="severidad"
              :class="`severidad--${claseSev(alertaSeleccionada.severity_label)}`"
            >
              {{ NOMBRE_SEV[alertaSeleccionada.severity_label] || alertaSeleccionada.severity_label }}
            </span>
            <h4>{{ alertaSeleccionada.producto_nombre }}</h4>
            <p class="modal-sub codigo">
              {{ alertaSeleccionada.fuente.toUpperCase() }} ·
              {{ alertaSeleccionada.alert_id }}
            </p>
          </div>
          <button class="modal-cerrar" aria-label="Cerrar" @click="cerrarDetalle">
            <Icono nombre="equis" :tamano="17" />
          </button>
        </header>

        <div class="modal-cuerpo">
          <section>
            <h5>Descripción del riesgo</h5>
            <p class="riesgo-texto" lang="en">{{ alertaSeleccionada.riesgo_texto }}</p>
          </section>

          <dl class="detalles">
            <template v-for="d in detalles" :key="d.etiqueta">
              <dt>{{ d.etiqueta }}</dt>
              <dd :class="{ codigo: d.codigo }">
                <span v-if="d.valor">{{ d.valor }}</span>
                <span v-else class="sin-dato">sin dato</span>
              </dd>
            </template>
          </dl>
        </div>

        <footer class="modal-pie">
          <a
            :href="alertaSeleccionada.url_oficial"
            target="_blank"
            rel="noopener"
            class="btn btn--secundario btn--pequeno"
          >
            Abrir en {{ alertaSeleccionada.fuente.toUpperCase() }}
            <Icono nombre="externo" :tamano="13" />
          </a>
          <span class="modal-nota">
            El texto y la clasificación son los de la fuente oficial. Aquí no se
            reinterpretan ni se traducen.
          </span>
        </footer>
      </div>
    </div>
  </div>
</template>

<script setup>
// Las llamadas pasan por el cliente de api.js y no por fetch directo: es el
// unico sitio que adjunta el token y el que cierra la sesion ante un 401.
//
// Este componente venia escrito para Vue CLI (process.env.VUE_APP_*, puerto
// 8000, clave de token "token"). Nada de eso existe aqui: el bundler es Vite,
// la API escucha en 8001 y el token se guarda en `agroscout_token`. Tal cual
// estaba, reventaba al montarlo con "process is not defined".
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'
import Icono from './Icono.vue'

const SEVERIDADES = [
  { valor: '', nombre: 'Todas' },
  { valor: 'critical', nombre: 'Crítica' },
  { valor: 'high', nombre: 'Alta' },
  { valor: 'medium', nombre: 'Media' },
  { valor: 'low', nombre: 'Baja' },
]

// Los nombres, sin emoji. El color lo pone la barra de la izquierda y el
// rótulo se lee igual en gris.
const NOMBRE_SEV = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
}

const CLASE_SEV = {
  critical: 'critica',
  high: 'alta',
  medium: 'media',
  low: 'baja',
}

const alertas = ref([])
const cargando = ref(false)
const error = ref(false)
const alertaSeleccionada = ref(null)
const estadisticas = ref({
  total_alertas: 0,
  alertas_criticas: 0,
  alertas_activas_90d: 0,
  ultima_actualizacion: null,
})

const filtroSeveridad = ref('')
const filtroDias = ref(90)
const filtroLimite = ref(50)

const claseSev = (label) => CLASE_SEV[label] || 'baja'

const cargarAlertas = async () => {
  cargando.value = true
  error.value = false

  try {
    const data = await api.alertasActivas({
      limite: filtroLimite.value,
      dias: filtroDias.value,
      severidad: filtroSeveridad.value,
    })

    alertas.value = data.alertas
    // Las tarjetas de arriba NO se rellenan desde aqui. Los conteos que
    // devuelve /activas son los de la pagina ya filtrada y recortada por
    // el limite, asi que al filtrar por "critical" las tarjetas pasaban a
    // mostrar el total de lo filtrado en vez del global. Los totales
    // buenos salen de /estadisticas/resumen.
  } catch (e) {
    console.error('Error cargando alertas:', e)
    alertas.value = []
    // Antes esto dejaba la lista vacía y nada más, así que un fallo de red se
    // veía exactamente igual que «no hay alertas». Son dos mensajes opuestos:
    // uno dice que todo está en orden y el otro que no sabemos si lo está.
    error.value = true
  } finally {
    cargando.value = false
  }
}

const cargarEstadisticas = async () => {
  try {
    estadisticas.value = await api.estadisticasAlertas()
  } catch (e) {
    console.error('Error cargando estadísticas:', e)
  }
}

const ponerSeveridad = (valor) => {
  filtroSeveridad.value = valor
  cargarAlertas()
}

const mostrarDetalle = async (alerta) => {
  try {
    alertaSeleccionada.value = await api.alertaDetalle(alerta.alert_id)
  } catch (e) {
    console.error('Error cargando detalles:', e)
  }
}

const cerrarDetalle = () => {
  alertaSeleccionada.value = null
}

const capitalizarPrimera = (str) =>
  str ? str.charAt(0).toUpperCase() + str.slice(1) : ''

const formatearFecha = (fechaStr) => {
  if (!fechaStr) return ''
  const fecha = new Date(fechaStr)
  return fecha.toLocaleDateString('es-ES', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Los campos del detalle, en una tabla.
 *
 * Antes eran doce bloques `<div class="detalle-item">` escritos a mano, cada
 * uno con su `v-if`, y los que faltaban desaparecían: el hueco se cerraba y no
 * quedaba forma de saber si el campo no venía o si nadie lo había puesto. Aquí
 * se recorren siempre los mismos y los vacíos dicen «sin dato».
 */
const detalles = computed(() => {
  const a = alertaSeleccionada.value
  if (!a) return []
  return [
    { etiqueta: 'Categoría de riesgo', valor: capitalizarPrimera(a.riesgo_categoria) },
    { etiqueta: 'Fecha emitida', valor: formatearFecha(a.fecha_emitida) },
    { etiqueta: 'Días desde', valor: a.dias_desde != null ? `${a.dias_desde} días` : '' },
    { etiqueta: 'País de origen', valor: a.pais_origen },
    { etiqueta: 'País de destino', valor: a.pais_destino },
    { etiqueta: 'Empresa', valor: a.empresa },
    { etiqueta: 'Referencia', valor: a.reference_number, codigo: true },
    {
      etiqueta: 'Severidad',
      valor: a.severity_score != null ? `${a.severity_score.toFixed(1)} / 5` : '',
    },
  ]
})

onMounted(() => {
  cargarAlertas()
  cargarEstadisticas()
})
</script>

<style scoped>
.alertas {
  max-width: 1180px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------------------------------------------------------------- *
 *  Cabecera
 * ---------------------------------------------------------------- */

.cabecera {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 32px;
  flex-wrap: wrap;
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 0.69rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--verde-texto);
}

.cabecera h1 {
  margin: 0;
  font-size: 2rem;
}

.entradilla {
  margin: 8px 0 0;
  max-width: 62ch;
  font-size: 0.9375rem;
  color: var(--texto-atenuado);
}

.contadores {
  display: flex;
  gap: 28px;
  margin: 0;
}

.contadores div { text-align: right; }

.contadores dt {
  font-size: 0.66rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-weight: 700;
  color: var(--texto-sin-dato);
  margin-bottom: 2px;
}

.contadores dd { margin: 0; }

/* Los contadores no llevan tarjeta ni gradiente: son tres números, y una
   tarjeta alrededor de un número solo añade borde. */
.cifra.critica { color: var(--sev-critica); }
.cifra.alta    { color: var(--sev-alta); }

.actualizado {
  margin: -8px 0 0;
  font-size: 0.78rem;
  color: var(--texto-sin-dato);
}

.actualizado strong { color: var(--texto-atenuado); font-weight: 600; }

/* ---------------------------------------------------------------- *
 *  Filtros
 * ---------------------------------------------------------------- */

.filtros {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  padding: 12px 14px;
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  background: var(--superficie);
}

.punto {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex: none;
}

.punto--todas    { background: var(--texto-tenue); }
.punto--critical { background: var(--sev-critica); }
.punto--high     { background: var(--sev-alta); }
.punto--medium   { background: var(--sev-media); }
.punto--low      { background: var(--sev-baja); }

.separador {
  width: 1px;
  height: 22px;
  background: var(--borde);
  margin: 0 4px;
}

.campo-en-linea {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}

.campo-en-linea select { font-size: 0.82rem; padding: 6px 10px; }

.cuenta {
  margin-left: auto;
  font-size: 0.82rem;
  color: var(--texto-atenuado);
}

.cuenta b { color: var(--tinta); }

/* ---------------------------------------------------------------- *
 *  Estados
 * ---------------------------------------------------------------- */

.estado {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 22px;
  font-size: 0.9375rem;
  color: var(--texto-atenuado);
}

.estado strong { display: block; color: var(--tinta); }
.estado p { margin: 3px 0 0; font-size: 0.85rem; }

.estado--error {
  align-items: flex-start;
  border-color: var(--critico-borde);
  background: var(--critico-fondo);
  color: var(--critico);
}

.estado--error strong { color: var(--critico); }
.estado--error p { color: var(--texto-atenuado); }

.barra {
  flex: none;
  display: block;
  width: 90px;
  height: 4px;
  border-radius: 999px;
  background: #EEF1EF;
  overflow: hidden;
}

.barra-barrido {
  display: block;
  width: 33%;
  height: 100%;
  border-radius: 999px;
  background: var(--verde);
  animation: ags-barrido 1.4s ease-in-out infinite;
}

/* ---------------------------------------------------------------- *
 *  Lista
 * ---------------------------------------------------------------- */

.lista {
  display: grid;
  gap: 8px;
}

/*
  Rejilla de anchos fijos salvo la descripción, que es la que se estira. Con
  todas las columnas fluidas, la de severidad cambiaba de ancho según el texto
  y los rótulos dejaban de alinearse entre filas, que es lo único que hace que
  esta lista se pueda barrer en vertical.
*/
.alerta {
  display: grid;
  grid-template-columns: 5px 128px 1fr 172px 84px 128px;
  align-items: stretch;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  overflow: hidden;
  transition: border-color 0.15s;
}

.alerta:hover { border-color: var(--borde-fuerte); }

.alerta-barra { background: var(--borde-medio); }

.sev-critical .alerta-barra { background: var(--sev-critica); }
.sev-high     .alerta-barra { background: var(--sev-alta); }
.sev-medium   .alerta-barra { background: var(--sev-media); }
.sev-low      .alerta-barra { background: var(--sev-baja); }

.alerta-sev {
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  padding: 14px 16px;
  border-right: 1px solid var(--borde-suave);
}

.sev-rotulo {
  font-size: 0.72rem;
  font-weight: 750;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.sev-critical .sev-rotulo { color: var(--sev-critica); }
.sev-high     .sev-rotulo { color: var(--sev-alta); }
.sev-medium   .sev-rotulo { color: var(--sev-media); }
.sev-low      .sev-rotulo { color: var(--sev-baja); }

.sev-fuente {
  font-size: 0.66rem;
  letter-spacing: 0.04em;
  color: var(--texto-sin-dato);
}

.alerta-cuerpo {
  padding: 14px 18px;
  min-width: 0;
}

.alerta-cuerpo h2 {
  margin: 0 0 4px;
  font-size: 0.9375rem;
  font-weight: 700;
  letter-spacing: -0.008em;
  line-height: 1.3;
}

.alerta-desc {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: var(--texto-atenuado);
}

.alerta-riesgo {
  display: flex;
  flex-direction: column;
  gap: 3px;
  justify-content: center;
  padding: 14px 16px;
  border-left: 1px solid var(--borde-suave);
  min-width: 0;
}

.riesgo-valor {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--texto);
}

.riesgo-meta {
  font-size: 0.75rem;
  color: var(--texto-sin-dato);
}

.alerta-score {
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  align-items: center;
  padding: 14px 10px;
  border-left: 1px solid var(--borde-suave);
}

.score-cifra {
  font-size: 1.125rem;
  font-weight: 750;
  color: var(--tinta);
}

.score-barra {
  display: block;
  width: 56px;
  height: 4px;
  border-radius: 999px;
  background: #EEF1EF;
  overflow: hidden;
}

.score-relleno {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--borde-medio);
}

.sev-critical .score-relleno { background: var(--sev-critica); }
.sev-high     .score-relleno { background: var(--sev-alta); }
.sev-medium   .score-relleno { background: var(--sev-media); }
.sev-low      .score-relleno { background: var(--sev-baja); }

.alerta-acciones {
  display: flex;
  flex-direction: column;
  gap: 6px;
  justify-content: center;
  padding: 14px;
  border-left: 1px solid var(--borde-suave);
  background: var(--superficie-sutil);
}

.enlace-fuente {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--texto-atenuado);
  text-decoration: none;
}

.enlace-fuente:hover { color: var(--verde-texto); }

/* ---------------------------------------------------------------- *
 *  Detalle
 * ---------------------------------------------------------------- */

.modal-fondo {
  position: fixed;
  inset: 0;
  z-index: 50;
  background: rgba(15, 21, 18, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal {
  width: 100%;
  max-width: 600px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--sombra-elevada);
}

.modal-cabecera {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px 22px 16px;
  border-bottom: 1px solid var(--borde-suave);
}

.modal-titulo { flex: 1; min-width: 0; }
.modal-titulo h4 { margin: 6px 0 3px; font-size: 1.0625rem; line-height: 1.3; }
.modal-sub { margin: 0; font-size: 0.72rem; color: var(--texto-sin-dato); }

.modal-cerrar {
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: var(--r-xs);
  border: 1px solid transparent;
  background: transparent;
  color: var(--texto-atenuado);
  cursor: pointer;
}

.modal-cerrar:hover { background: var(--lienzo); color: var(--tinta); }

.modal-cuerpo {
  overflow-y: auto;
  padding: 18px 22px;
  display: grid;
  gap: 18px;
}

.modal-cuerpo h5 {
  margin: 0 0 8px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.riesgo-texto {
  margin: 0;
  font-size: 0.875rem;
  line-height: 1.6;
  color: var(--texto);
}

.detalles {
  display: grid;
  grid-template-columns: minmax(140px, auto) 1fr;
  gap: 0;
  margin: 0;
}

.detalles dt,
.detalles dd {
  margin: 0;
  padding: 9px 0;
  border-bottom: 1px solid var(--borde-suave);
  font-size: 0.85rem;
}

.detalles dt { color: var(--texto-atenuado); padding-right: 16px; }
.detalles dd { color: var(--tinta); font-weight: 600; }

.modal-pie {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  padding: 14px 22px;
  border-top: 1px solid var(--borde-suave);
  background: var(--superficie-sutil);
}

.modal-nota {
  flex: 1;
  min-width: 200px;
  font-size: 0.72rem;
  line-height: 1.5;
  color: var(--texto-sin-dato);
}

/* ---------------------------------------------------------------- *
 *  Estrecho
 * ---------------------------------------------------------------- */

/*
  Por debajo de 1080 px la rejilla de seis columnas deja la descripción en 90 px
  y el nombre del producto en cuatro líneas. Se apila: la barra de severidad
  pasa a ser un filo superior y cada bloque ocupa el ancho.
*/
@media (max-width: 1080px) {
  .alerta {
    grid-template-columns: 1fr auto;
    grid-template-areas:
      'barra  barra'
      'sev    score'
      'cuerpo cuerpo'
      'riesgo riesgo'
      'acc    acc';
  }

  .alerta-barra   { grid-area: barra; height: 4px; }
  .alerta-sev     { grid-area: sev; flex-direction: row; align-items: center; gap: 10px; border-right: 0; }
  .alerta-cuerpo  { grid-area: cuerpo; padding-top: 0; }
  .alerta-riesgo  { grid-area: riesgo; border-left: 0; border-top: 1px solid var(--borde-suave); }
  .alerta-score   { grid-area: score; flex-direction: row; gap: 8px; border-left: 0; }
  .alerta-acciones {
    grid-area: acc;
    flex-direction: row;
    border-left: 0;
    border-top: 1px solid var(--borde-suave);
  }

  .alerta-desc { -webkit-line-clamp: 4; line-clamp: 4; }
}

@media (max-width: 760px) {
  .cabecera { gap: 18px; }
  .contadores { gap: 20px; }
  .contadores div { text-align: left; }
  .cuenta { margin-left: 0; }
  .modal-fondo { padding: 0; align-items: flex-end; }
  .modal { max-width: none; max-height: 92vh; border-radius: var(--r-lg) var(--r-lg) 0 0; }
}
</style>
