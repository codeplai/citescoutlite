<!--
  El acceso.

  ## La única firma de marca que queda

  El degradado verde→azul se ha retirado del cuerpo de la aplicación —competía
  con el ámbar de aviso y el rojo de crítico, que en este sistema significan
  algo— pero aquí sobrevive, ya sin el azul, en la banda superior de la
  tarjeta. Es el sitio donde una firma tiene sentido: la pantalla que no
  enseña ningún dato y cuyo único trabajo es decir de quién es esto.

  ## Los errores dicen qué hacer

  «Error al conectar con el servidor» no es un mensaje, es un encogimiento de
  hombros. En una demo con la API caída, quien lo lee no sabe si escribió mal
  la contraseña, si le falta red o si el backend no está arrancado. Los tres
  casos se separan aquí y cada uno lleva su salida.
-->
<template>
  <div class="acceso">
    <div class="tarjeta superficie animate-fade-in">
      <div class="firma" aria-hidden="true"></div>

      <div class="marca">
        <h1>AgroScout <span class="highlight">IA</span></h1>
        <p class="entidad">CITEagroindustrial Chavimochic</p>
      </div>

      <form class="formulario" novalidate @submit.prevent="handleLogin">
        <div class="campo">
          <label for="email">Correo electrónico</label>
          <input
            id="email"
            v-model="email"
            type="email"
            name="email"
            placeholder="usuario@cite.gob.pe"
            autocomplete="username"
            required
            :disabled="isLoading"
            :aria-invalid="errorMsg ? 'true' : undefined"
            :aria-describedby="errorMsg ? 'error-acceso' : undefined"
          />
        </div>

        <div class="campo">
          <label for="password">Contraseña</label>
          <input
            id="password"
            v-model="password"
            type="password"
            name="password"
            placeholder="••••••••"
            autocomplete="current-password"
            required
            :disabled="isLoading"
            :aria-invalid="errorMsg ? 'true' : undefined"
            :aria-describedby="errorMsg ? 'error-acceso' : undefined"
          />
        </div>

        <!--
          `aria-busy` y el texto que cambia son la misma información por dos
          vías: la que se ve y la que se oye. Un botón que solo se deshabilita
          no anuncia nada a quien usa lector de pantalla, y el intento de
          acceso puede tardar lo que tarde Supabase en responder.
        -->
        <button
          type="submit"
          class="btn btn--principal btn--bloque acceder"
          :disabled="isLoading"
          :aria-busy="isLoading"
        >
          <span v-if="isLoading" class="hilandero" aria-hidden="true"></span>
          {{ isLoading ? 'Validando…' : 'Entrar' }}
        </button>

        <!--
          `role="alert"` para que el fallo se anuncie en cuanto aparece: sin
          esto, quien no ve la pantalla pulsa Entrar, no pasa nada aparente y
          no tiene forma de enterarse de que hubo un error.
        -->
        <p v-if="errorMsg" id="error-acceso" class="error" role="alert">
          <Icono nombre="info" :tamano="16" />
          <span>
            <strong>{{ errorMsg.titulo }}</strong>
            <span class="error-que-hacer">{{ errorMsg.quehacer }}</span>
          </span>
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api.js'
import { entrar } from '../sesion.js'
import Icono from './Icono.vue'

const email = ref('')
const password = ref('')
const errorMsg = ref(null)
const isLoading = ref(false)

const route = useRoute()
const router = useRouter()

/**
 * A dónde ir tras entrar. Se vuelve a donde se quería ir —sin esto, caducar la
 * sesión en Promociones te dejaría siempre en Consulta—, pero el valor viene
 * de la barra de direcciones y hay que acotarlo.
 *
 * Solo se acepta una ruta interna: una sola barra al principio. `//evil.pe` es
 * protocolo-relativa y el navegador la trataría como otro dominio, que es la
 * forma clásica de convertir una pantalla de login en un redirector abierto.
 * `/\evil.pe` cuenta igual: varios navegadores tratan la contrabarra como
 * barra al normalizar la URL.
 */
function destinoSeguro(volverA) {
  if (typeof volverA !== 'string') return { name: 'consulta' }
  if (!/^\/[^/\\]/.test(volverA)) return { name: 'consulta' }
  return volverA
}

/**
 * Traduce el fallo a algo accionable.
 *
 * Los tres casos se distinguen porque exigen tres cosas distintas de quien
 * está delante: corregir lo que escribió, mirar el log del servidor, o ir a
 * arrancar la API. Dárselos como un único «error al conectar» le obliga a
 * probar los tres a ciegas.
 */
function explicar(status) {
  if (status === 401) {
    return {
      titulo: 'Correo o contraseña incorrectos',
      quehacer:
        'Revisa los dos campos. Las credenciales de demostración están en ' +
        '.env.local, no en el repositorio.',
    }
  }
  if (status >= 500) {
    return {
      titulo: 'El servidor respondió con un error',
      quehacer:
        'No es cosa de tus credenciales. Mira la ventana «AgroScout API»: el ' +
        'motivo está en su log.',
    }
  }
  return {
    titulo: 'No se pudo contactar con el servidor',
    quehacer:
      'La API debería escuchar en :8001. Comprueba que iniciar.bat la ' +
      'levantó y que sigue abierta.',
  }
}

const handleLogin = async () => {
  if (!email.value || !password.value) return

  isLoading.value = true
  errorMsg.value = null

  try {
    // El backend hace de proxy del password grant de Supabase y conserva la
    // misma forma de request y response que en S1, así que este componente no
    // necesita ninguna clave de Supabase.
    const res = await api.login(email.value, password.value)

    if (!res.ok) {
      errorMsg.value = explicar(res.status)
      return
    }

    const data = await res.json()
    entrar(data.user, data.access_token)
    await router.push(destinoSeguro(route.query.volverA))
  } catch {
    // Un fallo de `fetch` es red o servidor caído: nunca llega status.
    errorMsg.value = explicar(0)
  } finally {
    isLoading.value = false
  }
}
</script>

<style scoped>
.acceso {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 24px;
  background: var(--lienzo);
}

.tarjeta {
  position: relative;
  width: 100%;
  max-width: 400px;
  padding: 40px 36px 36px;
  overflow: hidden;
  box-shadow: var(--sombra-elevada);
}

/* La firma. 4px de degradado de marca en el borde superior y nada más: no hay
   ningún dato debajo con el que pueda competir. */
.firma {
  position: absolute;
  inset: 0 0 auto;
  height: 4px;
  background: var(--firma-marca);
}

.marca {
  text-align: center;
  margin-bottom: 32px;
}

.marca h1 {
  margin: 0 0 6px;
  font-size: 1.875rem;
  font-weight: 800;
  letter-spacing: -0.028em;
}

.highlight {
  color: var(--verde);
}

.entidad {
  margin: 0;
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--texto-atenuado);
}

.formulario {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.campo {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.campo label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--texto-atenuado);
}

.acceder {
  margin-top: 6px;
  padding: 12px;
  font-size: 0.9375rem;
}

/* Anillo, no rueda: gira sin dar a entender un porcentaje. */
.hilandero {
  width: 15px;
  height: 15px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: girar 0.7s linear infinite;
}

@keyframes girar {
  to { transform: rotate(360deg); }
}

.error {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  margin: 0;
  padding: 12px 14px;
  font-size: 0.82rem;
  line-height: 1.5;
  color: var(--critico);
  background: var(--critico-fondo);
  border: 1px solid var(--critico-borde);
  border-radius: var(--r-sm);
}

.error strong {
  display: block;
  font-weight: 700;
}

.error-que-hacer {
  display: block;
  margin-top: 3px;
  color: var(--texto-atenuado);
}
</style>
