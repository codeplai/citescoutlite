# Tareas de Auditoría §4 — Priorización para Semana 1

**Fecha:** 2026-07-29  
**Criterios:** Impacto en capacidad funcional → Dependencias entre tareas → Riesgo de conflictos de versión  
**Principio:** Cada tarea deja el MVP en mejor estado; sin regresiones ni conflictos semánticos.

---

## ORDEN DE EJECUCIÓN (de menor a mayor prioridad)

### TIER 1 · DEPENDENCIAS Y DECISIONES BINARIAS (Día 1)

Estas deben hacerse **en paralelo** antes de tocar código. No hay dependencias entre ellas.

#### **T1.1** — Punto 19: Declarar dependencias faltantes
- **Impacto:** 🔴 CRÍTICO — bloquea `uv sync` en máquina limpia
- **Tamaño:** 2 minutos
- **Tarea:** En `pyproject.toml`, agregar a `dependencies`:
  - `markdown>=3.1.4` (usado en `informe_weasyprint.py:7`)
  - `requests>=2.31.0` (usado en `cargar_off.py:1`)
  - `xhtml2pdf>=0.2.15` (usado en `informe_weasyprint.py:149`)
- **Verificación:** `uv sync` en terminal limpia sin errores
- **Nota sobre versiones:** Estas tres son librerías maduras sin cambios rotos en los últimos 2 años. No causan conflictos.

#### **T1.2** — Punto 11: Verificar Huawei MaaS modelos disponibles (D2)
- **Impacto:** ⚠️ BLOQUEANTE — afecta cálculo de presupuesto del pitch
- **Tamaño:** 1 reunión (30 min máx)
- **Tarea:** 
  - Contactar Huawei o verificar en `HUAWEI_MAAS_API_KEY` qué modelos están disponibles
  - Específicamente: ¿existe `glm-4.7-flashx` o equivalente barato?
  - Si existe → recalcular presupuesto US$0.01/consulta
  - Si NO existe → notificar que T2.7 escalará costo y revisar pitch
- **Decisión:** Si no hay modelo barato, el presupuesto v2 del PLAN cambia
- **Documento:** Actualizar `.env.example` alineación `HUAWEI_MAAS_API_KEY` vs `ZAI_API_KEY`

#### **T1.3** — Punto 9: Preparar tarifa por modelo en configuración
- **Impacto:** ⚠️ Bloqueante para T2.3 (cost-meter)
- **Tamaño:** 15 minutos
- **Tarea:**
  - Crear archivo `config/tarifas_llm.json`:
    ```json
    {
      "glm-4.7-flashx": {"entrada_por_1k": 0.001, "salida_por_1k": 0.002},
      "glm-4.7": {"entrada_por_1k": 0.003, "salida_por_1k": 0.006},
      "glm-5.2": {"entrada_por_1k": 0.010, "salida_por_1k": 0.020}
    }
    ```
  - Cargar en `Dependencias` como atributo `tarifas_modelos`
- **Verificación:** `Dependencias.tarifas_modelos["glm-5.2"]["entrada_por_1k"]` existe
- **Nota:** NO cambiar aún qué modelos usan las etapas (eso es T2.7)

---

### TIER 2 · FUNDACIONES SIN DEPENDENCIAS (Día 1-2, paralelo con T1)

Estas no dependen entre sí pero todas dependen de T1.1 (dependencias instaladas).

#### **T2.1** — Punto 8: Arreglar entry point ETL
- **Impacto:** 🔴 Bloqueador — `uv run etl` no funciona
- **Tamaño:** 5 minutos
- **Tarea:**
  - En `etl/indexar_vectores.py`, renombrar función de `indexar_vectores()` a `main()`
  - O cambiar `pyproject.toml:24` de `"etl.indexar_vectores:main"` a `"etl.indexar_vectores:indexar_vectores"`
  - **Elegir la opción más sensata:** renombrar a `main()` (es la convención CLI)
- **Verificación:** `uv run etl` ejecuta sin error "module has no attribute"

#### **T2.2** — Punto 18: Decidir motor de PDF (D9)
- **Impacto:** ⚠️ Arquitectónico — necesita decisión antes de s4 (deck PPTX)
- **Tamaño:** decisión inmediata (30 min de prueba si hay duda)
- **Opciones:**
  1. **WeasyPrint** (como documentan v1 y v2): Mejor CSS, más visual, alineado con roadmap
  2. **xhtml2pdf** (lo que corre): Más pobre en CSS, pero funciona hoy
- **Recomendación:** WeasyPrint; la clase ya se llama `InformeWeasyPrint`, solo hay que cambiar la implementación
- **Tarea si WeasyPrint:**
  - Reemplazar líneas 149-151 de `informe_weasyprint.py` con WeasyPrint
  - Verificar que el HTML generado funciona igual
  - `weasyprint>=63.0` ya está en `pyproject.toml`
- **Tarea si xhtml2pdf:**
  - Renombrar clase a `InformeXHTML2PDF` (honestidad semántica)
  - Actualizar imports en `main.py`
  - Documentar por qué NO se usa WeasyPrint
- **Verificación:** Uno de los PDFs en `informes/` se genera sin error

#### **T2.3** — Punto 5: Reemplazar `fecha_dato` inventada
- **Impacto:** 🔴 Bloqueador P04, P05 — datos falsos
- **Tamaño:** 30 minutos
- **Tarea:**
  - En `adaptadores/busqueda_lancedb.py:33`, reemplazar `fecha_dato=datetime.date.today()` por:
    - `fecha_dato = res.get("fecha_dato")` (si viene de LanceDB)
    - O si no está en LanceDB: `fecha_dato = None`
  - Actualizar `etl/cargar_off.py` para traer fecha real de OFF en cada producto:
    - Agregar al dict de producto: `"fecha_dato": item.get("last_modified_t", None)` (timestamp OFF)
    - Convertir a `datetime.date` si existe
  - Actualizar `dominio/producto_existente.py:fecha_dato` para aceptar `None`
- **Verificación:** `ProductoExistente.fecha_dato` no es `date.today()` en ningún producto
- **Nota sobre versiones:** Sin cambios de dependencia; Pydantic ya maneja `date | None`

#### **T2.4** — Punto 4: Derivar `usa_insumo_directo` de ingredientes
- **Impacto:** 🟡 Alto — guard clause no es real hoy
- **Tamaño:** 1-2 horas
- **Tarea:**
  - En `casos_de_uso/etapas/buscar_productos.py` (o nueva función en adaptadores), implementar lógica:
    ```python
    def detectar_uso_directo(ingredientes_texto: str, sinonimos_insumo: list[str]) -> bool:
        """Retorna True si el insumo aparece directamente en el texto de ingredientes."""
        ingredientes_lower = ingredientes_texto.lower()
        for sinonimo in sinonimos_insumo:
            if sinonimo.lower() in ingredientes_lower:
                return True
        return False
    ```
  - En `buscar_productos()`, después de obtener cada `ProductoExistente`, recalcular:
    `p.usa_insumo_directo = detectar_uso_directo(p.ingredientes, interpretado.sinonimos)`
  - Eliminar el hardcodeado `"usa_insumo_directo": True` de `cargar_off.py:45`
  - Actualizar `indexar_vectores.py` para guardar el valor derivado (no inventarlo)
- **Verificación:** Consulta con "mango" en datos reales (S2) muestra n_directos < total
- **Nota:** Esta tarea necesita datos reales (S2), pero la lógica se puede escribir ahora

#### **T2.5** — Punto 12: Incluir modelo en clave cache
- **Impacto:** 🔴 Bloqueador P02 — cache hit falsa
- **Tamaño:** 20 minutos
- **Tarea:**
  - En `casos_de_uso/etapas/ejecutor.py:11-15`, modificar `_generar_clave_cache()`:
    - Agregar parámetro `modelo: str`
    - Incluir modelo en `base`: `f"{entrada_str}|{modelo}|{kwargs_str}|{etapa}|{snapshot_version}"`
  - En `etapa()` (línea 17), pasar modelo: obtener de `d.redactor.modelo_por_etapa[num_etapa]` (preparar en T1.3)
  - En `etapa_sync()` (línea 49), que no usa modelo, pasar cadena vacía
- **Verificación:** Cambiar modelo en `redactor_glm.py` y verificar que se recalcula
- **Nota:** No hay conflicto de versiones; es cambio puro de lógica

#### **T2.6** — Punto 13: Implementar modo `--offline` real
- **Impacto:** 🟡 Alto — plan B de demo sin internet
- **Tamaño:** 2-3 horas
- **Tarea:**
  - En `api/main.py:33`, actualmente se lee `AGROSCOUT_OFFLINE` pero no se usa
  - Crear adaptador `VerificadorOpenFDA` y `VerificadorRAG` con fallback offline:
    - Si `offline_mode=True` y no hay cache: retornar "Modo offline: sin datos regulatorios" en lugar de error
  - En `evaluar_insumo()`, respetar `offline_mode` del contexto (pasar en `Dependencias`)
  - Agregar a `Dependencias`: `offline_mode: bool`
  - En `main.py:52`, agregar: `offline_mode=offline_mode`
  - Grabar un run completo offline con `--offline=1` para demo fallback
- **Verificación:** Ejecutar offline retorna informe sin errores (valores parciales OK)
- **Nota:** No necesita cambiar versiones; es lógica condicional

---

### TIER 3 · COST-METER Y AUTH (Día 2-3, secuencial después de T2)

Estas dependen de T1.3 (tarifa por modelo). No hay dependencia entre ellas.

#### **T3.1** — Punto 9: Implementar cost-meter real
- **Impacto:** 🔴 Bloqueador P12, P13 — presupuestos
- **Tamaño:** 2-3 horas
- **Dependencia:** T1.3 (tarifa por modelo disponible)
- **Tarea:**
  - En `casos_de_uso/etapas/ejecutor.py`, función `etapa()`:
    - Reemplazar línea 46: `costo_usd=0.0` por cálculo real:
      ```python
      modelo = d.redactor.modelo_por_etapa.get(num_etapa, "glm-5.2")
      tarifa = d.tarifas_modelos.get(modelo, {})
      costo_usd = (tokens_entrada * tarifa.get("entrada_por_1k", 0) / 1000) + \
                  (tokens_salida * tarifa.get("salida_por_1k", 0) / 1000)
      ```
  - En `etapa_sync()` línea 57, pasar `costo_usd=0.0` (etapas síncronas no tienen token)
  - En `adaptadores/auditoria_sqlite.py`, verificar que `registrar_etapa()` guarda `costo_usd`
  - En `api/main.py`, endpoint `/ejecucion/{id}/tokens` también retornar `sum(costo_usd)`
- **Verificación:** Consulta guarda `costo_usd > 0.0` en base; endpoint retorna costo en US$
- **Nota sobre versiones:** Sin cambios de dependencia

#### **T3.2** — Punto 14-16: Auth real (bcrypt + JWT, endpoints protegidos)
- **Impacto:** 🔴 Bloqueador P01 — multi-tenant
- **Tamaño:** 4-5 horas
- **Dependencia:** Ninguna (paralelo con T3.1)
- **Subtareas:**
  - **T3.2.1** Contraseñas con bcrypt:
    - Agregar a `pyproject.toml`: `bcrypt>=4.1.0`, `python-jose[cryptography]>=3.3.0`
    - Crear `adaptadores/autenticacion.py`:
      ```python
      import bcrypt
      def hash_password(pwd: str) -> str:
          return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
      def verificar_password(pwd: str, hash_: str) -> bool:
          return bcrypt.checkpw(pwd.encode(), hash_.encode())
      ```
    - Actualizar `update_schema.py:22-23`: hasear contraseña antes de insertar
    - Cambiar comparación en `main.py:65` a `verificar_password(req.password, row_hash)`
  - **T3.2.2** JWT en lugar de cadena fija:
    - En `adaptadores/autenticacion.py`, agregar:
      ```python
      from datetime import datetime, timedelta
      from jose import jwt
      def generar_token(user_id: int, email: str) -> str:
          payload = {"user_id": user_id, "email": email, "exp": datetime.utcnow() + timedelta(hours=24)}
          return jwt.encode(payload, "secret-key", algorithm="HS256")
      def verificar_token(token: str) -> dict:
          return jwt.decode(token, "secret-key", algorithms=["HS256"])
      ```
    - Reemplazar `main.py:71` por generar JWT real
  - **T3.2.3** Proteger endpoints:
    - Crear middleware en `api/main.py`:
      ```python
      from fastapi import Depends, HTTPException
      def get_current_user(authorization: str = Header(...)):
          token = authorization.replace("Bearer ", "")
          try:
              payload = verificar_token(token)
              return payload["user_id"]
          except:
              raise HTTPException(status_code=401)
      ```
    - Agregar parámetro `current_user: int = Depends(get_current_user)` a `/consultas`, `/informes/{id}`, `/ejecucion/{id}/tokens`
    - En `/informes/{id}`, verificar que el informe pertenece al usuario o lanzar 403
  - **T3.2.4** CORS seguro:
    - Reemplazar `main.py:25` por:
      ```python
      allow_origins=["http://localhost:3000", "http://localhost:8001"],
      ```
    - Remover `allow_credentials=True` a menos que sea estrictamente necesario
- **Verificación:** 
  - POST `/token` con credenciales retorna JWT válido
  - JWT expirado es rechazado
  - `/consultas` sin token retorna 401
  - `/informes/{id}` de otro usuario retorna 403
- **Nota sobre versiones:** `python-jose` + `bcrypt` son estables; no causan conflictos

#### **T3.3** — Punto 10: Modelos por etapa
- **Impacto:** 🟡 Alto — presupuesto real
- **Tamaño:** 1-2 horas
- **Dependencia:** T3.1 (cost-meter), T1.2 (decisión D2 sobre flashx disponible)
- **Tarea:**
  - En `Dependencias`, agregar atributo:
    ```python
    modelo_por_etapa = {
        1: "glm-4.7-flashx",  # O el más barato disponible (D2)
        2: "glm-4.7-flashx",
        3: "glm-4.7",
        # 4 y 5 son etapas diferidas (S4)
    }
    ```
  - En `RedactorGLM.__init__()`, recibir y guardar este diccionario
  - Cambiar `redactor_glm.py:19,51` de hardcodeado `"glm-5.2"` a `self.modelo_por_etapa[num_etapa]`
  - En `ejecutor.py`, obtener modelo: `modelo = d.redactor.modelo_por_etapa.get(num_etapa, "glm-5.2")`
- **Verificación:** Etapa 1 usa flashx, etapa 3 usa 4.7 (verificar en logs o auditoría)
- **Nota:** Si D2 dice "no hay flashx", degradar a 4.7 y recalcular presupuesto en el PLAN

---

### TIER 4 · BÚSQUEDA Y VECTORES (Día 3-4, alto riesgo)

Estas dependen de datos (parcialmente). No hay conflicto entre ellas pero T4.1 + T4.2 requieren cuidado en versiones.

#### **T4.1** — Punto 1: Embeddings reales con bge-m3
- **Impacto:** 🔴 Bloqueador P03 — búsqueda funcional
- **Tamaño:** 3-4 horas + tiempo de descarga/indexado
- **Dependencia:** T2.1 (ETL entry point), datos (S2)
- **Tarea:**
  - Agregar a `pyproject.toml`: `sentence-transformers>=2.2.2`
  - En `etl/indexar_vectores.py`, reemplazar FTS por embeddings:
    ```python
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("BAAI/bge-m3")
    embeddings = model.encode([f"{p['nombre']} {p['categoria']}" for p in productos])
    ```
  - Guardar embeddings en LanceDB con datos, no FTS:
    ```python
    data_lancedb = [
        {
            "id_fuente": p["id_fuente"],
            "nombre": p["nombre"],
            "vector": embeddings[i],  # Agregar vector
            ...
        }
        for i, p in enumerate(productos)
    ]
    tabla = db.create_table("productos", data=data_lancedb, mode="overwrite")
    ```
  - En `busqueda_lancedb.py`, cambiar búsqueda:
    ```python
    query_vector = model.encode(" ".join(sinonimos))
    resultados = tabla.search(query_vector).limit(k).to_list()
    ```
  - Medir p95 de latencia con datos reales (S2)
- **Verificación:** p95 < 2 seg con 50-200 productos por insumo
- **Nota sobre versiones:** `sentence-transformers` puede ser pesado (~1 GB descarga de modelo), pero no causa conflictos con otras dependencias. Cuidado: `torch` es transitividad pesada.

#### **T4.2** — Punto 2: DuckDB usado en formulación (diferido, pero preparar)
- **Impacto:** 🟡 Alto — P07 (formulación)
- **Tamaño:** 2-3 horas (pero es S4, preparar arquitectura ahora)
- **Dependencia:** T2.1 (ETL), datos con histórico (S2)
- **Tarea:** (esta se prepara pero ejecuta en S4)
  - `duckdb>=1.1.2` ya en `pyproject.toml`
  - Crear `adaptadores/motor_tendencias_duckdb.py`:
    ```python
    import duckdb
    def cargar_snapshot(path: str) -> duckdb.DuckDBPyConnection:
        conn = duckdb.connect(f"{path}/datos.duckdb")
        return conn
    def mineria_formulacion(conn, insumo: str) -> list[str]:
        resultados = conn.execute(f"""
            SELECT DISTINCT hipotesis FROM historico
            WHERE insumo = '{insumo}'
            ORDER BY fecha DESC LIMIT 5
        """).fetchall()
        return [r[0] for r in resultados]
    ```
  - No integrar aún (es S4), solo arquitectura lista
- **Verificación:** Función sin errores (datos de prueba falsos)
- **Nota:** Sin conflictos; `duckdb` es aislado

#### **T4.3** — Punto 3: ETL masivo de OFF (Día 1 paralelo, ejecutar S2)
- **Impacto:** 🔴 Bloqueador P03 — datos reales
- **Tamaño:** 2-4 horas descarga + 1 hora procesamiento (pero corre en paralelo)
- **Dependencia:** T2.1 (entry point), T2.3 (fecha real)
- **Tarea:** (Iniciar HOY pero ejecutar lentamente en background)
  - En `etl/cargar_off.py`, cambiar línea 5-7 para descargar export masivo:
    ```python
    def cargar_off_masivo(insumo="", output_file="data/off_export.json"):
        print(f"Descargando export masivo de OFF...")
        # Usar endpoint de descarga completa, no búsqueda
        url = "https://world.openfoodfacts.org/data/exports/products.jsonl.gz"
        # O para subset por categoría: cargar incrementalmente
    ```
  - Filtrar por los 5 insumos: arándano, palta, espárrago, mango, quinua
  - Garantizar 50-200 productos por insumo (verificar cobertura)
  - Incluir `fecha_dato` real
- **Verificación:** `data/off_productos.json` contiene 250-1000 productos totales con datos reales
- **Nota:** Iniciar descarga EN PARALELO el día 1 (tarea asyncrónica larga)

---

### TIER 5 · DOCUMENTACIÓN E INFRAESTRUCTURA (Día 4-5)

#### **T5.1** — Punto 6: Crear `datasets/` con manifest
- **Impacto:** 🟡 Alto — reproducibilidad
- **Tamaño:** 1-2 horas (después de T4.3)
- **Dependencia:** T4.3 (datos descargados)
- **Tarea:**
  - Crear directorio `datasets/2026-07/`
  - Mover/copiar `data/off_productos.json`, `data/usda_productos.json`, etc. a `datasets/2026-07/`
  - Crear `datasets/2026-07/manifest.json`:
    ```json
    {
      "fecha_descarga": "2026-07-29T14:30:00Z",
      "version_taxonomia": "0.1",
      "fuentes": {
        "off_productos": {
          "filas": 487,
          "hash_sha256": "abc123...",
          "fecha_fuente": "2026-07-28"
        },
        "usda_productos": {
          "filas": 34,
          "hash_sha256": "def456...",
          "fecha_fuente": "2026-07-28"
        }
      }
    }
    ```
  - En `main.py:51`, cambiar `snapshot_version="2026-07"` a leer del manifest: `snapshot_version = json.load(open("datasets/2026-07/manifest.json"))["version_taxonomia"]`
  - En CI, validar que manifest existe y es válido
- **Verificación:** `snapshot_version` es "0.1" (de manifest), no cadena fija
- **Nota:** Sin conflictos de versión

#### **T5.2** — Punto 7: Generar `contratos/` en CI
- **Impacto:** 🟡 Medio — auditoría
- **Tamaño:** 1-2 horas
- **Dependencia:** Ninguna (paralelo)
- **Tarea:**
  - Crear script `scripts/generar_contratos.py`:
    ```python
    from dominio.insumo import InsumoInterpretado
    from dominio.insight_mercado import InsightDeMercado
    import json
    contratos = {
        "InsumoInterpretado": InsumoInterpretado.model_json_schema(),
        "InsightDeMercado": InsightDeMercado.model_json_schema(),
        # ... más
    }
    with open("contratos/schemas.json", "w") as f:
        json.dump(contratos, f, indent=2)
    ```
  - Ejecutar en CI antes de tests
  - Guardar en `contratos/schemas.json`
  - Documentar: los contratos son la **fuente de verdad**, no las clases
- **Verificación:** `contratos/schemas.json` existe y valida un Pydantic model real
- **Nota:** Sin conflictos

---

## RESUMEN DE PRECEDENCIAS

```
T1.1 (dependencias)
  ├─ T2.1, T2.2, T2.3, T2.4, T2.5, T2.6 (paralelo)
  └─ T1.2 (verificar Huawei)
      └─ T1.3 (tarifa por modelo)
          ├─ T3.1 (cost-meter)
          └─ T3.3 (modelos por etapa)
  
  T2.1 (entry point)
      └─ T4.3 (ETL masivo) → T5.1 (datasets/)
  
  T2.3 (fecha real) ─┐
  T4.3 (ETL masivo) ─┤
  T3.2 (auth)       ─┤ Todos necesarios para S2
  T4.1 (embeddings) ─┘

  T3.2 (auth) + T3.1 (cost-meter) + T3.3 (modelos) ← independientes

  T4.2 (DuckDB arquitectura) ← preparar ahora, ejecutar S4
  T5.2 (contratos CI) ← después, bajo impacto
```

---

## CHECKLIST DE CONFLICTOS DE VERSIÓN

| Tarea | Dependencia Nueva | Conflicto Potencial | Mitigación |
|---|---|---|---|
| T1.1 | markdown, requests, xhtml2pdf | Ninguno (librerías maduras) | Usar versiones conservadoras |
| T3.2.1 | bcrypt, python-jose | Ninguno (crypto isoladas) | No mezclar con openssl viejo |
| T4.1 | sentence-transformers, torch | Posible: torch + otra IA | Usar torch 2.1+ para compatibilidad |
| T4.3 | Nada nuevo | Ninguno | Solo cambio de ETL |
| Resto | Nada nuevo | Ninguno | — |

**Nota crítica:** `sentence-transformers` trae `torch` como transitividad. Si hay otro proyecto con PyTorch diferente, puede haber conflicto. Solución: usar `pip-tools` o `poetry.lock` para pinear exactas.

---

## EJECUCIÓN RECOMENDADA

### Día 1 (2026-07-29)
- **Paralelo:**
  - T1.1 (2 min) → verifica `uv sync`
  - T1.2 (30 min) → contactar Huawei
  - T1.3 (15 min) → tarifa JSON
  - T2.1 (5 min) → arreglar entry point
  - T2.2 (30 min) → decidir PDF
  - T2.3 (30 min) → fecha real
  - T4.3 (iniciar descarga OFF en background)
- **Secuencial después:**
  - T2.4, T2.5, T2.6 (paralelo, 2-3 horas)

### Día 2 (2026-07-30)
- Finalizar T4.3 (datos descargados?)
- T3.1 (cost-meter, 2 horas)
- T3.2 (auth real, 4 horas)
- **Paralelo:** T3.3 (modelos, 1-2 horas)

### Día 3 (2026-07-31)
- T4.1 (embeddings + indexado, 3-4 horas)
- **Paralelo:** T5.1 (datasets/), T5.2 (contratos/)
- T4.2 preparar arquitectura (DuckDB, 1 hora)

### Días 4-5 (2026-08-01/02)
- Integración, pruebas manuales
- Verificar `uv sync` en máquina limpia
- Ejecutar suite P01-P13 (parcial, lo que es posible sin S2 datos)
- Grabar run offline (T2.6)

**Hito:** Al final de Semana 1, 10-12 de los 20 puntos resueltos, MVP bootstrap listo para S2.

---

*Documento de referencia para ejecución paralela sin regresiones ni conflictos semánticos.*
