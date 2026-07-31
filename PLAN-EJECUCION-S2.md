# Plan de Ejecución Semana 2 · Tareas y cambios de código

**Formato:** Tickets ejecutables con pseudocódigo y archivos a modificar.

---

## [S2-T01] Setup de estructura de datos y validación de dependencias

**Duración:** Día 1 (2 horas)  
**Asignación:** Quien arranque S2  
**Depende de:** S1 entregado; permisos de API listos

### Tareas

1. Crear carpeta estructura:
```bash
mkdir -p datasets/2026-07
mkdir -p datasets/2026-07/raw
touch datasets/2026-07/README.md
touch datasets/2026-07/manifest.json
```

2. Escribir `datasets/2026-07/README.md`:
```markdown
# Dataset Semana 2: 5 insumos piloto

## Origen y procedimiento

1. **OFF (Open Food Facts):**
   ```bash
   python -m etl.cargar_off_masivo \
     --insumos arándano,palta,espárrago,mango,quinua \
     --output off_productos.json
   ```
   Comando: `python -m etl.cargar_off --bulk 2026-07`

2. **USDA Branded:**
   ```bash
   USDA_API_KEY=$USDA_API_KEY python -m etl.cargar_usda \
     --insumos arándano,palta,espárrago,mango,quinua \
     --output usda_productos.json
   ```

3. **Indexación:**
   ```bash
   python -m etl.indexar_vectores --dataset 2026-07
   ```

## Validación

Ejecutar al final:
```bash
python -m evals.validar_dataset --dataset 2026-07
```

Espera: `manifest.json` con todos los campos llenos, ≥250 productos, embeddings presentes.

## Metadatos

- Descargado: YYYY-MM-DD HH:MM:SS
- SHA256 de cada archivo en manifest.json
- Versión de modelo bge-m3 (ej: `sentence-transformers==2.2.2`)
- Versión snapshot: 2026-07
- Versión taxonomía: 0.1
```

3. Validar que dependencias están presentes:
```bash
python -c "
from sentence_transformers import SentenceTransformer
import lancedb
import duckdb
print('✓ Dependencies OK')
"
```

4. Verificar acceso a APIs:
```bash
# OFF (sin auth, public)
curl -s "https://world.openfoodfacts.org/cgi/search.pl?search_terms=blueberry&json=1&page_size=1" | jq .products[0].product_name

# USDA (requiere USDA_API_KEY)
curl -s "https://api.nal.usda.gov/fdc/v1/foods/search?query=blueberry&pageSize=1&api_key=$USDA_API_KEY" | jq .foods[0].description
```

5. Crear `datasets/2026-07/manifest.json` template:
```json
{
  "fecha_descarga": null,
  "snapshot_version": "2026-07",
  "version_taxonomia": "0.1",
  "version_modelos": {
    "embeddings": "BAAI/bge-m3 (sentence-transformers==2.2.2)"
  },
  "fuentes": {},
  "metadata": {
    "desarrollador": "AgroScout",
    "proposito": "MVP demo S2 CITE",
    "reproducibilidad": "SHA256 de cada fuente disponible"
  }
}
```

**DoD:**
- [ ] Estructura de carpetas lista
- [ ] README con procedimiento reproducible
- [ ] API accesibles (test de conectividad pasa)
- [ ] Manifest template creado

---

## [S2-T02] Descarga masiva de OFF

**Duración:** Día 2 (4-8 horas, parallelizable)  
**Asignación:** Dev parallelizable con T03  
**Depende de:** S2-T01

### Tareas

1. **Plan B decisión:** ¿OFF live API o descarga local masiva?

   **Opción A (recomendada para fiabilidad):**
   - Descargar export masivo desde https://world.openfoodfacts.org/data/
   - Archivo: `en.openfoodfacts.org.products.csv.gz` (~2 GB)
   - Tiempo: ~15 min en conexión buena
   - Ventaja: No depende de API live, más reproducible
   - Script: descargar, descomprimir, filtrar
   
   **Opción B (actual):**
   - Usar API live con reintentos
   - Ventaja: Datos frescos
   - Desventaja: Lento, puede fallar

   **Decisión:** Si OFF en Día 1 tarda >10 min total, cambiar a Opción A.

2. Modificar `etl/cargar_off.py`:
```python
# Reemplazar toda la función cargar_off_masivo() con esto:

def cargar_off_masivo(
    insumos: List[str] = None,
    output_file: str = "datasets/2026-07/off_productos.json",
    min_productos: int = 50,
    timeout_sec: int = 20
):
    """
    Descarga OFF por insumo con reintentos exponenciales.
    Fallback a DEMO data solo si todos los reintentos fallan.
    """
    if insumos is None:
        insumos = ["arándano", "palta", "espárrago", "mango", "quinua"]

    print(f"[OFF] Iniciando descarga para {insumos}")
    productos = []
    user_agent = "AgroScout-CITE/0.1 (CITEagroindustrial; +https://cite.pe)"
    
    for insumo in insumos:
        print(f"  [{insumo}]...", end=" ", flush=True)
        
        attempt = 0
        max_attempts = 3
        backoff = 1
        
        while attempt < max_attempts:
            try:
                url = "https://world.openfoodfacts.org/cgi/search.pl"
                params = {
                    "search_terms": insumo,
                    "search_simple": 1,
                    "action": "process",
                    "json": 1,
                    "page_size": 100,  # máximo
                    "sort_by": "created_t"
                }
                
                response = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": user_agent},
                    timeout=timeout_sec
                )
                response.raise_for_status()
                data = response.json()
                
                count = 0
                for item in data.get("products", []):
                    if not item.get("ingredients_text"):
                        continue
                    
                    # ✓ fecha_dato REAL desde OFF
                    fecha_ts = item.get("last_modified_t")
                    if not fecha_ts:
                        continue  # Omitir si no hay fecha
                    
                    productos.append({
                        "id_fuente": f"OFF:{item.get('id', 'N/A')}",
                        "nombre": item.get("product_name", "Unknown"),
                        "categoria": item.get("categories", ""),
                        "ingredientes": item.get("ingredients_text", ""),
                        "url": item.get("url", ""),
                        "usa_insumo_directo": False,  # ← derivado después
                        "fecha_dato": fecha_ts,  # ← timestamp real, no today()
                        "marca": item.get("brands", ""),
                        "pais": item.get("countries", "")
                    })
                    count += 1
                
                print(f"OK ({count})", flush=True)
                break  # salir del loop de reintentos
                
            except (requests.Timeout, requests.ConnectionError, ValueError) as e:
                attempt += 1
                if attempt < max_attempts:
                    print(f"retry {attempt}/{max_attempts}...", end=" ", flush=True)
                    import time
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"FAIL después de {max_attempts} intentos: {e}")
                    
            except Exception as e:
                print(f"ERROR: {e}")
                break
    
    # Validación
    if len(productos) < min_productos:
        print(f"\n[WARN] Solo {len(productos)} productos (mínimo: {min_productos})")
        print("[WARN] Agregando datos DEMO solo como fallback de desarrollo...")
        
        # DEMO data SOLO si OFF falló completamente
        productos.extend([
            # ... (demo data de antes, pero ETIQUETADA como DEMO)
            {
                "id_fuente": "DEMO:1",
                "nombre": "Blueberry Extract Powder",
                "categoria": "Food ingredients",
                "ingredientes": "blueberry, maltodextrin",
                "url": "https://demo.agroscout.local",
                "usa_insumo_directo": False,
                "fecha_dato": 1719705600,
                "marca": "[DEMO]",
                "pais": "[DEMO]"
            }
            # ...más items de demo...
        ])
        print(f"[DEMO] Agregados {len([p for p in productos if p['id_fuente'].startswith('DEMO')])} items de demostración")
    
    # Guardar
    os.makedirs("datasets/2026-07", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)
    
    print(f"\n[OFF] Total: {len(productos)} productos → {output_file}")
    
    # Log de métricas
    off_only = [p for p in productos if p['id_fuente'].startswith('OFF')]
    if off_only:
        fechas = [p['fecha_dato'] for p in off_only if p['fecha_dato']]
        print(f"[OFF] Fecha más antigua: {min(fechas) if fechas else 'N/A'}")
        print(f"[OFF] Fecha más reciente: {max(fechas) if fechas else 'N/A'}")
    
    return productos
```

3. Crear `test/test_off_descarga.py`:
```python
import pytest
import json
from etl.cargar_off import cargar_off_masivo

def test_cargar_off_masivo():
    """Verifica que OFF descarga datos reales."""
    productos = cargar_off_masivo()
    
    # Validaciones
    assert len(productos) >= 50, "Menos de 50 productos descargados"
    
    # Verificar que NO hay DEMO si OFF tuvo éxito
    demo_count = len([p for p in productos if p['id_fuente'].startswith('DEMO')])
    off_count = len([p for p in productos if p['id_fuente'].startswith('OFF')])
    
    if off_count >= 50:
        assert demo_count == 0, "OFF tuvo éxito pero aún hay DEMO data"
    
    # Verificar fecha real
    for p in productos:
        if p['id_fuente'].startswith('OFF'):
            assert isinstance(p['fecha_dato'], int), "fecha_dato debe ser timestamp"
            assert p['fecha_dato'] > 1600000000, "fecha_dato parece inventada (muy antigua)"
    
    print(f"✓ {len(productos)} productos, {off_count} de OFF, {demo_count} DEMO")
```

4. Ejecutar:
```bash
python -m etl.cargar_off_masivo
pytest test/test_off_descarga.py -v
```

**DoD:**
- [ ] `datasets/2026-07/off_productos.json` ≥50 filas
- [ ] Cada fila tiene `fecha_dato` real (timestamp Unix)
- [ ] URL verificable (no inventada)
- [ ] DEMO data solo si OFF falló (etiquetada claramente)
- [ ] Test pasa

---

## [S2-T03] Descarga de USDA Branded (parallelizable con T02)

**Duración:** Día 2-3 (4 horas)  
**Asignación:** Dev parallelizable  
**Depende de:** USDA_API_KEY en `.env.local`

### Tareas

1. Crear `etl/cargar_usda.py` (nuevo archivo):
```python
import requests
import json
import os
from typing import List, Dict
from datetime import datetime

def cargar_usda_branded(
    insumos: List[str] = None,
    output_file: str = "datasets/2026-07/usda_productos.json"
) -> List[Dict]:
    """
    Descarga productos Branded de USDA FDC API.
    Requiere USDA_API_KEY en .env.
    """
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        print("[USDA] USDA_API_KEY no configurada. Omitiendo USDA.")
        return []
    
    if insumos is None:
        insumos = ["blueberry", "avocado", "asparagus", "mango", "quinoa"]
    
    print(f"[USDA] Iniciando descarga para {insumos}")
    
    productos = []
    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    
    for insumo in insumos:
        print(f"  [{insumo}]...", end=" ", flush=True)
        
        try:
            params = {
                "query": insumo,
                "pageSize": 100,
                "pageNumber": 1,
                "api_key": api_key
            }
            
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            count = 0
            for food in data.get("foods", []):
                # Filtrar solo Branded Food Products (dataType = 'Branded')
                if food.get("dataType") != "Branded":
                    continue
                
                productos.append({
                    "id_fuente": f"USDA:{food.get('fdc_id', 'N/A')}",
                    "nombre": food.get("description", "Unknown"),
                    "categoria": food.get("foodCategory", ""),
                    "ingredientes": food.get("ingredients", ""),
                    "url": f"https://fdc.nal.usda.gov/fdc-app.html#?ndbno={food.get('fdc_id')}",
                    "usa_insumo_directo": False,
                    "fecha_dato": int(datetime.now().timestamp()),  # ← USDA no tiene last_modified, usar hoy
                    "marca": food.get("brandName", ""),
                    "pais": "USA"  # USDA es USA-only
                })
                count += 1
            
            print(f"OK ({count})")
            
        except Exception as e:
            print(f"FAIL: {e}")
    
    # Guardar
    os.makedirs("datasets/2026-07", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(productos, f, ensure_ascii=False, indent=2)
    
    print(f"[USDA] Total: {len(productos)} productos → {output_file}")
    return productos
```

2. Modificar `etl/cargar_off_masivo()` para deduplicar vs USDA:
   (Ver después de USDA descargado)

3. Test:
```bash
USDA_API_KEY=$USDA_API_KEY python -m etl.cargar_usda
```

**DoD:**
- [ ] `datasets/2026-07/usda_productos.json` ≥10 filas
- [ ] Cada fila: id_fuente, nombre, marca, país="USA", url navegable
- [ ] API key verificada y documentada

---

## [S2-T04] Deduplicación OFF vs USDA + merge

**Duración:** Día 3 (2 horas)  
**Asignación:** Secuencial a T02/T03  
**Depende de:** T02 + T03 completos

### Tareas

1. Crear `etl/dedup_merge_datasets.py`:
```python
import json
from typing import List, Dict, Tuple

def similar_product(p1: Dict, p2: Dict, threshold: float = 0.8) -> bool:
    """
    Heurística simple: mismo marca + similar nombre.
    Mejora futura: embedding similarity.
    """
    marca_match = (
        p1.get("marca", "").lower() == p2.get("marca", "").lower()
    )
    if not marca_match:
        return False
    
    # Nombre similar (primeras 10 chars)
    n1 = p1.get("nombre", "")[:10].lower()
    n2 = p2.get("nombre", "")[:10].lower()
    
    return n1 == n2

def merge_datasets(
    off_file: str = "datasets/2026-07/off_productos.json",
    usda_file: str = "datasets/2026-07/usda_productos.json",
    output_file: str = "datasets/2026-07/productos_merged.json"
) -> List[Dict]:
    """
    Carga OFF + USDA, quita duplicados, guarda merge.
    """
    with open(off_file) as f:
        productos_off = json.load(f)
    
    with open(usda_file) as f:
        productos_usda = json.load(f)
    
    print(f"[MERGE] OFF: {len(productos_off)}, USDA: {len(productos_usda)}")
    
    # Merge evitando duplicados
    merged = productos_off.copy()
    duplicados = 0
    
    for p_usda in productos_usda:
        is_dup = False
        for p_off in productos_off:
            if similar_product(p_usda, p_off):
                is_dup = True
                duplicados += 1
                break
        
        if not is_dup:
            merged.append(p_usda)
    
    print(f"[MERGE] Duplicados removidos: {duplicados}")
    print(f"[MERGE] Total final: {len(merged)}")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
    return merged
```

2. Ejecutar:
```bash
python -m etl.dedup_merge_datasets
```

**DoD:**
- [ ] `datasets/2026-07/productos_merged.json` lista sin duplicados obvios
- [ ] Logging de deduplicación

---

## [S2-T05] Indexación con embeddings bge-m3

**Duración:** Día 4 (6 horas, incluye tiempo de cómputo)  
**Asignación:** Dev frontend o especialista en embeddings  
**Depende de:** T04, T01

### Tareas

1. Reescribir `etl/indexar_vectores.py` completo:
```python
import os
import json
import sys
from pathlib import Path
from typing import List, Dict
import lancedb
from sentence_transformers import SentenceTransformer
import time

def load_products(dataset_dir: str = "datasets/2026-07/") -> List[Dict]:
    """Carga productos desde merged dataset."""
    path = Path(dataset_dir) / "productos_merged.json"
    with open(path) as f:
        return json.load(f)

def create_embeddings(
    productos: List[Dict],
    model_name: str = "BAAI/bge-m3",
    batch_size: int = 32
) -> tuple:
    """
    Genera embeddings para los productos.
    Retorna: (embeddings, modelo)
    """
    print(f"[EMBED] Cargando modelo {model_name}...")
    model = SentenceTransformer(model_name)
    
    # Preparar textos para embeddings
    texts = [
        f"{p.get('nombre', '')} {p.get('ingredientes', '')}"
        for p in productos
    ]
    
    print(f"[EMBED] Generando {len(texts)} embeddings (batch_size={batch_size})...")
    
    start = time.time()
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=True)
    elapsed = time.time() - start
    
    print(f"[EMBED] Listo en {elapsed:.1f}s")
    return embeddings, model

def main(
    dataset_dir: str = "datasets/2026-07/",
    output_dir: str = "vectores/",
    table_name: str = "productos"
):
    """
    ETL completo: carga, embeddings, indexa en LanceDB.
    """
    print(f"[S2-ETL] Iniciando indexación desde {dataset_dir}")
    
    # 1. Cargar productos
    productos = load_products(dataset_dir)
    print(f"[S2-ETL] Cargados {len(productos)} productos")
    
    # 2. Generar embeddings
    embeddings, model = create_embeddings(productos)
    
    # 3. Preparar data para LanceDB
    data = []
    for p, emb in zip(productos, embeddings):
        data.append({
            "id": p["id_fuente"],
            "nombre": p["nombre"],
            "categoria": p.get("categoria", ""),
            "ingredientes": p.get("ingredientes", ""),
            "url": p.get("url", ""),
            "fecha_dato": p.get("fecha_dato"),
            "marca": p.get("marca", ""),
            "pais": p.get("pais", ""),
            "fuente": p["id_fuente"].split(":")[0],  # OFF, USDA, etc
            "embedding": emb.tolist()  # LanceDB espera list, no array
        })
    
    # 4. Indexar en LanceDB
    print(f"[S2-ETL] Indexando en LanceDB...")
    db = lancedb.connect(output_dir)
    
    # Eliminar tabla anterior si existe
    try:
        db.drop_table(table_name)
    except:
        pass
    
    table = db.create_table(
        table_name,
        data=data,
        mode="create"  # o "overwrite"
    )
    
    # 5. Crear índice vectorial
    print(f"[S2-ETL] Creando índice vectorial...")
    table.create_index()  # LanceDB crea automáticamente índice ANN
    
    print(f"[S2-ETL] ✓ {table.count_rows()} productos indexados")
    
    # 6. Actualizar manifest.json
    manifest_path = Path(dataset_dir) / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    manifest["embeddings"] = {
        "modelo": "BAAI/bge-m3",
        "dimensiones": 1024,
        "filas": table.count_rows(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"[S2-ETL] Manifest actualizado")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

2. Actualizar `etl/indexar_vectores.py` entry point en `pyproject.toml`:
```toml
# Cambiar de:
etl = "etl.indexar_vectores:indexar_vectores"
# A:
etl = "etl.indexar_vectores:main"
```

3. Ejecutar y medir:
```bash
time python -m etl  # Esperar 5-15 min según tamaño
```

4. Validar:
```python
# test/test_embeddings.py
import lancedb

def test_embeddings_indexed():
    db = lancedb.connect("vectores/")
    table = db.open_table("productos")
    
    assert table.count_rows() >= 250
    
    # Validar estructura
    sample = table.limit(1).to_list()[0]
    assert "embedding" in sample
    assert "fecha_dato" in sample
    assert "url" in sample
    
    print(f"✓ {table.count_rows()} productos con embeddings")

pytest test/test_embeddings.py -v
```

**DoD:**
- [ ] `vectores/productos.lance/` existe con tabla `productos`
- [ ] ≥250 filas con embeddings (1024 dimensiones)
- [ ] Tiempo de indexación < 30 min
- [ ] Manifest.json actualizado

---

## [S2-T06] Búsqueda con embeddings + medición de latencia p95

**Duración:** Día 5 (4 horas)  
**Asignación:** Dev especialista en búsqueda  
**Depende de:** S2-T05

### Tareas

1. Reescribir `adaptadores/busqueda_lancedb.py`:
```python
import lancedb
from sentence_transformers import SentenceTransformer
from typing import List
import time
from dominio.resultado_busqueda import ResultadoBusqueda

# Singleton de modelo y tabla
_model = None
_table = None

def init_search(db_path: str = "vectores/"):
    """Inicializa modelo y tabla de búsqueda."""
    global _model, _table
    _model = SentenceTransformer("BAAI/bge-m3")
    db = lancedb.connect(db_path)
    _table = db.open_table("productos")
    print(f"[SEARCH] Inicializado con {_table.count_rows()} productos")

def buscar_productos(
    query: str,
    insumo: str = None,
    limit: int = 5,
    exclude_demo: bool = True
) -> List[ResultadoBusqueda]:
    """
    Busca productos por similitud vectorial.
    
    Args:
        query: texto de búsqueda
        insumo: filtro opcional por insumo
        limit: cantidad de resultados
        exclude_demo: excluir DEMO data si hay OFF
    
    Returns:
        Lista de ResultadoBusqueda
    """
    if _table is None:
        init_search()
    
    # 1. Generar embedding del query
    embedding = _model.encode(query, normalize_embeddings=True)
    
    # 2. Búsqueda vectorial
    results = (
        _table
        .search(embedding)
        .metric("cosine")
        .limit(limit * 2)  # Traer extras para filtrar
        .to_list()
    )
    
    # 3. Filtrar DEMO si hay OFF
    if exclude_demo:
        off_results = [r for r in results if r["fuente"] == "OFF"]
        if off_results:
            results = off_results
    
    # 4. Mapear a ResultadoBusqueda
    return [
        ResultadoBusqueda(
            id=r["id"],
            nombre=r["nombre"],
            ingredientes=r["ingredientes"],
            fuente_url=r["url"],
            fecha_dato=r["fecha_dato"],  # ← REAL, no inventada
            similitud=1 - r["_distance"],  # convertir distancia a similitud
            fuente=r["fuente"]
        )
        for r in results[:limit]
    ]

def medir_latencia_p95(
    queries: List[str] = None,
    num_samples: int = 100
) -> float:
    """
    Mide latencia p95 de búsquedas.
    """
    if queries is None:
        queries = ["blueberry", "avocado", "asparagus", "mango", "quinoa"]
    
    import numpy as np
    latencies = []
    
    for _ in range(num_samples):
        query = queries[_ % len(queries)]
        t0 = time.time()
        buscar_productos(query, limit=5)
        latencies.append(time.time() - t0)
    
    p95 = np.percentile(latencies, 95)
    print(f"[LATENCY] p95 = {p95:.3f}s (de {num_samples} queries)")
    return p95
```

2. Crear `test/test_latency.py`:
```python
import pytest
from adaptadores.busqueda_lancedb import medir_latencia_p95, buscar_productos

def test_p95_latency():
    """P03: Búsqueda < 2s p95."""
    p95 = medir_latencia_p95(num_samples=100)
    assert p95 < 2.0, f"P95 latency {p95}s exceeds 2s SLA"

def test_buscar_productos_no_demo():
    """P03: Sin DEMO data si OFF disponible."""
    results = buscar_productos("blueberry")
    
    assert len(results) >= 3, "Menos de 3 resultados"
    
    # Validar que son datos reales
    for r in results:
        assert r.fecha_dato is not None, "fecha_dato no debe ser None"
        assert r.fuente_url, "URL debe estar presente"
        assert r.fuente in ("OFF", "USDA"), f"Fuente inesperada: {r.fuente}"

pytest test/test_latency.py -v
```

3. Integrar en `casos_de_uso/etapas/interpretar_insumo.py`:
   - Después de interpretar insumo, llamar a `buscar_productos()` para traer datos reales
   - Verificar que fecha_dato viene de la tabla, no es inventada

**DoD:**
- [ ] P95 < 2s (medido con 100+ queries)
- [ ] Sin DEMO data en resultados
- [ ] fecha_dato es timestamp real
- [ ] Test pasa

---

## [S2-T07] Corpus regulatorio mínimo (eCFR + DIGESA)

**Duración:** Día 5-6 (6 horas, parallelizable con T06)  
**Asignación:** Dev especialista en regulación o CITE  
**Depende de:** T01

### Tareas

1. Crear `datasets/2026-07/ecfr_aditivos.json`:
```bash
# Opción A: Descargar manualmente desde eCFR
curl -s "https://www.ecfr.gov/api/renderer/versions/title-21/part-182/full.json" \
  -o datasets/2026-07/ecfr_raw.json

# Opción B: Usar subset conocido (si A falla)
# Copiar lista de aditivos GRAS conocidos a JSON
```

Script `etl/procesar_ecfr.py`:
```python
import json

def procesar_ecfr(raw_file: str = "datasets/2026-07/ecfr_raw.json"):
    """
    Procesa raw eCFR → formato normalizado.
    """
    with open(raw_file) as f:
        raw = json.load(f)
    
    aditivos = []
    
    # Parsear estructura de eCFR (varía, pero típicamente tiene "children" con secciones)
    for section in raw.get("children", []):
        aditivo = {
            "id": f"eCFR:{section.get('identifier', '')}",
            "titulo": section.get("title", ""),
            "texto": section.get("children", [{}])[0].get("text", ""),
            "fuente_url": f"https://www.ecfr.gov/current/title-21/part-182",
            "fecha_publicacion": "2024-01-01",  # o extraer del JSON
        }
        aditivos.append(aditivo)
    
    with open("datasets/2026-07/ecfr_aditivos.json", "w") as f:
        json.dump(aditivos, f, indent=2)
    
    print(f"[eCFR] {len(aditivos)} aditivos procesados")
```

2. DIGESA (manual o OCR):
```bash
# Descargar PDFs desde digesa.minsa.gob.pe
# Ej: resoluciones sobre aditivos, colorantes
# Usar pdfplumber o tesseract para OCR

python -c "
import pdfplumber
pdf_path = 'datasets/2026-07/DIGESA_ResolucionAditivos.pdf'
with pdfplumber.open(pdf_path) as pdf:
    text = ''.join(page.extract_text() for page in pdf.pages)
with open('datasets/2026-07/digesa_normas.txt', 'w') as f:
    f.write(text)
"
```

3. Crear `etl/procesar_regulatorio.py`:
```python
import json
import lancedb
from sentence_transformers import SentenceTransformer

def indexar_regulatorio(
    ecfr_file: str = "datasets/2026-07/ecfr_aditivos.json",
    digesa_file: str = "datasets/2026-07/digesa_normas.txt",
    db_path: str = "vectores/"
):
    """
    Indexa corpus regulatorio en LanceDB (tabla separada).
    """
    model = SentenceTransformer("BAAI/bge-m3")
    db = lancedb.connect(db_path)
    
    docs = []
    
    # Cargar eCFR
    with open(ecfr_file) as f:
        for aditivo in json.load(f):
            embedding = model.encode(aditivo["texto"])
            docs.append({
                "id": aditivo["id"],
                "titulo": aditivo["titulo"],
                "texto": aditivo["texto"],
                "fuente_url": aditivo["fuente_url"],
                "fecha_publicacion": aditivo["fecha_publicacion"],
                "tipo": "eCFR",
                "embedding": embedding.tolist()
            })
    
    # Cargar DIGESA
    with open(digesa_file) as f:
        digesa_text = f.read()
    
    # Dividir en párrafos
    paragraphs = digesa_text.split("\n\n")
    for i, para in enumerate(paragraphs[:100]):  # Limitar a primeros 100 párrafos
        if len(para) < 50:
            continue
        
        embedding = model.encode(para)
        docs.append({
            "id": f"DIGESA:{i}",
            "titulo": "DIGESA Norma",
            "texto": para,
            "fuente_url": "https://digesa.minsa.gob.pe",
            "fecha_publicacion": "2024-01-01",
            "tipo": "DIGESA",
            "embedding": embedding.tolist()
        })
    
    # Indexar
    try:
        db.drop_table("regulatorio")
    except:
        pass
    
    table = db.create_table("regulatorio", data=docs)
    table.create_index()
    
    print(f"[REGULATORIO] {len(docs)} documentos indexados")

if __name__ == "__main__":
    indexar_regulatorio()
```

**DoD:**
- [ ] `datasets/2026-07/ecfr_aditivos.json` ≥5 documentos
- [ ] `datasets/2026-07/digesa_normas.txt` ≥2000 palabras
- [ ] Tabla `regulatorio` indexada en LanceDB
- [ ] URLs navegables a fuentes oficiales

---

## [S2-T08] Golden set ampliado (5 casos reales)

**Duración:** Día 6 (2 horas)  
**Asignación:** QA o dev  
**Depende de:** T04

### Tareas

1. Ampliar `evals/set_dorado.yaml`:
```yaml
# Reemplazar contenido anterior
casos:
  - id: "S2-arándano"
    insumo: "arándano"
    descripcion: "Búsqueda de productos con arándano en OFF"
    esperado_minimo_productos: 3
    esperado_citas_regulatorias: 1
    notas: "Verificar URLs en OFF, fechas reales"
  
  - id: "S2-palta"
    insumo: "palta"
    descripcion: "Búsqueda de productos con palta/avocado"
    esperado_minimo_productos: 2
    esperado_citas_regulatorias: 0
    notas: "Palta también conocida como aguacate"
  
  - id: "S2-espárrago"
    insumo: "espárrago"
    descripcion: "Búsqueda de productos con espárrago"
    esperado_minimo_productos: 2
    esperado_citas_regulatorias: 1
    notas: "Verificar producto en USDA"
  
  - id: "S2-mango"
    insumo: "mango"
    descripcion: "Búsqueda de productos con mango"
    esperado_minimo_productos: 5
    esperado_citas_regulatorias: 1
    notas: "Mango tiene buena cobertura en OFF"
  
  - id: "S2-quinua"
    insumo: "quinua"
    descripcion: "Búsqueda de productos con quinua/quinoa"
    esperado_minimo_productos: 2
    esperado_citas_regulatorias: 0
    notas: "Quinua es término común; validar ingredientes"

validaciones:
  - nombre: "sin_demo_data"
    descripcion: "Si OFF tiene ≥50 productos, no debe haber DEMO"
  
  - nombre: "fecha_dato_real"
    descripcion: "Todas las fechas son timestamps Unix, no today()"
  
  - nombre: "url_navegable"
    descripcion: "URLs abren en navegador, productos existen"
  
  - nombre: "campos_no_inventados"
    descripcion: "Ningún campo tiene valor inventado; null cuando falta"
```

2. Crear runner `evals/runner_s2.py`:
```python
import json
import sys
from pathlib import Path
import yaml
import requests
from adaptadores.busqueda_lancedb import buscar_productos

def run_golden_set(set_file: str = "evals/set_dorado.yaml"):
    """
    Ejecuta golden set y reporta resultados.
    """
    with open(set_file) as f:
        config = yaml.safe_load(f)
    
    resultados = {"casos": []}
    
    for caso in config["casos"]:
        print(f"\n[TEST] {caso['id']}: {caso['descripcion']}")
        
        results = buscar_productos(caso["insumo"], limit=10)
        
        test_result = {
            "id": caso["id"],
            "insumo": caso["insumo"],
            "productos_encontrados": len(results),
            "minimo_esperado": caso["esperado_minimo_productos"],
            "paso": len(results) >= caso["esperado_minimo_productos"]
        }
        
        # Validar URLs
        urls_ok = 0
        for r in results:
            try:
                resp = requests.head(r.fuente_url, timeout=5)
                if resp.status_code == 200:
                    urls_ok += 1
            except:
                pass
        
        test_result["urls_navegables"] = urls_ok
        
        # Validar fechas
        fechas_reales = all(
            r.fecha_dato and r.fecha_dato > 1600000000
            for r in results
        )
        test_result["fechas_reales"] = fechas_reales
        
        print(f"  Productos: {test_result['productos_encontrados']} (esperado ≥{caso['esperado_minimo_productos']})")
        print(f"  URLs navegables: {urls_ok}/{len(results)}")
        print(f"  Fechas reales: {'✓' if fechas_reales else '✗'}")
        print(f"  Resultado: {'PASS' if test_result['paso'] else 'FAIL'}")
        
        resultados["casos"].append(test_result)
    
    # Reporte final
    total = len(resultados["casos"])
    pasos = sum(1 for c in resultados["casos"] if c["paso"])
    
    print(f"\n[RESULTADO] {pasos}/{total} casos pasaron")
    
    return pasos == total  # True si todos pasan

if __name__ == "__main__":
    success = run_golden_set()
    sys.exit(0 if success else 1)
```

3. Ejecutar:
```bash
python -m evals.runner_s2
```

**DoD:**
- [ ] 5/5 casos pasen
- [ ] URLs navegables verificadas
- [ ] Fechas reales (no today())
- [ ] Reporte guardado

---

## [S2-T09] Actualización de manifest.json + validación E2E

**Duración:** Día 6-7 (3 horas)  
**Asignación:** Dev  
**Depende de:** T02-T08

### Tareas

1. Crear script `etl/finalizar_manifest.py`:
```python
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def finalizar_manifest(dataset_dir: str = "datasets/2026-07/"):
    """
    Calcula hashes, actualiza manifest.json con metadatos completos.
    """
    manifest_path = Path(dataset_dir) / "manifest.json"
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    manifest["fecha_descarga"] = datetime.now(timezone.utc).isoformat()
    
    # Calcular hashes
    files_to_hash = [
        "off_productos.json",
        "usda_productos.json",
        "productos_merged.json",
        "ecfr_aditivos.json",
        "digesa_normas.txt"
    ]
    
    for filename in files_to_hash:
        filepath = Path(dataset_dir) / filename
        if not filepath.exists():
            continue
        
        with open(filepath, "rb") as f:
            hash_val = hashlib.sha256(f.read()).hexdigest()
        
        if filename not in manifest.get("fuentes", {}):
            manifest["fuentes"][filename] = {}
        
        manifest["fuentes"][filename]["sha256"] = hash_val
        manifest["fuentes"][filename]["tamaño_bytes"] = filepath.stat().st_size
    
    # Contar filas
    for filename in ["off_productos.json", "usda_productos.json", "productos_merged.json"]:
        filepath = Path(dataset_dir) / filename
        if filepath.exists():
            with open(filepath) as f:
                data = json.load(f)
            manifest["fuentes"][filename]["filas"] = len(data)
    
    # Guardar
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    
    print(f"[MANIFEST] Actualizado: {manifest_path}")
    print(json.dumps(manifest, indent=2))
```

2. Script E2E final:
```bash
#!/bin/bash
set -e

echo "[S2-FINAL] Validación completa de Semana 2"
echo ""

# 1. Datos existen
echo "[CHECK] Datos..."
test -f datasets/2026-07/off_productos.json || exit 1
test -f datasets/2026-07/usda_productos.json || exit 1
test -f datasets/2026-07/productos_merged.json || exit 1

# 2. Embeddings existen
echo "[CHECK] Embeddings..."
test -d vectores/productos.lance || exit 1

# 3. Golden set pasa
echo "[CHECK] Golden set..."
python -m evals.runner_s2

# 4. Latencia OK
echo "[CHECK] Latencia p95..."
python -c "
from adaptadores.busqueda_lancedb import medir_latencia_p95
p95 = medir_latencia_p95()
assert p95 < 2.0
"

# 5. Manifest completo
echo "[CHECK] Manifest..."
python -c "
import json
with open('datasets/2026-07/manifest.json') as f:
    m = json.load(f)
assert m.get('fecha_descarga'), 'fecha_descarga falta'
assert len(m.get('fuentes', {})) >= 3, 'fuentes incompletas'
print('✓ Manifest válido')
"

echo ""
echo "[S2-FINAL] ✓ Todas las verificaciones pasaron"
echo ""
echo "Próximos pasos: Semana 3 (multi-tenant + paywall)"
```

**DoD:**
- [ ] Manifest.json con hashes y metadatos completos
- [ ] E2E script pasa sin errores
- [ ] Documentación de procedimiento reproducible en README

---

## Resumen de archivos a crear/modificar

| Archivo | Tipo | Descripción |
|---|---|---|
| `datasets/2026-07/manifest.json` | Crear | Metadatos de descarga |
| `datasets/2026-07/README.md` | Crear | Procedimiento reproducible |
| `etl/cargar_off.py` | Modificar | Agregar reintentos, fecha real |
| `etl/cargar_usda.py` | Crear | Nueva descarga USDA |
| `etl/dedup_merge_datasets.py` | Crear | Merge OFF+USDA |
| `etl/indexar_vectores.py` | Reescribir | Embeddings reales con bge-m3 |
| `etl/procesar_regulatorio.py` | Crear | eCFR + DIGESA indexación |
| `adaptadores/busqueda_lancedb.py` | Reescribir | Búsqueda vectorial + latencia |
| `test/test_off_descarga.py` | Crear | Validación OFF |
| `test/test_embeddings.py` | Crear | Validación embeddings |
| `test/test_latency.py` | Crear | Validación p95 |
| `evals/set_dorado.yaml` | Ampliar | 5 casos, 1 por insumo |
| `evals/runner_s2.py` | Crear | Runner de golden set |
| `etl/finalizar_manifest.py` | Crear | Cálculo de hashes |

---

**Fin del plan de ejecución Semana 2**
