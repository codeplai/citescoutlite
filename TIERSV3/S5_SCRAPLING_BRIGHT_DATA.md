# Semana 5 · SCRAPLING + BRIGHT DATA (N2 COMPLETA)

**Objetivo:** N2 funcional, 97+ tiendas en cascada, procedencia clara por campo.

**Duración:** 5 días · **Equipo:** Backend (2) + QA (1)

---

## ITEMS SEMANA 5

### 5.1 IMPLEMENTAR SCRAPLING (DINÁMICO, TIENDAS CON JS)
- **Descripción:** Renderizado con JavaScript para sitios que carga contenido dinámicamente
- **Tareas:**
  - [ ] Instalar Scrapling SDK (o alternativa: Playwright headless)
  - [ ] Crear adapter `ScraplingTransport`:
    ```python
    class ScraplingTransport(Transport):
        def buscar(self, tienda_id, query):
            # Scrapling renderiza JS, retorna HTML completo
            response = client.request(tienda_id.url, ...)
            return response.rendered_html
    ```
  - [ ] Timeout: 30s por página (JS render tarda)
  - [ ] Huellas digitales: 30-50 tiendas con JS pesado (SPAs, Shopify dinámicas)
  - [ ] Rate-limit: 0.1 req/s por dominio (más lento que httpx)
  - [ ] Test: tienda Shopify con lazy-load → renderizada completa
- **Duración:** 1.5 días
- **Dependencias:** Ninguna (puede paralelizar con 5.2)
- **DoD:** ScraplingTransport implementado, 30-50 tiendas identificadas

---

### 5.2 INTEGRAR BRIGHT DATA SCRAPER API (ASYNC WEBHOOK)
- **Descripción:** API que scrapea sitios anti-bot (Amazon, Costco, etc.)
- **Tareas:**
  - [ ] Configurar Bright Data Scraper API (ya existe licencia de v2)
  - [ ] Modelo asíncrono: trigger → get snapshot_id → webhook
  - [ ] Para 5 tiendas: Amazon, Costco, Instacart, Kroger, Meituan
  - [ ] Crear tabla `bright_data_requests`:
    - `request_id, tienda_id, query, snapshot_id, webhook_received, data_json, created_at, completed_at, status`
  - [ ] Webhook endpoint: `/api/webhooks/bright-data` recibe snapshot
  - [ ] Timeout: 5 min esperando webhook; si no llega, mark as failed
  - [ ] Retry: si falla, reintentar 1x con 2 min delay
- **Duración:** 1.5 días
- **Dependencias:** Ninguna (paralelizable con 5.1)
- **DoD:** Webhook recibe datos, status pasa a 'completed', datos parseables

---

### 5.3 CREAR TABLA SWEEP_ATTEMPTS (COBERTURA DECLARADA)
- **Descripción:** 1 fila por tienda, incluso si falla o no se consulta
- **Tareas:**
  - [ ] Migración: tabla `sweep_attempts` (ya en ARQUITECTURA pero no implementada)
    - Campos: `sweep_id (FK), store_id, status ('ok'/'failed'/'blocked_policy'/'blocked_server'/'blocked_robots'/'skipped_budget'/'circuit_open'/'deferred'/'out_of_scope'), transport, offers_found, cost_usd, error_reason, started_at, completed_at`
  - [ ] Trigger: al terminar barrido de insumo, insertar 1 fila por tienda en `sweep_attempts`
  - [ ] Status: captura qué pasó (bloqueo por policy, rate-limit agotado, etc.)
  - [ ] Índice: (sweep_id, store_id) para queries de cobertura
- **Duración:** 0.5 días
- **Dependencias:** DB (S1)
- **DoD:** Tabla poblada post-sweep, P14 puede consultarla

---

### 5.4 IMPLEMENTAR CANARIO DIARIO (QUALITY CONTROL)
- **Descripción:** Validar que adaptadores no rompieron tras cambios en tiendas
- **Tareas:**
  - [ ] Función `canary_check()` que corre 02:30 UTC cada día
  - [ ] 2-3 tiendas conocidas + 1 producto conocido por tienda
  - [ ] Assertions: "encontrar 20-50 ofertas", "precio dentro de X-Y rango"
  - [ ] Si falla: log en audit_log + alert PagerDuty (bajo priority)
  - [ ] Logging: qué tienda falló, por qué (HTML structure cambió, etc.)
  - [ ] Action: developer verifica y actualiza adapter si necesario
- **Duración:** 0.5 días
- **Dependencias:** Shelf Radar N1 (v2 ya funciona)
- **DoD:** Canario corre cada noche, alerta si falla

---

### 5.5 DEDUPLICACIÓN POR EAN + FUSIÓN DE FUENTES
- **Descripción:** Si N1 y N2 ven el mismo producto, fusionar inteligentemente
- **Tareas:**
  - [ ] Regla: EAN es llave primaria en `catalogo_comercial`
  - [ ] Si dos fuentes dan EAN igual:
    - [ ] Prioridad: N1 (bajo costo) > N2 (licenciado) > N3 (no aplica)
    - [ ] Campos: mantener union de campos non-null (ej: N1 tiene precio, N2 tiene stock)
    - [ ] Procedencia: guardar `price.fuente='N1_VTEX'`, `stock.fuente='N2_BrightData'`
  - [ ] Dedup: trigger en `catalogo_comercial` al insert
  - [ ] Metrics: % de duplicados, % de campos fusionados
- **Duración:** 0.5 días
- **Dependencias:** catalogo_comercial (v2), sweep_attempts (5.3)
- **DoD:** Dedup funciona, procedencia clara por campo

---

### 5.6 ACTUALIZAR COBERTURA_METADATA EN MAPA COMERCIAL
- **Descripción:** Calcular estadísticas de cobertura post-sweep
- **Tareas:**
  - [ ] Función `calcular_cobertura(sweep_id) → CoberturaMetadata`:
    ```python
    {
        "in_scope": 97,
        "verified": 72,  # status='ok'
        "blocked_policy": 15,  # no se consultó por ToS
        "blocked_server": 5,
        "blocked_robots": 3,
        "skipped_budget": 2,
        "failed": 3,
        "coverage_pct": 72 / 97 * 100 = 74.2,
        "publishable": True,  # > 60%
        "note": "Amazon, Costco bloqueados por política; se consultan bajo N2 licenciado."
    }
    ```
  - [ ] Guardar en `mapa_comercial_metadata` (tabla nueva)
  - [ ] Si coverage < 60%, `publishable=false` → informe lo advierte en portada
- **Duración:** 0.5 días
- **Dependencias:** sweep_attempts (5.3)
- **DoD:** Cobertura calculada y declarada en informe

---

### 5.7 INTEGRAR N2 EN PUERTO (BRIGHT DATA WEBHOOK HANDLING)
- **Descripción:** Puerto ahora consulta N2 si nivel >= 2
- **Tareas:**
  - [ ] Actualizar `PuertoDescubrimientoComercial`:
    ```python
    if nivel_maximo_costo >= 2:
        # Enqueue job: trigger Bright Data para 5 tiendas
        for tienda in [Amazon, Costco, Instacart, Kroger, Meituan]:
            enqueue bright_data_scrape(tienda, query)
        
        # Esperar webhook (hasta 5 min) o devolver parcial
        time.sleep(30)  # brief wait
        n2_results = fetch_bright_data_completed_for_run_id(run_id)
        resultados.extend(n2_results)
    ```
  - [ ] Si webhook no llega a tiempo, marcar status='deferred' y retornar partial result
  - [ ] Cost: Bright Data es flat $200/año, no por query
- **Duración:** 1 día
- **Dependencias:** Bright Data (5.2), puerto (2.5)
- **DoD:** Puerto invoca N2, maneja async webhook

---

### 5.8 TEST P14 Y P19 (COBERTURA DECLARADA + CANARIO)
- **Tareas:**
  - [ ] **P14:** Mapa comercial de "quinua" → sweep_attempts tiene 97 filas
    - Cada fila tiene store_id, status, ofertas encontradas
    - 72 'ok', 15 'blocked_policy', etc.
    - coverage_pct = 74% > 60%, publishable=true
  - [ ] **P19:** Canario overnight → 0 alerts (adaptadores no rompieron)
    - Si hubiera rotura (tienda rediseñó), alert sería disparado
- **Duración:** 0.5 días
- **Dependencias:** Cobertura (5.6), canario (5.4)
- **DoD:** P14 verde, P19 verde

---

### 5.9 DOCUMENTACIÓN: SHELF RADAR ARCHITECTURE (ACTUALIZAR)
- **Tareas:**
  - [ ] Documento: actualizar `SHELF_RADAR_ARQUITECTURA.md`
  - [ ] Secciones:
    - [ ] N1: 42 tiendas, 4 adaptadores (VTEX, Shopify, JSON-LD, Scrapling)
    - [ ] N2: 5 tiendas Bright Data, webhook model
    - [ ] N3: Agente (referencia a F4)
    - [ ] Procedencia escalera (5 niveles)
    - [ ] Canario diario, robots.txt, rate-limit
    - [ ] Cobertura por país (tabla)
- **Duración:** 0.5 días
- **Dependencias:** Todos (5.1-5.8)
- **DoD:** Documento refleja v3 completa

---

## DEFINITION OF DONE (S5)

- [ ] ScraplingTransport implementado (30-50 tiendas dinámicas)
- [ ] Bright Data Scraper API integrada (5 tiendas anti-bot)
- [ ] sweep_attempts tabla poblada post-sweep
- [ ] Canario diario detecta roturas de adapter
- [ ] Deduplicación por EAN funciona
- [ ] Procedencia clara por campo (N1/N2/N3 identificable)
- [ ] Cobertura calculada y declarada
- [ ] N2 integrado en puerto (cascada completa)
- [ ] P14 verde (cobertura declarada)
- [ ] P19 verde (canario funciona)
- [ ] SHELF_RADAR_ARQUITECTURA.md actualizado

---

## RIESGOS S5

| Riesgo | Mitigación |
|---|---|
| Scrapling es lento, > 30s por tienda | Usar concurrencia (pool de 5 requests simultáneos), aumentar timeout a 60s |
| Bright Data webhook nunca llega | Configurar reintentos en Bright Data; fallback a esperar en loop |
| Dedup por EAN elimina productos legítimos diferentes | Revisar lógica con especialista (EAN puede ser duplicado en diferentes presentaciones) |
| Canario es demasiado sensible, falsa alarma cada día | Ajustar assertions; usar fuzzy matching en lugar de exact |
| N2 consulta toma demasiado tiempo (usuario espera > 10s) | Enqueue early, no esperar webhook; usuario ve "datos pending en X min" |

---

## NOTAS

- **Paralelización:** 5.1 y 5.2 en paralelo (Scrapling vs Bright Data)
- **Licencia Bright Data:** confirmada en S2 de v2; usar misma key
- **Equipo:** 2 backend (adapters + webhook) + 1 QA (tests + canario)
