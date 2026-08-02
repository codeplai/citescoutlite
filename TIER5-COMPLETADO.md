# TIER 5 COMPLETADO - Búsqueda optimizada (Gate P03)

**Fecha:** 2026-08-02  
**Duración:** ~1 hora  
**Status:** ✅ 100% COMPLETADO — **P03 VERDE**

---

## Tareas ejecutadas

### ✅ T5.1: Reescribir `adaptadores/busqueda_lancedb.py` (vectorial real)

La búsqueda ya usaba embeddings (no FTS) desde S1, pero tenía dos defectos que
devolvían datos degradados, y no cumplía el requisito de latencia por diseño.

**Defectos corregidos:**

| # | Defecto | Impacto | Corrección |
|---|---------|---------|------------|
| 1 | Leía `res.get("id_fuente")`, pero la columna en LanceDB se llama `id` (la escribió [tier4_gpu.py:135](etl/tier4_gpu.py#L135)) | **Los 28.236 productos devolvían `id_fuente="Unknown"`** → citas no trazables (rompe P04) | Lee `id` con `id_fuente` como fallback |
| 2 | `res.get("usa_insumo_directo", True)` sobre una columna inexistente | Default optimista `True` contra un dataset donde el campo es `False` en las 28.236 filas ("será derivado después", [cargar_off_bulk.py:141](etl/cargar_off_bulk.py#L141)) | Default `False`; el valor real lo deriva [buscar_productos.py:21](casos_de_uso/etapas/buscar_productos.py#L21) contra los sinónimos |
| 3 | `db.list_tables()` en lancedb 0.36 devuelve un objeto paginado, no una lista | `"productos" not in db.list_tables()` daba falso → **0 resultados** | Normaliza vía `getattr(listado, "tables", listado)` |

**Mejoras de latencia:**

- **Singletons de proceso** para el modelo y la tabla. Antes, cargar bge-m3
  (~8 s) y abrir la tabla ocurría por instancia; ahora una vez por proceso.
- **`.select()` sin la columna `embedding`**: evita transferir 30 × 1024 floats
  por consulta hacia el dominio, donde nadie los usa.
- **Prefiltro DEMO condicional**: solo se aplica si el snapshot mezcla DEMO con
  fuentes reales. El snapshot actual es 100 % OFF, así que no paga el filtro.
  Si todo fuera DEMO no se filtra (mejor devolver DEMO que devolver cero).

**Otros cambios:**

- Métrica `cosine` explícita en la consulta, coherente con el índice IvfPq
  COSINE de TIER 4. No se normaliza el vector de query: la distancia coseno es
  invariante a la escala y los vectores indexados tampoco están normalizados.
- `fecha_dato` se convierte desde timestamp Unix int64; ante valor inválido
  devuelve `None`. **Nunca inventa una fecha.**
- Nuevo campo opcional `similitud` (= `1 - _distance`) en `ProductoExistente`,
  para trazar el ranking.
- `AGROSCOUT_DEVICE` permite forzar `cpu`/`cuda`; por defecto autodetecta.
- Se preserva el contrato del puerto `CatalogoProductos.buscar(sinonimos, k)`.
  El plan proponía una firma nueva (`buscar_productos(query, limit)`); se
  descartó para no romper `api/main.py` ni `casos_de_uso/`.

---

### ✅ T5.2: Medición de latencia p95

**Gate P03: p95 < 2000 ms sobre 100+ queries.**

Medido con `medir_latencia_p95()` sobre los 5 insumos piloto, 100 queries,
k=30, con warm-up previo (la carga del modelo ocurre una vez al arrancar el
proceso, no por consulta).

```
GPU (RTX 4060 Laptop):
  media  43.3ms | p50  43.2ms | p95  45.2ms | p99  47.0ms | max  47.5ms
  → 44x de margen bajo el gate

CPU (AGROSCOUT_DEVICE=cpu):
  media 151.5ms | p50 151.3ms | p95 173.0ms | p99 178.0ms | max 180.1ms
  → 11.5x de margen bajo el gate
```

**El gate se cumple con o sin GPU**, lo que elimina la dependencia de hardware
para P03 en despliegue.

---

## Verificación

`test/test_latency.py` — **3/3 PASSED** (suite completa: 6/6)

| Test | Verifica |
|------|----------|
| `test_p95_latencia_bajo_2s` | p95 < 2000 ms sobre 100 queries |
| `test_resultados_trazables_y_sin_demo` | `id_fuente` ≠ "Unknown" (regresión del defecto 1), sin fuente DEMO, `fecha_dato` no nula, `url` presente, `similitud` presente |
| `test_cobertura_5_insumos_piloto` | Los 5 insumos devuelven resultados |

```bash
python -m pytest test/test_latency.py -v      # o: python test/test_latency.py
python -m adaptadores.busqueda_lancedb        # solo la medición de latencia
```

**Relevancia semántica** (top-1 por insumo, verificada manualmente):

| Insumo | Similitud top-1 | Resultado |
|--------|-----------------|-----------|
| mango | 0.7891 | correcto |
| quinua | 0.7279 | `quinoa` |
| espárrago | 0.6163 | `Esparrago` |
| arándano | 0.4395 | `Blueberry` |
| palta | 0.3566 | `Avocados` |

Las similitudes bajas de arándano y palta se deben a que la query concatena
sinónimos (`"palta aguacate avocado"`), lo que diluye el embedding. El
**ranking es correcto** en los 5 casos: el top-8 de palta son todos productos
de aguacate.

---

## DoD de TIER 5

- [x] `busqueda_lancedb.py` usa embeddings (no FTS)
- [x] p95 latencia < 2 segundos (100 queries; 45.2 ms GPU / 173.0 ms CPU)
- [x] Sin DEMO data en resultados (snapshot 100 % OFF; prefiltro listo si aparece)
- [x] `fecha_dato` es real (timestamp Unix del snapshot, rango 2015-2026, nunca inventada)
- [x] `test_latency.py` pasa (3/3)

---

## Notas para TIER 6/7

1. **`usa_insumo_directo` sigue sin derivarse en el dataset** (`False` en las
   28.236 filas). El dominio lo recalcula en cada búsqueda contra los
   sinónimos, así que el pipeline es correcto, pero
   `productos_merged.json` no es fuente de verdad para ese campo. Si TIER 7 lo
   audita desde el JSON, dará 0 directos.
2. **`pytest` no estaba instalado en `venv/`** pese a estar declarado en
   `pyproject.toml`. Se instaló (9.1.1).
3. **`venv/` no tiene `fastapi`**: es el entorno de embeddings/búsqueda
   (lancedb, sentence-transformers, torch+cu126). La API corre desde otro
   entorno. Preexistente, no bloquea TIER 5.
4. El `manifest.json` describe el snapshot viejo de 89 productos en
   `fuentes`/`estadisticas` (coverage de espárrago = 0), mientras que la tabla
   indexada tiene 28.236. **TIER 7 debe regenerar esas estadísticas** al
   calcular los SHA256.
