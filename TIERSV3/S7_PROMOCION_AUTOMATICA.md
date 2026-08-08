# Semana 7 · PROMOCIÓN AUTOMÁTICA POR MUESTREO

**Objetivo:** 80% de N3 se promueve automáticamente; 20% manual para casos edge.

**Duración:** 5 días · **Equipo:** Backend (2) + QA (1)

---

## ITEMS SEMANA 7

### 7.1 IMPLEMENTAR WATERMARK BINARIO (MUESTREO SISTEMÁTICO)
- **Descripción:** Decidir qué productos promocionar automáticamente
- **Tareas:**
  - [ ] Función `watermark(offer_id, seed_weekly) → bool`:
    ```python
    def should_promote(offer_id, seed):
        hash_value = int(hashlib.sha256(f"{offer_id}{seed}".encode()).hexdigest(), 16)
        return (hash_value % 100) < 80  # 80% true, 20% false
    ```
  - [ ] Seed: cambia cada semana (Mon 00:00 UTC), determinista
  - [ ] Resultado: 80% de ofertas son candidatas a promoción automática
  - [ ] Logging: guardar en `promotion_watermark_log` qué offers fueron seleccionados
  - [ ] Test: misma offer_id + seed → determinista (siempre true o siempre false)
- **Duración:** 0.5 días
- **Dependencias:** Ninguna
- **DoD:** Watermark determinista, 80% hit rate verificable

---

### 7.2 CREAR TABLA PROMOTION_RULES Y FORMULARIO DE REGLAS
- **Descripción:** Configurar reglas que definen qué puede promocionarse
- **Tareas:**
  - [ ] Tabla `promotion_rules`:
    - `rule_id, nombre_regla, descripción, expresión (JSON), activo, created_at, updated_at`
  - [ ] Reglas base (JSON DSL):
    ```json
    {
      "price_range": {"min_pct_of_historical": 80, "max_pct_of_historical": 120},
      "stock": {"min_units": 1},
      "url_validity": {"check_200_ok": true, "check_recency_hours": 24},
      "date_freshness": {"max_days_old": 7},
      "tienda_class": {"exclude": ["marketplace"]}
    }
    ```
  - [ ] Panel CITE: UI simple para editar reglas (JSON editor o form builder)
- **Duración:** 1 día
- **Dependencias:** DB (S1)
- **DoD:** Tabla creada, 5-10 reglas base pre-pobladas

---

### 7.3 IMPLEMENTAR VALIDADOR DE REGLAS (ANTI-GARBAGE)
- **Descripción:** Chequear que offer cumple todas las reglas
- **Tareas:**
  - [ ] Función `validar_offer_contra_reglas(offer, rules) → ValidationResult`:
    ```python
    def validate(offer, rules):
        errors = []
        
        # Precio
        if not (rules.price.min <= offer.precio <= rules.price.max):
            errors.append(f"Precio {offer.precio} fuera de rango [{rules.price.min}, {rules.price.max}]")
        
        # Stock
        if offer.stock is None or offer.stock < rules.stock.min:
            errors.append(f"Stock insuficiente")
        
        # URL
        if not url_is_valid(offer.url):
            errors.append(f"URL no accessible")
        
        # Fecha
        if (now - offer.fecha).days > rules.date_freshness.max_days:
            errors.append(f"Dato muy antiguo ({(now - offer.fecha).days} días)")
        
        return ValidationResult(passed=(len(errors)==0), errors=errors)
    ```
  - [ ] Retorna: `passed: bool, errors: [str]`
  - [ ] Logging: guardar en `promotion_validation_log` por qué se rechazó cada offer
- **Duración:** 1 día
- **Dependencias:** promotion_rules (7.2)
- **DoD:** Validador rechaza offers inválidas, logging completo

---

### 7.4 CREAR TABLA PROMOTION_LOG (AUDITORÍA)
- **Descripción:** Registro inmutable de todas las promociones
- **Tareas:**
  - [ ] Tabla `promotion_log`:
    - `log_id, staging_id (FK), promotion_type ('auto'/'manual'), promoted_by (user_id o 'system'), timestamp, rules_applied (array), validation_errors, result ('promoted'/'rejected')`
  - [ ] Índices: (staging_id), (promoted_by, timestamp)
  - [ ] Trigger: insertar row automático al promover
  - [ ] Reporte: "X offers promovidos automáticamente hoy, Y manual, Z rechazados"
- **Duración:** 0.5 días
- **Dependencias:** staging_agente (S2)
- **DoD:** Log funciona, auditoría completa

---

### 7.5 IMPLEMENTAR JOB DE PROMOCIÓN AUTOMÁTICA
- **Descripción:** Correr cada noche para promocionar candidatos
- **Tareas:**
  - [ ] Job: `job_promotion_auto` → 04:00 UTC cada noche
  - [ ] Pasos:
    1. Obtener offers en staging_agente con `watermark=true` (80%)
    2. Para cada offer: validar contra rules
    3. Si válido: mover a `catalogo_comercial` (update `promoted_at`)
    4. Registrar en `promotion_log`
    5. Registrar evento en `eventos_job`
  - [ ] Resultado: "X promovidos, Y rechazados por regla Z"
  - [ ] SLA: < 15 min (decenas de offers, no miles)
- **Duración:** 1.5 días
- **Dependencias:** Watermark (7.1), validador (7.3), procrastinate (S3)
- **DoD:** Job corre cada noche, promotion_log poblado

---

### 7.6 PANEL CITE: UI DE PROMOCIÓN MANUAL (20%)
- **Descripción:** Interfaz para promocionar offers rechazados o dudar
- **Tareas:**
  - [ ] Frontend: new page "Promociones"
  - [ ] Listado: offers en `staging_agente` con watermark=false (20% manual)
  - [ ] Por cada offer:
    - [ ] Mostrar datos (nombre, precio, URL, fecha)
    - [ ] Mostrar por qué se rechazó (si aplica)
    - [ ] Botón "Promover" (admin only)
    - [ ] Botón "Rechazar" (borrar después de 24h)
  - [ ] Bulk actions: seleccionar 5 offers → promover todos
  - [ ] Historial: ver promociones de hoy/semana/mes
- **Duración:** 1.5 días
- **Dependencias:** UI framework (Vue 3, ya existe en v2)
- **DoD:** UI funciona, eventos de promoción manual registran

---

### 7.7 INTEGRACIÓN: PROMOTION_TYPE EN CATALOGO_COMERCIAL
- **Descripción:** Registrar cómo fue promovido cada producto
- **Tareas:**
  - [ ] Campo en `catalogo_comercial`: `promotion_source ('auto_watermark' | 'manual_human' | 'n1_direct' | 'n2_direct')`
  - [ ] En informe: opcional, footnote pequeño "promovido automáticamente" si es auto
  - [ ] Query: "¿qué % de datos son auto-promovidos?" → métrica de confianza
- **Duración:** 0.5 días
- **Dependencias:** promotion_log (7.4)
- **DoD:** Campo se llena, queries muestran % auto

---

### 7.8 VALIDACIÓN DE REGLAS EN EDGE CASES
- **Descripción:** Testing exhaustivo del validador
- **Tareas:**
  - [ ] Test casos:
    - [ ] Precio fuera de rango → rechazar
    - [ ] Stock=0 → rechazar
    - [ ] URL muerta → rechazar
    - [ ] Dato 8 días viejo (rules dicen max 7) → rechazar
    - [ ] Tienda=marketplace → si excluida en rules, rechazar
    - [ ] Todo válido → aceptar
  - [ ] Logs: verificar que cada rechazo queda registrado
- **Duración:** 0.5 días
- **Dependencias:** Validador (7.3)
- **DoD:** 6/6 casos pasan, logging completo

---

### 7.9 STATISTICAS Y DASHBOARD DE PROMOCIONES
- **Descripción:** Ver en tiempo real cómo va la promoción
- **Tareas:**
  - [ ] Panel: new widget "Promociones 24h"
    - [ ] Automáticas: 150 de 180 (83%)
    - [ ] Manual: 15 promovidas por admin
    - [ ] Rechazadas: 15 (8%)
    - [ ] Gráfico: pie chart
  - [ ] Motivo de rechazo: "Precio fuera de rango" (10), "Stock insuficiente" (5)
  - [ ] Trend: gráfico de barras últimos 7 días
- **Duración:** 0.5 días
- **Dependencias:** promotion_log (7.4)
- **DoD:** Widget muestra stats en vivo

---

### 7.10 DOCUMENTACIÓN Y PROCEDIMIENTO OPERACIONAL
- **Tareas:**
  - [ ] Documento: `PROMOTION_PROCEDURES.md`
  - [ ] Secciones:
    - [ ] Cómo configurar reglas (UI o JSON)
    - [ ] Cómo revisar ofertas del 20% manual
    - [ ] Cómo interpretar logs de rechazo
    - [ ] Ejemplos: "qué pasa si cambio precio_range a 70-130%"
  - [ ] Entrenamiento CITE: 30 min live demo
- **Duración:** 0.5 días
- **Dependencias:** Todos (7.1-7.9)
- **DoD:** Documento claro, CITE puede operar sin dev support

---

## DEFINITION OF DONE (S7)

- [ ] Watermark determinista implementado (80/20 split)
- [ ] promotion_rules tabla y editor en panel
- [ ] Validador de reglas implementado (anti-garbage)
- [ ] promotion_log tabla con auditoría completa
- [ ] Job promotion_auto corre cada noche
- [ ] UI manual promotion en panel (20%)
- [ ] Campo promotion_source en catalogo_comercial
- [ ] Test de validador: 6 casos pasan
- [ ] Dashboard de promociones en panel
- [ ] PROMOTION_PROCEDURES.md escrito

---

## RIESGOS S7

| Riesgo | Mitigación |
|---|---|
| Reglas son demasiado estrictas, 100% rechazado | Audit logs; CITE ajusta rules más lengas |
| Reglas son demasiado laxas, garbage entra | Aumentar strictness; pre-review antes de producción |
| Watermark bias (tiendas grandes vs pequeñas) | No hay bias; watermark es per-offer, no per-tienda |
| Job tarde > 15 min | Si hay 10k+ offers, paralelizar con N workers |
| Manual promotion es tediosa (solo 20 offers por noche) | Bulk action button + smart filtering (mostrar rechazados por precio primero) |

---

## NOTAS

- **Equipo:** 2 backend (job + validador) + 1 QA
- **Reglas:** Hacer parametrizables para que CITE pueda ajustar sin dev
- **20% manual:** No es pesado (27 offers/noche = ~1 min de review), aceptable
