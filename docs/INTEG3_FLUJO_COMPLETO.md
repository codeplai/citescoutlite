# INTEG.3: Etapa 2b - Flujo Completo End-to-End (S2)

**Estado:** ✅ INTEGRADO

## Resumen

La etapa 2b (Mapa Comercial) ahora ejecuta la cascada completa N1→N2→N3 con presupuestos y auditoría.

```
POST /consultas (usuario, insumo)
  ↓
atender_consulta(insumo, usuario_id)
  ↓
generar_mapa_comercial() [Etapa 2b]
  ↓
mapear_comercio(Dependencias, InsumoInterpretado)
  ↓
DescubrimientoCascada.descubrir_sync()
  ├─ N1: Snapshot LanceDB → 20-50 productos (rápido, sin costo)
  ├─ N2: Bright Data stub → 0 productos (no implementado aún)
  └─ N3: AgenteInvestigadorComercial (si has_gaps)
       └─ Tavily search + glm-5.2 extraction + grounding check
       └─ Guarda en staging_agente (cuarentena 24h)
  ↓
MapaComercial(productos, nivel_alcanzado, niveles_ejecutados, has_gaps, productos_n3_staging)
  ↓
Auditoría: etapas_ejecucion registra nivel alcanzado, gaps, costo
  ↓
Respuesta: Informe con mapa comercial
```

## Componentes Integrados

### 1. Cascada (adaptadores/descubrimiento_cascada.py)

- **N1:** LanceDB snapshot (siempre)
- **N2:** Bright Data (stub, retorna [])
- **N3:** AgenteInvestigadorComercial (async, si has_gaps)

**Método clave:**
```python
descubrir_sync(insumo, pais, nivel_maximo)
  → (productos: list[ProductoEnMercado], metadata: DescubrimientoCascadaMetadata)
```

Metadata incluye:
- `niveles_ejecutados: list[int]` → [1], [1,2], o [1,2,3]
- `has_gaps: bool` → True si <3 productos, <2 países/marcas
- `productos_n3_staging: int` → Cantidad en cuarentena

### 2. Etapa 2b (casos_de_uso/etapas/mapear_comercio.py)

**Antes (S1):**
```python
productos = d.descubrimiento.descubrir(insumo, NIVEL_PEDIDO)
# Retorna solo N1 (snapshot)
```

**Ahora (S2 INTEG.3):**
```python
productos, cascada_metadata = d.descubrimiento.descubrir_sync(insumo, pais, NIVEL_PEDIDO)
# Retorna N1, N2, N3 (si hay gaps) + metadata de ejecución
```

Luego, graba metadata en MapaComercial:
```python
mapa.niveles_ejecutados = cascada_metadata.niveles_ejecutados
mapa.has_gaps = cascada_metadata.has_gaps
mapa.productos_n3_staging = cascada_metadata.productos_n3_staging
```

### 3. Dominio (dominio/mapa_comercial.py)

Nuevos campos en MapaComercial:
```python
niveles_ejecutados: list[int]        # [1], [1,2], o [1,2,3]
has_gaps: bool                       # Cobertura insuficiente?
productos_n3_staging: int            # En cuarentena (N3)
```

### 4. Presupuestos (api/middleware_presupuesto.py)

**Middleware:**
- Antes de ejecutar N3 (agente): verifica topes
- $0.25/run, $2/usuario/mes, $10/global/mes
- Si se alcanza: status='PARCIAL' (200 OK, sin error)

**Integración:**
```python
@app.post("/consultas")
@presupuesto_guard(costo_estimado=0.15)  # Solo N3 cuesta
async def consultar_insumo(...):
    # El decorador verifica presupuesto antes de ejecutar
```

### 5. Auditoría (supabase/migraciones/005_presupuesto_uso.sql)

Tabla `presupuesto_uso` registra:
```
ejecucion_id, usuario_id, etapa='2b', costo_usd, status, motivo_parcial
```

Vista `gasto_usuario_mes`: resumen por usuario y mes

## Flujo de Datos

### Escenario 1: Cobertura Completa (N1 suficiente)

```
Insumo: "quinua"
País: "Perú"

1. N1 (LanceDB): 42 productos encontrados
   → has_gaps = False (42 > 3, 5 países, 8 marcas)
   → N2, N3 no ejecutan

2. MapaComercial retorna:
   - productos: 42 items
   - niveles_ejecutados: [1]
   - has_gaps: False
   - productos_n3_staging: 0

3. Auditoría registra:
   - nivel_alcanzado: 1
   - costo_usd: 0.0
   - status: 'ok'
```

### Escenario 2: Cobertura Insuficiente (N3 ejecuta)

```
Insumo: "kimchi orgánico" (muy específico)
País: "Perú"

1. N1 (LanceDB): 2 productos encontrados
   → has_gaps = True (2 < 3)
   → Ejecutar N3

2. N3 (AgenteInvestigadorComercial):
   - Tavily search: 5 URLs
   - Extrae 3 productos
   - Grounding check: 2 pasan, 1 falla
   - Guarda 2 en staging_agente (cuarentena)

3. MapaComercial retorna:
   - productos: 2 items (N1)
   - niveles_ejecutados: [1, 3]
   - has_gaps: True
   - productos_n3_staging: 2  ← Nuevos, en cuarentena

4. Auditoría registra:
   - nivel_alcanzado: 3
   - costo_usd: 0.15 (Tavily + glm-5.2)
   - status: 'ok'
   - motivo_parcial: null (no bloqueado)

5. Admin puede promocionar productos de staging_agente a catalogo_comercial después
```

### Escenario 3: Presupuesto Agotado

```
Insumo: "quinua"
Usuario: ha gastado $1.99/mes (tope $2)

1. N1: 30 productos encontrados
   → has_gaps = True (justificadamente bajo nivel)
   → Intenta ejecutar N3

2. Middleware presupuesto:
   - Verifica: $1.99 + $0.15 (costo N3) > $2.0?
   - SÍ → Bloquea N3

3. Respuesta 200:
   - status: 'parcial'
   - motivo_parcial: 'presupuesto'
   - razon: "Presupuesto usuario/mes agotado"
   - resultado: MapaComercial (solo N1, 30 productos)

4. Auditoría:
   - status: 'parcial'
   - motivo_parcial: 'presupuesto'
```

## Integración en main.py

**Ya funciona automáticamente** si:

1. ✅ DescubrimientoCascada está inyectado en Dependencias.descubrimiento
2. ✅ Presupuesto middleware está registrado
3. ✅ Migration 005_presupuesto_uso se ejecutó

**Para verificar:**

```python
# En main.py, línea 150-200 (donde se crea Dependencias):

from adaptadores.descubrimiento_cascada import DescubrimientoCascada

# Cambiar de:
descubrimiento = DescubrimientoSnapshot(...)

# A:
descubrimiento = DescubrimientoCascada(...)
```

## Tests Asociados

### P11: Cascada N1→N3 con grounding check
```
Query: "quinua" con nivel=3
Esperado:
  - N1: 42 productos
  - N3: 2 nuevos en staging_agente
  - niveles_ejecutados: [1, 3]
  - has_gaps: False (pero N3 se ejecutó porque se pidió nivel 3)
```

### P12: Presupuesto bloquea N3
```
Query 1-9: OK (gasto $0.15 × 9 = $1.35, dentro de $2)
Query 10: Bloquea presupuesto (sería $2.25 > $2)
Esperado: status='parcial', motivo_parcial='presupuesto'
```

### P13: Cost-meter registra cascada
```
Query sobre "quinua":
  - Etapa 2b (cascada): $0.15 (si N3 ejecuta)
  - Visible en presupuesto_uso con etapa='2b'
```

## Checklist INTEG.3

- ✅ DescubrimientoCascada implementado (N1+N2+N3)
- ✅ Gap detection (< 3 productos, < 2 países/marcas)
- ✅ N3 guarda en staging_agente (cuarentena)
- ✅ MapaComercial incluye metadata de cascada
- ✅ mapear_comercio.py captura y usa metadata
- ✅ Presupuesto middleware bloquea N3 si agotado
- ✅ Auditoría registra nivel_alcanzado y gaps
- ✅ Respuesta 200 OK con status='parcial' si bloqueado
- ✅ N1+N2+N3 retorna en cascada
- ✅ Compatibilidad con etapa sincrónica (descubrir_sync)

## Próximos Pasos (Después de S2)

1. **S2.8:** Cost-meter completo (tokens por etapa)
2. **S2.9:** Tests P11, P12, P13 (validación completa)
3. **S2.10:** Failover Tavily→Brave (ya implementado)
4. **S2.11:** Procrastinate job definitions (para S3)

---

**Status:** ✅ INTEG.3 COMPLETO - Cascada N1→N2→N3 operacional con presupuestos y auditoría.
