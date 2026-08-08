# Semana 2 · AGENTE + CUARENTENA (F4 PARTE 1/2)

**Objetivo:** N3 funcional en cascada, AgenteInvestigadorComercial operacional, cuarentena con grounding check.

**Duración:** 5 días · **Equipo:** Backend (2) + QA (1)

---

## ITEMS SEMANA 2

### 2.1 IMPLEMENTAR AGENTEIVENSTIGADORCOMERCIAL (PYDANTIC AI + TAVILY)
- **Descripción:** Agente que busca en web, extrae productos, valida schema
- **Tareas:**
  - [ ] Instalar Pydantic AI + Tavily SDK
  - [ ] Crear clase `AgenteInvestigadorComercial` en `casos_de_uso/agente/`
  - [ ] Toolset (3 funciones):
    - [ ] `buscar_web(query: str, país: str) → list[SearchResult]` via Tavily
    - [ ] `abrir_url(url: str) → str (HTML)` via trafilatura o httpx + parsing
    - [ ] `extraer_producto(html: str, schema: ProductoSchema) → Producto` via glm-5.2 tool-use
  - [ ] Fallback: si Tavily fail, usar Brave Search API (tiene endpoint compatible)
  - [ ] Timeout: 60s por busca, 30s por extracción, 10s por validación de schema
  - [ ] Retornar: `{producto, fuente_url, html_capturado, timestamp, modelo_usado}`
- **Duración:** 2 días
- **Dependencias:** Huawei ModelArts API confirmed (model glm-5.2 disponible)
- **DoD:** Agente ejecutable, toolset completo, retorna JSON schema válido

---

### 2.2 CONFIGURAR ROBOTS.TXT + RATE-LIMITING POR DOMINIO
- **Descripción:** Cumplimiento de cortesía: respetar robots.txt, no bombardear servidores
- **Tareas:**
  - [ ] Parsear robots.txt de cada sitio durante inicialización
  - [ ] Aplicar reglas Disallow (rutas prohibidas), Crawl-delay, Request-rate
  - [ ] Token bucket por dominio: 0.4 req/s con jitter ±20%
  - [ ] Circuit breaker: 3 fallos consecutivos → pausa 6h
  - [ ] User-Agent: `AgroScoutIA/1.0 (+https://agroscout.ai/bot)`
  - [ ] Mantener allowlist: sitios donde sí se puede scrapear (OFF, Comtrade, etc.)
  - [ ] Mantener denylist: sitios donde está prohibido (Amazon sin API, etc.)
- **Duración:** 1 día
- **Dependencias:** Agente (2.1)
- **DoD:** Robots.txt respetado, rate-limit funciona, circuit breaker se activa

---

### 2.3 CREAR TABLA STAGING_AGENTE Y SCHEMA DE CUARENTENA
- **Descripción:** Almacén de datos sin verificar, antes de promoción manual
- **Tareas:**
  - [ ] Migración SQL: crear tabla `staging_agente`
    - Campos: `staging_id (PK), insumo, país, mes, producto_json, fuente_url, html_capturado, provenance='agente', no_verificado=true, ttl=24h, grounding_check_status, validation_errors, created_at, promoted_at`
  - [ ] Índices: (insumo, país, mes) para lookup rápido
  - [ ] Trigger: auto-borrar rows > 24h sin revisar
  - [ ] Constraint: `promoted_at IS NULL` while en staging (se llena solo al pasar a catalogo_comercial)
- **Duración:** 0.5 días
- **Dependencias:** DB S1 (1.2)
- **DoD:** Tabla creada, índices en su lugar, trigger funciona

---

### 2.4 IMPLEMENTAR GROUNDING CHECK
- **Descripción:** Validar que cada valor literal está en el HTML capturado (no inventado)
- **Tareas:**
  - [ ] Función `grounding_check(html: str, producto: dict) → CheckResult`
  - [ ] Para cada campo en producto (`nombre`, `precio`, `marca`, `stock`):
    - [ ] Buscar substring literal en el HTML
    - [ ] Si no está, marcar como `failed`; incluir dónde se buscó
  - [ ] Threshold: todos los campos críticos deben estar en HTML o marcar `no_verificado`
  - [ ] Retornar: `{passed: bool, errors: [...]}`
  - [ ] Logging: guardar resultado en `staging_agente.grounding_check_status`
- **Duración:** 0.5 días
- **Dependencias:** Agente (2.1), staging_agente (2.3)
- **DoD:** Grounding check detectable en logs, marca errores si HTML no tiene datos

---

### 2.5 INTEGRAR AGENTE EN PUERTO DESCUBRIMIENTCOMERCIAL (CASCADA)
- **Descripción:** N1 → N2 stub → N3 agente, todo en cascada con nivel_maximo_costo
- **Tareas:**
  - [ ] Actualizar `PuertoDescubrimientoComercial`:
    ```python
    def ejecutar(insumo, país, nivel_maximo_costo):
        resultados = []
        
        # N1 (siempre)
        n1_data = shelf_radar_n1(insumo, país)
        resultados.extend(n1_data)
        
        # N2 (si nivel >= 2)
        if nivel_maximo_costo >= 2:
            n2_data = bright_data_n2(insumo, país)
            resultados.extend(n2_data)
        
        # N3 (si nivel >= 3 y hay gaps)
        if nivel_maximo_costo >= 3 and has_gaps(resultados):
            n3_data = agente_n3(insumo, país)  # → staging_agente
            # No agregar a resultados aún; requiere promoción manual
        
        return resultados, cobertura_metadata
    ```
  - [ ] Parámetro `nivel_maximo_costo` derivado del plan del tenant
  - [ ] Test: consulta con nivel=1 → solo N1; nivel=3 → N1+N2+N3 en cascada
- **Duración:** 1 día
- **Dependencias:** Agente (2.1), Puerto existente, staging_agente (2.3)
- **DoD:** Cascada funciona, nivel_maximo_costo respetado, gaps detectados

---

### 2.6 IMPLEMENTAR PRESUPUESTOS EN TIEMPO REAL
- **Descripción:** Topes de US$0.25/run · US$2/tenant·mes · US$10 global·mes con kill-switch
- **Tareas:**
  - [ ] Schema: tabla `presupuesto_config`
    - `tier_id, run_cost_limit ($0.25), tenant_month_limit ($2), global_day_limit ($10)`
  - [ ] Tabla: `presupuesto_uso` (tracking en vivo)
    - `run_id, tenant_id, etapa, timestamp, cost_usd, token_in, token_out, status`
  - [ ] Middleware en FastAPI: antes de invocar agente, chequear presupuestos
    - `if run_cost_used + delta > 0.25 OR tenant_month_used + delta > 2 OR global_day_used + delta > 10:`
    - `status = 'PARCIAL' (degrade, no error); return early con resultado vacío`
  - [ ] Retornar: siempre un result (nunca un 500), pero status='PARCIAL' si se alcanzó tope
  - [ ] Kill-switch UI: admin en panel puede pausar agente globalmente
- **Duración:** 1.5 días
- **Dependencias:** Middleware de aplicación, DB (1.2)
- **DoD:** Presupuestos chequeados pre-request, status PARCIAL cuando alcanza tope, no hay errores

---

### 2.7 INTEGRAR AGENTE EN ETAPA 2B (MAPA COMERCIAL)
- **Descripción:** La etapa 2b ahora invoca al puerto completo (N1+N2+N3)
- **Tareas:**
  - [ ] Actualizar `MapaComercial` en etapa 2b:
    ```python
    @etapa(nombre="2b_MapaComercial")
    def ejecutar(insumo_interpretado, país, nivel_maximo_costo):
        puerto_result = puerto_descubrimiento(
            insumo_interpretado, país, nivel_maximo_costo
        )
        # puerto_result.catalogo_comercial (N1+N2 directos)
        # puerto_result.staging_agente (N3 pendiente promoción)
        
        return MapaComercialResult(
            catalogo_comercial,
            gaps (dónde falta dato),
            cobertura_metadata
        )
    ```
  - [ ] Auditoría: cada call queda en `etapas_ejecucion` con nivel usado y costo
  - [ ] Test: insumo "quinua" → desglose N1 (42 tiendas encontradas), N2 (5), N3 (gaps si existe)
- **Duración:** 1 día
- **Dependencias:** Agente (2.1), presupuestos (2.6)
- **DoD:** Etapa 2b invoca puerto completo, auditoría registra nivel y costo

---

### 2.8 COST-METER: CALCULAR COSTO REAL POR ETAPA Y TENANT
- **Descripción:** Facturación en vivo: qué le costó esta consulta al tenant
- **Tareas:**
  - [ ] Schema: `costo_config` (tarifa por modelo, por token)
    - `modelo, precio_input ($/M tokens), precio_output ($/M tokens)`
  - [ ] En cada `etapa()` call:
    - [ ] Medir: tokens_in, tokens_out (via LiteLLM)
    - [ ] Calcular: costo_usd = (tokens_in × precio_in + tokens_out × precio_out) / 1_000_000
    - [ ] Agregar a `presupuesto_uso` (run, tenant, etapa, costo, timestamp)
  - [ ] Reporte: cost-meter disponible en panel (ver S8)
  - [ ] Test: consulta sobre 5 productos → desglose de costo por etapa (E1: $0.001, E2a: $0.0005, etc.)
- **Duración:** 1 día
- **Dependencias:** etapa() wrapper (ya existe), tarifas configuradas
- **DoD:** Cost-meter registra todos los calls, total por run verificable, P13 green

---

### 2.9 TESTES P11, P12, P13
- **Descripción:** Validar que agente, cuarentena y presupuestos funcionan honestamente
- **Tareas:**
  - [ ] **P11** (Agente → cuarentena → grounding check → promoción manual → catálogo):
    - [ ] Query con nivel=3 sobre "quinua" 
    - [ ] Agente busca 3 URLs
    - [ ] Grounding check: 2 pasan, 1 falla por precio inconsistente
    - [ ] 2 productos en staging_agente con `no_verificado=true`
    - [ ] Admin promueve 1 manualmente → aparece en catalogo_comercial
    - [ ] Verificar: promoted_at se llena, provenance='agente'
  - [ ] **P12** (Presupuestos run/tenant/global + kill-switch):
    - [ ] Correr 9 queries de agente × $0.25 = $2.25 (excede tenant limit $2)
    - [ ] Query 10 devuelve status='PARCIAL' sin error
    - [ ] Informe gratuito completo (etapas 1-3 no bloqueadas)
    - [ ] Panel muestra tenant_cost_month = $2.00 (tope aplicado)
  - [ ] **P13** (Cost-meter por tenant):
    - [ ] Dashboard panel: E1 consumió $0.005, E2a $0.001, E3 $0.003, etapa 3 $0.002 = $0.011/consulta
    - [ ] Proyección mensual: $0.011 × 100 consultas = $1.10 (dentro de $2)
    - [ ] Cuota visualizable: barra de progreso 55% de $2
- **Duración:** 1 día
- **Dependencias:** Agente (2.1), cuarentena (2.3), presupuestos (2.6), cost-meter (2.8)
- **DoD:** P11 verde, P12 verde, P13 verde

---

### 2.10 FAILOVER DEL AGENTE (TAVILY → BRAVE FALLBACK)
- **Descripción:** Si Tavily cae, seguir usando Brave sin perder presupuesto
- **Tareas:**
  - [ ] Circuit breaker en agente:
    - [ ] 3 timeouts/errores de Tavily → usar Brave
    - [ ] Brave: endpoint público (no es tan potente pero es backup)
    - [ ] Reset después de 1 hora (reintentar Tavily)
  - [ ] Logging: registrar en `audit_log` cada fallover
  - [ ] Test: simular Tavily timeout → agente usa Brave, resultado igual
  - [ ] Presupuesto: Brave también tiene costo (parametrizable)
- **Duración:** 0.5 días
- **Dependencias:** Agente (2.1)
- **DoD:** Failover automático, Brave funciona, logging presente

---

### 2.11 INTEGRACIÓN CON COLA PROCRASTINATE (PREP PARA S3)
- **Descripción:** Preparar jobs de agente para correr en worker (no síncronamente)
- **Tareas:**
  - [ ] Crear job definition: `job_agente_run(run_id, insumo, país, nivel)`
  - [ ] Enqueue lógica: en endpoint `/consultas`, si `nivel >= 3`, enqueue job (no ejecutar sync)
  - [ ] Status: devolver 202 (Accepted) con job_id, no 200 (el cliente verá evento de progreso)
  - [ ] Setup: procrastinate connector a DB (ya listо en S1)
  - [ ] Nota: workers aún no existen (S3); por ahora jobs quedan enqueued
- **Duración:** 0.5 días
- **Dependencias:** Presupuestos (2.6), DB (1.2)
- **DoD:** Job definition creado, enqueue lógica en endpoint

---

## DEFINITION OF DONE (S2)

- [ ] AgenteInvestigadorComercial implementado (toolset completo)
- [ ] Robots.txt parsing + rate-limiting por dominio
- [ ] staging_agente tabla creada con TTL trigger
- [ ] Grounding check funciona, detecta invenciones
- [ ] Puerto DescubrimientoComercial con cascada N1→N2→N3
- [ ] Presupuestos en tiempo real (3 niveles, kill-switch)
- [ ] Etapa 2b invoca puerto completo
- [ ] Cost-meter calcula y registra costo real
- [ ] P11, P12, P13 verdes
- [ ] Failover Tavily→Brave implementado
- [ ] Job definition de agente creado
- [ ] Documentación: ADR-005 (Huawei + fallback strategy)

---

## RIESGOS S2

| Riesgo | Mitigación |
|---|---|
| Agente es lento (> 60s por busca) | Timeout de 30s; fallback a Brave rápido |
| Tavily quota insuficiente | Verificar limits día 1, pedir aumento si necesario |
| Grounding check es demasiado estricto, rechaza 100% | Ajustar umbral; permitir 1-2 campos no verificados |
| Presupuestos son complejos, bugs | Implementar con test-driven development, casos de borde |
| Circuit breaker no se resetea, queda en Brave forever | Agregar timestamp de reset, reintentar Tavily cada 1h |

---

## NOTAS

- **Parallelización:** Items 2.1-2.2 en paralelo (agente + rate-limiting)
- **Tavily:** Usar sandbox/demo key primero para testing, luego API key de prod
- **Brave:** Endpoint: `https://api.search.brave.com/res/v1/web/search` (no requiere auth, solo 2000 req/día)
- **Equipo:** 2 backend para agente + cuarentena (pueden paralelizar); 1 QA para test
