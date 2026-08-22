<template>
  <div class="auditoria">
    <header class="cabecera">
      <div>
        <h2>Auditoría</h2>
        <p class="sub">
          Quién hizo qué en el panel, con el antes y el después. Se conserva un año.
        </p>
      </div>
    </header>

    <div class="barra">
      <label class="campo">
        <span>Acción</span>
        <select v-model="filtros.evento" @change="buscar">
          <option value="">Todas</option>
          <option v-for="e in eventos" :key="e" :value="e">{{ nombreEvento(e) }}</option>
        </select>
      </label>

      <label class="campo">
        <span>Usuario</span>
        <input v-model.trim="filtros.usuario_email" placeholder="parte del correo"
               @keyup.enter="buscar" />
      </label>

      <label class="campo">
        <span>Desde</span>
        <input type="date" v-model="filtros.desde" @change="buscar" />
      </label>

      <label class="campo">
        <span>Hasta</span>
        <input type="date" v-model="filtros.hasta" @change="buscar" />
      </label>

      <div class="acciones">
        <button class="btn" :disabled="cargando" @click="buscar">Buscar</button>
        <button class="btn" :disabled="cargando" @click="limpiar">Limpiar</button>
        <button class="btn primario" :disabled="cargando || !total" @click="exportar">
          Exportar CSV
        </button>
      </div>
    </div>

    <p v-if="aviso" :class="['aviso', avisoTipo]">{{ aviso }}</p>

    <div v-if="cargando" class="vacio">Cargando…</div>
    <div v-else-if="!entradas.length" class="vacio">
      No hay nada registrado con esos filtros.
    </div>

    <template v-else>
      <table class="tabla">
        <thead>
          <tr>
            <th>Cuándo</th>
            <th>Acción</th>
            <th>Usuario</th>
            <th>Sobre qué</th>
            <th class="col-detalle"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="e in entradas" :key="e.audit_id">
            <tr :class="{ abierta: abierta === e.audit_id }">
              <td class="cuando">{{ fecha(e.ocurrido_en) }}</td>
              <td><span class="etiqueta">{{ nombreEvento(e.evento) }}</span></td>
              <td class="usuario">{{ e.usuario_email || '—' }}</td>
              <td class="entidad">
                <span v-if="e.entidad">{{ e.entidad }}</span>
                <code v-if="e.entidad_id" :title="e.entidad_id">{{ corto(e.entidad_id) }}</code>
                <span v-if="!e.entidad && !e.entidad_id">—</span>
              </td>
              <td class="col-detalle">
                <button class="btn menudo" @click="alternar(e.audit_id)">
                  {{ abierta === e.audit_id ? 'Ocultar' : 'Ver' }}
                </button>
              </td>
            </tr>

            <tr v-if="abierta === e.audit_id" class="detalle">
              <td colspan="5">
                <!-- Sin cambio de estado que enseñar no se pinta un panel
                     vacío: un "antes: {}" al lado de un "después: {}" hace
                     creer que se perdió el dato. -->
                <div v-if="e.antes || e.despues" class="paneles">
                  <div class="panel">
                    <h4>Antes</h4>
                    <p v-if="!e.antes" class="ninguno">No existía</p>
                    <dl v-else>
                      <template v-for="c in clavesDe(e)" :key="'a' + c">
                        <dt :class="{ cambiada: cambio(e, c) }">{{ c }}</dt>
                        <dd :class="{ cambiada: cambio(e, c) }">{{ valor(e.antes, c) }}</dd>
                      </template>
                    </dl>
                  </div>

                  <div class="panel">
                    <h4>Después</h4>
                    <p v-if="!e.despues" class="ninguno">Dejó de existir</p>
                    <dl v-else>
                      <template v-for="c in clavesDe(e)" :key="'d' + c">
                        <dt :class="{ cambiada: cambio(e, c) }">{{ c }}</dt>
                        <dd :class="{ cambiada: cambio(e, c) }">{{ valor(e.despues, c) }}</dd>
                      </template>
                    </dl>
                  </div>
                </div>
                <p v-else class="ninguno bloque">
                  Esta acción no cambió ningún campo; queda registrada porque una
                  persona la ejecutó.
                </p>

                <div v-if="tieneDetalles(e)" class="panel contexto">
                  <h4>Contexto</h4>
                  <dl>
                    <template v-for="(v, c) in e.detalles" :key="'x' + c">
                      <dt>{{ c }}</dt>
                      <dd>{{ comoTexto(v) }}</dd>
                    </template>
                  </dl>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <div class="paginacion">
        <button class="btn" :disabled="desplazamiento === 0 || cargando"
                @click="pagina(-1)">Anteriores</button>
        <span class="rango">
          {{ desplazamiento + 1 }}–{{ desplazamiento + entradas.length }} de {{ total }}
        </span>
        <button class="btn" :disabled="!hayMas || cargando"
                @click="pagina(1)">Siguientes</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'

const LIMITE = 50

// Los nombres técnicos son los que valen para filtrar y exportar, pero en la
// tabla se lee la versión en castellano: el panel lo usa CITE, no quien
// escribió el enum.
const NOMBRES = {
  promotion_manual: 'Promoción manual',
  promotion_rejected: 'Rechazo manual',
  plan_changed: 'Cambio de plan',
  kill_switch_toggled: 'Kill-switch',
  rule_updated: 'Regla modificada',
  login: 'Inicio de sesión',
  export: 'Exportación',
}

const entradas = ref([])
const eventos = ref([])
const total = ref(0)
const desplazamiento = ref(0)
const cargando = ref(false)
const abierta = ref(null)
const aviso = ref('')
const avisoTipo = ref('info')

const filtros = reactive({ evento: '', usuario_email: '', desde: '', hasta: '' })

const hayMas = computed(() => desplazamiento.value + entradas.value.length < total.value)

const nombreEvento = (e) => NOMBRES[e] || e
const corto = (id) => (id && id.length > 12 ? `${id.slice(0, 8)}…` : id)

const fecha = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'medium' })
}

const comoTexto = (v) => {
  if (v === null || v === undefined) return '—'
  return typeof v === 'object' ? JSON.stringify(v) : String(v)
}

const valor = (obj, clave) => (obj && clave in obj ? comoTexto(obj[clave]) : '—')

/** La unión de claves de antes y después, para que las filas se alineen. */
const clavesDe = (e) => [...new Set([
  ...Object.keys(e.antes || {}),
  ...Object.keys(e.despues || {}),
])]

/** Si esa clave cambió. Es lo único que se busca al abrir una fila. */
const cambio = (e, clave) =>
  JSON.stringify(e.antes?.[clave]) !== JSON.stringify(e.despues?.[clave])

const tieneDetalles = (e) => e.detalles && Object.keys(e.detalles).length > 0

const alternar = (id) => { abierta.value = abierta.value === id ? null : id }

async function cargar() {
  cargando.value = true
  aviso.value = ''
  try {
    const datos = await api.auditoria({
      ...filtros, limite: LIMITE, desplazamiento: desplazamiento.value,
    })
    entradas.value = datos.entradas
    total.value = datos.total
  } catch (e) {
    aviso.value = `No se pudo cargar la auditoría: ${e.message}`
    avisoTipo.value = 'error'
  } finally {
    cargando.value = false
  }
}

function buscar() {
  // Cambiar un filtro vuelve a la primera página. Sin esto, filtrar estando en
  // la página 3 de 300 resultados deja la tabla vacía sobre 10 resultados y
  // parece que el filtro no encontró nada.
  desplazamiento.value = 0
  abierta.value = null
  cargar()
}

function limpiar() {
  Object.keys(filtros).forEach((k) => { filtros[k] = '' })
  buscar()
}

function pagina(direccion) {
  desplazamiento.value = Math.max(0, desplazamiento.value + direccion * LIMITE)
  abierta.value = null
  cargar()
}

async function exportar() {
  cargando.value = true
  try {
    const { blob, total: t, exportados } = await api.exportarAuditoria(filtros)

    const url = URL.createObjectURL(blob)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = `auditoria-${new Date().toISOString().slice(0, 10)}.csv`
    enlace.click()
    URL.revokeObjectURL(url)

    if (exportados < t) {
      aviso.value = `Se exportaron ${exportados} de ${t} registros. ` +
                    'Acota el rango de fechas para llevártelo entero.'
      avisoTipo.value = 'error'
    } else {
      aviso.value = `${exportados} registros exportados.`
      avisoTipo.value = 'info'
    }
  } catch (e) {
    aviso.value = `No se pudo exportar: ${e.message}`
    avisoTipo.value = 'error'
  } finally {
    cargando.value = false
  }
}

onMounted(async () => {
  try {
    eventos.value = (await api.eventosAuditoria()).eventos
  } catch {
    // El desplegable se queda con "Todas". Filtrar por acción es una comodidad;
    // no poder listar los eventos no debe impedir ver la auditoría.
  }
  cargar()
})
</script>

<style scoped>
.auditoria {
  padding: 0 0 40px;
}

.cabecera {
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
  align-items: flex-end;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.campo {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--texto-atenuado);
}

.campo select,
.campo input {
  font-size: 0.88rem;
  padding: 7px 10px;
  border-radius: 6px;
  border: 1px solid var(--borde-fuerte);
  background: var(--superficie);
  color: var(--texto);
}

.acciones {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.btn {
  background: var(--superficie);
  color: var(--texto);
  border: 1px solid var(--borde);
  padding: 7px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn.primario {
  background: var(--verde);
  border-color: var(--verde-texto);
  color: var(--superficie);
}

.btn.menudo { padding: 3px 9px; font-size: 0.78rem; }

.aviso {
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.9rem;
  margin: 0 0 12px;
}

.aviso.info { background: var(--verde-tinte); color: var(--verde-texto); }
.aviso.error { background: var(--critico-fondo); color: var(--critico); }

.vacio {
  padding: 40px;
  text-align: center;
  color: var(--texto-atenuado);
}

.tabla {
  width: 100%;
  border-collapse: collapse;
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 10px;
  overflow: hidden;
  font-size: 0.88rem;
}

.tabla th {
  text-align: left;
  padding: 10px 12px;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
  border-bottom: 1px solid var(--borde);
}

.tabla td {
  padding: 9px 12px;
  border-bottom: 1px solid rgba(45, 151, 102, 0.1);
  vertical-align: top;
}

tr.abierta td { background: rgba(45, 151, 102, 0.05); }

.cuando { white-space: nowrap; color: var(--texto-atenuado); }
.usuario { word-break: break-all; }

.etiqueta {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--verde-tinte);
  color: var(--verde-texto);
  font-size: 0.78rem;
  font-weight: 600;
}

.entidad code {
  margin-left: 6px;
  font-size: 0.78rem;
  color: var(--texto-atenuado);
}

.col-detalle { text-align: right; width: 1%; }

.detalle td { background: rgba(45, 151, 102, 0.04); }

.paneles {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.panel h4 {
  margin: 0 0 8px;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.panel.contexto { margin-top: 16px; }

.panel dl {
  margin: 0;
  display: grid;
  grid-template-columns: minmax(90px, auto) 1fr;
  gap: 3px 12px;
  font-size: 0.84rem;
}

.panel dt { color: var(--texto-atenuado); }
.panel dd { margin: 0; word-break: break-word; }

/* Lo único que se busca al abrir una fila es qué cambió. */
.panel dt.cambiada, .panel dd.cambiada {
  background: rgba(255, 193, 7, 0.18);
  border-radius: 3px;
  padding: 0 3px;
  font-weight: 600;
  color: var(--texto);
}

.ninguno { color: var(--texto-atenuado); font-style: italic; margin: 0; font-size: 0.85rem; }
.ninguno.bloque { padding: 4px 0; }

.paginacion {
  display: flex;
  align-items: center;
  gap: 14px;
  justify-content: flex-end;
  margin-top: 14px;
  font-size: 0.85rem;
}

.rango { color: var(--texto-atenuado); }

@media (max-width: 800px) {
  .paneles { grid-template-columns: 1fr; }
  .acciones { margin-left: 0; }
}
</style>
