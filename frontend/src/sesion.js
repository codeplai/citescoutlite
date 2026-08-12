/**
 * S8.1 - Quién ha entrado, en un solo sitio.
 *
 * Hasta ahora esto vivía en `App.vue` como dos `ref` sueltos, y bastaba: había
 * una pantalla y un `v-if`. Con el router hay tres sitios que necesitan lo
 * mismo —el guard antes de navegar, la barra lateral para decidir qué enseñar
 * y la cabecera para el correo—, y ninguno es padre de los otros.
 *
 * ## El rol no se guarda en localStorage
 *
 * El correo y el token sí, porque hacen falta para reanudar la sesión al
 * recargar. El rol no: **es una respuesta del servidor y se vuelve a pedir**.
 * Guardarlo invitaría a que el guard leyese de un sitio que cualquiera puede
 * reescribir desde las herramientas de desarrollo.
 *
 * Aun así, lo que decide de verdad es `requiere_admin` en cada endpoint. Esto
 * es para no enseñar una puerta que se va a cerrar en la cara.
 */

import { reactive } from 'vue'
import { api, CLAVE_TOKEN, CLAVE_USUARIO, NoAutorizado } from './api.js'

export const sesion = reactive({
  email: localStorage.getItem(CLAVE_USUARIO) || '',
  rol: null,       // null = todavía no se ha preguntado
})

// La promesa en vuelo, no un booleano: si la barra lateral y el guard piden el
// perfil a la vez —que es justo lo que pasa al recargar—, un booleano deja al
// segundo sin nada que esperar y navegaría sin saber el rol.
let enVuelo = null

export function hayToken() {
  return Boolean(localStorage.getItem(CLAVE_TOKEN))
}

export function esAdmin() {
  return sesion.rol === 'admin'
}

/** El perfil del servidor, pedido una sola vez por sesión. */
export async function asegurarPerfil() {
  if (sesion.rol) return sesion
  if (!enVuelo) {
    enVuelo = api.sesion()
      .then((datos) => {
        sesion.email = datos.email || sesion.email
        sesion.rol = datos.rol || 'operador'
        return sesion
      })
      .catch((error) => {
        // Un 401 ya lo gestionó api.js: limpió el token y avisó, así que el
        // guard mandará al login. Cualquier otro fallo —el backend caído— se
        // resuelve hacia el lado seguro: sin privilegios. Enseñar el panel de
        // administración porque no se pudo comprobar el rol sería exactamente
        // al revés.
        if (!(error instanceof NoAutorizado)) sesion.rol = 'operador'
        return sesion
      })
      .finally(() => { enVuelo = null })
  }
  return enVuelo
}

export function entrar(email, token) {
  localStorage.setItem(CLAVE_TOKEN, token)
  localStorage.setItem(CLAVE_USUARIO, email)
  sesion.email = email
  sesion.rol = null    // se vuelve a preguntar: puede ser otra persona
}

export function salir() {
  localStorage.removeItem(CLAVE_TOKEN)
  localStorage.removeItem(CLAVE_USUARIO)
  sesion.email = ''
  sesion.rol = null
  enVuelo = null
}
