# TIER 4 - GPU Quick Start (15-30 minutos)

**Para máquina con:** GPU 8GB NVIDIA + 64GB RAM + Windows

---

## 1️⃣ Verificar GPU

```cmd
nvidia-smi
```

**Debe mostrar:**
```
NVIDIA-SMI 555.00  Driver Version: 555.00  CUDA Version: 12.5
GPU: NVIDIA GeForce RTX XXXX (8192 MB)
```

Si NO funciona → Instalar driver: https://www.nvidia.com/Download/index.aspx

---

## 2️⃣ Setup (5 minutos)

Abrir PowerShell en carpeta `mvp`:

```powershell
# Crear virtual environment
python -m venv venv
venv\Scripts\activate

# Instalar dependencias GPU
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers lancedb numpy

# Verificar GPU detectada
python << 'EOF'
import torch
print(f"GPU disponible: {torch.cuda.is_available()}")
print(f"GPU: {torch.cuda.get_device_name(0)}")
EOF
```

Debe mostrar: `GPU disponible: True` + nombre de GPU

---

## 3️⃣ Ejecutar TIER 4 (15-30 min)

```powershell
python etl/tier4_gpu.py
```

**Salida esperada:**
```
[2026-07-30T21:23:17] ======================================================================
[2026-07-30T21:23:17] TIER 4: Embeddings GPU-optimizado (NVIDIA CUDA)
[2026-07-30T21:23:17] ======================================================================
[2026-07-30T21:23:17] [GPU] Detectada: NVIDIA GeForce RTX XXXX (8.0GB)
[2026-07-30T21:23:18] [LOAD] Leyendo 28236 productos...
[2026-07-30T21:23:18] [LOAD] OK: 28236 productos
[2026-07-30T21:23:19] [MODEL] Cargando bge-m3 en CUDA...
[2026-07-30T21:23:35] [MODEL] OK en 16s
[2026-07-30T21:23:35] [EMBED] Generando 28236 embeddings (batch_size=128)...
[2026-07-30T21:25:35] [EMBED] 2000/28236 (7%) - 150.3 prod/s
[2026-07-30T21:27:35] [EMBED] 4000/28236 (14%) - 148.2 prod/s
...
[2026-07-XX:XX:XX] [EMBED] OK en XXXs (100+ prod/s)
[2026-07-XX:XX:XX] [SUCCESS] TIER 4 COMPLETADO (GPU)
```

---

## 4️⃣ Verificar Resultado

```cmd
# Ver últimas líneas del log
type datasets\2026-07\embeddings.log

# Debe terminar con: [SUCCESS] TIER 4 COMPLETADO (GPU)
```

---

## ⚡ Comparativa de tiempos

| GPU | Tiempo | Speed |
|-----|--------|-------|
| RTX 4090 | 3-5 min | 300 prod/s |
| RTX 3090 | 5-8 min | 200 prod/s |
| **RTX 3060 (8GB)** | **15-20 min** | **100 prod/s** ← Tu caso |
| CPU i9 16-core | 2-3 horas | 4-5 prod/s |

---

## 🔧 Troubleshooting

**Q: GPU no detectada**
```
A: Instalar CUDA 12.1: https://developer.nvidia.com/cuda-12-1-0-download-archive
   Reiniciar máquina
   Verificar: nvidia-smi
```

**Q: OutOfMemory (GPU 8GB)**
```
A: Editar tier4_gpu.py línea 80:
   batch_size = 64  (en lugar de 128)
   Seguirá siendo rápido: ~20-30 min
```

**Q: Script muy lento (< 50 prod/s)**
```
A: Verificar:
   1. nvidia-smi (debe mostrar Python usando GPU)
   2. Cerrar videojuegos/Blender/aplicaciones GPU
   3. Revisar batch_size=128 en tier4_gpu.py
```

---

## 📊 Después de Completar

```cmd
# Ver manifest.json actualizado
type datasets\2026-07\manifest.json

# Debe incluir:
# "embeddings": {
#   "modelo": "BAAI/bge-m3",
#   "dimensiones": 1024,
#   "filas": 28236,
#   "dispositivo": "CUDA",
#   "batch_size": 128,
#   "timestamp": "2026-07-30T21:XX:XX..."
# }
```

---

**Tiempo total de configuración + ejecución: 30 minutos**

Después de TIER 4, pasar a TIER 5 (búsqueda vectorial + latencia p95).
