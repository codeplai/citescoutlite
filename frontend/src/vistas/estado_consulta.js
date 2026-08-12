/**
 * El resultado de la última consulta, fuera del componente.
 *
 * Antes vivía en `App.vue`, que envolvía todas las pestañas, así que ir a
 * Alertas y volver lo conservaba. Al pasar Consulta a ser una ruta, su estado
 * se destruye al navegar: sin esto, asomarse a Promociones te borraría una
 * búsqueda que cuesta dinero y medio minuto.
 *
 * Es memoria del proceso, no persistencia: recargar la página lo pierde. Para
 * que sobreviviera haría falta poder recuperar una ejecución por su id, y hoy
 * el backend solo devuelve el PDF (`/informes/{id}`), no el resultado. Cuando
 * exista, el sitio natural es la propia URL: `/consulta/:ejecucionId`.
 */

import { ref } from 'vue'

export const resultadoConsulta = ref(null)

export function olvidarConsulta() {
  resultadoConsulta.value = null
}
