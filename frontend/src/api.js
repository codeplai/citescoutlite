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

// Exportada: cuando una petición no llega a salir, la pantalla tiene que poder
// decir **a qué dirección** estaba llamando. Sin eso, «no se pudo contactar con
// el servidor» no distingue un backend caído de un VITE_API_URL mal puesto.
export const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export const CLAVE_TOKEN = 'agroscout_token'
export const CLAVE_USUARIO = 'agroscout_user'

export class NoAutorizado extends Error {}

/**
 * Un error del backend con su código a mano.
 *
 * Antes se lanzaba `new Error(\`${status}: ${detalle}\`)` y quien lo recogía
 * tenía que buscar el número dentro de la cadena con `includes('404')` — que
 * además casa con un 404 que aparezca en el cuerpo del mensaje. Con el código
 * en un campo, la interfaz puede decir cosas distintas para «no existe», «no
 * tienes permiso» y «el servidor se rompió», que es justo lo que hace falta
 * cuando algo falla y hay que averiguar por qué.
 */
export class ErrorHttp extends Error {
  constructor(status, detalle) {
    super(`${status}: ${detalle}`)
    this.status = status
    this.detalle = detalle
  }
}

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
    const crudo = await respuesta.text()
    // El backend responde `{"detail": "..."}`; se saca el texto para no
    // enseñar el JSON en bruto a quien lea la pantalla.
    let detalle = crudo.slice(0, 300)
    try {
      detalle = JSON.parse(crudo).detail ?? detalle
    } catch { /* no era JSON: se deja el cuerpo tal cual */ }
    throw new ErrorHttp(respuesta.status, detalle)
  }

  return respuesta.json()
}

/**
 * Igual que `pedir`, pero devuelve el cuerpo como Blob.
 *
 * Hace falta porque una descarga con `<a href>` no lleva la cabecera
 * `Authorization`, y el export de auditoría exige rol de administrador: el
 * enlace directo daría 401. Se baja con fetch y se entrega el binario para que
 * quien llama lo guarde.
 */
async function pedirArchivo(ruta) {
  const respuesta = await fetch(`${BASE}${ruta}`, { headers: cabeceras() })

  if (respuesta.status === 401) {
    localStorage.removeItem(CLAVE_TOKEN)
    localStorage.removeItem(CLAVE_USUARIO)
    window.dispatchEvent(new CustomEvent('agroscout:sesion-caducada'))
    throw new NoAutorizado('Sesión caducada')
  }
  if (!respuesta.ok) {
    throw new Error(`${respuesta.status}: ${(await respuesta.text()).slice(0, 200)}`)
  }

  return {
    blob: await respuesta.blob(),
    // El backend avisa por cabecera si el fichero va cortado. Sin esto, quien
    // exporta se lo lleva creyendo que está entero.
    total: Number(respuesta.headers.get('X-Total-Registros') || 0),
    exportados: Number(respuesta.headers.get('X-Registros-Exportados') || 0),
  }
}

const conFiltros = (filtros) => {
  const params = new URLSearchParams()
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor !== '' && valor != null) params.append(clave, valor)
  }
  return params
}

export const api = {
  login: (email, password) =>
    fetch(`${BASE}/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    }),

  // S8.1 - Quién está mirando el panel, y con qué rol. El rol no salía por
  // ningún endpoint, así que el panel no podía decidir qué entradas enseñar.
  sesion: () => pedir('/api/sesion'),

  consultar: (texto) =>
    pedir('/consultas', { method: 'POST', body: JSON.stringify({ texto }) }),

  uso: () => pedir('/uso'),

  /**
   * El bucket es privado: el backend no devuelve el PDF sino una URL firmada de
   * una hora. Se pide en el momento de descargar, no al generar el informe,
   * porque un enlace emitido al principio puede caducar antes de usarse.
   */
  urlInforme: (ejecucionId) => pedir(`/informes/${ejecucionId}`),

  /**
   * T6 - Análisis regulatorio de los aditivos de un producto.
   *
   * Solo van los dos identificadores. La lista de aditivos NO se manda: el
   * backend la relee del informe, porque quien manda la lista decide el
   * resultado y entonces el análisis dejaría de describir el snapshot para
   * describir lo que le mandó la interfaz.
   *
   * `encodeURIComponent` sobre el id no es adorno: son de la forma
   * `OFF:00000036` y los dos puntos hay que escaparlos en la ruta.
   */
  analisisAditivos: (ejecucionId, productoId) =>
    pedir(`/api/analisis-aditivos/${encodeURIComponent(ejecucionId)}`
          + `/${encodeURIComponent(productoId)}`),

  /**
   * Lo mismo para una fila de las tablas de góndola.
   *
   * Va por endpoint aparte porque las ofertas no están en `mapa.productos`:
   * viven en sus tres listas y se identifican por su URL de origen, no por un
   * `producto_id` que no tienen. Los ingredientes tampoco se mandan: el backend
   * los relee del informe.
   */
  analisisOferta: (ejecucionId, fuenteUrl) =>
    pedir(`/api/analisis-aditivos/${encodeURIComponent(ejecucionId)}/oferta`
          + `?url=${encodeURIComponent(fuenteUrl)}`),

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

  // S8.3 - Auditoría. Solo administradores; el backend responde 403 al resto.
  eventosAuditoria: () => pedir('/api/auditoria/eventos'),

  auditoria: ({ limite = 50, desplazamiento = 0, ...filtros } = {}) => {
    const params = conFiltros(filtros)
    params.append('limite', limite)
    params.append('desplazamiento', desplazamiento)
    return pedir(`/api/auditoria?${params}`)
  },

  // El CSV lleva los MISMOS filtros que la tabla: lo que se descarga tiene que
  // ser lo que se está viendo.
  exportarAuditoria: (filtros = {}) =>
    pedirArchivo(`/api/auditoria/export.csv?${conFiltros(filtros)}`),

  // S8.5 y S8.9 - Control. Solo administradores.
  killSwitch: () => pedir('/api/admin/kill-switch'),

  fijarKillSwitch: ({ activo, motivo = null }) =>
    pedir('/api/admin/kill-switch', {
      method: 'PUT', body: JSON.stringify({ activo, motivo }),
    }),

  usuariosAdmin: () => pedir('/api/admin/usuarios'),

  cambiarPlan: (usuarioId, plan) =>
    pedir(`/api/admin/usuarios/${usuarioId}/plan`, {
      method: 'PUT', body: JSON.stringify({ plan }),
    }),

  // S8.2 - Cost-meter. Todo en una llamada: con endpoints separados, un
  // refresco a medias dejaría la serie de una ventana y el desglose de otra, y
  // las cifras dejarían de cuadrar delante de quien las está leyendo.
  costos: (dias = 30) => pedir(`/api/costos?dias=${dias}`),

  exportarCostos: (detalle, dias = 30) =>
    pedirArchivo(`/api/costos/export.csv?detalle=${detalle}&dias=${dias}`),
}
