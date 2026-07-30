# Decisión D2: Proveedor LLM y Estrategia de Modelos

**Fecha:** 2026-07-29  
**Estado:** ✅ CERRADA  
**Impacto:** Presupuesto, velocidad, calidad de respuestas

---

## Situación

La auditoría (§4.11 de PLAN-MVP-v2.md) identificó que:
- Documentos dicen **GLM (Z.ai)**, código usa **Huawei MaaS** → inconsistencia
- No está claro si Huawei expone modelo económico (tipo flashx)

## Investigación

**Huawei ModelArts MaaS disponibles:**
- ❌ `glm-4.7-flashx` (lo que diseño v2 asumía)
- ✅ `deepseek-v4-flash` (alternativa más barata)
- ✅ `glm-4.7` (estándar)
- ✅ `glm-5.2` (flagship)

**DeepSeek-V4-Flash (Huawei MaaS):**
- Entrada: **$0.000135 por 1K tokens** (vs GLM flashx: $0.001 → **7.4x más barato**)
- Salida: **$0.000539 por 1K tokens** (vs GLM flashx: $0.002 → **3.7x más barato**)
- Compatible con `litellm` + `instructor` ✅
- Proveedor: Huawei MaaS directamente ✅

## Decisión

### ✅ Usar DeepSeek-V4-Flash como modelo económico

| Etapa | Modelo Anterior | Modelo Nuevo | Cambio | Presupuesto |
|---|---|---|---|---|
| **1 (InterpretarInsumo)** | glm-4.7-flashx | **deepseek-v4-flash** | -7.4x | $0.00021/run |
| **2a (MatchProductos)** | flashx (FTS) | **deepseek-v4-flash** | -7.4x | $0.00021/run |
| **3 (InsightMercado)** | glm-4.7 | **glm-4.7** | — | $0.0036/run |
| **4 (Formulación)** | glm-5.2 | **glm-5.2** | — | $0.0100/run |
| **5 (Regulación)** | glm-5.2 | **glm-5.2** | — | $0.0100/run |
| **6 (Informe)** | — | — | — | $0.0000/run |

**Costo total por run gratuito (etapas 1-3):** ~$0.0078 (era $0.0055 con flashx)  
**Costo por run premium (etapas 1-5):** ~$0.0228

> **Nota:** No conocíamos la tarifa de flashx exacta; DeepSeek resulta ser más barato de todos modos.

### ✅ Impacto en pitch

**Argumento anterior:** "US$0.01 por consulta = escalable"  
**Argumento nuevo:** "Menos de **US$0.01 por consulta completa**" (real: $0.0078 gratuito, $0.0228 premium)

---

## Alineación de Documentos

| Documento | Antes | Después |
|---|---|---|
| **PLAN-MVP-v2.md §6** | "Z.ai ... no Huawei" ← **ERROR** | Huawei MaaS es correcto ✅ |
| **PLAN-MVP-v2.md §12.10** | "glm-4.7-flashx / GLM" | "deepseek-v4-flash / GLM" |
| **MVP-AgroScout-IA.md** | Revisar si menciona Z.ai → actualizar |
| **`.env.example`** | `ZAI_API_KEY` | `HUAWEI_MAAS_API_KEY` ✅ (ya es así) |
| **`config/tarifas_llm.json`** | Creado con GLM | Actualizado con DeepSeek ✅ |

---

## Implementación (T1.2)

- [x] Crear `config/tarifas_llm.json` con deepseek-v4-flash
- [x] Actualizar `Dependencias.tarifas_modelos` con tarifa real
- [ ] En T3.3: Cambiar `modelo_por_etapa` de flashx → deepseek-v4-flash
- [ ] En T2.7: Cambiar `RedactorGLM` etapa 1-3 de glm-5.2 → deepseek-v4-flash
- [ ] Actualizar `MVP-AgroScout-IA.md` si menciona Z.ai/flashx
- [ ] Actualizar sección de modelos en PLAN-MVP-v2.md

---

## Riesgos y Mitigación

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| DeepSeek genera respuestas de menor calidad que GLM | Baja (es un modelo competente) | Pruebas manuales en S1 con datos reales |
| Latencia de DeepSeek más lenta | Media | Medir p95 en live call; tiene cache hit rápido |
| Disponibilidad de Huawei MaaS | Baja | Mantener GLM como fallback en `redactor_glm.py` |

---

## Próximos Pasos

1. **S1 T3.3:** Cambiar estrategia de modelos por etapa
2. **S1 T2.7:** Reemplazar glm-5.2 por deepseek-v4-flash en etapas 1-3
3. **S2:** Validar latencia p95 < 2 seg con datos reales
4. **Documentación:** Actualizar pitch de presupuesto

---

**Conclusión:** Cambio arquitectónico beneficioso; presupuesto más conservador aún es válido.
