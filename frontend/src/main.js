import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router/index.js'

const app = createApp(App).use(router)

// Se monta cuando el router ha resuelto la primera navegación, no antes.
// Montar de inmediato renderiza una vez con la ruta sin resolver —`meta` vacío
// y las rutas perezosas todavía descargándose—, y `App.vue` decide con
// `meta.publica` si dibuja la barra lateral: el login aparecería un instante
// con el panel montado alrededor.
router.isReady().then(() => app.mount('#app'))
