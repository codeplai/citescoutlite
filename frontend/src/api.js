/**
 * Cliente HTTP del backend.
 *
 * Existe porque hasta S3 la SPA solo mandaba el token en el login: `/consultas`,
 * `/informes/{id}` y el consumo se llamaban sin cabecera `Authorization` contra
 * endpoints que la exigen desde S1. La búsqueda devolvía 401 siempre y el error
 * se mostraba como "Ocurrió un error al consultar el insumo".
 *
 * Un solo sitio adjunta el token, y un solo sitio decide qué hacer con un 401.
 */

const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export const CLAVE_TOKEN = 'agroscout_token'
export const CLAVE_USUARIO = 'agroscout_user'

export class NoAutorizado extends Error {}

function cabeceras(extra = {}) {
  const token = localStorage.getItem(CLAVE_TOKEN)
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  }
}

async function pedir(ruta, opciones = {}) {
  const respuesta = await fetch(`${BASE}${ruta}`, {
    ...opciones,
    headers: cabeceras(opciones.headers),
  })

  if (respuesta.status === 401) {
    // El token de Supabase vive ~1 h. Al caducar, la sesión se cierra sola en
    // vez de dejar la interfaz fallando sin explicación.
    localStorage.removeItem(CLAVE_TOKEN)
    localStorage.removeItem(CLAVE_USUARIO)
    window.dispatchEvent(new CustomEvent('agroscout:sesion-caducada'))
    throw new NoAutorizado('Sesión caducada')
  }

  if (!respuesta.ok) {
    const detalle = await respuesta.text()
    throw new Error(`${respuesta.status}: ${detalle.slice(0, 200)}`)
  }

  return respuesta.json()
}

export const api = {
  login: (email, password) =>
    fetch(`${BASE}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),

  consultar: (texto) =>
    pedir('/consultas', { method: 'POST', body: JSON.stringify({ texto }) }),

  uso: () => pedir('/uso'),

  /**
   * El bucket es privado: el backend no devuelve el PDF sino una URL firmada de
   * una hora. Se pide en el momento de descargar, no al generar el informe,
   * porque un enlace emitido al principio puede caducar antes de usarse.
   */
  urlInforme: (ejecucionId) => pedir(`/informes/${ejecucionId}`),

  // S6.7 - Alertas de retiro (openFDA + RASFF).
  alertasActivas: ({ limite = 50, dias = 90, severidad = '' } = {}) => {
    const params = new URLSearchParams({ limite, dias })
    if (severidad) params.append('severidad', severidad)
    return pedir(`/api/alertas/activas?${params}`)
  },

  alertaDetalle: (alertId) => pedir(`/api/alertas/${alertId}`),

  estadisticasAlertas: () => pedir('/api/alertas/estadisticas/resumen'),

  // S7.6 - Promocion manual (el 20 % que revisa una persona).
  promocionesPendientes: ({ limite = 50, soloConErrores = false } = {}) => {
    const params = new URLSearchParams({ limite, solo_con_errores: soloConErrores })
    return pedir(`/api/promociones/pendientes?${params}`)
  },

  promover: (stagingId) =>
    pedir(`/api/promociones/${stagingId}/promover`, { method: 'POST' }),

  promoverLote: (stagingIds) =>
    pedir('/api/promociones/promover-lote', {
      method: 'POST',
      body: JSON.stringify({ staging_ids: stagingIds }),
    }),

  rechazar: (stagingId) =>
    pedir(`/api/promociones/${stagingId}/rechazar`, { method: 'POST' }),

  historialPromociones: (dias = 7) =>
    pedir(`/api/promociones/historial?dias=${dias}`),

  resumenPromociones: () => pedir('/api/promociones/resumen'),

  // Todo el widget de 7.9 en una llamada: si el resumen y la tendencia
  // vinieran por separado, un refresco a medias mezclaria dos ventanas.
  estadisticasPromociones: ({ horas = 24, dias = 7 } = {}) =>
    pedir(`/api/promociones/estadisticas?horas=${horas}&dias=${dias}`),
}
