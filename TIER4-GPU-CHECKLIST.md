# TIER 4 GPU - Checklist Pre-Ejecución

Verificar TODO antes de ejecutar `python etl/tier4_gpu.py`

---

## 🖥️ Hardware

- [ ] GPU NVIDIA de 8GB instalada
- [ ] Verificar: `nvidia-smi` muestra GPU
- [ ] RAM: 64GB disponibles (verificar con Task Manager)
- [ ] Disco: 20GB libres en C:\ o donde esté `mvp/`

---

## 📦 Software

- [ ] Python 3.9+ instalado
  ```cmd
  python --version
  # Esperado: Python 3.10 o 3.11
  ```

- [ ] NVIDIA Driver actualizado
  ```cmd
  nvidia-smi
  # Debe mostrar versión Driver > 500
  ```

- [ ] CUDA Toolkit 12.1 instalado
  ```cmd
  nvcc --version
  # Esperado: CUDA release 12.1 o similar
  ```

- [ ] Visual Studio Build Tools (requerido para algunas libs)
  - Windows SDK
  - C++ build tools

---

## 📂 Archivos y Directorios

- [ ] Proyecto copiado a máquina con GPU
  ```cmd
  dir mvp\
  # Debe tener: etl\, datasets\, vectores\, TIER4-README.md
  ```

- [ ] Archivo de entrada existe
  ```cmd
  dir datasets\2026-07\productos_merged.json
  # Tamaño: 15-20MB
  # Cantidad: 28236 líneas JSON
  ```

- [ ] Directorio `vectores/` creado
  ```cmd
  mkdir vectores
  ```

- [ ] Script TIER 4 GPU existe
  ```cmd
  dir etl\tier4_gpu.py
  # Debe existir
  ```

---

## 🔧 Configuración Python

- [ ] Crear virtual environment
  ```cmd
  python -m venv venv
  venv\Scripts\activate
  # Debe mostrar (venv) en prompt
  ```

- [ ] pip actualizado
  ```cmd
  pip --version
  # Esperado: pip 24.x o similar
  ```

- [ ] PyTorch con CUDA instalado
  ```cmd
  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
  ```

- [ ] Verificar PyTorch detecta GPU
  ```cmd
  python << 'EOF'
  import torch
  print(f"CUDA available: {torch.cuda.is_available()}")
  print(f"GPU: {torch.cuda.get_device_name(0)}")
  print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
  EOF
  # Esperado:
  # CUDA available: True
  # GPU: NVIDIA GeForce RTX XXXX
  # VRAM: 8.0 GB
  ```

- [ ] Dependencias instaladas
  ```cmd
  pip install sentence-transformers lancedb numpy
  pip list | findstr "sentence transformers lancedb numpy torch"
  # Debe listar todas
  ```

---

## 🔐 Permisos

- [ ] Permisos de lectura en `datasets/2026-07/`
  ```cmd
  dir datasets\2026-07\
  # Debe ver archivos
  ```

- [ ] Permisos de escritura en `vectores/`
  ```cmd
  echo test > vectores\test.txt && del vectores\test.txt
  # Si no da error, está OK
  ```

- [ ] Permisos de escritura en `datasets/2026-07/`
  ```cmd
  echo test > datasets\2026-07\test.txt && del datasets\2026-07\test.txt
  # Si no da error, está OK
  ```

---

## 🌐 Internet

- [ ] Conexión a internet estable (primera ejecución descarga modelo ~500MB)
  ```cmd
  ping huggingface.co
  # Debe responder
  ```

---

## 💾 Limpieza Previa

- [ ] Cerrar aplicaciones que usen GPU:
  - [ ] Videojuegos
  - [ ] Blender
  - [ ] CUDA applications
  - [ ] Rendering software

- [ ] Liberar RAM:
  ```cmd
  taskmgr.exe
  # Cerrar aplicaciones no esenciales
  # Objetivo: >10GB RAM libre
  ```

- [ ] Limpiar cache de transformers (primera ejecución):
  ```cmd
  # Antes de instalar dependencias:
  # No hay caché aún
  
  # En ejecuciones posteriores, cache puede ocupar 500MB-1GB
  # Está en: %USERPROFILE%\.cache\huggingface\
  ```

---

## 📋 Verificación Final

Ejecutar este script ANTES de TIER 4:

```powershell
Write-Host "=== VERIFICACIÓN PRE-TIER 4 ==="
Write-Host ""

# Python
Write-Host "Python:"
python --version
Write-Host ""

# GPU
Write-Host "GPU:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader,nounits
Write-Host ""

# CUDA
Write-Host "CUDA:"
nvcc --version | findstr "release"
Write-Host ""

# PyTorch
Write-Host "PyTorch detecta GPU:"
python << 'EOF'
import torch
print(f"CUDA: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
EOF
Write-Host ""

# Archivos
Write-Host "Archivos:"
if (Test-Path "datasets\2026-07\productos_merged.json") {
    $size = (Get-Item "datasets\2026-07\productos_merged.json").Length / 1MB
    Write-Host "  productos_merged.json: $($size.ToString('F1')) MB (OK)"
} else {
    Write-Host "  ERROR: productos_merged.json NO ENCONTRADO"
}

if (Test-Path "etl\tier4_gpu.py") {
    Write-Host "  tier4_gpu.py: OK"
} else {
    Write-Host "  ERROR: tier4_gpu.py NO ENCONTRADO"
}

if (Test-Path "vectores") {
    Write-Host "  vectores/: OK"
} else {
    Write-Host "  ERROR: vectores/ NO EXISTE"
}

Write-Host ""
Write-Host "=== VERIFICACIÓN COMPLETA ==="
```

Guardar como `verify_tier4.ps1` y ejecutar:
```powershell
.\verify_tier4.ps1
```

---

## ✅ Sí, Todo está OK si:

- [x] `python --version` muestra Python 3.9+
- [x] `nvidia-smi` muestra GPU NVIDIA 8GB
- [x] `torch.cuda.is_available()` retorna `True`
- [x] `productos_merged.json` existe y es >15MB
- [x] `vectores/` directorio creado
- [x] Puedo escribir en `vectores/` y `datasets/2026-07/`

---

## 🚀 LISTO PARA EJECUTAR

```powershell
python etl/tier4_gpu.py
# ETA: 15-30 minutos
```

Salida esperada:
```
[2026-07-30T21:23:17] [GPU] Detectada: NVIDIA GeForce RTX XXXX (8.0GB)
[2026-07-30T21:23:35] [EMBED] Generando 28236 embeddings (batch_size=128)...
[2026-07-30T21:25:35] [EMBED] 2000/28236 (7%) - 150.3 prod/s
...
[2026-07-XX:XX:XX] [SUCCESS] TIER 4 COMPLETADO (GPU)
```

