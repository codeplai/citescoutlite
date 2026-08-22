<template>
  <section class="dashboard viz-root">
    <header class="cab">
      <h3>Promociones · últimas {{ horas }} h</h3>
      <button class="btn-sm" :disabled="cargando" @click="cargar">Actualizar</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div v-else-if="!datos" class="vacio">Cargando…</div>

    <template v-else>
      <!-- Cifra principal + fila de KPI. Un numero solo no es un grafico. -->
      <div class="kpis">
        <div class="hero">
          <span class="hero-num">{{ datos.resumen.pct_auto }}<span class="pct">%</span></span>
          <span class="hero-etq">automáticas</span>
        </div>
        <div class="tiles">
          <div class="tile" v-for="k in kpis" :key="k.clave">
            <span class="punto" :style="{ background: k.color }" aria-hidden="true"></span>
            <span class="valor">{{ k.valor }}</span>
            <span class="etq">{{ k.etiqueta }}</span>
          </div>
        </div>
      </div>

      <!-- Parte-todo: barra apilada, no un grafico de tarta. Con tres porciones
           la tarta obliga a comparar angulos; la barra se lee de un vistazo y
           deja sitio a las etiquetas. -->
      <div class="bloque" v-if="datos.resumen.total">
        <h4>Reparto</h4>
        <div class="apilada" role="img" :aria-label="etiquetaReparto">
          <!-- flex-grow y no width en %: con anchos al 100 % los huecos de
               2px se suman y el ultimo segmento se sale de la pista. Con
               flex-grow, el reparto ya descuenta los huecos. -->
          <div
            v-for="k in kpisConValor"
            :key="k.clave"
            class="seg"
            :style="{ flexGrow: k.valor, background: k.color }"
            :title="`${k.etiqueta}: ${k.valor}`"
          ></div>
        </div>
        <!-- Etiquetas directas: obligatorias porque uno de los tonos queda por
             debajo de 3:1 sobre el blanco de la tarjeta. El color no puede ser
             el unico portador del dato. -->
        <ul class="leyenda">
          <li v-for="k in kpisConValor" :key="k.clave">
            <span class="punto" :style="{ background: k.color }" aria-hidden="true"></span>
            {{ k.etiqueta }} <b>{{ k.valor }}</b> ({{ pct(k.valor) }} %)
          </li>
        </ul>
      </div>

      <div class="bloque" v-if="motivos.length">
        <h4>Motivos de rechazo</h4>
        <div class="barras">
          <div class="fila" v-for="m in motivos" :key="m.regla">
            <span class="nombre" :title="m.regla">{{ m.regla }}</span>
            <span class="pista">
              <span class="barra" :style="{ width: anchoMotivo(m.veces) + '%' }"></span>
            </span>
            <span class="num">{{ m.veces }}</span>
          </div>
        </div>
      </div>

      <div class="bloque">
        <h4>Últimos {{ dias }} días</h4>
        <div class="tendencia">
          <div class="dia" v-for="d in datos.tendencia" :key="d.dia">
            <div class="columna" :title="tituloDia(d)">
              <span
                v-for="k in kpis"
                :key="k.clave"
                class="seg-v"
                :style="{ height: alturaDia(d[k.clave]) + 'px', background: k.color }"
              ></span>
            </div>
            <span class="fecha">{{ d.dia.slice(5) }}</span>
          </div>
        </div>
        <p class="nota" v-if="maxDia === 0">Sin actividad registrada en el periodo.</p>
      </div>

      <details class="tabla-vista">
        <summary>Ver como tabla</summary>
        <table>
          <thead>
            <tr><th>Día</th><th>Automáticas</th><th>Manuales</th><th>Rechazadas</th></tr>
          </thead>
          <tbody>
            <tr v-for="d in datos.tendencia" :key="d.dia">
              <td>{{ d.dia }}</td><td>{{ d.auto }}</td>
              <td>{{ d.manual }}</td><td>{{ d.rechazadas }}</td>
            </tr>
          </tbody>
        </table>
      </details>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'

const props = defineProps({
  horas: { type: Number, default: 24 },
  dias: { type: Number, default: 7 },
})

const datos = ref(null)
const cargando = ref(false)
const error = ref('')

// Slots 1-3 de la paleta categorica validada (azul, naranja, aqua). El orden
// es el mecanismo de seguridad para daltonismo, no decoracion: se usan en
// orden y el mismo color significa lo mismo en los tres graficos.
const COLORES = { auto: '#2a78d6', manual: '#eb6834', rechazadas: '#1baf7a' }

const kpis = computed(() => [
  { clave: 'auto', etiqueta: 'Automáticas', color: COLORES.auto,
    valor: datos.value?.resumen.promovidos_auto ?? 0 },
  { clave: 'manual', etiqueta: 'Manuales', color: COLORES.manual,
    valor: datos.value?.resumen.promovidos_manual ?? 0 },
  { clave: 'rechazadas', etiqueta: 'Rechazadas', color: COLORES.rechazadas,
    valor: datos.value?.resumen.rechazados ?? 0 },
])

const kpisConValor = computed(() => kpis.value.filter((k) => k.valor > 0))

const total = computed(() => datos.value?.resumen.total ?? 0)

const pct = (n) => (total.value ? Math.round((n / total.value) * 1000) / 10 : 0)

const etiquetaReparto = computed(() =>
  kpis.value.map((k) => `${k.etiqueta}: ${k.valor}`).join(', '))

const motivos = computed(() =>
  Object.entries(datos.value?.resumen.motivos_de_rechazo ?? {})
    .map(([regla, veces]) => ({ regla, veces }))
    .sort((a, b) => b.veces - a.veces))

const maxMotivo = computed(() => Math.max(1, ...motivos.value.map((m) => m.veces)))
const anchoMotivo = (n) => Math.round((n / maxMotivo.value) * 100)

const maxDia = computed(() => Math.max(
  0, ...(datos.value?.tendencia ?? []).map((d) => d.auto + d.manual + d.rechazadas)))

// Altura en px dentro de una columna de 90. Se escala sobre 84 y no sobre 90
// para dejar sitio a los dos huecos de 2px entre los tres segmentos: con el
// dia mas alto al 100 % la columna se desbordaria por 4px.
//
// El minimo de 2px es para que un dia con un solo registro se vea; sin el,
// un 1 sobre 300 redondea a cero y el dato desaparece del grafico.
const ALTO_COLUMNA = 84

const alturaDia = (n) => {
  if (!n) return 0
  return Math.max(2, Math.round((n / Math.max(1, maxDia.value)) * ALTO_COLUMNA))
}

const tituloDia = (d) =>
  `${d.dia} · ${d.auto} auto, ${d.manual} manual, ${d.rechazadas} rechazadas`

const cargar = async () => {
  cargando.value = true
  error.value = ''
  try {
    datos.value = await api.estadisticasPromociones({
      horas: props.horas, dias: props.dias,
    })
  } catch (e) {
    error.value = `No se pudieron cargar las estadísticas: ${e.message}`
  } finally {
    cargando.value = false
  }
}

defineExpose({ cargar })
onMounted(cargar)
</script>

<style scoped>
.dashboard {
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 12px;
  padding: 18px 20px;
  margin-bottom: 24px;
}

.cab {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

h3 {
  margin: 0;
  font-size: 1rem;
}

h4 {
  margin: 0 0 8px;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--texto-atenuado);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.btn-sm {
  background: transparent;
  border: 1px solid var(--borde);
  color: var(--texto-atenuado);
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.8rem;
  cursor: pointer;
}

.error {
  background: rgba(208, 59, 59, 0.1);
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.9rem;
}

.vacio {
  color: var(--texto-atenuado);
  padding: 20px 0;
}

.kpis {
  display: flex;
  align-items: center;
  gap: 32px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

.hero {
  display: flex;
  flex-direction: column;
}

.hero-num {
  font-size: 3rem;
  font-weight: 700;
  line-height: 1;
  color: var(--texto);
}

.pct {
  font-size: 1.4rem;
  margin-left: 2px;
}

.hero-etq {
  font-size: 0.8rem;
  color: var(--texto-atenuado);
}

.tiles {
  display: flex;
  gap: 22px;
}

.tile {
  display: flex;
  flex-direction: column;
}

.tile .valor {
  font-size: 1.4rem;
  font-weight: 600;
}

.tile .etq {
  font-size: 0.75rem;
  color: var(--texto-atenuado);
}

.punto {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  margin-right: 5px;
}

.bloque {
  margin-bottom: 20px;
}

/* Barra apilada. El hueco de 2px entre segmentos los separa sin depender de
   que los colores contrasten entre si. */
.apilada {
  display: flex;
  gap: 2px;
  height: 14px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--lienzo);
}

.seg {
  height: 100%;
  flex-basis: 0;
  min-width: 3px; /* una porcion de 1 sobre 400 sigue siendo visible */
}

.leyenda {
  list-style: none;
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  padding: 0;
  margin: 8px 0 0;
  font-size: 0.82rem;
  color: var(--texto-atenuado);
}

.leyenda b {
  color: var(--texto);
}

.barras .fila {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 0.82rem;
}

.nombre {
  width: 170px;
  color: var(--texto-atenuado);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pista {
  flex: 1;
  background: var(--lienzo);
  border-radius: 4px;
  height: 10px;
}

.barra {
  display: block;
  height: 100%;
  background: var(--verde);
  border-radius: 4px;
}

.num {
  width: 28px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.tendencia {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  height: 110px;
}

.dia {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.columna {
  display: flex;
  flex-direction: column-reverse;
  justify-content: flex-start;
  gap: 2px;
  width: 100%;
  max-width: 34px;
  height: 90px;
}

.seg-v {
  width: 100%;
  border-radius: 2px;
}

.fecha {
  font-size: 0.7rem;
  color: var(--texto-atenuado);
  margin-top: 6px;
  font-variant-numeric: tabular-nums;
}

.nota {
  font-size: 0.8rem;
  color: var(--texto-atenuado);
  margin: 6px 0 0;
}

.tabla-vista {
  font-size: 0.82rem;
  color: var(--texto-atenuado);
}

.tabla-vista summary {
  cursor: pointer;
}

.tabla-vista table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}

.tabla-vista th,
.tabla-vista td {
  text-align: left;
  padding: 4px 6px;
  border-bottom: 1px solid var(--borde);
  font-variant-numeric: tabular-nums;
}
</style>
