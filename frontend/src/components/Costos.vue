<template>
  <div class="costos viz-root">
    <header class="cabecera">
      <div>
        <h2>Costes</h2>
        <p class="sub">En qué se va el dinero. Últimos {{ dias }} días.</p>
      </div>
      <div class="acciones">
        <select v-model.number="dias" @change="cargar">
          <option :value="7">7 días</option>
          <option :value="30">30 días</option>
          <option :value="90">90 días</option>
          <option :value="365">1 año</option>
        </select>
        <button class="btn" :disabled="cargando" @click="cargar">Actualizar</button>
      </div>
    </header>

    <p v-if="error" class="aviso error">{{ error }}</p>
    <div v-else-if="!datos" class="vacio">Cargando…</div>

    <template v-else>
      <!-- Mes en curso y cuota -->
      <section class="tarjeta">
        <div class="kpis">
          <div class="hero">
            <span class="hero-num">${{ datos.mes.costo_usd.toFixed(4) }}</span>
            <span class="hero-etq">gastado este mes</span>
          </div>
          <div class="tiles">
            <div class="tile">
              <span class="valor">{{ datos.mes.runs }}</span>
              <span class="etq">consultas del mes</span>
            </div>
            <div class="tile">
              <span class="valor">${{ datos.mes.proyeccion_cierre_usd.toFixed(4) }}</span>
              <span class="etq">proyección de cierre</span>
            </div>
            <div class="tile">
              <span class="valor">${{ datos.mes.tope_global_usd.toFixed(2) }}</span>
              <span class="etq">tope global del mes</span>
            </div>
          </div>
        </div>

        <div class="cuota">
          <div class="pista-cuota">
            <span class="usado" :class="nivelCuota" :style="{ width: anchoCuota + '%' }"></span>
            <!-- La proyección se marca sobre la misma pista: lo que importa no
                 es sólo cuánto se lleva gastado, sino si al ritmo actual se va
                 a pasar del tope antes de que acabe el mes. -->
            <span v-if="marcaProyeccion !== null" class="marca"
                  :style="{ left: marcaProyeccion + '%' }"
                  :title="`Proyección de cierre: $${datos.mes.proyeccion_cierre_usd.toFixed(4)}`"></span>
          </div>
          <p class="pie-cuota">
            <template v-if="datos.mes.pct_del_tope !== null">
              {{ datos.mes.pct_del_tope }} % del tope · la marca es la proyección
              de cierre
              <strong v-if="proyeccionSePasa" class="alerta">
                — al ritmo actual se supera el tope
              </strong>
            </template>
            <template v-else>
              Sin tope configurado: no se puede calcular el porcentaje.
            </template>
          </p>
        </div>
      </section>

      <!-- Serie diaria -->
      <section class="tarjeta">
        <div class="cab-bloque">
          <h3>Gasto por día</h3>
          <button class="btn-sm" @click="exportar('serie')">CSV</button>
        </div>

        <div v-if="maxDia > 0" class="serie">
          <div class="dia" v-for="d in datos.serie" :key="d.dia">
            <div class="columna">
              <span class="barra-v" :style="{ height: altura(d.costo_usd) + 'px' }"
                    :title="tituloDia(d)"></span>
            </div>
            <span class="fecha">{{ d.dia.slice(5) }}</span>
          </div>
        </div>
        <p v-else class="nota">Sin gasto registrado en el periodo.</p>

        <details class="tabla-vista">
          <summary>Ver como tabla</summary>
          <table>
            <thead>
              <tr><th>Día</th><th class="num">Consultas</th><th class="num">Coste</th><th class="num">Tokens</th></tr>
            </thead>
            <tbody>
              <tr v-for="d in datos.serie" :key="d.dia">
                <td>{{ d.dia }}</td>
                <td class="num">{{ d.runs }}</td>
                <td class="num">${{ d.costo_usd.toFixed(6) }}</td>
                <td class="num">{{ d.tokens }}</td>
              </tr>
            </tbody>
          </table>
        </details>
      </section>

      <!-- Reparto por etapa -->
      <section class="tarjeta">
        <div class="cab-bloque">
          <h3>Reparto por etapa</h3>
          <button class="btn-sm" @click="exportar('etapa')">CSV</button>
        </div>

        <template v-if="etapasConCoste.length">
          <!-- Barra apilada y no una tarta: con seis porciones la tarta obliga
               a comparar ángulos. -->
          <div class="apilada" role="img" :aria-label="etiquetaEtapas">
            <div v-for="e in etapasConCoste" :key="e.etapa" class="seg"
                 :style="{ flexGrow: e.costo_usd, background: color(e.etapa) }"
                 :title="`Etapa ${e.etapa}: $${e.costo_usd.toFixed(6)}`"></div>
          </div>
          <!-- Etiquetas directas: el color no puede ser el único portador del
               dato, y varios tonos quedan por debajo de 3:1 sobre el blanco. -->
          <ul class="leyenda">
            <li v-for="e in etapasConCoste" :key="e.etapa">
              <span class="punto" :style="{ background: color(e.etapa) }" aria-hidden="true"></span>
              Etapa {{ e.etapa }} <b>${{ e.costo_usd.toFixed(6) }}</b>
              ({{ pctEtapa(e.costo_usd) }} %)
            </li>
          </ul>
        </template>
        <p v-else class="nota">Ninguna etapa registró coste en el periodo.</p>

        <!-- Que una etapa cueste 0 no significa que no se ejecutara: la caché
             la sirve gratis. Sin esta tabla, "etapa 4: $0" se lee como "la
             etapa 4 no se ejecuta", que es una conclusión falsa y cara. -->
        <table class="tabla">
          <thead>
            <tr><th>Etapa</th><th class="num">Veces</th><th class="num">De caché</th><th class="num">Coste</th><th class="num">Tokens</th></tr>
          </thead>
          <tbody>
            <tr v-for="e in datos.por_etapa" :key="e.etapa">
              <td>{{ e.etapa }}</td>
              <td class="num">{{ e.veces }}</td>
              <td class="num">{{ e.cache_hits }}</td>
              <td class="num">${{ e.costo_usd.toFixed(6) }}</td>
              <td class="num">{{ e.tokens }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Por usuario -->
      <section class="tarjeta">
        <div class="cab-bloque">
          <h3>Por usuario</h3>
          <button class="btn-sm" @click="exportar('usuario')">CSV</button>
        </div>
        <div class="barras">
          <div class="fila" v-for="u in datos.por_usuario" :key="u.usuario_id">
            <span class="nombre" :title="u.email || u.usuario_id">
              {{ u.email || '(sin perfil)' }}
              <em class="plan">{{ u.plan }}</em>
            </span>
            <span class="pista">
              <span class="barra" :style="{ width: anchoUsuario(u.costo_usd) + '%' }"></span>
            </span>
            <span class="num">${{ u.costo_usd.toFixed(6) }}</span>
            <span class="num runs">{{ u.runs }} runs</span>
          </div>
        </div>
      </section>

      <!-- Por estado -->
      <section class="tarjeta">
        <div class="cab-bloque">
          <h3>Cómo cerraron las consultas</h3>
          <button class="btn-sm" @click="exportar('estado')">CSV</button>
        </div>
        <p class="sub">
          Un run parcial gasta menos, pero también entrega menos. Aquí se ve si
          el ahorro viene de la caché o de que se están degradando.
        </p>
        <div class="barras">
          <div class="fila" v-for="e in datos.por_estado" :key="e.motivo">
            <span class="nombre">{{ nombreMotivo(e.motivo) }}</span>
            <span class="pista">
              <span class="barra" :style="{ width: anchoEstado(e.runs) + '%' }"></span>
            </span>
            <span class="num">{{ e.runs }}</span>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const ALTURA_MAXIMA = 90

// Los tres primeros son los de PromocionesDashboard (paleta categórica
// validada). Los otros tres extienden la serie para las seis etapas; se usan
// SIEMPRE con etiqueta directa al lado, así que el contraste del tono no es lo
// único que distingue una etapa de otra.
const COLORES = ['#2a78d6', '#eb6834', '#1baf7a', '#8b5cf6', '#d4a017', '#64748b']

const NOMBRES_MOTIVO = {
  ok: 'Completas',
  presupuesto: 'Degradadas por presupuesto',
  pocos_productos: 'Degradadas por falta de datos',
  paywall: 'Limitadas por el plan',
  error: 'Con error',
  sin_estado: 'Sin estado registrado',
}

const datos = ref(null)
const dias = ref(30)
const cargando = ref(false)
const error = ref('')

const orden = computed(() => datos.value?.por_etapa.map((e) => e.etapa) || [])
const color = (etapa) => COLORES[orden.value.indexOf(etapa) % COLORES.length]

const etapasConCoste = computed(
  () => datos.value?.por_etapa.filter((e) => e.costo_usd > 0) || [])

const totalEtapas = computed(
  () => etapasConCoste.value.reduce((s, e) => s + e.costo_usd, 0))

const maxDia = computed(
  () => Math.max(0, ...(datos.value?.serie.map((d) => d.costo_usd) || [0])))

const maxUsuario = computed(
  () => Math.max(0, ...(datos.value?.por_usuario.map((u) => u.costo_usd) || [0])))

const maxEstado = computed(
  () => Math.max(0, ...(datos.value?.por_estado.map((e) => e.runs) || [0])))

const altura = (v) => (maxDia.value > 0 ? Math.max(2, (v / maxDia.value) * ALTURA_MAXIMA) : 0)
const anchoUsuario = (v) => (maxUsuario.value > 0 ? Math.max(1, (v / maxUsuario.value) * 100) : 0)
const anchoEstado = (v) => (maxEstado.value > 0 ? Math.max(1, (v / maxEstado.value) * 100) : 0)
const pctEtapa = (v) => (totalEtapas.value > 0 ? ((v / totalEtapas.value) * 100).toFixed(1) : '0.0')

const anchoCuota = computed(() => {
  const m = datos.value?.mes
  if (!m || !m.tope_global_usd) return 0
  // Se recorta al 100 %: una barra que se sale de su pista no dice "nos hemos
  // pasado", dice que la pantalla está rota. Que se ha superado lo dice el
  // color y el porcentaje del pie.
  return Math.min(100, (m.costo_usd / m.tope_global_usd) * 100)
})

const nivelCuota = computed(() => {
  const pct = datos.value?.mes.pct_del_tope
  if (pct === null || pct === undefined) return ''
  if (pct >= 100) return 'agotada'
  if (pct >= 80) return 'cerca'
  return ''
})

const marcaProyeccion = computed(() => {
  const m = datos.value?.mes
  if (!m || !m.tope_global_usd) return null
  const pct = (m.proyeccion_cierre_usd / m.tope_global_usd) * 100
  return pct > 100 ? null : pct    // fuera de la pista no se puede dibujar
})

const proyeccionSePasa = computed(() => {
  const m = datos.value?.mes
  return Boolean(m?.tope_global_usd && m.proyeccion_cierre_usd > m.tope_global_usd)
})

const etiquetaEtapas = computed(() => etapasConCoste.value
  .map((e) => `Etapa ${e.etapa}: ${pctEtapa(e.costo_usd)} %`).join('; '))

const nombreMotivo = (m) => NOMBRES_MOTIVO[m] || m

const tituloDia = (d) =>
  `${d.dia}: $${d.costo_usd.toFixed(6)} · ${d.runs} consultas · ${d.tokens} tokens`

async function cargar() {
  cargando.value = true
  error.value = ''
  try {
    datos.value = await api.costos(dias.value)
  } catch (e) {
    error.value = `No se pudieron cargar los costes: ${e.message}`
  } finally {
    cargando.value = false
  }
}

async function exportar(detalle) {
  try {
    const { blob } = await api.exportarCostos(detalle, dias.value)
    const url = URL.createObjectURL(blob)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = `costos-${detalle}-${dias.value}d.csv`
    enlace.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = `No se pudo exportar: ${e.message}`
  }
}

onMounted(cargar)
</script>

<style scoped>
.costos { padding: 0 0 40px; }

.cabecera {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

h2 { margin: 0 0 4px; }
h3 { margin: 0; font-size: 1rem; }

.sub { margin: 0; color: var(--texto-atenuado); font-size: 0.9rem; }

.acciones { display: flex; gap: 8px; }

.tarjeta {
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.cab-bloque {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

select, .btn, .btn-sm {
  background: var(--superficie);
  color: var(--texto);
  border: 1px solid var(--borde);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 6px 12px;
}

.btn-sm { padding: 4px 10px; font-size: 0.78rem; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.aviso { padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; }
.aviso.error { background: var(--critico-fondo); color: var(--critico); }

.vacio, .nota { padding: 16px 0; color: var(--texto-atenuado); font-size: 0.9rem; }

/* -- KPIs y cuota -------------------------------------------------------- */

.kpis { display: flex; gap: 32px; align-items: center; flex-wrap: wrap; }

.hero { display: flex; flex-direction: column; }
.hero-num { font-size: 2rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.hero-etq { font-size: 0.82rem; color: var(--texto-atenuado); }

.tiles { display: flex; gap: 24px; flex-wrap: wrap; }
.tile { display: flex; flex-direction: column; }
.tile .valor { font-size: 1.1rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.tile .etq { font-size: 0.76rem; color: var(--texto-atenuado); }

.cuota { margin-top: 20px; }

.pista-cuota {
  position: relative;
  height: 12px;
  border-radius: 999px;
  background: rgba(108, 117, 125, 0.16);
  overflow: visible;
}

.usado {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: var(--verde);
}

.usado.cerca { background: var(--aviso); }
.usado.agotada { background: var(--critico); }

.marca {
  position: absolute;
  top: -3px;
  width: 2px;
  height: 18px;
  background: var(--texto);
}

.pie-cuota { margin: 8px 0 0; font-size: 0.82rem; color: var(--texto-atenuado); }
.alerta { color: var(--critico); }

/* -- Serie diaria -------------------------------------------------------- */

.serie {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  overflow-x: auto;
  padding-bottom: 4px;
}

.dia { display: flex; flex-direction: column; align-items: center; gap: 4px; min-width: 22px; }

.columna {
  display: flex;
  flex-direction: column-reverse;
  height: 90px;
  width: 100%;
  justify-content: flex-start;
}

.barra-v { display: block; width: 100%; background: var(--verde); border-radius: 2px 2px 0 0; }

.fecha { font-size: 0.62rem; color: var(--texto-atenuado); white-space: nowrap; }

/* -- Barra apilada ------------------------------------------------------- */

.apilada { display: flex; gap: 2px; height: 20px; margin-bottom: 10px; }
.seg { border-radius: 3px; min-width: 3px; }

.leyenda {
  list-style: none;
  margin: 0 0 14px;
  padding: 0;
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 0.82rem;
}

.leyenda li { display: flex; align-items: center; gap: 6px; }

.punto { width: 9px; height: 9px; border-radius: 2px; flex-shrink: 0; }

/* -- Barras horizontales ------------------------------------------------- */

.barras { display: flex; flex-direction: column; gap: 8px; }

.fila { display: flex; align-items: center; gap: 10px; font-size: 0.85rem; }

.nombre {
  width: 230px;
  flex-shrink: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan {
  font-style: normal;
  font-size: 0.72rem;
  color: var(--texto-atenuado);
  margin-left: 6px;
}

.pista { flex: 1; height: 10px; background: rgba(108, 117, 125, 0.14); border-radius: 999px; }
.barra { display: block; height: 100%; background: var(--verde); border-radius: 999px; }

.num { font-variant-numeric: tabular-nums; text-align: right; min-width: 78px; }
.num.runs { min-width: 68px; color: var(--texto-atenuado); font-size: 0.8rem; }

/* -- Tablas -------------------------------------------------------------- */

.tabla, .tabla-vista table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }

.tabla th, .tabla-vista th {
  text-align: left;
  padding: 7px 10px;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
  border-bottom: 1px solid var(--borde);
}

.tabla td, .tabla-vista td {
  padding: 7px 10px;
  border-bottom: 1px solid rgba(45, 151, 102, 0.1);
}

.tabla th.num, .tabla td.num, .tabla-vista th.num, .tabla-vista td.num { text-align: right; }

.tabla-vista { margin-top: 14px; }

.tabla-vista summary {
  cursor: pointer;
  font-size: 0.82rem;
  color: var(--texto-atenuado);
  margin-bottom: 8px;
}

@media (max-width: 700px) {
  .nombre { width: 130px; }
  .kpis { gap: 20px; }
}
</style>
