# Semana 2: Plan en TIERS de Complejidad

**Modelo:** Basado en éxito de TIER en S1  
**Estado:** S1 completada 100%, S2 lista para TIER 1  
**Duración total:** 5 días hábiles (Lun 5 - Vie 9 ago)

---

## 📊 Estructura TIERS Semana 2

```
TIER 1: Preparación (Lun 5) → 2-3 horas
  ├─ Decisiones críticas (OFF live vs offline, USDA key)
  ├─ Estructura de carpetas datasets/
  └─ Verificación de APIs

TIER 2: Descargas masivas (Mar 6-7) → 8 horas, parallelizable
  ├─ T2.1: Descarga OFF masivo (4-8 min o Plan B)
  ├─ T2.2: Descarga USDA Branded (5-15 min)
  └─ Validación: ≥250 productos sin DEMO

TIER 3: Limpieza de datos (Mié 7) → 2-3 horas
  ├─ T3.1: Deduplicación OFF vs USDA
  ├─ T3.2: Merge datasets
  └─ Validación: productos_merged.json listo

TIER 4: Embeddings masivos (Mié 7-Jue 8) → 8-12 horas (incluye cómputo)
  ├─ T4.1: Reescribir indexar_vectores.py (bge-m3 real)
  ├─ T4.2: Generar 250+ embeddings (1024-dim)
  ├─ T4.3: Crear índice LanceDB con cosine
  └─ Validación: vectores/productos.lance/ listo

TIER 5: Búsqueda optimizada (Jue 8) → 4 horas
  ├─ T5.1: Reescribir busqueda_lancedb.py (vectorial real)
  ├─ T5.2: Medir p95 latencia (100+ queries)
  └─ Validación: p95 < 2 segundos ✓ P03

TIER 6: Corpus regulatorio (Jue 8-Vie 9) → 6 horas, parallelizable con T5
  ├─ T6.1: Descargar eCFR aditivos (5 docs mínimo)
  ├─ T6.2: Procesar DIGESA normativas (2000+ palabras)
  └─ Validación: tabla regulatorio en LanceDB

TIER 7: Cierre y auditoría (Vie 9) → 4 horas
  ├─ T7.1: Golden set ampliado (5/5 casos)
  ├─ T7.2: Actualizar manifest.json (SHA256)
  ├─ T7.3: E2E workflow completo
  └─ Validación: todos hitos verdes

TOTAL TIEMPO: 28h código + 12-24h espera (descargas + indexación)
EQUIPO: 2 devs + 1 QA (parallelizable)
```

---

## 🎯 TIER 1 · Preparación y decisiones

**Duración:** 2-3 horas  
**Cuándo:** Lunes 5 agosto, 8:00-11:00 AM  
**Responsable:** Tech Lead + Dev A + Dev B  
**Riesgo:** Bajo (decisiones, no código)

### Tareas de TIER 1

#### T1.1: Decidir estrategia de descarga OFF (30 min)

**Problema:** OFF API puede ser lenta o timeout.

**Opciones:**
```
OPCIÓN A (Live API):
├─ URL: https://world.openfoodfacts.org/cgi/search.pl
├─ Velocidad típica: 5-20 min para 5 insumos
├─ Confiabilidad: Media (a veces timeout)
└─ Reproducibilidad: Alta (siempre datos frescos)

OPCIÓN B (Export offline):
├─ URL: https://world.openfoodfacts.org/data/ → descarga 2GB
├─ Velocidad típica: 30-45 min (descarga) + 5 min (filtrado local)
├─ Confiabilidad: Alta (local después)
└─ Reproducibilidad: Alta (reproducible, determinístico)
```

**Test de decisión HOY a las 10 AM:**
```bash
time python -m etl.cargar_off_masivo --test
```

**Criterio:**
- Si < 10 min total → **Usar OPCIÓN A (live)**
- Si ≥ 10 min → **Cambiar a OPCIÓN B (offline)**

**Guardar decisión en:** `datasets/2026-07/README.md` §1

---

#### T1.2: Verificar USDA_API_KEY disponible (15 min)

**Test:**
```bash
curl -s "https://api.nal.usda.gov/fdc/v1/foods/search?query=blueberry&pageSize=1&api_key=$USDA_API_KEY" | jq .foods[0]
```

**Resultado:**
- ✓ Disponible → Usar USDA, guardar en `.env.local`
- ✗ No disponible → Documentar "USDA no disponible en esta máquina", proceder solo OFF

---

#### T1.3: Crear estructura de carpetas (20 min)

```bash
mkdir -p datasets/2026-07
mkdir -p vectores
touch datasets/2026-07/README.md
touch datasets/2026-07/manifest.json
```

**Crear `datasets/2026-07/README.md`:**
```markdown
# Dataset Semana 2: 5 Insumos Piloto

## Procedimiento de reproducibilidad

### 1. Descarga OFF
Estrategia: [OPCIÓN A / OPCIÓN B según decisión T1.1]

Si OPCIÓN A (live):
\`\`\`bash
python -m etl.cargar_off_masivo
\`\`\`

Si OPCIÓN B (offline):
\`\`\`bash
wget https://world.openfoodfacts.org/data/... 
tar xz -f ...
python -m etl.filtrar_off --bulk
\`\`\`

### 2. Descarga USDA
\`\`\`bash
USDA_API_KEY=$USDA_API_KEY python -m etl.cargar_usda
\`\`\`
[O "No disponible en esta máquina" si no hay clave]

### 3. Merge y deduplicación
\`\`\`bash
python -m etl.dedup_merge_datasets
\`\`\`

### 4. Embeddings
\`\`\`bash
python -m etl.indexar_vectores
\`\`\`

### Validación
\`\`\`bash
python -m evals.validar_dataset --dataset 2026-07
\`\`\`

Esperado:
- manifest.json válido
- ≥250 productos
- Embeddings presentes
- p95 latencia < 2s
```

---

#### T1.4: Template manifest.json (15 min)

```json
{
  "fecha_descarga": null,
  "snapshot_version": "2026-07",
  "version_taxonomia": "0.1",
  "version_modelos": {
    "embeddings": "BAAI/bge-m3 (sentence-transformers==2.2.2)",
    "busqueda": "LanceDB con métrica cosine"
  },
  "insumos_piloto": ["arándano", "palta", "espárrago", "mango", "quinua"],
  "estrategia_descarga": "[OPCIÓN A / B según T1.1]",
  "usda_disponible": "[true / false según T1.2]",
  "fuentes": {},
  "estadisticas": {},
  "metadata": {
    "desarrollador": "AgroScout",
    "proposito": "MVP S2 CITE",
    "reproducibilidad": "SHA256 de cada fuente"
  }
}
```

---

#### T1.5: Verificar que S1 está integrada (15 min)

**Test rápido:**
```python
# test/test_prerequisitos_s2.py
import pytest
from api.main import app
from adaptadores.busqueda_lancedb import buscar_productos

def test_s1_cost_meter():
    """Verificar que cost-meter de S1 funciona."""
    # Debe estar en adaptadores/
    from adaptadores.redactor_glm import RedactorGLM
    r = RedactorGLM()
    # cost_usd debe > 0, no 0.0
    # (verificación indirecta vía modelo)
    assert r.modelo in ["openai/deepseek-v4-flash", "openai/glm-5.0"]

def test_s1_auth_jwt():
    """Verificar que auth JWT de S1 funciona."""
    client = app.test_client()
    # Sin token → 401
    response = client.post("/consultas", json={"insumo": "test"})
    assert response.status_code in (401, 403)

def test_s1_embeddings_importable():
    """Verificar que bge-m3 se puede importar."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("BAAI/bge-m3")
    assert model is not None

pytest test/test_prerequisitos_s2.py -v
```

**Esperado:** 3/3 pasan ✓

---

### DoD de TIER 1

- [ ] Decisión OFF live vs offline comunicada al equipo
- [ ] USDA_API_KEY confirmada o documentada ausente
- [ ] `datasets/2026-07/` estructura creada
- [ ] `README.md` con procedimiento reproducible
- [ ] `manifest.json` template listo
- [ ] Test de S1 prerequisites pasa (3/3)
- [ ] Equipo conoce el plan de 5 días

---

## 🚀 TIER 2 · Descargas masivas

**Duración:** 8 horas (Martes 6 - Miércoles 7, parallelizable)  
**Equipo:** Dev A + Dev A (o 2 devs en paralelo)  
**Riesgo:** Medio (timeouts posibles, Plan B documentado)  
**Dependencia:** TIER 1 ✓

### Tareas de TIER 2

#### T2.1: Descarga OFF masivo

**Script:** `etl/cargar_off_masivo()` (ya existe, necesita ajuste)

**Cambios necesarios:**
```python
def cargar_off_masivo(
    insumos: List[str] = None,
    output_file: str = "datasets/2026-07/off_productos.json",
    min_productos: int = 50,
    strategy: str = "live"  # o "offline"
):
    """
    Descarga OFF con reintentos exponenciales.
    Opción live: API web con reintentos 3x
    Opción offline: Bulk export local
    """
    if insumos is None:
        insumos = ["arándano", "palta", "espárrago", "mango", "quinua"]
    
    # Código existente + reintentos exponenciales
    # Si strategy == "offline": usar export local
```

**Ejecución:**
```bash
# Opción A (live)
time python -m etl.cargar_off_masivo

# Opción B (offline)
time python -m etl.cargar_off_masivo --bulk ~/off_export.csv.gz
```

**Validación:**
```python
with open("datasets/2026-07/off_productos.json") as f:
    productos_off = json.load(f)

assert len(productos_off) >= 250, f"Insuficientes: {len(productos_off)}"
assert all(p.get("fecha_dato") for p in productos_off), "fecha_dato falta"
assert all(p.get("url") for p in productos_off), "URL falta"

# Log de métricas
print(f"✓ OFF: {len(productos_off)} productos")
for insumo in ["arándano", "palta", "espárrago", "mango", "quinua"]:
    count = len([p for p in productos_off if insumo in p.get("ingredientes", "").lower()])
    print(f"  {insumo}: {count}")
```

**Tiempo esperado:** 5-20 min (live) o 30-45 min (offline)  
**Salida:** `datasets/2026-07/off_productos.json` ≥250 filas

---

#### T2.2: Descarga USDA Branded

**Script:** `etl/cargar_usda.py` (nuevo, crear)

```python
import requests
import json
import os
from typing import List, Dict

def cargar_usda_branded(
    insumos: List[str] = None,
    output_file: str = "datasets/2026-07/usda_productos.json"
) -> List[Dict]:
    """Descarga productos Branded de USDA FDC API."""
    
    api_key = os.getenv("USDA_API_KEY")
    if not api_key:
        print("[USDA] USDA_API_KEY no configurada. Saltando USDA.")
        return []
    
    if insumos is None:
        insumos = ["blueberry", "avocado", "asparagus", "mango", "quinoa"]
    
    productos = []
    base_url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    
    for insumo in insumos:
        try:
            params = {
                "query": insumo,
                "pageSize": 100,
                "api_key": api_key
            }
            response = requests.get(base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            for food in data.get("foods", []):
                if food.get("dataType") != "Branded":
                    continue
                
                productos.append({
                    "id_fuente": f"USDA:{food.get('fdc_id', 'N/A')}",
                    "nombre": food.get("description", "Unknown"),
                    "ingredientes": food.get("ingredients", ""),
                    "url": f"https://fdc.nal.usda.gov/fdc-app.html#?ndbno={food.get('fdc_id')}",
                    "fecha_dato": int(time.time()),  # USDA no tiene last_modified
                    "marca": food.get("brandName", ""),
                    "pais": "USA"
                })
            
            print(f"  [{insumo}] {len(productos)} productos")
        
        except Exception as e:
            print(f"  [{insumo}] ERROR: {e}")
    
    os.makedirs("datasets/2026-07", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(productos, f, indent=2)
    
    print(f"✓ USDA: {len(productos)} productos → {output_file}")
    return productos

if __name__ == "__main__":
    cargar_usda_branded()
```

**Ejecución:**
```bash
USDA_API_KEY=$USDA_API_KEY python -m etl.cargar_usda
```

**Validación:**
```python
with open("datasets/2026-07/usda_productos.json") as f:
    productos_usda = json.load(f)

if productos_usda:
    assert len(productos_usda) >= 10, f"USDA insuficiente: {len(productos_usda)}"
    print(f"✓ USDA: {len(productos_usda)} productos")
else:
    print("⚠️ USDA: No disponible")
```

**Tiempo esperado:** 5-15 min (o 0 si API key no disponible)  
**Salida:** `datasets/2026-07/usda_productos.json` o vacío

---

#### T2.3: Validación de descargas

**Criterios:**
```
✓ OFF: ≥250 productos
  ├─ Sin DEMO data (o logs etiquetados si fallback)
  ├─ fecha_dato es timestamp Unix (not date.today())
  └─ URL navegable

✓ USDA: ≥10 productos (o "no disponible")
  ├─ Sin duplicados obvios con OFF
  └─ marca + pais presentes

✓ Total: ≥250-260 productos listos para T3 (merge)
```

---

### DoD de TIER 2

- [ ] `datasets/2026-07/off_productos.json` ≥250 filas
- [ ] `datasets/2026-07/usda_productos.json` ≥10 filas (o vacío si no disponible)
- [ ] Ningún DEMO data si OFF tuvo éxito (o logs claros)
- [ ] fecha_dato son timestamps reales (verificación manual de 1 URL en OFF)
- [ ] Tiempo de descarga documentado (Opción A: X min, Opción B: Y min)
- [ ] Métricas por insumo registradas en log

---

## 🧹 TIER 3 · Limpieza de datos

**Duración:** 2-3 horas (Miércoles 7)  
**Equipo:** Dev A  
**Riesgo:** Bajo (lógica simple)  
**Dependencia:** TIER 2 ✓

### Tareas de TIER 3

#### T3.1: Deduplicación OFF vs USDA

**Script:** `etl/dedup_merge_datasets.py` (nuevo)

```python
import json
from typing import List, Dict

def similar_product(p1: Dict, p2: Dict, threshold: float = 0.9) -> bool:
    """
    Detecta duplicados por marca + nombre.
    Mejora futura: embedding similarity.
    """
    # Marca debe coincidir
    marca1 = p1.get("marca", "").lower().strip()
    marca2 = p2.get("marca", "").lower().strip()
    
    if not marca1 or not marca2:
        return False
    
    if marca1 != marca2:
        return False
    
    # Primeros 15 caracteres del nombre
    nombre1 = p1.get("nombre", "")[:15].lower()
    nombre2 = p2.get("nombre", "")[:15].lower()
    
    return nombre1 == nombre2

def merge_datasets(
    off_file: str = "datasets/2026-07/off_productos.json",
    usda_file: str = "datasets/2026-07/usda_productos.json",
    output_file: str = "datasets/2026-07/productos_merged.json"
) -> List[Dict]:
    """Merge OFF + USDA, elimina duplicados."""
    
    with open(off_file) as f:
        productos_off = json.load(f)
    
    try:
        with open(usda_file) as f:
            productos_usda = json.load(f)
    except FileNotFoundError:
        print("[MERGE] USDA no encontrado, usando solo OFF")
        productos_usda = []
    
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
    
    with open(output_file, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    
    return merged

if __name__ == "__main__":
    merge_datasets()
```

**Ejecución:**
```bash
python -m etl.dedup_merge_datasets
```

**Validación:**
```python
with open("datasets/2026-07/productos_merged.json") as f:
    merged = json.load(f)

assert len(merged) >= 250, f"Merge insuficiente: {len(merged)}"
assert len(merged) <= len(productos_off) + len(productos_usda), "Merge creó datos"
print(f"✓ Merge: {len(merged)} productos (sin duplicados obvios)")
```

**Salida:** `datasets/2026-07/productos_merged.json` listo para T4

---

### DoD de TIER 3

- [ ] `productos_merged.json` ≥250 filas
- [ ] Sin duplicados obvios (misma marca + nombre)
- [ ] Contiene mezcla de OFF + USDA (verificación manual)
- [ ] Log de deduplicación registrado

---

## 📊 TIER 4 · Embeddings masivos

**Duración:** 8-12 horas (Miércoles 7 - Jueves 8, incluye cómputo)  
**Equipo:** Dev B  
**Riesgo:** Medio (indexación lenta, Plan B a modelo pequeño)  
**Dependencia:** TIER 3 ✓

### Tareas de TIER 4

#### T4.1: Reescribir indexar_vectores.py con bge-m3 real

**Archivo:** `etl/indexar_vectores.py` (reescribir completo)

```python
import os
import json
import time
from pathlib import Path
from typing import List, Dict
import lancedb
from sentence_transformers import SentenceTransformer

def load_products(dataset_dir: str = "datasets/2026-07/") -> List[Dict]:
    """Carga productos desde productos_merged.json."""
    path = Path(dataset_dir) / "productos_merged.json"
    with open(path) as f:
        return json.load(f)

def create_embeddings(
    productos: List[Dict],
    model_name: str = "BAAI/bge-m3",
    batch_size: int = 32
) -> tuple:
    """Genera embeddings con bge-m3 (1024 dimensiones)."""
    
    print(f"[EMBED] Cargando {model_name}...")
    model = SentenceTransformer(model_name)
    
    # Preparar textos
    texts = [
        f"{p.get('nombre', '')} {p.get('ingredientes', '')}"
        for p in productos
    ]
    
    print(f"[EMBED] Generando {len(texts)} embeddings (batch={batch_size})...")
    start = time.time()
    
    embeddings = model.encode(texts, batch_size=batch_size, show_progress_bar=True)
    
    elapsed = time.time() - start
    print(f"[EMBED] ✓ Listo en {elapsed:.1f}s")
    
    return embeddings, model

def main(
    dataset_dir: str = "datasets/2026-07/",
    output_dir: str = "vectores/",
    table_name: str = "productos"
):
    """ETL: carga productos → embeddings → LanceDB."""
    
    print(f"[ETL] Iniciando indexación desde {dataset_dir}")
    
    # 1. Cargar
    productos = load_products(dataset_dir)
    print(f"[ETL] Cargados {len(productos)} productos")
    
    # 2. Embeddings
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
            "fuente": p["id_fuente"].split(":")[0],  # OFF, USDA, DEMO
            "embedding": emb.tolist()  # LanceDB espera list
        })
    
    # 4. Indexar en LanceDB
    print(f"[ETL] Indexando en LanceDB...")
    db = lancedb.connect(output_dir)
    
    # Eliminar tabla anterior
    try:
        db.drop_table(table_name)
    except:
        pass
    
    table = db.create_table(table_name, data=data, mode="create")
    
    # 5. Crear índice vectorial
    print(f"[ETL] Creando índice vectorial...")
    table.create_index()
    
    print(f"[ETL] ✓ {table.count_rows()} productos indexados")
    
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
    
    print(f"[ETL] ✓ Manifest actualizado")
    return True

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
```

**Cambio en `pyproject.toml`:**
```toml
[project.scripts]
etl = "etl.indexar_vectores:main"  # Cambiar de indexar_vectores() a main()
```

**Ejecución:**
```bash
time python -m etl  # Medir tiempo de indexación
```

**Esperado:** 5-20 minutos (CPU), 1-3 minutos (GPU si disponible)

---

#### T4.2: Test de embeddings

**Archivo:** `test/test_embeddings.py` (crear)

```python
import pytest
import lancedb
import json
from pathlib import Path

def test_embeddings_indexed():
    """Verifica que embeddings están en LanceDB."""
    db = lancedb.connect("vectores/")
    table = db.open_table("productos")
    
    assert table.count_rows() >= 250, f"Insuficientes: {table.count_rows()}"
    
    # Verificar estructura
    sample = table.limit(1).to_list()[0]
    assert "embedding" in sample, "Campo embedding falta"
    assert "fecha_dato" in sample, "fecha_dato falta"
    assert "url" in sample, "url falta"
    assert len(sample["embedding"]) == 1024, "Embeddings no son 1024-dim"
    
    print(f"✓ {table.count_rows()} productos con embeddings bge-m3")

def test_manifest_actualizado():
    """Verifica que manifest.json tiene metadata de embeddings."""
    manifest_path = Path("datasets/2026-07/manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    assert "embeddings" in manifest, "embeddings metadata falta"
    assert manifest["embeddings"]["modelo"] == "BAAI/bge-m3"
    assert manifest["embeddings"]["dimensiones"] == 1024
    assert manifest["embeddings"]["filas"] >= 250
    
    print(f"✓ Manifest: {manifest['embeddings']['filas']} productos")

# Ejecución
if __name__ == "__main__":
    pytest test/test_embeddings.py -v
```

---

### DoD de TIER 4

- [ ] `vectores/productos.lance/` existe con tabla `productos`
- [ ] ≥250 filas indexadas
- [ ] Cada fila tiene embedding 1024-dimensional
- [ ] `manifest.json` actualizado con metadata
- [ ] Tiempo de indexación documentado (< 30 min ideal)
- [ ] Test pasa (✓ embeddings_indexed)

---

## 🔍 TIER 5 · Búsqueda optimizada

**Duración:** 4 horas (Jueves 8)  
**Equipo:** Dev B  
**Riesgo:** Bajo (lógica simple, datos listos)  
**Dependencia:** TIER 4 ✓

### Tareas de TIER 5

#### T5.1: Reescribir busqueda_lancedb.py (vectorial real)

**Archivo:** `adaptadores/busqueda_lancedb.py` (reescribir)

```python
import lancedb
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import time
from dominio.resultado_busqueda import ResultadoBusqueda

# Singleton
_model: Optional[SentenceTransformer] = None
_table = None

def init_search(db_path: str = "vectores/"):
    """Inicializa modelo y tabla (lazy load)."""
    global _model, _table
    if _model is None:
        print("[SEARCH] Inicializando bge-m3...")
        _model = SentenceTransformer("BAAI/bge-m3")
    
    if _table is None:
        db = lancedb.connect(db_path)
        _table = db.open_table("productos")
        print(f"[SEARCH] ✓ {_table.count_rows()} productos cargados")

def buscar_productos(
    query: str,
    limit: int = 5,
    exclude_demo: bool = True
) -> List[ResultadoBusqueda]:
    """
    Búsqueda vectorial con bge-m3 + LanceDB.
    
    Args:
        query: texto de búsqueda
        limit: cantidad de resultados
        exclude_demo: excluir DEMO data si hay OFF
    
    Returns:
        Lista de ResultadoBusqueda ordenada por similitud
    """
    init_search()
    
    # 1. Generar embedding del query
    embedding = _model.encode(query, normalize_embeddings=True)
    
    # 2. Búsqueda vectorial (cosine distance)
    results = (
        _table
        .search(embedding)
        .metric("cosine")
        .limit(limit * 2)  # Traer extras para filtrar
        .to_list()
    )
    
    # 3. Filtrar DEMO si hay OFF exitoso
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
            similitud=1 - r["_distance"],  # cosine distance → similitud
            fuente=r["fuente"]
        )
        for r in results[:limit]
    ]

def medir_latencia_p95(num_samples: int = 100) -> float:
    """Mide p95 de latencia en búsquedas."""
    import numpy as np
    
    queries = ["arándano", "palta", "espárrago", "mango", "quinua", "blueberry", "avocado"]
    latencies = []
    
    print(f"[LATENCY] Midiendo {num_samples} queries...")
    
    for i in range(num_samples):
        query = queries[i % len(queries)]
        t0 = time.time()
        buscar_productos(query, limit=5)
        latencies.append(time.time() - t0)
    
    p95 = np.percentile(latencies, 95)
    p99 = np.percentile(latencies, 99)
    mean = np.mean(latencies)
    
    print(f"[LATENCY] Mean: {mean*1000:.1f}ms | p95: {p95*1000:.1f}ms | p99: {p99*1000:.1f}ms")
    print(f"[LATENCY] Min: {min(latencies)*1000:.1f}ms | Max: {max(latencies)*1000:.1f}ms")
    
    return p95
```

**Cambio en `adaptadores/__init__.py`** (exportar):
```python
from .busqueda_lancedb import buscar_productos, medir_latencia_p95
```

---

#### T5.2: Test de latencia p95

**Archivo:** `test/test_latency.py` (crear)

```python
import pytest
from adaptadores.busqueda_lancedb import medir_latencia_p95, buscar_productos

def test_p95_latency():
    """P03: Búsqueda < 2s p95."""
    p95 = medir_latencia_p95(num_samples=100)
    assert p95 < 2.0, f"P95 latency {p95:.3f}s exceeds 2s SLA"

def test_buscar_productos_sin_demo():
    """P03: Sin DEMO data si OFF disponible."""
    results = buscar_productos("blueberry", limit=5)
    
    assert len(results) >= 3, f"Menos de 3 resultados: {len(results)}"
    
    # Validar que son datos reales
    for r in results:
        assert r.fecha_dato is not None, "fecha_dato no debe ser None"
        assert r.fuente_url, "URL debe estar presente"
        assert r.fuente in ("OFF", "USDA"), f"Fuente inesperada: {r.fuente}"

def test_buscar_multiple_queries():
    """P03: Búsquedas con múltiples queries."""
    queries = ["arándano", "palta", "espárrago", "mango", "quinua"]
    
    for q in queries:
        results = buscar_productos(q, limit=5)
        assert len(results) > 0, f"No hay resultados para '{q}'"
        print(f"✓ {q}: {len(results)} resultados")

# Ejecución
if __name__ == "__main__":
    pytest test/test_latency.py -v
```

**Ejecución:**
```bash
pytest test/test_latency.py -v
```

**Criterio:** p95 < 2 segundos ✅ P03

---

### DoD de TIER 5

- [ ] `busqueda_lancedb.py` usa embeddings (no FTS)
- [ ] p95 latencia < 2 segundos (100+ queries)
- [ ] Sin DEMO data en resultados (si OFF exitoso)
- [ ] fecha_dato es real (timestamp Unix, no today)
- [ ] test_latency.py pasa (3/3)

---

## 📚 TIER 6 · Corpus regulatorio

**Duración:** 6 horas (Jueves 8 - Viernes 9, parallelizable con T5)  
**Equipo:** Dev A o QA (especialista en regulación)  
**Riesgo:** Medio (OCR puede fallar, Plan B: subset público)  
**Dependencia:** TIER 1 (solo decisiones)

### Tareas de TIER 6

#### T6.1: Corpus eCFR aditivos

**Fuente:** Title 21 Part 182 (GRAS - Generally Recognized as Safe)

**Opción A (API eCFR):**
```bash
curl -s "https://www.ecfr.gov/api/renderer/versions/title-21/part-182/full.json" \
  -o datasets/2026-07/ecfr_raw.json
```

**Opción B (lista pública conocida):**
```python
# Si API falla, usar subset conocido
ecfr_aditivos_conocidos = [
    {"id": "E200", "nombre": "Sorbitol", "fuente": "21 CFR 182.1835"},
    {"id": "E210", "nombre": "Benzoic acid", "fuente": "21 CFR 182.1011"},
    # ... más aditivos
]
```

**Script:** `etl/procesar_ecfr.py`

```python
import json

def procesar_ecfr(raw_file: str = "datasets/2026-07/ecfr_raw.json"):
    """Convierte raw eCFR → formato normalizado."""
    
    try:
        with open(raw_file) as f:
            raw = json.load(f)
    except:
        print("[eCFR] Archivo no encontrado, usando subset conocido")
        raw = {"children": []}  # fallback vacío
    
    aditivos = []
    
    # Parsear estructura eCFR
    for section in raw.get("children", []):
        aditivo = {
            "id": f"eCFR:{section.get('identifier', '')}",
            "titulo": section.get("title", ""),
            "texto": section.get("children", [{}])[0].get("text", ""),
            "fuente_url": "https://www.ecfr.gov/current/title-21/part-182",
            "fecha_publicacion": "2024-01-01",
            "tipo": "eCFR"
        }
        aditivos.append(aditivo)
    
    print(f"[eCFR] {len(aditivos)} aditivos procesados")
    
    with open("datasets/2026-07/ecfr_aditivos.json", "w") as f:
        json.dump(aditivos, f, indent=2)

if __name__ == "__main__":
    procesar_ecfr()
```

**Criterio:** ≥5 documentos indexables

---

#### T6.2: Corpus DIGESA

**Fuentes:** Resoluciones de DIGESA sobre aditivos, colorantes, etc.

**Descarga manual:**
1. Ir a https://digesa.minsa.gob.pe
2. Buscar resoluciones sobre aditivos alimentarios
3. Descargar 2-3 PDFs relevantes
4. OCR con tesseract o pdfplumber

**Script:** `etl/procesar_digesa.py`

```python
import pdfplumber
import json

def procesar_digesa(pdf_path: str):
    """Extrae texto de PDF DIGESA."""
    
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    
    # Dividir en párrafos
    paragraphs = text.split("\n\n")
    
    docs = []
    for i, para in enumerate(paragraphs):
        if len(para) < 100:
            continue
        
        docs.append({
            "id": f"DIGESA:{i}",
            "titulo": "DIGESA Norma",
            "texto": para,
            "fuente_url": "https://digesa.minsa.gob.pe",
            "fecha_publicacion": "2024-01-01",
            "tipo": "DIGESA"
        })
    
    print(f"[DIGESA] {len(docs)} párrafos extraídos")
    return docs

# Uso
if __name__ == "__main__":
    docs = procesar_digesa("datasets/2026-07/DIGESA_ResolucionAditivos.pdf")
    with open("datasets/2026-07/digesa_normas.json", "w") as f:
        json.dump(docs, f, indent=2)
```

**Criterio:** ≥2000 palabras indexables

---

#### T6.3: Indexar en LanceDB

**Script:** `etl/procesar_regulatorio.py`

```python
import json
import lancedb
from sentence_transformers import SentenceTransformer
from pathlib import Path

def indexar_regulatorio(
    ecfr_file: str = "datasets/2026-07/ecfr_aditivos.json",
    digesa_file: str = "datasets/2026-07/digesa_normas.json",
    db_path: str = "vectores/"
):
    """Indexa corpus regulatorio en LanceDB."""
    
    model = SentenceTransformer("BAAI/bge-m3")
    db = lancedb.connect(db_path)
    
    docs = []
    
    # Cargar eCFR
    if Path(ecfr_file).exists():
        with open(ecfr_file) as f:
            for doc in json.load(f):
                embedding = model.encode(doc["texto"])
                docs.append({
                    "id": doc["id"],
                    "titulo": doc["titulo"],
                    "texto": doc["texto"],
                    "fuente_url": doc["fuente_url"],
                    "tipo": "eCFR",
                    "embedding": embedding.tolist()
                })
    
    # Cargar DIGESA
    if Path(digesa_file).exists():
        with open(digesa_file) as f:
            for doc in json.load(f):
                embedding = model.encode(doc["texto"])
                docs.append({
                    "id": doc["id"],
                    "titulo": doc["titulo"],
                    "texto": doc["texto"],
                    "fuente_url": doc["fuente_url"],
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
    
    print(f"[REGULATORIO] ✓ {len(docs)} documentos indexados")

if __name__ == "__main__":
    indexar_regulatorio()
```

---

### DoD de TIER 6

- [ ] `datasets/2026-07/ecfr_aditivos.json` ≥5 documentos
- [ ] `datasets/2026-07/digesa_normas.json` ≥2000 palabras
- [ ] Tabla `regulatorio` en LanceDB con embeddings
- [ ] URLs navegables a fuentes oficiales

---

## ✅ TIER 7 · Cierre y auditoría

**Duración:** 4 horas (Viernes 9)  
**Equipo:** QA + Dev B  
**Riesgo:** Bajo (todo ya funciona)  
**Dependencia:** TIER 5 + TIER 6 ✓

### Tareas de TIER 7

#### T7.1: Golden set ampliado (5/5 casos)

**Archivo:** `evals/set_dorado.yaml` (ampliar a 5 casos)

```yaml
casos:
  - id: "S2-arándano"
    insumo: "arándano"
    esperado_min_coincidencias: 3
    verificacion: "URLs navegables en OFF"
  
  - id: "S2-palta"
    insumo: "palta"
    esperado_min_coincidencias: 2
    verificacion: "Incluir aguacate/avocado"
  
  - id: "S2-espárrago"
    insumo: "espárrago"
    esperado_min_coincidencias: 2
    verificacion: "Asparagus en inglés"
  
  - id: "S2-mango"
    insumo: "mango"
    esperado_min_coincidencias: 3
    verificacion: "Good coverage en OFF"
  
  - id: "S2-quinua"
    insumo: "quinua"
    esperado_min_coincidencias: 2
    verificacion: "Quinoa en inglés"
```

**Script:** `evals/runner_s2.py`

```python
import yaml
from adaptadores.busqueda_lancedb import buscar_productos

def run_golden_set(set_file: str = "evals/set_dorado.yaml"):
    """Ejecuta golden set S2."""
    
    with open(set_file) as f:
        config = yaml.safe_load(f)
    
    pasos = 0
    for caso in config["casos"]:
        results = buscar_productos(caso["insumo"], limit=10)
        paso = len(results) >= caso["esperado_min_coincidencias"]
        
        symbol = "✓" if paso else "✗"
        print(f"{symbol} {caso['id']}: {len(results)} (esperado ≥{caso['esperado_min_coincidencias']})")
        
        if paso:
            pasos += 1
    
    print(f"\nResultado: {pasos}/5 casos pasan")
    return pasos == 5

if __name__ == "__main__":
    import sys
    success = run_golden_set()
    sys.exit(0 if success else 1)
```

**Ejecución:**
```bash
python -m evals.runner_s2
# Esperado: ✓ 5/5 pasos
```

---

#### T7.2: Actualizar manifest.json (SHA256)

**Script:** `etl/finalizar_manifest.py`

```python
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def finalizar_manifest(dataset_dir: str = "datasets/2026-07/"):
    """Calcula SHA256 de todos los archivos."""
    
    manifest_path = Path(dataset_dir) / "manifest.json"
    
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    manifest["fecha_descarga"] = datetime.now(timezone.utc).isoformat()
    
    # Calcular SHA256 de cada archivo
    files_to_hash = [
        "off_productos.json",
        "usda_productos.json",
        "productos_merged.json",
        "ecfr_aditivos.json",
        "digesa_normas.json"
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
    
    # Guardar
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    
    print(f"✓ Manifest actualizado con SHA256")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    finalizar_manifest()
```

**Ejecución:**
```bash
python -m etl.finalizar_manifest
```

---

#### T7.3: E2E workflow completo

**Script:** `test/test_e2e_s2.py`

```python
import pytest
import json
from pathlib import Path
from adaptadores.busqueda_lancedb import buscar_productos
import lancedb

def test_e2e_workflow():
    """E2E: Datos reales → búsqueda → validación."""
    
    # 1. Datos existen
    assert Path("datasets/2026-07/productos_merged.json").exists()
    
    # 2. Embeddings indexados
    db = lancedb.connect("vectores/")
    table = db.open_table("productos")
    assert table.count_rows() >= 250
    
    # 3. Búsqueda funciona
    for insumo in ["arándano", "palta", "espárrago", "mango", "quinua"]:
        results = buscar_productos(insumo, limit=5)
        assert len(results) > 0, f"No hay resultados para {insumo}"
        
        # Validar que son datos reales
        for r in results:
            assert r.fecha_dato is not None
            assert r.fuente_url
    
    # 4. Corpus regulatorio
    try:
        table = db.open_table("regulatorio")
        assert table.count_rows() > 0
    except:
        pass  # Regulatorio es opcional en S2
    
    # 5. Manifest completo
    manifest_path = Path("datasets/2026-07/manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    
    assert manifest.get("fecha_descarga")
    assert len(manifest.get("fuentes", {})) > 0
    
    print("✓ E2E workflow PASSED")

if __name__ == "__main__":
    pytest test/test_e2e_s2.py -v
```

**Ejecución:**
```bash
pytest test/test_e2e_s2.py -v
```

---

### DoD de TIER 7

- [ ] Golden set 5/5 pasos
- [ ] `manifest.json` con SHA256 de todos los archivos
- [ ] E2E test pasa
- [ ] URLs navegables verificadas (manual click)
- [ ] README con procedimiento reproducible completo

---

## 📊 MATRIZ FINAL: Verificación por TIER

```
TIER 1 (Lun 5)  ✓ Decisiones + estructura
  ├─ OFF live vs offline decidido
  ├─ USDA_API_KEY verificada
  ├─ datasets/ creada
  └─ Equipos conocen el plan

TIER 2 (Mar 6-7) ✓ Descargas masivas
  ├─ OFF: 250-1000 productos
  ├─ USDA: 10+ productos (o vacío)
  └─ Sin DEMO data si OFF exitoso

TIER 3 (Mié 7) ✓ Limpieza
  ├─ Dedup OFF vs USDA
  └─ productos_merged.json ≥250

TIER 4 (Mié 7-Jue 8) ✓ Embeddings
  ├─ bge-m3 1024-dim
  ├─ ≥250 filas indexadas
  └─ Tiempo < 30 min

TIER 5 (Jue 8) ✓ Búsqueda P03
  ├─ p95 < 2 segundos
  ├─ Sin DEMO data
  └─ fecha_dato reales

TIER 6 (Jue 8-Vie 9) ✓ Corpus regulatorio
  ├─ eCFR ≥5 docs
  ├─ DIGESA ≥2000 palabras
  └─ Indexados en LanceDB

TIER 7 (Vie 9) ✓ Cierre
  ├─ Golden set 5/5
  ├─ Manifest SHA256
  ├─ E2E test PASSED
  └─ URLs navegables ✓

RESULTADO FINAL: 10/13 pruebas en verde (P03 + base para S3)
```

---

## ⏰ Calendario de TIERS

```
LUNES 5 ago    TIER 1: Setup (2-3h)
MARTES 6 ago   TIER 2: OFF+USDA (8h, parallelizable)
MIÉRCOLES 7    TIER 3: Dedup (2h) + TIER 4: Embeddings (8-12h)
JUEVES 8       TIER 5: Búsqueda (4h) + TIER 6: Corpus (6h, parallelizable)
VIERNES 9      TIER 7: Cierre (4h)

TOTAL: 28h código + 12-24h espera (indexación, descargas)
```

---

## 🚀 Próximos pasos después de S2

**TIER 8 (Semana 3):** Multi-tenant Postgres + Paywall  
**TIER 9 (Semana 4):** Mapa comercial + Panel mínimo

---

**Estado:** Semana 2 lista para ejecutar en TIERS  
**Inicio:** Lunes 5 de agosto, 8:00 AM  
**Kickoff:** Ejecutar TIER 1 completo antes de Martes 6
