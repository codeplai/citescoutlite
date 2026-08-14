<!--
  Una tabla de precio de góndola: a cuánto se vende hoy y dónde.

  Existe como componente porque hay DOS —Perú y Alemania— y son casi idénticas.
  Copiadas, la primera vez que alguien afinase una de las dos quedarían
  discrepando, y como el entregable es justo la comparación entre ambas, se
  leería mal sin que nada fallara.

  Lo que cambia entre mercados va por props (título, subtítulo, cómo se llaman
  las tiendas); lo que no cambia —el orden, los «sin dato», el chip de EAN
  repetido, la ficha nutricional— vive aquí una sola vez.
-->
<template>
  <!--
    La sección se pinta SIEMPRE, aunque no haya ofertas.

    Antes se ocultaba entera con `v-if="ofertas.length"`, por una razón buena:
    una tabla vacía con cabeceras se lee como un fallo de carga. Pero el
    remedio tenía un coste peor, y se pagó dos veces depurando: si no hay nada,
    **«este mercado no tiene ofertas» y «esto se rompió» se ven exactamente
    igual**, que es no ver nada. La primera vez la causa fue una caché con el
    esquema viejo; la segunda, una API sin reiniciar. En los dos casos el
    síntoma en pantalla fue el mismo: ausencia muda.

    La salida no es enseñar una tabla vacía —eso sigue leyéndose como error—
    sino declarar la ausencia en una línea. Es el principio de la casa aplicado
    a la propia interfaz: el dato o es real, o dice que no está.
  -->
  <section class="gondola">
    <h3 class="gondola-titulo">
      {{ titulo }}
      <span class="gondola-n">{{ ofertas.length }} ofertas</span>
    </h3>
    <p class="gondola-sub">
      <!-- Cómo se obtuvo, que no es igual en los dos mercados y cambia lo que
           vale la cifra. Va arriba y no en el pie por eso. -->
      {{ subtitulo }}
    </p>

    <!--
      No dice por qué está vacío, y es deliberado: desde aquí no se distingue
      «se consultó y no había» de «no se consultó» —el interruptor del servidor,
      un término que la etapa 1 no supo traducir—. Afirmar una de las dos sería
      inventar. Lo que sí se afirma es que se miró y esto es lo que hay.
    -->
    <p v-if="!ofertas.length" class="gondola-vacia">
      Sin ofertas para este insumo en esta consulta.
    </p>

    <div v-else class="mapa-tabla-scroll">
      <table class="mapa-tabla gondola-tabla">
        <thead>
          <tr>
            <th>Producto</th><th>Tienda</th><th class="num">Precio</th>
            <th class="num">Stock</th><th>EAN</th>
            <th>Ingredientes</th>
            <th>Especificaciones nutricionales</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in ofertas" :key="o.fuente_url + o.tienda"
              :class="{ comparable: esComparable(o) }">
            <td class="col-producto">
              <a :href="o.fuente_url" target="_blank" rel="noopener">{{ o.nombre }}</a>
              <!-- El EAN es lo único que identifica el MISMO producto en dos
                   tiendas: el nombre cambia de una a otra. Marcarlo es lo que
                   convierte la lista en una comparación. -->
              <span v-if="esComparable(o)" class="chip-comparable"
                    title="El mismo producto está en otra tienda de esta tabla">
                también en otra tienda
              </span>
            </td>
            <td>{{ o.tienda }}</td>

            <!--
              Tres estados, y el del medio es el que importa fuera de Perú.

              Antes esta celda pintaba solo `precio_pen` y caía a «sin dato»
              cuando venía null. Con Perú daba igual —la conversión es la
              identidad y nunca es null—, pero para un precio en euros sin tasa
              del BCRP se estaba TIRANDO un precio que sí se había leído: el
              backend conserva `precio` y `moneda` a propósito para este caso.
              Un hueco donde hay dato es peor que no tener la columna.
            -->
            <td class="num precio">
              <template v-if="o.precio_pen !== null && o.precio_pen !== undefined">
                <span v-if="esLocal(o)">S/ {{ o.precio_pen.toFixed(2) }}</span>
                <template v-else>
                  <span class="precio-origen">{{ enOrigen(o) }}</span>
                  <span class="precio-flecha" aria-hidden="true">→</span>
                  <!-- La tasa, su fecha y su fuente viajan en el title: una
                       cifra convertida sin ellas no es auditable, y en un
                       informe de CITE hay que poder responder «¿con qué tipo de
                       cambio?» meses después. -->
                  <span :title="detalleConversion(o)">S/ {{ o.precio_pen.toFixed(2) }}</span>
                  <!--
                    Y de dónde sale la tasa, **a la vista** y no solo en el
                    title. El euro y el dólar los publica el BCRP y son
                    citables en un informe; el franco suizo NO tiene serie en
                    el BCRP, así que sus soles vienen de un agregador
                    comercial. Una columna «S/» que mezcla las dos
                    procedencias sin distinguirlas es justo lo que este
                    informe evita en todo lo demás: el hover no vale, porque
                    no existe al imprimir ni en un móvil.
                  -->
                  <span v-if="!esOficial(o)" class="chip-tasa"
                        :title="detalleConversion(o)">
                    tasa no oficial
                  </span>
                </template>
              </template>
              <template v-else-if="tienePrecio(o)">
                <span class="precio-origen">{{ enOrigen(o) }}</span>
                <span class="sin-dato">sin conversión</span>
              </template>
              <span v-else class="sin-dato">sin dato</span>
            </td>

            <!-- Stock vacío = la tienda no lo publica, o dio una cifra
                 centinela. Nunca cero: cero sí sería un dato. -->
            <td class="num">
              <span v-if="o.stock !== null && o.stock !== undefined">{{ o.stock }}</span>
              <span v-else class="sin-dato">sin dato</span>
            </td>
            <td class="ean">
              <span v-if="o.ean">{{ o.ean }}</span>
              <span v-else class="sin-dato">sin dato</span>
            </td>

            <!--
              Ingredientes y alérgenos: de qué está hecho.

              La lista de ingredientes NO la publica ninguna cadena peruana. Se
              buscó por cinco vías —especificaciones del API, el grupo
              «Componentes del Producto», la descripción, el HTML de la ficha y
              OpenFoodFacts por EAN— y el dato vive en el envase físico, no en
              la web. La columna dice «sin dato» y eso es la respuesta correcta,
              no un fallo del extractor.

              Lo que sí llega es el alérgeno declarado, que Makro publica. Se
              enseña aquí y no dentro de la ficha nutricional porque es una
              advertencia de seguridad alimentaria: hay que verla sin tener que
              abrir nada.
            -->
            <td class="composicion">
              <button v-if="o.ingredientes" class="btn-ficha"
                      @click="composicionAbierta = o">
                Ver lista
              </button>
              <button v-else-if="o.alergenos" class="btn-ficha alergeno"
                      @click="composicionAbierta = o"
                      title="La tienda no publica los ingredientes, pero sí el alérgeno declarado">
                ⚠ alérgenos
              </button>
              <span v-else class="sin-dato">sin dato</span>
            </td>

            <!--
              Dos estados, no tres: o la tienda publica la tabla o no. Aquí no
              cabe el "ninguno" que sí tiene la columna de aditivos del mapa,
              porque una ficha sin tabla nutricional no significa que el
              producto no tenga nutrientes.
            -->
            <td>
              <button v-if="o.nutricion" class="btn-ficha" @click="nutriAbierta = o">
                Ver tabla
              </button>
              <span v-else class="sin-dato">sin dato</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!--
      Ficha de composición. Mismo anclaje que la nutricional: solo sobre esta
      sección.
    -->
    <div v-if="composicionAbierta" class="modal-fondo modal-fondo-gondola"
         @click.self="composicionAbierta = null">
      <div class="modal" role="dialog" aria-modal="true">
        <header class="modal-cabecera">
          <div>
            <h4>{{ composicionAbierta.nombre }}</h4>
            <p class="modal-sub">
              {{ composicionAbierta.tienda }} ·
              <a :href="composicionAbierta.fuente_url" target="_blank" rel="noopener">
                ver ficha en la tienda
              </a>
            </p>
          </div>
          <button class="modal-cerrar" @click="composicionAbierta = null"
                  aria-label="Cerrar">×</button>
        </header>

        <div class="modal-cuerpo">
          <section v-if="composicionAbierta.ingredientes">
            <h5>Ingredientes</h5>
            <p class="composicion-texto">{{ composicionAbierta.ingredientes }}</p>
          </section>

          <!-- Se dice que faltan, en vez de omitir la sección. Un apartado
               ausente se lee como «no se miró»; esto declara que se miró. -->
          <section v-else>
            <h5>Ingredientes</h5>
            <p class="composicion-ausente">
              La tienda no publica la lista de ingredientes en su ficha. No se
              completa desde otra fuente: el dato está en el envase, y atribuir
              a este producto los ingredientes de otro parecido sería inventar.
            </p>
          </section>

          <section v-if="composicionAbierta.alergenos">
            <h5>Alérgenos declarados</h5>
            <p class="composicion-alergenos">{{ composicionAbierta.alergenos }}</p>
          </section>

          <p class="nutri-origen">
            Leído de la ficha de {{ composicionAbierta.tienda }} en el momento
            de la consulta.
          </p>
        </div>
      </div>
    </div>

    <!--
      Ficha nutricional. Se superpone solo a esta sección, no a toda la página:
      quien la abre está comparando filas de ESTA tabla.
    -->
    <div v-if="nutriAbierta" class="modal-fondo modal-fondo-gondola"
         @click.self="nutriAbierta = null">
      <div class="modal" role="dialog" aria-modal="true">
        <header class="modal-cabecera">
          <div>
            <h4>{{ nutriAbierta.nombre }}</h4>
            <p class="modal-sub">
              {{ nutriAbierta.tienda }} ·
              <a :href="nutriAbierta.fuente_url" target="_blank" rel="noopener">
                ver ficha en la tienda
              </a>
            </p>
          </div>
          <button class="modal-cerrar" @click="nutriAbierta = null" aria-label="Cerrar">×</button>
        </header>

        <div class="modal-cuerpo">
          <!-- La base va primero y destacada: sin ella, «210,6 kcal» no se
               puede comparar con nada. Podría ser de 30 g o de 60 g. -->
          <p class="nutri-porcion">
            Valores por porción de
            <strong>{{ nutriAbierta.nutricion.porcion || 'tamaño no declarado' }}</strong>
            <span v-if="nutriAbierta.nutricion.porciones_envase">
              · {{ nutriAbierta.nutricion.porciones_envase }} porciones por envase
            </span>
          </p>

          <dl class="nutri-tabla">
            <template v-for="f in filasNutri" :key="f.etiqueta">
              <dt>{{ f.etiqueta }}</dt>
              <dd>{{ f.valor }}</dd>
            </template>
          </dl>

          <p v-if="nutriAbierta.nutricion.alergenos" class="nutri-alergenos">
            <strong>Alérgenos declarados:</strong>
            {{ nutriAbierta.nutricion.alergenos }}
          </p>

          <!-- La advertencia de la propia tienda sobre sus cifras. Va a la
               vista y no en letra pequeña: presentar como medido algo que la
               ficha marca como teórico sería lo contrario de lo que hace este
               informe. -->
          <p v-if="nutriAbierta.nutricion.nota" class="nutri-nota">
            ⚠️ La tienda declara: «{{ nutriAbierta.nutricion.nota }}»
          </p>

          <p class="nutri-origen">
            Leído de la ficha de {{ nutriAbierta.tienda }}. No se ha recalculado
            ni completado con otras fuentes.
          </p>
        </div>
      </div>
    </div>

    <!-- Sin ofertas no hay tiendas que listar, y «Cadenas consultadas: .» es
         peor que no decir nada: parece un fallo de plantilla. -->
    <p v-if="ofertas.length" class="gondola-pie">
      {{ etiquetaTiendas }}: {{ tiendas.join(', ') }}.
      <template v-if="nComparables">
        <strong>{{ nComparables }}</strong>
        {{ nComparables === 1 ? 'producto aparece' : 'productos aparecen' }}
        en más de una tienda: son las filas marcadas, y ahí se ve la diferencia
        de precio por el mismo código de barras.
      </template>
    </p>

    <!-- El pie de la tasa solo aparece si en esta tabla hay alguna: no se
         avisa de un problema que esta tabla no tiene. -->
    <p v-if="fuentesNoOficiales.length" class="gondola-pie gondola-tasa">
      ⚠️ El BCRP no publica tipo de cambio para
      {{ monedasNoOficiales.join(', ') }}. Los importes en soles de esas filas
      se han convertido con {{ fuentesNoOficiales.join(', ') }} y
      <strong>no son cifras oficiales</strong>: el precio de la izquierda, el
      que publica la tienda, sí lo es.
    </p>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  titulo: { type: String, required: true },
  // Lista vacía = no se consultó ese mercado, o no había nada. La sección
  // entera no se pinta: una tabla vacía con cabeceras se lee como un fallo de
  // carga, no como una ausencia declarada.
  ofertas: { type: Array, default: () => [] },
  subtitulo: { type: String, required: true },
  // «Cadenas consultadas» en Perú —se sabe cuáles se preguntaron— frente a
  // «Tiendas encontradas» en Alemania, donde el agente trae lo que halla. No es
  // cosmético: decir «consultadas» de una lista que no se eligió sería falso.
  etiquetaTiendas: { type: String, default: 'Tiendas' },
})

const MONEDA_LOCAL = 'PEN'

const SIMBOLOS = { PEN: 'S/', EUR: '€', USD: 'US$', GBP: '£' }

const nutriAbierta = ref(null)
// Estado propio y no reutilizando `nutriAbierta`: son dos fichas distintas
// —composición y nutrición— y compartir la variable obligaría a preguntar de
// cuál se trata en cada uso. Además pueden abrirse desde columnas distintas de
// la misma fila.
const composicionAbierta = ref(null)

const tiendas = computed(() =>
  [...new Set(props.ofertas.map(o => o.tienda))].sort()
)

// EAN que aparece en más de una tienda. Es lo que hace que esta tabla sea una
// comparación y no una lista: el nombre del producto cambia de una tienda a
// otra, el código de barras no.
const eansRepetidos = computed(() => {
  const cuenta = new Map()
  for (const o of props.ofertas) {
    if (!o.ean) continue
    cuenta.set(o.ean, (cuenta.get(o.ean) ?? 0) + 1)
  }
  return new Set([...cuenta].filter(([, n]) => n > 1).map(([ean]) => ean))
})

const esComparable = (oferta) => Boolean(oferta.ean) && eansRepetidos.value.has(oferta.ean)
const nComparables = computed(() => eansRepetidos.value.size)

const tienePrecio = (o) => o.precio !== null && o.precio !== undefined
const esLocal = (o) => (o.moneda || MONEDA_LOCAL).toUpperCase() === MONEDA_LOCAL

/** El precio tal como lo publica la tienda, con el símbolo de su moneda. */
const enOrigen = (o) => {
  if (!tienePrecio(o)) return ''
  const moneda = (o.moneda || '').toUpperCase()
  // Con el código ISO cuando no se conoce el símbolo: 'CHF 4,99' se entiende,
  // '4,99' a secas no dice en qué se paga.
  return `${SIMBOLOS[moneda] ?? moneda} ${o.precio.toFixed(2)}`.trim()
}

/**
 * Si la tasa con la que se convirtió esa fila es la del banco central.
 *
 * `adaptadores/tipo_cambio.py` etiqueta la fuente: 'BCRP · <nombre de la
 * serie>' cuando la publica el banco, y 'exchangerate-api.com (no oficial)'
 * cuando cae al respaldo. Se mira ese prefijo y no una lista de monedas
 * porque quien decide es el backend: el día que el BCRP publique el franco,
 * basta con añadir la serie allí y esta tabla deja de marcarlo sola.
 */
const esOficial = (o) => /^BCRP/.test(o.conversion?.fuente ?? '')

// Las filas convertidas con una tasa que no es del BCRP. Se agregan para el
// pie: repetir la explicación entera en cada fila la volvería ruido, y el chip
// de la celda ya dice cuáles son.
const filasNoOficiales = computed(() =>
  props.ofertas.filter(o =>
    o.precio_pen !== null && o.precio_pen !== undefined && !esLocal(o) && !esOficial(o))
)

const monedasNoOficiales = computed(() =>
  [...new Set(filasNoOficiales.value.map(o => (o.moneda || '').toUpperCase()).filter(Boolean))].sort()
)

const fuentesNoOficiales = computed(() =>
  [...new Set(filasNoOficiales.value.map(o => o.conversion?.fuente).filter(Boolean))].sort()
)

/** Con qué se convirtió. Sin esto la cifra en soles no es citable. */
const detalleConversion = (o) => {
  const c = o.conversion
  if (!c) return 'Convertido a soles'
  const partes = [`1 ${c.moneda_origen} = ${c.tasa} PEN`]
  if (c.fecha_tasa) partes.push(`tasa del ${c.fecha_tasa}`)
  if (c.fuente) partes.push(c.fuente)
  return partes.join(' · ')
}

// Orden fijo, el de una etiqueta nutricional. Se recorre siempre igual aunque
// falten campos, para que dos productos se puedan comparar leyendo en paralelo;
// los que la tienda no publica no se pintan, en vez de salir a cero.
const CAMPOS_NUTRI = [
  ['calorias', 'Calorías'],
  ['proteinas', 'Proteínas'],
  ['carbohidratos', 'Carbohidratos'],
  ['azucares', 'Azúcares'],
  ['grasas', 'Grasas'],
  ['sodio', 'Sodio'],
]

const filasNutri = computed(() => {
  const n = nutriAbierta.value?.nutricion
  if (!n) return []

  const filas = CAMPOS_NUTRI
    .filter(([clave]) => n[clave])
    .map(([clave, etiqueta]) => ({ etiqueta, valor: n[clave] }))

  // Lo que la ficha traía y no estaba previsto, con su nombre original. Se
  // enseña en vez de tirarlo: una etiqueta desconocida sigue siendo un dato.
  for (const [etiqueta, valor] of Object.entries(n.otros ?? {})) {
    filas.push({ etiqueta, valor })
  }
  return filas
})
</script>

<style scoped>
/*
  Los estilos van copiados de Result.vue y no importados porque los `<style
  scoped>` de Vue no cruzan al hijo. Es el precio de extraer el componente, y
  sale a cuenta: la plantilla y la lógica —que son lo que se desincroniza— ya
  no están duplicadas.
*/

.gondola {
  margin-top: 28px;
  padding-top: 22px;
  /* Separador visible: son tablas que responden preguntas distintas, y sin una
     línea entre ellas la de abajo se lee como continuación de la de arriba. */
  border-top: 2px solid var(--card-border);
  /* Ancla de la ficha nutricional. Sin esto, el overlay treparía hasta el
     siguiente ancestro posicionado y taparía también la tabla de arriba, que no
     tiene nada que ver con lo que se está mirando. */
  position: relative;
}

/* La sección puede ser corta si el insumo tiene pocas ofertas, e `inset: 0`
   heredaría esa altura dejando la ficha aplastada. */
.modal-fondo-gondola { min-height: 360px; }

.gondola-titulo {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 4px;
  font-size: 1.05rem;
}

.gondola-n {
  font-size: 0.76rem;
  font-weight: 600;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(100, 116, 139, 0.14);
}

.gondola-sub, .gondola-pie {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
  line-height: 1.5;
}

.gondola-pie { margin-top: 10px; }

/* La ausencia declarada. Se parece a un «sin dato» de celda —mismo gris, mismo
   fondo tenue— porque es lo mismo a escala de sección: un hueco que se sabe que
   es hueco, no un fallo de carga. */
.gondola-vacia {
  margin: 14px 0 0;
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 0.84rem;
  background: rgba(100, 116, 139, 0.1);
  color: var(--text-muted);
}

.gondola-tabla .num { text-align: right; font-variant-numeric: tabular-nums; }
.gondola-tabla .precio { font-weight: 600; }

/* El precio original, atenuado frente a la cifra en soles: la columna se ordena
   y se compara por los soles, y el origen está para poder auditarla. */
.precio-origen {
  font-weight: 500;
  color: var(--text-muted);
}

.precio-flecha {
  margin: 0 4px;
  color: var(--text-muted);
}

/* Ámbar y no rojo: la cifra no está mal, solo no la respalda el banco central.
   Con texto y no solo con color, por lo mismo que el chip de EAN repetido. */
.chip-tasa {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 600;
  white-space: nowrap;
  background: rgba(217, 119, 6, 0.14);
  color: #92400E;
}

.gondola-tasa { margin-top: 6px; }

.gondola-tabla .ean {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  color: var(--text-muted);
}

/* Fondo tenue en las filas que se pueden comparar entre tiendas. El chip de
   texto va al lado a propósito: el color no puede ser el único portador. */
.gondola-tabla tr.comparable { background: rgba(45, 151, 102, 0.06); }

.chip-comparable {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 0.66rem;
  font-weight: 600;
  background: rgba(45, 151, 102, 0.16);
  color: var(--primary-hover);
  white-space: nowrap;
}

.mapa-tabla-scroll {
  margin-top: 16px;
  overflow-x: auto;
}

.mapa-tabla {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.mapa-tabla th {
  text-align: left;
  padding: 8px 10px;
  background: rgba(100, 116, 139, 0.12);
  border-bottom: 2px solid var(--card-border);
  white-space: nowrap;
  font-weight: 600;
}

.mapa-tabla td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--card-border);
  vertical-align: top;
  white-space: nowrap;
}

.mapa-tabla tbody tr:hover {
  background: rgba(100, 116, 139, 0.06);
}

/* El nombre es lo único que puede ser largo; se le deja crecer y se corta. */
.col-producto {
  white-space: normal;
  min-width: 240px;
  max-width: 380px;
}

.mapa-tabla a {
  color: var(--primary-color);
  text-decoration: none;
}

.mapa-tabla a:hover {
  text-decoration: underline;
}

/*
  Atenuada y a la vez visible: el objetivo no es esconder el hueco —sería lo
  contrario de lo que el mapa quiere enseñar— sino que se lea como un hueco
  declarado y no como un dato más de la fila.
*/
.sin-dato {
  display: inline-block;
  font-size: 0.78rem;
  padding: 1px 7px;
  border-radius: 10px;
  background: rgba(100, 116, 139, 0.14);
  color: var(--text-muted);
}

.btn-ficha {
  padding: 4px 10px;
  font-size: 0.78rem;
  white-space: nowrap;
  border-radius: 6px;
  border: 1px solid var(--card-border);
  background: rgba(56, 189, 248, 0.12);
  color: var(--primary-color);
  cursor: pointer;
}

.btn-ficha:hover {
  background: rgba(56, 189, 248, 0.24);
}

.modal-fondo {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.55);
}

.modal {
  width: 100%;
  max-width: 620px;
  /* Del alto del panel, no del viewport: la ficha vive dentro de su caja. */
  max-height: 100%;
  display: flex;
  flex-direction: column;
  text-align: left;
  border-radius: 12px;
  border: 1px solid var(--card-border);
  background: var(--card-bg, #fff);
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.4);
}

.modal-cabecera {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--card-border);
}

.modal-cabecera h4 {
  margin: 0 0 4px 0;
  font-size: 1.02rem;
}

.modal-sub {
  margin: 0;
  font-size: 0.82rem;
  color: var(--text-muted);
}

.modal-sub a {
  color: var(--primary-color);
}

.modal-cerrar {
  margin-left: auto;
  border: none;
  background: none;
  font-size: 1.6rem;
  line-height: 1;
  cursor: pointer;
  color: var(--text-muted);
}

.modal-cuerpo {
  padding: 18px 22px;
  overflow-y: auto;
}

.nutri-porcion {
  margin: 0 0 14px;
  font-size: 0.88rem;
  color: var(--text-muted);
}

.nutri-tabla {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0;
  margin: 0;
  font-size: 0.9rem;
}

.nutri-tabla dt,
.nutri-tabla dd {
  padding: 7px 2px;
  margin: 0;
  border-bottom: 1px solid rgba(45, 151, 102, 0.14);
}

.nutri-tabla dd {
  text-align: right;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.nutri-alergenos {
  margin: 16px 0 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.nutri-nota {
  margin: 14px 0 0;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(217, 119, 6, 0.1);
  color: #92400E;
  font-size: 0.84rem;
}

/* --- Composición: ingredientes y alérgenos ------------------------------- */

.composicion { white-space: nowrap; }

/* Ámbar y no verde: el botón no ofrece la lista de ingredientes —esa no
   existe— sino una advertencia de alérgenos. Que se distinga del «Ver lista»
   evita que quien recorra la columna crea que están enseñando lo mismo. */
.btn-ficha.alergeno {
  border-color: rgba(217, 119, 6, 0.45);
  color: #92400E;
  background: rgba(217, 119, 6, 0.08);
}

.composicion-texto {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.55;
}

.composicion-ausente {
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
  color: var(--text-muted);
}

.composicion-alergenos {
  margin: 0;
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(217, 119, 6, 0.1);
  color: #92400E;
  font-size: 0.86rem;
  line-height: 1.5;
}

.nutri-origen {
  margin: 14px 0 0;
  font-size: 0.78rem;
  font-style: italic;
  color: var(--text-muted);
}
</style>
