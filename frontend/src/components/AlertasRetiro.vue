<template>
  <div class="alertas-retiro">
    <!-- Header con resumen -->
    <div class="header-alertas">
      <div class="titulo">
        <h2>🚨 Vigilancia de Retiros</h2>
        <p class="subtitle">Alertas activas de FDA + RASFF (últimas 90 días)</p>
      </div>

      <div class="estadisticas">
        <div class="stat-card">
          <div class="stat-valor">{{ estadisticas.alertas_criticas }}</div>
          <div class="stat-label">Críticas</div>
          <div class="stat-icon">🔴</div>
        </div>

        <div class="stat-card">
          <div class="stat-valor">{{ estadisticas.alertas_activas_90d }}</div>
          <div class="stat-label">Activas</div>
          <div class="stat-icon">⚠️</div>
        </div>

        <div class="stat-card">
          <div class="stat-valor">{{ estadisticas.total_alertas }}</div>
          <div class="stat-label">Totales</div>
          <div class="stat-icon">📊</div>
        </div>

        <div class="stat-card small">
          <div class="stat-label">Última actualización</div>
          <div class="stat-valor-small">{{ formatearFecha(estadisticas.ultima_actualizacion) }}</div>
        </div>
      </div>
    </div>

    <!-- Controles de filtro -->
    <div class="filtros">
      <div class="filtro-grupo">
        <label>Severidad:</label>
        <select v-model="filtroSeveridad" @change="cargarAlertas">
          <option value="">Todas</option>
          <option value="critical">🔴 Crítica</option>
          <option value="high">🟠 Alta</option>
          <option value="medium">🟡 Media</option>
          <option value="low">🟢 Baja</option>
        </select>
      </div>

      <div class="filtro-grupo">
        <label>Días:</label>
        <select v-model.number="filtroDias" @change="cargarAlertas">
          <option value="7">Últimos 7 días</option>
          <option value="30">Últimos 30 días</option>
          <option value="90">Últimos 90 días</option>
        </select>
      </div>

      <div class="filtro-grupo">
        <label>Límite:</label>
        <input
          v-model.number="filtroLimite"
          type="number"
          min="1"
          max="200"
          @change="cargarAlertas"
        />
      </div>

      <button @click="cargarAlertas" class="btn-refresh">
        🔄 Actualizar
      </button>
    </div>

    <!-- Listado de alertas -->
    <div class="alertas-lista">
      <div v-if="cargando" class="loading">
        ⏳ Cargando alertas...
      </div>

      <div v-else-if="alertas.length === 0" class="sin-alertas">
        ✅ Sin alertas activas para los filtros seleccionados
      </div>

      <div v-else class="alertas-container">
        <div
          v-for="alerta in alertas"
          :key="alerta.alert_id"
          :class="['alerta-card', `severity-${alerta.severity_label}`]"
          @click="mostrarDetalle(alerta)"
        >
          <!-- Encabezado -->
          <div class="alerta-header">
            <div class="alerta-titulo">
              <span class="badge" :class="`badge-${alerta.severity_label}`">
                {{ etiquetaSeveridad(alerta.severity_label) }}
              </span>
              <h3>{{ alerta.producto_nombre }}</h3>
            </div>

            <div class="alerta-fuente">
              <span class="fuente-badge" :class="`fuente-${alerta.fuente}`">
                {{ alerta.fuente.toUpperCase() }}
              </span>
            </div>
          </div>

          <!-- Contenido -->
          <div class="alerta-contenido">
            <div class="contenido-fila">
              <span class="label">Riesgo:</span>
              <span class="valor">
                {{ capitalizarPrimera(alerta.riesgo_categoria) }}
              </span>
            </div>

            <div class="contenido-fila">
              <span class="label">Descripción:</span>
              <span class="valor">{{ alerta.riesgo_texto }}</span>
            </div>

            <div class="contenido-fila">
              <span class="label">Fecha:</span>
              <span class="valor">
                {{ formatearFecha(alerta.fecha_emitida) }}
                <span class="dias-atrás">(hace {{ alerta.dias_desde }} días)</span>
              </span>
            </div>

            <div class="contenido-fila">
              <span class="label">País Origen:</span>
              <span class="valor">{{ alerta.pais_origen }}</span>
            </div>

            <div v-if="alerta.severity_score" class="contenido-fila">
              <span class="label">Score:</span>
              <div class="score-bar">
                <div
                  class="score-fill"
                  :style="{ width: (alerta.severity_score / 5) * 100 + '%' }"
                ></div>
                <span class="score-valor">{{ alerta.severity_score.toFixed(1) }}/5</span>
              </div>
            </div>
          </div>

          <!-- Pie -->
          <div class="alerta-footer">
            <a :href="alerta.url_oficial" target="_blank" class="link-oficial">
              🔗 Ver en fuente oficial
            </a>
            <span class="click-hint">Click para más detalles →</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de detalles -->
    <div v-if="alertaSeleccionada" class="modal-overlay" @click="cerrarDetalle">
      <div class="modal-contenido" @click.stop>
        <button class="btn-cerrar" @click="cerrarDetalle">✕</button>

        <h2>Detalles de Alerta</h2>

        <div class="detalles-grid">
          <div class="detalle-item">
            <span class="label">ID:</span>
            <span class="valor monospace">{{ alertaSeleccionada.alert_id }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">Fuente:</span>
            <span class="valor">{{ alertaSeleccionada.fuente.toUpperCase() }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">Producto:</span>
            <span class="valor">{{ alertaSeleccionada.producto_nombre }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">Severidad:</span>
            <span class="valor">
              {{ etiquetaSeveridad(alertaSeleccionada.severity_label) }}
              ({{ alertaSeleccionada.severity_score?.toFixed(1) }}/5)
            </span>
          </div>

          <div class="detalle-item full-width">
            <span class="label">Descripción del Riesgo:</span>
            <span class="valor">{{ alertaSeleccionada.riesgo_texto }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">Categoría de Riesgo:</span>
            <span class="valor">{{ capitalizarPrimera(alertaSeleccionada.riesgo_categoria) }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">Fecha Emitida:</span>
            <span class="valor">{{ formatearFecha(alertaSeleccionada.fecha_emitida) }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">Días Desde:</span>
            <span class="valor">{{ alertaSeleccionada.dias_desde }} días</span>
          </div>

          <div class="detalle-item">
            <span class="label">País Origen:</span>
            <span class="valor">{{ alertaSeleccionada.pais_origen }}</span>
          </div>

          <div class="detalle-item">
            <span class="label">País Destino:</span>
            <span class="valor">{{ alertaSeleccionada.pais_destino }}</span>
          </div>

          <div v-if="alertaSeleccionada.empresa" class="detalle-item">
            <span class="label">Empresa:</span>
            <span class="valor">{{ alertaSeleccionada.empresa }}</span>
          </div>

          <div v-if="alertaSeleccionada.reference_number" class="detalle-item">
            <span class="label">Referencia:</span>
            <span class="valor monospace">{{ alertaSeleccionada.reference_number }}</span>
          </div>

          <div class="detalle-item full-width">
            <span class="label">Fuente Oficial:</span>
            <a :href="alertaSeleccionada.url_oficial" target="_blank" class="link-oficial-modal">
              {{ alertaSeleccionada.url_oficial }}
            </a>
          </div>
        </div>

        <div class="modal-acciones">
          <button @click="cerrarDetalle" class="btn-cerrar-modal">Cerrar</button>
          <a :href="alertaSeleccionada.url_oficial" target="_blank" class="btn-original">
            Abrir en FDA/RASFF
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
// Las llamadas pasan por el cliente de api.js y no por fetch directo: es el
// unico sitio que adjunta el token y el que cierra la sesion ante un 401.
//
// Este componente venia escrito para Vue CLI (process.env.VUE_APP_*, puerto
// 8000, clave de token "token"). Nada de eso existe aqui: el bundler es Vite,
// la API escucha en 8001 y el token se guarda en `agroscout_token`. Tal cual
// estaba, reventaba al montarlo con "process is not defined".
import { ref, onMounted } from "vue";
import { api } from "../api.js";

export default {
  name: "AlertasRetiro",

  setup() {
    const alertas = ref([]);
    const cargando = ref(false);
    const alertaSeleccionada = ref(null);
    const estadisticas = ref({
      total_alertas: 0,
      alertas_criticas: 0,
      alertas_activas_90d: 0,
      ultima_actualizacion: null,
    });

    const filtroSeveridad = ref("");
    const filtroDias = ref(90);
    const filtroLimite = ref(50);

    // Cargar alertas del API
    const cargarAlertas = async () => {
      cargando.value = true;

      try {
        const data = await api.alertasActivas({
          limite: filtroLimite.value,
          dias: filtroDias.value,
          severidad: filtroSeveridad.value,
        });

        alertas.value = data.alertas;
        // Las tarjetas de arriba NO se rellenan desde aqui. Los conteos que
        // devuelve /activas son los de la pagina ya filtrada y recortada por
        // el limite, asi que al filtrar por "critical" las tarjetas pasaban a
        // mostrar el total de lo filtrado en vez del global. Los totales
        // buenos salen de /estadisticas/resumen.
      } catch (error) {
        console.error("Error cargando alertas:", error);
        alertas.value = [];
      } finally {
        cargando.value = false;
      }
    };

    // Cargar estadísticas
    const cargarEstadisticas = async () => {
      try {
        estadisticas.value = await api.estadisticasAlertas();
      } catch (error) {
        console.error("Error cargando estadísticas:", error);
      }
    };

    // Mostrar detalle de alerta
    const mostrarDetalle = async (alerta) => {
      try {
        alertaSeleccionada.value = await api.alertaDetalle(alerta.alert_id);
      } catch (error) {
        console.error("Error cargando detalles:", error);
      }
    };

    const cerrarDetalle = () => {
      alertaSeleccionada.value = null;
    };

    // Utilidades
    const etiquetaSeveridad = (label) => {
      const etiquetas = {
        critical: "🔴 CRÍTICA",
        high: "🟠 ALTA",
        medium: "🟡 MEDIA",
        low: "🟢 BAJA",
      };
      return etiquetas[label] || label;
    };

    const capitalizarPrimera = (str) => {
      return str.charAt(0).toUpperCase() + str.slice(1);
    };

    const formatearFecha = (fechaStr) => {
      if (!fechaStr) return "N/A";
      const fecha = new Date(fechaStr);
      return fecha.toLocaleDateString("es-ES", {
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    };

    // Inicializar
    onMounted(() => {
      cargarAlertas();
      cargarEstadisticas();
    });

    return {
      alertas,
      cargando,
      alertaSeleccionada,
      estadisticas,
      filtroSeveridad,
      filtroDias,
      filtroLimite,
      cargarAlertas,
      mostrarDetalle,
      cerrarDetalle,
      etiquetaSeveridad,
      capitalizarPrimera,
      formatearFecha,
    };
  },
};
</script>

<style scoped>
.alertas-retiro {
  padding: 20px;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  min-height: 100vh;
}

/* Header */
.header-alertas {
  margin-bottom: 30px;
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.titulo h2 {
  margin: 0;
  color: #d63031;
  font-size: 28px;
}

.subtitle {
  margin: 8px 0 0 0;
  color: #7f8c8d;
  font-size: 14px;
}

/* Estadísticas */
.estadisticas {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
  margin-top: 15px;
}

.stat-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2);
}

.stat-card.small {
  grid-column: 1 / -1;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.stat-icon {
  font-size: 32px;
  margin-top: 10px;
}

.stat-valor {
  font-size: 32px;
  font-weight: bold;
}

.stat-valor-small {
  font-size: 12px;
  margin-top: 5px;
}

.stat-label {
  font-size: 12px;
  opacity: 0.9;
  margin-top: 8px;
}

/* Filtros */
.filtros {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  background: white;
  padding: 15px;
  border-radius: 8px;
  flex-wrap: wrap;
}

.filtro-grupo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.filtro-grupo label {
  font-weight: 600;
  color: #2c3e50;
}

.filtro-grupo select,
.filtro-grupo input {
  padding: 8px 12px;
  border: 1px solid #bdc3c7;
  border-radius: 4px;
  font-size: 14px;
}

.btn-refresh {
  padding: 8px 16px;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.3s;
}

.btn-refresh:hover {
  background: #5568d3;
}

/* Alertas */
.alertas-lista {
  margin-bottom: 30px;
}

.loading,
.sin-alertas {
  text-align: center;
  padding: 40px 20px;
  background: white;
  border-radius: 8px;
  color: #7f8c8d;
  font-size: 16px;
}

.sin-alertas {
  color: #27ae60;
  background: #ecf0f1;
}

.alertas-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.alerta-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s;
  border-left: 6px solid #95a5a6;
}

.alerta-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

.alerta-card.severity-critical {
  border-left-color: #e74c3c;
  background: linear-gradient(to right, rgba(231, 76, 60, 0.05) 0%, white 100%);
}

.alerta-card.severity-high {
  border-left-color: #e67e22;
  background: linear-gradient(to right, rgba(230, 126, 34, 0.05) 0%, white 100%);
}

.alerta-card.severity-medium {
  border-left-color: #f39c12;
}

.alerta-card.severity-low {
  border-left-color: #27ae60;
}

/* Card - Header */
.alerta-header {
  padding: 15px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  border-bottom: 1px solid #ecf0f1;
}

.alerta-titulo {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.alerta-titulo h3 {
  margin: 0;
  font-size: 16px;
  color: #2c3e50;
}

.badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.badge-critical {
  background: #e74c3c;
  color: white;
}

.badge-high {
  background: #e67e22;
  color: white;
}

.badge-medium {
  background: #f39c12;
  color: white;
}

.badge-low {
  background: #27ae60;
  color: white;
}

.fuente-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.fuente-openfda {
  background: #3498db;
  color: white;
}

.fuente-rasff {
  background: #9b59b6;
  color: white;
}

/* Card - Contenido */
.alerta-contenido {
  padding: 15px;
}

.contenido-fila {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
}

.contenido-fila:last-child {
  margin-bottom: 0;
}

.contenido-fila .label {
  font-weight: 600;
  color: #7f8c8d;
  min-width: 90px;
}

.contenido-fila .valor {
  color: #2c3e50;
  flex: 1;
  word-break: break-word;
}

.dias-atrás {
  color: #95a5a6;
  font-size: 12px;
}

.score-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.score-fill {
  height: 8px;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  border-radius: 4px;
  min-width: 50px;
}

.score-valor {
  font-weight: 600;
  font-size: 12px;
  min-width: 40px;
}

/* Card - Footer */
.alerta-footer {
  padding: 12px 15px;
  border-top: 1px solid #ecf0f1;
  background: #f8f9fa;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
}

.link-oficial {
  color: #667eea;
  text-decoration: none;
  font-weight: 600;
}

.link-oficial:hover {
  text-decoration: underline;
}

.click-hint {
  color: #bdc3c7;
  font-size: 11px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-contenido {
  background: white;
  border-radius: 12px;
  padding: 30px;
  max-width: 600px;
  width: 100%;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  position: relative;
}

.modal-contenido h2 {
  margin-top: 0;
  color: #2c3e50;
}

.btn-cerrar {
  position: absolute;
  top: 15px;
  right: 15px;
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #7f8c8d;
}

.detalles-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 15px;
  margin-bottom: 20px;
}

.detalles-grid .full-width {
  grid-column: 1 / -1;
}

.detalle-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.detalle-item .label {
  font-weight: 600;
  color: #7f8c8d;
  font-size: 12px;
}

.detalle-item .valor {
  color: #2c3e50;
  font-size: 14px;
}

.monospace {
  font-family: "Courier New", monospace;
  font-size: 12px;
  background: #f8f9fa;
  padding: 4px 8px;
  border-radius: 4px;
  word-break: break-all;
}

.link-oficial-modal {
  color: #667eea;
  text-decoration: none;
  word-break: break-all;
}

.link-oficial-modal:hover {
  text-decoration: underline;
}

.modal-acciones {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.btn-cerrar-modal,
.btn-original {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-cerrar-modal {
  background: #ecf0f1;
  color: #2c3e50;
}

.btn-cerrar-modal:hover {
  background: #bdc3c7;
}

.btn-original {
  background: #667eea;
  color: white;
  text-decoration: none;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-original:hover {
  background: #5568d3;
  color: white;
  text-decoration: none;
}

/* Responsive */
@media (max-width: 768px) {
  .alertas-container {
    grid-template-columns: 1fr;
  }

  .estadisticas {
    grid-template-columns: repeat(2, 1fr);
  }

  .filtros {
    flex-direction: column;
  }

  .detalles-grid {
    grid-template-columns: 1fr;
  }
}
</style>
