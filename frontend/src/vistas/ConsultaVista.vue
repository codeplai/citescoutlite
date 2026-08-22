<!--
  La pantalla de consulta: la pregunta o su respuesta, nunca las dos.

  El orden de aquí abajo es el único cambio del rediseño en este fichero, y no
  es cosmético: **el consumo va después del informe**. Antes lo precedía, así
  que lo primero que se leía tras cuarenta segundos de espera era cuánto se
  había gastado y no qué se había encontrado. El coste sigue estando —hay un
  tope y se puede agotar— pero en el pie y plegado en una línea.
-->
<template>
  <Search v-if="!resultadoConsulta" @search-result="resultadoConsulta = $event" />

  <div v-else>
    <Result :result="resultadoConsulta" @reset="olvidarConsulta" />
    <TokenUsage :ejecucion-id="resultadoConsulta.ejecucion_id" />
  </div>
</template>

<script setup>
import Search from '../components/Search.vue'
import Result from '../components/Result.vue'
import TokenUsage from '../components/TokenUsage.vue'
import { olvidarConsulta, resultadoConsulta } from './estado_consulta.js'
</script>
