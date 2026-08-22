<template>
  <div class="promociones">
    <header class="cabecera">
      <div>
        <h2>Promociones</h2>
        <p class="sub">
          Ofertas en cuarentena que esperan revisión · semana {{ semilla }}
        </p>
      </div>
    </header>

    <!-- S7.9. Las cifras viven en el widget, que ademas las grafica; tenerlas
         tambien aqui era dos sitios que pueden discrepar. -->
    <PromocionesDashboard ref="dashboard" />

    <div class="barra">
      <label class="filtro">
        <input type="checkbox" v-model="soloConErrores" @change="cargar" />
        Solo las que fallaron alguna regla
      </label>

      <div class="acciones-lote" v-if="seleccionadas.length">
        <span>{{ seleccionadas.length }} seleccionadas</span>
        <button class="btn primario" :disabled="ocupado" @click="promoverSeleccionadas">
          Promover seleccionadas
        </button>
      </div>

      <button class="btn" :disabled="ocupado" @click="cargar">Actualizar</button>
    </div>

    <p v-if="aviso" :class="['aviso', avisoTipo]">{{ aviso }}</p>

    <div v-if="cargando" class="vacio">Cargando…</div>
    <div v-else-if="!ofertas.length" class="vacio">
      Nada pendiente de revisión.
    </div>

    <table v-else class="tabla">
      <thead>
        <tr>
          <th class="col-check">
            <input type="checkbox" :checked="todasMarcadas" @change="alternarTodas" />
          </th>
          <th>Producto</th>
          <th>Precio</th>
          <th>Insumo</th>
          <th>En cuarentena</th>
          <th>Estado</th>
          <th class="col-acciones">Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="o in ofertas" :key="o.staging_id">
          <td>
            <input type="checkbox" :value="o.staging_id" v-model="seleccionadas" />
          </td>
          <td>
            <a :href="o.fuente_url" target="_blank" rel="noopener noreferrer">
              {{ o.producto?.nombre || '(sin nombre)' }}
            </a>
          </td>
          <td>{{ o.producto?.precio ?? '—' }}</td>
          <td>{{ o.insumo }}</td>
          <td :class="{ urgente: o.horas_en_cuarentena > 18 }">
            {{ o.horas_en_cuarentena }} h
          </td>
          <td>
            <span v-if="o.errores.length" class="motivos">
              <span v-for="e in o.errores" :key="e.regla" class="motivo" :title="e.motivo">
                {{ e.regla }}
              </span>
            </span>
            <span v-else-if="o.automatica === false" class="etiqueta">
              muestreo manual (20 %)
            </span>
            <span v-else class="etiqueta">sin revisar</span>
          </td>
          <td class="col-acciones">
            <button class="btn primario" :disabled="ocupado" @click="promover(o)">
              Promover
            </button>
            <button class="btn peligro" :disabled="ocupado" @click="rechazar(o)">
              Rechazar
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <section class="historial" v-if="historial.length">
      <h3>Historial (7 días)</h3>
      <ul>
        <li v-for="h in historial" :key="h.log_id">
          <span :class="['pill', h.resultado]">{{ h.resultado }}</span>
          <span class="pill tipo">{{ h.tipo }}</span>
          {{ h.producto || h.insumo || h.staging_id }}
          <span class="fecha">{{ formatearFecha(h.fecha) }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api.js'
import PromocionesDashboard from './PromocionesDashboard.vue'

const ofertas = ref([])
const historial = ref([])
const dashboard = ref(null)
const semilla = ref('')
const seleccionadas = ref([])
const soloConErrores = ref(false)
const cargando = ref(false)
const ocupado = ref(false)
const aviso = ref('')
const avisoTipo = ref('ok')

const todasMarcadas = computed(
  () => ofertas.value.length > 0 && seleccionadas.value.length === ofertas.value.length,
)

const alternarTodas = () => {
  seleccionadas.value = todasMarcadas.value ? [] : ofertas.value.map((o) => o.staging_id)
}

const mostrar = (texto, tipo = 'ok') => {
  aviso.value = texto
  avisoTipo.value = tipo
}

const cargar = async () => {
  cargando.value = true
  seleccionadas.value = []
  try {
    const datos = await api.promocionesPendientes({
      limite: 100,
      soloConErrores: soloConErrores.value,
    })
    ofertas.value = datos.ofertas
    semilla.value = datos.semilla
    historial.value = (await api.historialPromociones(7)).entradas
    // Tras promover o rechazar, las cifras del widget cambian.
    dashboard.value?.cargar()
  } catch (e) {
    mostrar(`No se pudo cargar: ${e.message}`, 'error')
    ofertas.value = []
  } finally {
    cargando.value = false
  }
}

// El 403 del backend es la respuesta a "solo admin promueve". Se traduce a
// algo que el operador entienda, en vez de enseñarle el codigo.
const traducirError = (e) =>
  String(e.message).startsWith('403')
    ? 'Necesitas rol de administrador para esto.'
    : e.message

const promover = async (oferta) => {
  ocupado.value = true
  try {
    const r = await api.promover(oferta.staging_id)
    if (r.ok) {
      mostrar('Oferta promovida.')
      await cargar()
    } else {
      mostrar(r.motivo, 'error')
    }
  } catch (e) {
    mostrar(traducirError(e), 'error')
  } finally {
    ocupado.value = false
  }
}

const rechazar = async (oferta) => {
  ocupado.value = true
  try {
    await api.rechazar(oferta.staging_id)
    mostrar('Oferta rechazada. Caducará sola en 24 h.')
    await cargar()
  } catch (e) {
    mostrar(traducirError(e), 'error')
  } finally {
    ocupado.value = false
  }
}

const promoverSeleccionadas = async () => {
  ocupado.value = true
  try {
    const resultados = await api.promoverLote(seleccionadas.value)
    const ok = resultados.filter((r) => r.ok).length
    const fallidas = resultados.filter((r) => !r.ok)
    // Se dice cuantas entraron Y por que fallaron las otras: un "15 promovidas"
    // a secas esconde que tres se quedaron fuera.
    mostrar(
      fallidas.length
        ? `${ok} promovidas. ${fallidas.length} no: ${fallidas[0].motivo}`
        : `${ok} promovidas.`,
      fallidas.length ? 'error' : 'ok',
    )
    await cargar()
  } catch (e) {
    mostrar(traducirError(e), 'error')
  } finally {
    ocupado.value = false
  }
}

const formatearFecha = (iso) =>
  iso ? new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' }) : ''

onMounted(cargar)
</script>

<style scoped>
.promociones {
  padding: 0 40px 40px;
}

.cabecera {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}

h2 {
  margin: 0 0 4px;
}

.sub {
  margin: 0;
  color: var(--texto-atenuado);
  font-size: 0.9rem;
}

.barra {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.filtro {
  font-size: 0.9rem;
  color: var(--texto-atenuado);
  cursor: pointer;
}

.acciones-lote {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
  font-size: 0.9rem;
}

/* Fondo claro: los realces van con los colores de marca y de estado, no con
   blancos translucidos, que sobre #F8F9FA no se ven. */
.btn {
  background: var(--superficie);
  color: var(--texto);
  border: 1px solid var(--borde);
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.primario {
  background: var(--verde);
  border-color: var(--verde-texto);
  color: var(--superficie);
}

.btn.peligro {
  background: var(--superficie);
  border-color: rgba(208, 59, 59, 0.45);
  color: var(--critico);
}

.aviso {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.9rem;
}

.aviso.ok {
  background: var(--verde-tinte);
  color: var(--verde-texto);
}

.aviso.error {
  background: rgba(208, 59, 59, 0.1);
  color: var(--critico);
}

.vacio {
  padding: 40px;
  text-align: center;
  color: var(--texto-atenuado);
}

.tabla {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.tabla th,
.tabla td {
  padding: 10px 8px;
  text-align: left;
  border-bottom: 1px solid var(--borde);
}

.tabla th {
  color: var(--texto-atenuado);
  font-weight: 600;
  font-size: 0.8rem;
}

.col-check {
  width: 34px;
}

.col-acciones {
  white-space: nowrap;
}

.col-acciones .btn + .btn {
  margin-left: 6px;
}

.urgente {
  color: var(--aviso);
  font-weight: 600;
}

.motivo {
  display: inline-block;
  background: rgba(239, 68, 68, 0.14);
  border-radius: 4px;
  padding: 2px 6px;
  margin-right: 4px;
  font-size: 0.75rem;
  cursor: help;
}

.etiqueta {
  color: var(--texto-atenuado);
  font-size: 0.8rem;
}

.historial {
  margin-top: 32px;
}

.historial ul {
  list-style: none;
  padding: 0;
  font-size: 0.85rem;
}

.historial li {
  padding: 6px 0;
  border-bottom: 1px solid var(--borde-suave);
}

.pill {
  display: inline-block;
  border-radius: 4px;
  padding: 1px 6px;
  margin-right: 6px;
  font-size: 0.72rem;
}

.pill.promoted {
  background: rgba(34, 197, 94, 0.16);
}

.pill.rejected {
  background: rgba(239, 68, 68, 0.16);
}

.pill.tipo {
  background: var(--borde);
}

.fecha {
  color: var(--texto-atenuado);
  margin-left: 8px;
}
</style>
