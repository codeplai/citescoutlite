# TIER 4: Embeddings Masivos con bge-m3

Guía para ejecutar la generación de embeddings (28,236 productos) en otra computadora.

---

## 🚀 QUICK START (Salta los detalles)

```cmd
# 1. Copiar proyecto a máquina con GPU 8GB
# 2. Abrir PowerShell en carpeta mvp
# 3. Ejecutar:

python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers lancedb numpy
python etl/tier4_gpu.py

# ✅ LISTO. ETA: 15-30 minutos
```

---

## 🎯 CONFIGURACIÓN DE TU MÁQUINA (OPTIMIZADA PARA GPU)

**Especificaciones disponibles:**
- ✅ GPU: 8GB VRAM (NVIDIA)
- ✅ RAM: 64GB (excelente)
- ✅ OS: Windows
- ✅ **ETA: 15-30 minutos** (vs 2-3 horas en CPU)

---

## 1. Requisitos de Sistema

### Para TU máquina (GPU NVIDIA 8GB):
- **GPU**: NVIDIA (RTX/GTX/Tesla) con 8GB VRAM ✅
- **CUDA**: 11.8 o 12.x
- **cuDNN**: 8.6+
- **RAM**: 64GB ✅
- **Disco**: 10GB libres
- **Python**: 3.9+
- **Windows**: 10/11 Pro o similar

### Verificar GPU instalada:
```cmd
# Windows CMD
nvidia-smi
# Debe mostrar: NVIDIA-SMI + versión CUDA + modelo GPU + 8GB VRAM
```

---

## 2. Configurar el Ambiente (WINDOWS + GPU NVIDIA)

### Paso 1: Verificar NVIDIA CUDA (CRÍTICO)

En Windows CMD o PowerShell:
```cmd
# Verificar que nvidia-smi funciona
nvidia-smi

# Salida esperada:
# NVIDIA-SMI 555.00    Driver Version: 555.00    CUDA Version: 12.5
# GPU: NVIDIA GeForce RTX 3060 (8192 MB) | Otros modelos
```

**Si `nvidia-smi` NO funciona:**
- Descargar NVIDIA Driver: https://www.nvidia.com/Download/driverDetails.aspx
- Instalar CUDA Toolkit 12.1: https://developer.nvidia.com/cuda-12-1-0-download-archive
- Instalar cuDNN: https://developer.nvidia.com/cudnn-downloads

### Paso 2: Clonar/copiar el proyecto
```cmd
# Windows CMD o PowerShell
git clone <repo-url>
cd mvp

# O simplemente copiar el directorio existente
```

### Paso 3: Crear ambiente virtual (WINDOWS)
```cmd
# PowerShell o CMD
python -m venv venv
venv\Scripts\activate

# Debe aparecer (venv) al inicio de la línea
```

### Paso 4: Instalar dependencias OPTIMIZADAS PARA GPU

```cmd
# Actualizar pip
python -m pip install --upgrade pip

# Instalar PyTorch con CUDA 12.1 (RECOMENDADO para GPU 8GB)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Instalar dependencias específicas
pip install sentence-transformers lancedb numpy

# Verificar que PyTorch usa GPU
python << 'EOF'
import torch
print(f"CUDA disponible: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No detectada'}")
print(f"Memoria GPU: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
EOF

# Esperado:
# CUDA disponible: True
# GPU: NVIDIA GeForce RTX XXXX (o similar)
# Memoria GPU: 8.0 GB
```

### Paso 5: Verificar archivos de entrada
```cmd
# Debe existir:
dir datasets\2026-07\productos_merged.json

# Debe tener ~28,236 productos
# Tamaño típico: 15-20MB
```

---

## 3. Ejecutar TIER 4 (Embeddings)

### ⚡ Opción A: Script GPU-OPTIMIZADO (RECOMENDADO PARA TI)

Crear archivo `etl/tier4_gpu.py` (copiado abajo) y ejecutar:

```cmd
# Windows PowerShell o CMD (venv activado)
python etl/tier4_gpu.py
```

**¿Qué hace?**
- Detecta GPU automáticamente
- Carga 28,236 productos desde `datasets/2026-07/productos_merged.json`
- Descarga modelo BAAI/bge-m3 (primera ejecución: ~500MB, se cachea)
- Genera embeddings de 1024 dimensiones en **batch_size=128** (GPU optimizado)
- **ETA: 15-30 minutos en GPU 8GB**
- Indexa en LanceDB
- Actualiza manifest.json

**Script GPU-optimizado (`etl/tier4_gpu.py`):**
```python
"""
TIER 4 GPU-optimizado: Embeddings con NVIDIA CUDA
ETA: 15-30 min en GPU 8GB
"""
import json
import time
import sys
import torch
from pathlib import Path
from datetime import datetime

try:
    import lancedb
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError as e:
    print(f"ERROR: {e}", file=sys.stderr, flush=True)
    sys.exit(1)


def log(msg):
    ts = datetime.now().isoformat()
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


log("="*70)
log("TIER 4: Embeddings GPU-optimizado (NVIDIA CUDA)")
log("="*70)

# Detectar GPU
if torch.cuda.is_available():
    device = "cuda"
    gpu_name = torch.cuda.get_device_name(0)
    gpu_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
    log(f"[GPU] Detectada: {gpu_name} ({gpu_mem:.1f}GB)")
else:
    device = "cpu"
    log("[GPU] NO DETECTADA - usando CPU (LENTO)")

# LOAD
log("[LOAD] Leyendo 28236 productos...")
try:
    with open("datasets/2026-07/productos_merged.json") as f:
        productos = json.load(f)
    log(f"[LOAD] OK: {len(productos)} productos")
except Exception as e:
    log(f"[ERROR] LOAD: {e}")
    sys.exit(1)

# MODEL
log(f"[MODEL] Cargando bge-m3 en {device.upper()}...")
start_model = time.time()
try:
    model = SentenceTransformer("BAAI/bge-m3", device=device)
    log(f"[MODEL] OK en {time.time()-start_model:.0f}s")
except Exception as e:
    log(f"[ERROR] MODEL: {e}")
    sys.exit(1)

# EMBED
batch_size = 128 if device == "cuda" else 4
log(f"[EMBED] Generando 28236 embeddings (batch_size={batch_size})...")
start_emb = time.time()
try:
    texts = [f"{p.get('nombre','')} {p.get('ingredientes','')}" for p in productos]

    embeddings_list = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embs = model.encode(batch, batch_size=batch_size, show_progress_bar=False)
        embeddings_list.extend(batch_embs)

        # Log cada 2000 productos (GPU) o 500 (CPU)
        log_interval = 2000 if device == "cuda" else 500
        if (i + batch_size) % log_interval == 0:
            elapsed = time.time() - start_emb
            rate = (i + batch_size) / elapsed
            pct = 100 * (i + batch_size) // len(texts)
            log(f"[EMBED] {i+batch_size}/{len(texts)} ({pct}%) - {rate:.1f} prod/s")

    embeddings = np.array(embeddings_list)
    elapsed_emb = time.time() - start_emb
    log(f"[EMBED] OK en {elapsed_emb:.0f}s ({len(productos)/elapsed_emb:.1f} prod/s)")
except Exception as e:
    log(f"[ERROR] EMBED: {e}")
    sys.exit(1)

# DATA
log("[DATA] Preparando registros...")
try:
    data = []
    for p, emb in zip(productos, embeddings):
        data.append({
            "id": p["id_fuente"],
            "nombre": p["nombre"],
            "categoria": p.get("categoria",""),
            "ingredientes": p.get("ingredientes",""),
            "url": p.get("url",""),
            "fecha_dato": p.get("fecha_dato"),
            "marca": p.get("marca",""),
            "pais": p.get("pais",""),
            "fuente": p["id_fuente"].split(":")[0],
            "embedding": emb.tolist()
        })
    log(f"[DATA] OK: {len(data)} registros")
except Exception as e:
    log(f"[ERROR] DATA: {e}")
    sys.exit(1)

# INDEX
log("[INDEX] Indexando en LanceDB...")
start_idx = time.time()
try:
    db = lancedb.connect("vectores")
    try:
        db.drop_table("productos")
    except:
        pass

    table = db.create_table("productos", data=data, mode="create")
    table.create_index()
    count = table.count_rows()
    log(f"[INDEX] OK en {time.time()-start_idx:.0f}s: {count} filas")
except Exception as e:
    log(f"[ERROR] INDEX: {e}")
    sys.exit(1)

# MANIFEST
log("[MANIFEST] Actualizando...")
try:
    with open("datasets/2026-07/manifest.json") as f:
        manifest = json.load(f)

    manifest["embeddings"] = {
        "modelo": "BAAI/bge-m3",
        "dimensiones": 1024,
        "filas": len(productos),
        "dispositivo": device.upper(),
        "batch_size": batch_size,
        "timestamp": datetime.now().isoformat()
    }

    with open("datasets/2026-07/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2, default=str)

    log("[MANIFEST] OK")
except Exception as e:
    log(f"[WARN] MANIFEST: {e}")

log("[SUCCESS] TIER 4 COMPLETADO (GPU)")
log("="*70)
sys.exit(0)
```

**Salida esperada:**
```
[2026-07-30T21:23:17] ======================================================================
[2026-07-30T21:23:17] TIER 4: Embeddings CPU-optimizado
[2026-07-30T21:23:17] ======================================================================
[2026-07-30T21:23:18] [LOAD] Leyendo 28236 productos...
[2026-07-30T21:23:18] [LOAD] OK: 28236 productos
[2026-07-30T21:23:19] [MODEL] Cargando bge-m3...
[2026-07-30T21:23:35] [MODEL] OK en 16s
[2026-07-30T21:23:35] [EMBED] Generando 28236 embeddings...
[2026-07-30T21:25:35] [EMBED] 500/28236 (2%) - 4.2 prod/s
[2026-07-30T21:27:35] [EMBED] 1000/28236 (4%) - 4.1 prod/s
...
[2026-07-XX:XX:XX] [EMBED] OK en XXXX s (5.2 prod/s)
[2026-07-XX:XX:XX] [DATA] Preparando registros...
[2026-07-XX:XX:XX] [DATA] OK: 28236 registros
[2026-07-XX:XX:XX] [INDEX] Indexando en LanceDB...
[2026-07-XX:XX:XX] [INDEX] OK en XXs: 28236 filas
[2026-07-XX:XX:XX] [MANIFEST] Actualizando...
[2026-07-XX:XX:XX] [MANIFEST] OK
[2026-07-XX:XX:XX] [SUCCESS] TIER 4 COMPLETADO
```

### Opción B: En Background (RECOMENDADO para TI - Windows)

```powershell
# Windows PowerShell (venv activado)
# Ejecutar en background y monitorear

$process = Start-Process `
  -FilePath python `
  -ArgumentList "etl/tier4_gpu.py" `
  -RedirectStandardOutput "datasets/2026-07/embeddings.log" `
  -RedirectStandardError "datasets/2026-07/embeddings_error.log" `
  -WindowStyle Hidden `
  -PassThru

Write-Host "Proceso iniciado: $($process.Id)"
Write-Host "GPU: NVIDIA (8GB VRAM)"
Write-Host "ETA: 15-30 minutos"
Write-Host ""
Write-Host "Monitoreo en vivo:"

# Monitorear cada 10 segundos
while ($true) {
    $lastLine = @(Get-Content "datasets/2026-07/embeddings.log" -Tail 1)
    Write-Host "$(Get-Date -Format 'HH:mm:ss'): $lastLine"
    
    if ($lastLine -match "SUCCESS|ERROR") { 
        Write-Host ""
        Write-Host "COMPLETADO: Ver datasets/2026-07/embeddings.log"
        break 
    }
    Start-Sleep -Seconds 10
}
```

### Opción C: Monitoreo en otra terminal (Windows)

Terminal 1 (ejecutar TIER 4):
```cmd
python etl/tier4_gpu.py
```

Terminal 2 (monitoreo en vivo):
```powershell
Get-Content "datasets/2026-07/embeddings.log" -Tail 20 -Wait
```

---

## 4. Estimación de Tiempo

### 🚀 TU CONFIGURACIÓN (GPU 8GB + 64GB RAM):
```
TIEMPO ESTIMADO: 15-30 MINUTOS
```

### Desglose de tiempos:
```
- Cargar modelo bge-m3:     ~20s
- Generar 28,236 embeddings: ~8-15 min (100-200 prod/s)
- Indexar en LanceDB:       ~3-5 min
- Actualizar manifest:      ~5s
────────────────────────────
TOTAL:                       ~12-25 minutos
```

### Comparativa por dispositivo:
```
GPU NVIDIA RTX 3090:   5-8 min
GPU NVIDIA RTX 4090:   3-5 min
GPU NVIDIA RTX 3060 (8GB): 15-20 min ← TU CASO
GPU NVIDIA RTX 3060 Ti:    8-12 min
GPU NVIDIA A100:           2-3 min

CPU Intel i9 16 cores: 2-3 horas
CPU Intel i7 8 cores:  3-5 horas
CPU AMD Ryzen 9:       2-3 horas
```

### Cálculo exacto:
```
28,236 productos / ~100-200 prod/s (GPU 8GB) = ~15-30 min
28,236 productos / ~4-5 prod/s (CPU) = ~2-3 horas
AHORRO DE TIEMPO: 90-95% más rápido con GPU
```

---

## 5. Monitorear Progreso

### Ver log completo:
```bash
cat datasets/2026-07/embeddings.log
```

### Ver últimas líneas (actualizar):
```bash
tail -20 datasets/2026-07/embeddings.log

# O en Windows PowerShell:
Get-Content "datasets/2026-07/embeddings.log" -Tail 20
```

### Ver progreso en vivo:
```bash
# Linux/Mac
tail -f datasets/2026-07/embeddings.log

# Windows PowerShell
Get-Content "datasets/2026-07/embeddings.log" -Tail 20 -Wait
```

---

## 6. Verificar Resultado

Una vez completado, verificar:

```bash
# 1. Log indica SUCCESS
tail -5 datasets/2026-07/embeddings.log
# Esperado: [SUCCESS] TIER 4 COMPLETADO

# 2. Archivo LanceDB existe
ls -lh vectores/productos.lance/
# Esperado: directorio con _versions/, data/, _transactions/

# 3. Manifest actualizado
cat datasets/2026-07/manifest.json | grep -A 5 embeddings
# Esperado: modelo, dimensiones: 1024, filas: 28236, timestamp

# 4. Test rápido (Python)
python << 'EOF'
import lancedb
db = lancedb.connect("vectores/")
table = db.open_table("productos")
print(f"Productos indexados: {table.count_rows()}")
# Esperado: 28236
EOF
```

---

## 7. Troubleshooting GPU + Windows

### Error: "CUDA is not available" o GPU no detectada
```cmd
# Verificar driver NVIDIA
nvidia-smi

# Soluciones:
1. Actualizar NVIDIA Driver: https://www.nvidia.com/Download/index.aspx
2. Instalar CUDA Toolkit 12.1: https://developer.nvidia.com/cuda-12-1-0-download-archive
3. Instalar cuDNN: https://developer.nvidia.com/cudnn-downloads
4. Reiniciar máquina después de instalar CUDA
5. Verificar nuevamente: nvidia-smi
```

### Error: "not enough memory" en GPU
```cmd
# Si la GPU tiene solo 8GB:
# Editar tier4_gpu.py línea ~80:
# batch_size = 64  # (cambiar de 128 a 64)

# O reducir aún más:
# batch_size = 32  (aún muy rápido: ~20-30 min)
```

### Error: "module 'sentence_transformers' not found"
```cmd
# En venv activado:
pip install sentence-transformers --upgrade
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Error: "lancedb connection failed"
```cmd
# Crear directorio:
mkdir vectores

# Verificar permisos de escritura
dir vectores
```

### Proceso es lento en GPU (< 50 prod/s)
```cmd
# Verificar que realmente use GPU:
python << 'EOF'
import torch
print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"Memoria: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
EOF

# Si muestra GPU correcta pero es lento:
# - Cerrar aplicaciones que usen GPU (videojuegos, Blender, etc.)
# - Verificar que batch_size=128 en tier4_gpu.py
```

### "OutOfMemoryError" en GPU 8GB
```cmd
# Reducir batch_size en tier4_gpu.py:
batch_size = 64  # (línea ~80)
# Seguirá siendo rápido: 20-30 min en lugar de 15-20 min
```

---

## 8. Después de Completar TIER 4 ✅

Una vez que veas `[SUCCESS] TIER 4 COMPLETADO`:

```cmd
# Windows CMD o PowerShell

# 1. Guardar log como referencia
copy datasets\2026-07\embeddings.log datasets\2026-07\embeddings_backup.log

# 2. Verificar manifest.json
type datasets\2026-07\manifest.json

# 3. Ver estadísticas finales
echo "Búsquedas indexadas:"
dir /s vectores\productos.lance\

# 4. Commit en git
git add datasets\2026-07\manifest.json "vectores\productos.lance\*"
git commit -m "TIER 4: Embeddings GPU (28236 productos, bge-m3 1024-dim, 15-30min)"
git push

# 5. Próximo paso: TIER 5
# Ver PLAN-TIERS-S2.md para búsqueda + latencia p95
```

**Manifest.json esperado:**
```json
{
  "embeddings": {
    "modelo": "BAAI/bge-m3",
    "dimensiones": 1024,
    "filas": 28236,
    "dispositivo": "CUDA",
    "batch_size": 128,
    "timestamp": "2026-07-30T21:XX:XXXX"
  }
}
```

---

## 9. Checklist Pre-Ejecución

- [ ] Python 3.9+ instalado: `python --version`
- [ ] Ambiente virtual creado y activado
- [ ] Dependencias instaladas: `pip list | grep -E "sentence|lancedb|torch"`
- [ ] Archivo de entrada existe: `datasets/2026-07/productos_merged.json`
- [ ] RAM disponible: `free -h` o Task Manager
- [ ] Disco libre: `df -h .` (mínimo 10GB)
- [ ] Directorio `vectores/` accesible
- [ ] Permisos de escritura en `datasets/` y `vectores/`

---

## 10. Script de Instalación Automática

Para automatizar todo (Linux/Mac/Windows):

```bash
#!/bin/bash
# setup_tier4.sh

echo "Configurando TIER 4..."

# 1. Ambiente virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# 2. Dependencias
pip install --upgrade pip
pip install sentence-transformers lancedb numpy torch

# 3. Crear directorio de salida
mkdir -p vectores
mkdir -p datasets/2026-07

# 4. Ejecutar TIER 4
echo "Iniciando TIER 4..."
python etl/tier4_cpu.py

echo "TIER 4 completado. Verifica datasets/2026-07/embeddings.log"
```

Guardar como `setup_tier4.sh` y ejecutar:
```bash
bash setup_tier4.sh
```

---

## 11. Contacto / Preguntas

Si hay problemas:
- Revisar `datasets/2026-07/embeddings.log` (log completo)
- Revisar `datasets/2026-07/embeddings_error.log` (errores)
- Verificar RAM disponible durante ejecución
- En Windows: usar PowerShell como Admin si hay problemas de permisos

---

**TIER 4 es el paso crítico para Semana 2.** Una vez completado, proceder a TIER 5 (búsqueda vectorial + medición de latencia p95).

