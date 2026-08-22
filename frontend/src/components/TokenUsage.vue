<!--
  El consumo del mes.

  ## Por qué esto ya no encabeza la pantalla

  Encabezaba el informe: una tarjeta de 120 px con titular, cifras, barra de
  8 px y el desglose por etapa, todo por encima del mapa comercial. O sea, lo
  primero que leía quien acababa de esperar cuarenta segundos por un análisis
  no era el análisis, era la factura.

  El consumo importa —hay un tope y se puede agotar— pero es información sobre
  el sistema, no sobre el insumo. Aquí baja al pie del informe y se pliega en
  una línea; el desglose por modelo se despliega bajo demanda, y su sitio de
  verdad es la pantalla de Costes, adonde lleva el enlace.

  La excepción es el freno de mano: si el gasto global está detenido, eso sí
  cambia lo que la pantalla puede hacer, así que se dice siempre y sin plegar.
-->
<template>
  <div v-if="uso" class="consumo no-imprimir">
    <!--
      `aria-expanded` + `aria-controls` para que el detalle plegado exista para
      el lector de pantalla en vez de aparecer y desaparecer sin explicación.
    -->
    <button
      class="linea"
      type="button"
      :aria-expanded="abierto"
      aria-controls="consumo-desglose"
      @click="abierto = !abierto"
    >
      <span class="etiqueta">Consumo del mes</span>

      <span class="barra" role="img" :aria-label="`${porcentaje.toFixed(0)} % del tope`">
        <span class="relleno" :class="nivel" :style="{ width: porcentaje + '%' }"></span>
      </span>

      <span class="cifras codigo">
        ${{ uso.costo_mes_usd.toFixed(4) }}
        <span class="tope">/ ${{ uso.tope_usd.toFixed(2) }}</span>
      </span>

      <span class="runs">
        {{ uso.runs }} {{ uso.runs === 1 ? 'consulta' : 'consultas' }} · plan {{ uso.plan }}
      </span>

      <span class="desplegar">
        {{ abierto ? 'ocultar desglose' : 'ver desglose' }}
        <Icono :nombre="abierto ? 'chevron-arriba' : 'chevron-abajo'" :tamano="14" />
      </span>
    </button>

    <!--
      El freno de mano no se pliega: mientras esté echado, ninguna consulta
      nueva va a gastar, y quien lo ignore va a leer un informe parcial sin
      entender por qué.
    -->
    <p v-if="uso.kill_switch_activo" class="detenido" role="status">
      <Icono nombre="info" :tamano="16" />
      Gasto global detenido. Las etapas de pago no se ejecutan hasta que se
      reanude desde Presupuestos y control.
    </p>

    <div v-show="abierto" id="consumo-desglose" class="desglose">
      <p v-if="!etapas.length" class="sin-dato">
        Esta consulta no registró etapas con coste.
      </p>

      <template v-else>
        <span class="rotulo">Última consulta</span>
        <span
          v-for="etapa in etapas"
          :key="etapa.etapa"
          class="etapa"
          :class="{ cacheada: etapa.cache_hit }"
          :title="etapa.cache_hit ? 'Respuesta servida desde caché: no se llamó al modelo' : etapa.modelo"
        >
          <b>{{ etapa.etapa }}</b>
          <span class="modelo codigo">{{ modeloCorto(etapa.modelo) }}</span>
          <span class="costo codigo">
            {{ etapa.cache_hit ? 'caché' : '$' + etapa.costo_usd.toFixed(4) }}
          </span>
        </span>
      </template>

      <RouterLink class="ir-costes" :to="{ name: 'costos' }">
        Desglose completo en Costes<Icono nombre="chevron-der" :tamano="13" />
      </RouterLink>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { api, NoAutorizado } from '../api.js'
import Icono from './Icono.vue'

const props = defineProps({
  ejecucionId: {
    type: String,
    default: null,
  },
})

const uso = ref(null)
const abierto = ref(false)

const etapas = computed(() => uso.value?.ultimo_run?.etapas || [])

const porcentaje = computed(() => {
  if (!uso.value?.tope_usd) return 0
  return Math.min(100, (uso.value.costo_mes_usd / uso.value.tope_usd) * 100)
})

const nivel = computed(() => {
  if (porcentaje.value >= 90) return 'agotado'
  if (porcentaje.value >= 60) return 'alto'
  return 'normal'
})

// 'openai/glm-5.2' -> 'glm-5.2'. El prefijo es del enrutado de litellm y no
// significa nada para quien lee el informe.
const modeloCorto = (modelo) => (modelo || '—').split('/').pop()

watch(
  () => props.ejecucionId,
  async () => {
    try {
      uso.value = await api.uso()
    } catch (error) {
      if (!(error instanceof NoAutorizado)) console.error(error)
      uso.value = null
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.consumo {
  max-width: 1180px;
  margin: 8px auto 0;
}

/* Toda la línea es el control: 28 px de alto, no una tarjeta. */
.linea {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  font-family: inherit;
  font-size: 0.8rem;
  text-align: left;
  padding: 8px 12px;
  border: 1px solid var(--borde);
  border-radius: var(--r-sm);
  background: var(--superficie);
  color: var(--texto-atenuado);
  cursor: pointer;
  transition: border-color 0.15s;
}

.linea:hover { border-color: var(--borde-fuerte); }

.etiqueta {
  font-weight: 650;
  color: var(--texto);
  flex: none;
}

/* 72 px: suficiente para leer «va por la mitad» de un vistazo, y no tanto como
   para pedir la atención que merece el informe de al lado. */
.barra {
  flex: none;
  width: 72px;
  height: 5px;
  border-radius: 999px;
  background: #EEF1EF;
  overflow: hidden;
}

.relleno {
  display: block;
  height: 100%;
  border-radius: 999px;
  transition: width 0.4s ease;
}

/* Tres tramos con el mismo significado que en el resto del sistema: verde
   normal, ámbar aviso, rojo crítico. */
.relleno.normal  { background: var(--verde); }
.relleno.alto    { background: var(--aviso); }
.relleno.agotado { background: var(--critico); }

.cifras {
  flex: none;
  font-weight: 700;
  color: var(--tinta);
  font-variant-numeric: tabular-nums;
}

.tope {
  font-weight: 400;
  color: var(--texto-sin-dato);
}

.runs {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.desplegar {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex: none;
  font-weight: 600;
  color: var(--verde-texto);
}

.detenido {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0 0;
  padding: 9px 12px;
  font-size: 0.8rem;
  border-radius: var(--r-sm);
  background: var(--critico-fondo);
  border: 1px solid var(--critico-borde);
  color: var(--critico);
}

.desglose {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-top: 8px;
  padding: 12px;
  font-size: 0.75rem;
  border: 1px solid var(--borde);
  border-radius: var(--r-sm);
  background: var(--superficie-sutil);
}

.etapa {
  display: inline-flex;
  gap: 7px;
  align-items: baseline;
  padding: 3px 10px;
  border-radius: var(--r-chip);
  background: var(--superficie);
  border: 1px solid var(--borde);
}

/* Borde discontinuo además del gris: «servido de caché» tiene que distinguirse
   de «costó poco» sin depender de notar un cambio de opacidad. */
.etapa.cacheada {
  border-style: dashed;
  color: var(--texto-sin-dato);
}

.etapa .modelo { color: var(--texto-atenuado); }
.etapa .costo { font-variant-numeric: tabular-nums; }

.ir-costes {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 600;
  text-decoration: none;
}

@media (max-width: 760px) {
  .linea { flex-wrap: wrap; }
  .runs { flex-basis: 100%; }
}
</style>
