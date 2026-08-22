<!--
  La pregunta y la espera. Dos estados de la misma pantalla.

  ## La pregunta

  Antes esto era una tarjeta titulada «Consulta de Insumos» con el título
  pintado en degradado y un campo de texto azul marino sobre fondo claro —la
  tercera carcasa—. Ahora es una sola pregunta centrada, porque literalmente no
  hay nada más que hacer aquí: escribir un insumo y pulsar Analizar.

  ## La espera dejó de inventarse un porcentaje

  La versión anterior enseñaba una barra que subía sola con
  `progress += (95 - progress) * 0.05` y un número grande debajo. Ese número no
  medía nada: era una asíntota hacia el 95 % que llegaba al 94 % tanto si el
  servidor iba a tardar treinta segundos como si iba a fallar. Un porcentaje
  falso es peor que ninguno, porque quien lo mira calcula cuánto le queda y
  planifica con esa cuenta.

  Lo que queda es lo que sí es verdad: **el reloj**, que cuenta segundos reales,
  y **la lista de etapas**, que dice qué está ocurriendo. La barra pasa a
  indeterminada —barre de izquierda a derecha— porque su trabajo es decir «sigo
  vivo», no «voy por la mitad».

  Las etapas siguen avanzando por temporizador, calibrado con los tiempos
  medidos en consultas reales, y la pantalla lo declara en una línea en vez de
  disimularlo. El arreglo de verdad es leer el avance del servidor por el
  websocket de `api/websocket_jobs.py`; eso es trabajo de conexión, no de
  interfaz, y no entra en este rediseño.
-->
<template>
  <div class="consulta">
    <!-- ================= 03 · La pregunta ================= -->
    <div v-if="!isLoading" class="pregunta animate-fade-in">
      <h1>¿Qué insumo evaluamos?</h1>
      <p class="entradilla">
        Escribe una materia prima o un producto y AgroScout barre bases
        abiertas y góndolas.
      </p>

      <form class="buscador" @submit.prevent="submitSearch">
        <label class="oculto" for="insumo">Insumo a evaluar</label>
        <span class="lupa" aria-hidden="true"><Icono nombre="buscar" :tamano="19" /></span>
        <input
          id="insumo"
          ref="campo"
          v-model="query"
          type="text"
          placeholder="Ej.: cáscara de cacao, mucílago de café…"
          autocomplete="off"
          required
        />
        <button type="submit" class="btn btn--principal" :disabled="!query.trim()">
          Analizar
        </button>
      </form>

      <!--
        Sugerencias, no ejemplos en el placeholder. El placeholder desaparece
        en cuanto se escribe una letra y con él la única pista de qué tipo de
        cosa espera el sistema; estas se quedan y además son pulsables.
      -->
      <div class="sugerencias">
        <button
          v-for="s in SUGERENCIAS"
          :key="s"
          type="button"
          class="chip chip--accion"
          @click="usarSugerencia(s)"
        >
          {{ s }}
        </button>
      </div>

      <fieldset class="fuentes">
        <legend>
          <span class="rotulo">Dónde buscamos</span>
          <!-- Marcado mientras la selección no filtre de verdad. Sin esto, en
               una demostración se entiende que ya decide, y quien la vea
               sacaría conclusiones de un filtro que no se aplicó. -->
          <span
            class="chip chip--plan"
            title="La selección todavía no filtra la búsqueda"
          >vista previa</span>
        </legend>

        <div class="rejilla">
          <!-- Checkbox real dentro de la etiqueta: se navega con el tabulador y
               un lector de pantalla lo anuncia como lo que es. La tarjeta es
               solo la piel. -->
          <label
            v-for="f in FUENTES"
            :key="f.clave"
            class="fuente"
            :class="{ activa: seleccionadas.includes(f.clave) }"
          >
            <input
              type="checkbox"
              :value="f.clave"
              :checked="seleccionadas.includes(f.clave)"
              :disabled="isLoading"
              @change="alternar(f.clave)"
            />
            <span class="marca" aria-hidden="true"></span>
            <span class="cuerpo">
              <span class="nombre">{{ f.nombre }}</span>
              <span class="detalle">{{ f.detalle }}</span>
              <span class="coste" :class="f.tono">{{ f.coste }}</span>
            </span>
          </label>
        </div>
      </fieldset>
    </div>

    <!-- ================= 04 · La espera ================= -->
    <!--
      `aria-live="polite"` sobre el bloque entero: el cambio de etapa se anuncia
      solo, sin interrumpir. Con `assertive` cortaría la lectura cuatro veces
      en cuarenta segundos.
    -->
    <div v-else class="espera animate-fade-in">
      <div class="espera-tarjeta superficie" aria-live="polite" aria-busy="true">
        <div class="espera-cabecera">
          <h2>Analizando «{{ consultaEnCurso }}»</h2>
          <span class="reloj codigo num">{{ segundos }} s</span>
        </div>

        <!-- Indeterminada: dice «sigo vivo», no «voy por la mitad». -->
        <div class="barra" role="presentation">
          <span class="barra-barrido"></span>
        </div>

        <ol class="etapas">
          <li
            v-for="(e, i) in etapas"
            :key="e.texto"
            class="etapa"
            :class="estadoEtapa(i)"
          >
            <span class="etapa-marca" aria-hidden="true">
              <Icono v-if="estadoEtapa(i) === 'hecho'" nombre="check" :tamano="12" />
            </span>
            <span class="etapa-texto">{{ e.texto }}</span>
            <span v-if="estadoEtapa(i) === 'curso'" class="etapa-estado">en curso</span>
          </li>
        </ol>

        <p class="espera-nota">
          Los tiempos de esta lista son los medidos en consultas anteriores, no
          el avance real del servidor. El reloj de arriba sí es real.
        </p>
      </div>
    </div>

    <!-- El fallo se queda en la pantalla, no en un `alert()` del navegador. -->
    <div v-if="error" class="fallo superficie" role="alert">
      <Icono nombre="info" :tamano="18" />
      <div>
        <strong>{{ error.titulo }}</strong>
        <p>{{ error.quehacer }}</p>
      </div>
      <button type="button" class="btn btn--secundario btn--pequeno" @click="error = null">
        Cerrar
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
import { api, NoAutorizado } from '../api.js'
import Icono from './Icono.vue'

/**
 * Dónde se busca. Cuatro fuentes con papeles distintos, no cuatro versiones de
 * lo mismo:
 *
 *   snapshot  → el catálogo global (OpenFoodFacts). Dice QUÉ productos existen
 *               y con qué composición. Instantáneo y sin coste.
 *   peru      → el mercado de origen. API público de VTEX: Wong, Metro, Plaza
 *               Vea y Makro. De aquí salen precio vigente, stock y EAN.
 *   alemania  → el mercado de destino. Dice a qué precio se vende allí, que es
 *               la pregunta de un exportador y no la responde ni el catálogo
 *               global ni la góndola peruana.
 *   suiza     → segundo mercado de destino.
 *
 * Perú y Alemania juntos son el mapa que interesa: lo que un producto cuesta
 * aquí y lo que cuesta en el primer destino europeo de la quinua y el cacao
 * peruanos. Por separado, cada mitad es solo una lista de precios.
 *
 * Los precios alemanes vienen en euros, y eso ya está resuelto:
 * `adaptadores/tipo_cambio.py` convierte a soles con la serie oficial del BCRP
 * (PD04648PD, TC Euro venta) y guarda la tasa, su fecha y su fuente junto a
 * cada oferta, de modo que las dos columnas del mapa son comparables.
 *
 * El coste va escrito en la tarjeta a propósito. Sin él, «marcar todo» parece
 * siempre la mejor opción, y no lo es: las tiendas alemanas pasan por el
 * agente, que tarda minutos y gasta en un run lo que las otras dos no gastan
 * en un día.
 *
 * Que pasen por el agente no fue una suposición: se sondearon REWE, Edeka,
 * Alnatura, Kaufland y Lidl el 2026-08-13 y ninguna publica precio sin
 * credencial (tres devuelven 403; REWE sirve catálogo pero con el precio
 * vacío). El detalle, en `adaptadores/catalogo_alemania.py`.
 *
 * OJO: la etiqueta «vista previa» de arriba tiene ahora consecuencia
 * económica, y desde que Suiza está conectada vale el DOBLE. Como el selector
 * no filtra, Alemania y Suiza se consultan SIEMPRE, estén marcadas o no, y son
 * dos runs de agente en serie en cada consulta. Hay dos frenos de mano en el
 * servidor —`AGROSCOUT_GONDOLA_DE=0` y `AGROSCOUT_GONDOLA_CH=0`— pero la
 * solución de verdad es propagar esta selección hasta `mapear_comercio`.
 *
 * Suiza también va por agente, y eso fue una decisión, no una imposición.
 * Medido el 2026-08-13 (ver `TIERSV3/S8_GONDOLA_SUIZA.md`): Piccantino publica
 * JSON-LD con precio en CHF y el extractor del proyecto ya lo lee —o sea, HAY
 * una vía gratis—; Migros y Coop devuelven 403; farmy.ch ni siquiera resuelve
 * por DNS. Se descartó construir la tabla solo con Piccantino porque es una
 * tienda gourmet de nicho y llamar «Suiza» a eso induce a error, mientras que
 * Migros y Coop son ~70 % del mercado. De ahí «Minutos · con coste».
 *
 * Con la misma honestidad que la tarjeta alemana: el agente **tampoco** entra
 * en Migros ni en Coop —el 403 es del servidor, no del método—, así que lo que
 * llene esta tabla serán tiendas suizas menores y Piccantino. Lo que el agente
 * aporta frente a Piccantino solo es alcance, no las dos cadenas grandes.
 *
 * El franco tiene además un matiz que el euro no tiene: **el BCRP no publica
 * serie de CHF**, así que la columna en soles de la tabla suiza sale de un
 * agregador comercial y no del banco central. La tabla lo marca fila a fila;
 * aquí no se dice porque lo que se elige en esta pantalla es la fuente del
 * precio, no la de la tasa.
 */
const FUENTES = [
  {
    clave: 'snapshot',
    nombre: 'OpenFoodFacts',
    detalle: 'Catálogo global de productos y composición',
    coste: 'Instantáneo · sin coste',
    tono: 'gratis',
  },
  {
    clave: 'peru',
    nombre: 'Ecommerce del Perú',
    detalle: 'Wong, Metro, Plaza Vea y Makro',
    coste: 'Segundos · sin coste',
    tono: 'gratis',
  },
  {
    clave: 'alemania',
    nombre: 'Ecommerce de Alemania',
    // NO dice «REWE, Edeka y Alnatura», que es lo que ponía. Esas tres
    // devuelven 403 al agente, así que en una pasada real por 'Heidelbeeren'
    // no salió ninguna: lo que aparece son tiendas alemanas más pequeñas de
    // venta directa. Prometer las cadenas grandes y entregar granjas online es
    // exactamente el tipo de hueco que este informe no se puede permitir.
    detalle: 'Tiendas alemanas abiertas al rastreo · precios en euros',
    coste: 'Minutos · con coste',
    tono: 'caro',
  },
  {
    clave: 'suiza',
    nombre: 'Ecommerce de Suiza',
    // Mismo criterio que la tarjeta de Alemania, y por el mismo motivo: Migros
    // y Coop —las dos que serían el mercado de verdad— devuelven 403, así que
    // no van a salir aquí por mucho que el agente las busque. Lo que aparece
    // son tiendas suizas más pequeñas y Piccantino. Nombrar las cadenas
    // grandes sería prometer lo que no llega.
    detalle: 'Tiendas suizas abiertas al rastreo · precios en francos',
    coste: 'Minutos · con coste',
    tono: 'caro',
  },
]

/**
 * Insumos de ejemplo. Los cuatro son cosas que el sistema resuelve bien y que
 * cubren los dos casos que sabe hacer: materia prima con precio MIDAGRI
 * (arándano) y producto transformado con aditivos que analizar (harina de
 * quinua). Una sugerencia que devolviera un informe vacío enseñaría a
 * desconfiar del buscador en el primer clic.
 */
const SUGERENCIAS = [
  'arándano',
  'cáscara de mango',
  'pulpa de maracuyá',
  'harina de quinua',
]

/**
 * Las etapas, con el segundo en que empieza cada una. Los cortes salen de los
 * tiempos medidos: interpretar es casi inmediato, el snapshot tarda unos
 * segundos y las góndolas por agente son las que se llevan la espera.
 */
const ETAPAS = [
  { texto: 'Interpretando las características del insumo', desde: 0 },
  { texto: 'Barriendo OpenFoodFacts', desde: 3 },
  { texto: 'Leyendo góndolas', desde: 8 },
  { texto: 'Redactando el informe', desde: 25 },
]

const query = ref('')
const campo = ref(null)
const isLoading = ref(false)
const consultaEnCurso = ref('')
const segundos = ref(0)
const error = ref(null)
// Arrancan las dos gratuitas. Alemania se marca a conciencia: es la única que
// cuesta dinero, y una opción cara activada por defecto se acaba pagando sin
// que nadie haya decidido pagarla.
const seleccionadas = ref(['snapshot', 'peru'])
const emit = defineEmits(['search-result'])

const etapas = computed(() => ETAPAS)

/** Marca o desmarca una fuente, sin dejar la búsqueda sin ninguna. */
const alternar = (clave) => {
  const puestas = seleccionadas.value
  if (!puestas.includes(clave)) {
    seleccionadas.value = [...puestas, clave]
    return
  }
  // Quitar la última dejaría un botón «Analizar» que no puede analizar nada.
  // Se ignora el clic en vez de deshabilitar la casilla: deshabilitada, la
  // única pista de por qué no se puede sería que no pasa nada al pulsarla.
  if (puestas.length > 1) {
    seleccionadas.value = puestas.filter((c) => c !== clave)
  }
}

/**
 * Rellena el campo y deja el cursor dentro, sin lanzar la consulta.
 *
 * Buscar directamente al pulsar la sugerencia gastaría una consulta —y en
 * góndolas de agente, dinero— por un clic que bien puede ser exploratorio.
 * Quien la quiera, pulsa Analizar.
 */
const usarSugerencia = (s) => {
  query.value = s
  campo.value?.focus()
}

/** Qué etapa va por dónde, deducido del reloj. */
const estadoEtapa = (i) => {
  const actual = ETAPAS.reduce(
    (acc, e, idx) => (segundos.value >= e.desde ? idx : acc),
    0,
  )
  if (i < actual) return 'hecho'
  if (i === actual) return 'curso'
  return 'pendiente'
}

let reloj = null

const arrancarReloj = () => {
  segundos.value = 0
  reloj = setInterval(() => {
    segundos.value += 1
  }, 1000)
}

const pararReloj = () => {
  if (reloj) clearInterval(reloj)
  reloj = null
}

// Salir de la pantalla a mitad de consulta dejaba el intervalo corriendo.
onUnmounted(pararReloj)

const submitSearch = async () => {
  const texto = query.value.trim()
  if (!texto) return

  isLoading.value = true
  consultaEnCurso.value = texto
  error.value = null
  const inicio = performance.now()
  arrancarReloj()

  try {
    // api.consultar adjunta el Authorization; antes se llamaba sin cabecera y
    // este endpoint exige token desde S1, así que siempre daba 401.
    const data = await api.consultar(texto)
    data.elapsedTime = ((performance.now() - inicio) / 1000).toFixed(1)
    emit('search-result', data)
  } catch (e) {
    console.error(e)
    if (!(e instanceof NoAutorizado)) {
      // Un 401 ya cierra la sesión y lo gestiona App.vue; avisar dos veces
      // sería ruido.
      //
      // Antes esto era un `alert()`. Un diálogo del navegador bloquea la
      // pestaña, no se puede copiar y se lleva por delante el contexto de lo
      // que se estaba mirando; además, en la demo se traga el foco y hay que
      // aceptarlo antes de poder seguir.
      error.value = {
        titulo: `No se pudo completar la consulta de «${texto}»`,
        quehacer:
          'Vuelve a intentarlo. Si se repite, el motivo está en el log de la ' +
          'ventana «AgroScout API»: la consulta pasa por góndolas de agente y ' +
          'esas llamadas pueden agotar su tiempo.',
      }
    }
  } finally {
    pararReloj()
    isLoading.value = false
  }
}
</script>

<style scoped>
.consulta {
  max-width: 700px;
  margin: 0 auto;
  padding: 40px 0 20px;
}

/* ---------------------------------------------------------------- *
 *  03 · La pregunta
 * ---------------------------------------------------------------- */

.pregunta {
  text-align: center;
}

.pregunta h1 {
  margin: 0 0 6px;
  font-size: 2.125rem;
  /* Sin `background-clip: text` con degradado. Además de traer el azul de
     vuelta, el texto recortado sobre degradado deja de tener color propio y
     se vuelve invisible en modo de alto contraste. */
  color: var(--tinta);
}

.entradilla {
  margin: 0 0 22px;
  font-size: 0.9375rem;
  color: var(--texto-atenuado);
}

/* El campo y el botón dentro del mismo recuadro: son una sola acción. */
.buscador {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px;
  background: var(--superficie);
  border: 1.5px solid var(--borde-fuerte);
  border-radius: var(--r-lg);
  box-shadow: var(--sombra);
  transition: border-color 0.15s, box-shadow 0.15s;
}

/* El foco se pinta en el contenedor, no en el input: si no, el anillo saldría
   dentro del recuadro y por debajo del botón. */
.buscador:focus-within {
  border-color: var(--verde);
  box-shadow: var(--foco);
}

.lupa {
  display: flex;
  align-items: center;
  padding-left: 12px;
  color: var(--texto-sin-dato);
}

.buscador input {
  flex: 1;
  min-width: 0;
  font-size: 1.0625rem;
  font-weight: 500;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--tinta);
  padding: 10px 4px;
  box-shadow: none;
}

.buscador input:focus {
  box-shadow: none;
  border: 0;
}

.buscador .btn--principal {
  padding: 11px 26px;
  font-size: 0.9375rem;
  border-radius: var(--r-md);
}

.oculto {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  clip-path: inset(50%);
  white-space: nowrap;
}

.sugerencias {
  margin-top: 12px;
  display: flex;
  gap: 7px;
  justify-content: center;
  flex-wrap: wrap;
}

/* -- Selector de fuentes ------------------------------------------ */

.fuentes {
  border: none;
  margin: 30px 0 0;
  padding: 0;
  text-align: left;
}

.fuentes legend {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 0 0 12px;
  width: 100%;
}

/* Dos columnas y no cuatro: con el ancho de la tarjeta, cuatro dejarían 140 px
   por fuente y «Wong, Metro, Plaza Vea y Makro» se partiría en cuatro líneas.
   En 2x2 cada una tiene ~290 px y el detalle cabe entero. */
.rejilla {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.fuente {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 12px 13px;
  border: 1px solid var(--borde);
  border-radius: var(--r-md);
  background: var(--superficie);
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
}

.fuente:hover { border-color: var(--borde-fuerte); }

.fuente.activa {
  border-color: var(--verde-borde);
  background: #F7FBF9;
}

/* La casilla real se oculta pero sigue ahí: recibe el foco del tabulador y el
   lector de pantalla la anuncia. El recuadro de abajo es solo la piel. */
.fuente input {
  position: absolute;
  opacity: 0;
  width: 1px;
  height: 1px;
  margin: 0;
  padding: 0;
}

.fuente input:focus-visible ~ .marca {
  box-shadow: var(--foco);
}

.marca {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  flex-shrink: 0;
  border: 1.5px solid var(--borde-fuerte);
  border-radius: 4px;
  background: var(--superficie);
  transition: border-color 0.15s, background-color 0.15s;
}

.fuente.activa .marca {
  border-color: var(--verde);
  background: var(--verde);
}

/* El palito del tick, dibujado con bordes: no hace falta ningún icono. */
.fuente.activa .marca::after {
  content: '';
  display: block;
  width: 4px;
  height: 8px;
  margin: 1px auto 0;
  border: solid #ffffff;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.cuerpo { display: flex; flex-direction: column; gap: 2px; min-width: 0; }

.nombre {
  font-size: 0.82rem;
  font-weight: 650;
  color: var(--tinta);
  line-height: 1.25;
}

.detalle {
  font-size: 0.72rem;
  color: var(--texto-atenuado);
  line-height: 1.35;
}

.coste {
  margin-top: 3px;
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.coste.gratis { color: var(--verde-texto); }
.coste.caro { color: var(--aviso); }

/* ---------------------------------------------------------------- *
 *  04 · La espera
 * ---------------------------------------------------------------- */

.espera {
  display: flex;
  justify-content: center;
  padding: 24px 0;
}

.espera-tarjeta {
  width: 100%;
  max-width: 520px;
  padding: 26px;
}

.espera-cabecera {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.espera-cabecera h2 {
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 700;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reloj {
  flex: none;
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--texto-atenuado);
}

.barra {
  height: 4px;
  border-radius: 999px;
  background: #EEF1EF;
  overflow: hidden;
  margin-bottom: 20px;
}

/* Un tercio de ancho que cruza de lado a lado. Sin punto de llegada, así que
   no se puede leer como progreso. */
.barra-barrido {
  display: block;
  width: 33%;
  height: 100%;
  border-radius: 999px;
  background: var(--verde);
  animation: ags-barrido 1.4s ease-in-out infinite;
}

.etapas {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 11px;
}

.etapa {
  display: flex;
  align-items: center;
  gap: 11px;
  font-size: 0.875rem;
  color: #A8B2AD;
}

.etapa.hecho { color: var(--texto-atenuado); }

.etapa.curso {
  color: var(--tinta);
  font-weight: 650;
}

.etapa-marca {
  flex: none;
  width: 17px;
  height: 17px;
  border-radius: 50%;
  border: 1px solid var(--borde-medio);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.etapa.hecho .etapa-marca {
  background: var(--verde);
  border-color: var(--verde);
}

/* La que está en curso late. Es la única señal de movimiento de la lista, y
   se apaga sola con prefers-reduced-motion. */
.etapa.curso .etapa-marca {
  border-color: var(--verde);
  animation: ags-pulso 1.6s ease-in-out infinite;
}

.etapa-texto { flex: 1; min-width: 0; }

.etapa-estado {
  flex: none;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--verde-texto);
}

.espera-nota {
  margin: 20px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--borde-suave);
  font-size: 0.75rem;
  line-height: 1.5;
  color: var(--texto-sin-dato);
}

/* ---------------------------------------------------------------- *
 *  Fallo
 * ---------------------------------------------------------------- */

.fallo {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  margin-top: 22px;
  padding: 14px 16px;
  border-color: var(--critico-borde);
  background: var(--critico-fondo);
  color: var(--critico);
  text-align: left;
}

.fallo > div { flex: 1; }

.fallo p {
  margin: 3px 0 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: var(--texto-atenuado);
}

@media (max-width: 640px) {
  .rejilla { grid-template-columns: 1fr; }
  .pregunta h1 { font-size: 1.75rem; }
  .buscador { flex-wrap: wrap; }
  .buscador .btn--principal { width: 100%; }
}
</style>
