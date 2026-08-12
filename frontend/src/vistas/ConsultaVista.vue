<template>
  <Search v-if="!resultadoConsulta" @search-result="resultadoConsulta = $event" />

  <div v-else>
    <TokenUsage :ejecucion-id="resultadoConsulta.ejecucion_id" />
    <Result :result="resultadoConsulta" @reset="olvidarConsulta" />
  </div>
</template>

<script setup>
import Search from '../components/Search.vue'
import Result from '../components/Result.vue'
import TokenUsage from '../components/TokenUsage.vue'
import { olvidarConsulta, resultadoConsulta } from './estado_consulta.js'
</script>
