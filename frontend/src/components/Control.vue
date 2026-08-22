<template>
  <div class="control">
    <header class="cabecera">
      <div>
        <h2>Presupuestos y control</h2>
        <p class="sub">
          El interruptor de gasto y el plan de cada usuario. Todo lo de esta
          pantalla queda auditado.
        </p>
      </div>
    </header>

    <p v-if="aviso" :class="['aviso', avisoTipo]">{{ aviso }}</p>

    <!-- Kill-switch (8.5) -->
    <section :class="['tarjeta', 'switch', { parado: killSwitch.activo }]">
      <div class="estado">
        <span class="punto" aria-hidden="true"></span>
        <div>
          <h3>{{ killSwitch.activo ? 'Gasto detenido' : 'Gasto permitido' }}</h3>
          <p class="explicacion">
            <template v-if="killSwitch.activo">
              Las consultas siguen respondiendo, pero se cierran en
              <strong>parcial</strong> sin ejecutar ninguna etapa de IA.
            </template>
            <template v-else>
              Las consultas se ejecutan con normalidad, dentro de los topes de
              gasto por run, por usuario y global.
            </template>
          </p>
          <p v-if="killSwitch.activo && killSwitch.motivo" class="motivo">
            «{{ killSwitch.motivo }}»
          </p>
          <p v-if="killSwitch.actualizado_en" class="pie">
            Último cambio: {{ fecha(killSwitch.actualizado_en) }}
          </p>
        </div>
      </div>

      <div class="accion">
        <input v-if="!killSwitch.activo" v-model.trim="motivo"
               class="motivo-entrada" maxlength="280"
               placeholder="Motivo (p. ej. «incidente de coste 12-ago»)" />
        <button :class="['btn', killSwitch.activo ? 'primario' : 'peligro']"
                :disabled="ocupado" @click="alternarSwitch">
          {{ killSwitch.activo ? 'Reanudar el gasto' : 'Detener el gasto' }}
        </button>
      </div>
    </section>

    <!-- Planes (8.9) -->
    <section class="tarjeta">
      <h3>Usuarios y planes</h3>
      <p class="explicacion">
        El plan decide qué etapas se ejecutan y cuánto puede gastar cada uno al
        mes. El consumo es del mes en curso.
      </p>

      <div v-if="cargando" class="vacio">Cargando…</div>
      <table v-else class="tabla">
        <thead>
          <tr>
            <th>Usuario</th>
            <th>Rol</th>
            <th class="num">Consultas</th>
            <th class="num">Gasto del mes</th>
            <th>Plan</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in usuarios" :key="u.id">
            <td class="correo">{{ u.email }}</td>
            <td>
              <span :class="['etiqueta', u.rol]">{{ u.rol }}</span>
            </td>
            <td class="num">{{ u.runs_mes }}</td>
            <td class="num">${{ u.costo_mes_usd.toFixed(4) }}</td>
            <td>
              <select :value="u.plan" :disabled="ocupado"
                      @change="cambiarPlan(u, $event.target.value)">
                <option v-for="p in planes" :key="p" :value="p">{{ p }}</option>
              </select>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '../api.js'

const killSwitch = reactive({
  activo: false, motivo: null, actualizado_por: null, actualizado_en: null,
})
const usuarios = ref([])
const planes = ref(['gratuito', 'premium'])
const motivo = ref('')
const cargando = ref(true)
const ocupado = ref(false)
const aviso = ref('')
const avisoTipo = ref('info')

const fecha = (iso) => (iso
  ? new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })
  : '—')

function copiarSwitch(datos) {
  Object.assign(killSwitch, {
    activo: datos.activo, motivo: datos.motivo,
    actualizado_por: datos.actualizado_por,
    actualizado_en: datos.actualizado_en,
  })
}

async function cargar() {
  cargando.value = true
  try {
    const [estado, lista] = await Promise.all([
      api.killSwitch(), api.usuariosAdmin(),
    ])
    copiarSwitch(estado)
    usuarios.value = lista.usuarios
    planes.value = lista.planes
  } catch (e) {
    aviso.value = `No se pudo cargar: ${e.message}`
    avisoTipo.value = 'error'
  } finally {
    cargando.value = false
  }
}

async function alternarSwitch() {
  // Detener el gasto para a TODO el mundo, no solo a quien pulsa. Un botón que
  // hace eso sin preguntar acaba pulsándose sin querer.
  const encendiendo = !killSwitch.activo
  const pregunta = encendiendo
    ? 'Se detendrá el gasto en IA para todos los usuarios. Las consultas ' +
      'seguirán respondiendo, pero sin ejecutar ninguna etapa. ¿Continuar?'
    : 'Se reanudará el gasto en IA para todos los usuarios. ¿Continuar?'
  if (!window.confirm(pregunta)) return

  ocupado.value = true
  aviso.value = ''
  try {
    const estado = await api.fijarKillSwitch({
      activo: encendiendo,
      motivo: encendiendo ? (motivo.value || null) : null,
    })
    copiarSwitch(estado)
    motivo.value = ''
    aviso.value = encendiendo
      ? 'Gasto detenido. Queda registrado en la auditoría.'
      : 'Gasto reanudado. Queda registrado en la auditoría.'
    avisoTipo.value = 'info'
  } catch (e) {
    aviso.value = `No se pudo cambiar el interruptor: ${e.message}`
    avisoTipo.value = 'error'
  } finally {
    ocupado.value = false
  }
}

async function cambiarPlan(usuario, plan) {
  if (plan === usuario.plan) return

  ocupado.value = true
  aviso.value = ''
  try {
    await api.cambiarPlan(usuario.id, plan)
    usuario.plan = plan
    aviso.value = `${usuario.email} pasa a plan ${plan}.`
    avisoTipo.value = 'info'
  } catch (e) {
    // Se recarga en vez de dejar el desplegable enseñando un plan que no se
    // guardó: la pantalla tiene que decir lo que hay en la base.
    aviso.value = `No se pudo cambiar el plan: ${e.message}`
    avisoTipo.value = 'error'
    await cargar()
  } finally {
    ocupado.value = false
  }
}

onMounted(cargar)
</script>

<style scoped>
.control { padding: 0 0 40px; }

.cabecera { margin-bottom: 20px; }
h2 { margin: 0 0 4px; }
h3 { margin: 0 0 4px; font-size: 1rem; }

.sub, .explicacion {
  margin: 0;
  color: var(--texto-atenuado);
  font-size: 0.9rem;
}

.tarjeta {
  background: var(--superficie);
  border: 1px solid var(--borde);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.switch {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  flex-wrap: wrap;
}

.switch.parado { border-color: rgba(217, 119, 6, 0.55); background: rgba(217, 119, 6, 0.06); }

.estado { display: flex; gap: 14px; align-items: flex-start; }

/* Verde/naranja, que es lo que pide 8.5. Naranja y no rojo a propósito: el
   sistema no está roto, está detenido a conciencia. */
.punto {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-top: 5px;
  flex-shrink: 0;
  background: var(--exito);
}

.switch.parado .punto { background: var(--aviso); }

.motivo { margin: 6px 0 0; font-size: 0.9rem; color: var(--aviso-texto); }

.pie { margin: 6px 0 0; font-size: 0.78rem; color: var(--texto-atenuado); }

.accion { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.motivo-entrada {
  min-width: 260px;
  font-size: 0.85rem;
  padding: 7px 10px;
  border-radius: 6px;
  border: 1px solid var(--borde-fuerte);
  background: var(--superficie);
}

.btn {
  background: var(--superficie);
  color: var(--texto);
  border: 1px solid var(--borde);
  padding: 8px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.88rem;
  white-space: nowrap;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

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
  margin: 0 0 16px;
}

.aviso.info { background: var(--verde-tinte); color: var(--verde-texto); }
.aviso.error { background: var(--critico-fondo); color: var(--critico); }

.vacio { padding: 24px; text-align: center; color: var(--texto-atenuado); }

.tabla {
  width: 100%;
  border-collapse: collapse;
  margin-top: 14px;
  font-size: 0.88rem;
}

.tabla th {
  text-align: left;
  padding: 8px 10px;
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
  border-bottom: 1px solid var(--borde);
}

.tabla td {
  padding: 9px 10px;
  border-bottom: 1px solid rgba(45, 151, 102, 0.1);
}

.num { text-align: right; font-variant-numeric: tabular-nums; }
.correo { word-break: break-all; }

.etiqueta {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  background: rgba(108, 117, 125, 0.15);
  color: var(--texto-atenuado);
}

.etiqueta.admin {
  background: rgba(45, 151, 102, 0.14);
  color: var(--verde-texto);
  font-weight: 600;
}

select {
  font-size: 0.85rem;
  padding: 5px 8px;
  border-radius: 6px;
  border: 1px solid var(--borde-fuerte);
  background: var(--superficie);
  color: var(--texto);
}

@media (max-width: 700px) {
  .switch { flex-direction: column; align-items: stretch; }
  .accion { justify-content: flex-start; }
  .motivo-entrada { min-width: 0; flex: 1; }
}
</style>
