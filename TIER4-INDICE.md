# TIER 4 - Índice de Documentación

**Tu máquina:** GPU 8GB NVIDIA + 64GB RAM + Windows  
**ETA:** 15-30 minutos

---

## 📖 Por dónde empezar

### Si tienes PRISA (15 minutos)
**LEE:** `TIER4-GPU-QUICK.md`
- Paso a paso mínimo
- Solo lo esencial

**SCRIPT A EJECUTAR:** `etl/tier4_gpu.py`

---

### Si quieres verificar que todo está OK
**LEE:** `TIER4-GPU-CHECKLIST.md`
- Hardware requerido ✓
- Software requerido ✓
- Permisos ✓
- Pre-ejecución

**EJECUTA:** Script de verificación incluido en checklist

---

### Si necesitas la guía completa
**LEE:** `TIER4-README.md`
- Requisitos detallados
- Instalación paso a paso
- GPU vs CPU comparativa
- Monitoreo en tiempo real
- Troubleshooting completo
- Aftercare

---

### Si necesitas entender TODO rápido
**LEE:** `TIER4-RESUMEN.txt`
- Overview de todo
- Timeline
- Archivos críticos
- FAQs

---

## 🎯 Flujo recomendado

```
┌─────────────────────┐
│ 1. TIER4-RESUMEN.txt│ (5 min - entender qué es)
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────┐
│ 2. TIER4-GPU-CHECKLIST.md│ (10 min - verificar setup)
└──────────┬───────────────┘
           │ ✓ TODO OK
           ▼
┌─────────────────────────┐
│ 3. TIER4-GPU-QUICK.md   │ (15 min - ejecutar)
│    python tier4_gpu.py  │
└──────────┬──────────────┘
           │ ✓ [SUCCESS]
           ▼
┌──────────────────────────┐
│ Pasar a TIER 5           │
│ (Ver PLAN-TIERS-S2.md)   │
└──────────────────────────┘
```

---

## 📂 Archivos en este directorio

| Archivo | Propósito | Tiempo |
|---------|-----------|--------|
| **TIER4-GPU-QUICK.md** | Quick start | 15 min |
| **TIER4-GPU-CHECKLIST.md** | Verificación | 10 min |
| **TIER4-README.md** | Guía completa | 20 min lectura |
| **TIER4-RESUMEN.txt** | Overview | 5 min |
| **TIER4-INDICE.md** | Este archivo | 2 min |
| **etl/tier4_gpu.py** | Script principal | ⚙️ Ejecutar |
| **etl/tier4_cpu.py** | Alternativa CPU | (si falla GPU) |

---

## 🚀 Resumen Ultra-Rápido

**Copy-paste esto en PowerShell (en carpeta mvp):**

```powershell
# Setup (primera vez: 5 min)
python -m venv venv
venv\Scripts\activate
pip install --upgrade pip
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers lancedb numpy

# Ejecutar TIER 4 (15-30 min)
python etl/tier4_gpu.py

# Verificar resultado
type datasets\2026-07\embeddings.log | find "SUCCESS"
```

**Listo.** Si ves `[SUCCESS] TIER 4 COMPLETADO (GPU)`, pasar a TIER 5.

---

## ✅ Checklist Pre-Ejecución

- [ ] GPU NVIDIA 8GB disponible: `nvidia-smi` funciona
- [ ] CUDA 12.1 instalado: `nvcc --version` muestra CUDA
- [ ] Python 3.9+: `python --version`
- [ ] Archivo entrada existe: `datasets\2026-07\productos_merged.json` (15-20MB)
- [ ] Directorio salida creado: `mkdir vectores`

Si todo OK → Ejecutar: `python etl/tier4_gpu.py`

---

## 🔧 Troubleshooting Rápido

| Problema | Solución |
|----------|----------|
| GPU no detectada | `nvidia-smi` → Instalar CUDA 12.1 |
| OutOfMemory | Editar `batch_size=64` en `tier4_gpu.py` línea 80 |
| `torch not found` | `pip install torch...` con URL cu121 |
| Proceso muy lento | Cerrar videojuegos/Blender, verificar GPU activa |
| Script no existe | Asegurar copié `etl/tier4_gpu.py` |

---

## 📞 ¿Dónde encontrar ayuda?

**Error específico:**
→ Buscar en `TIER4-README.md` sección "Troubleshooting"

**General:**
→ `TIER4-GPU-QUICK.md` sección "Troubleshooting"

**Setup:**
→ `TIER4-GPU-CHECKLIST.md`

**No entiendo algo:**
→ `TIER4-RESUMEN.txt` explicación simplificada

---

## 📊 Comparativa: TIER 4 en tu máquina

| Dispositivo | Tiempo | Speed | Energía |
|-------------|--------|-------|---------|
| **Tu GPU 8GB** | **15-30 min** | **100-200 prod/s** | Bajo |
| CPU (referencia) | 2-3 horas | 4-5 prod/s | Medio |
| GPU RTX 4090 | 3-5 min | 300 prod/s | Alto |

**Conclusión:** Tu GPU es excelente para esto. Muy rápido.

---

## 🎯 Después de Completar TIER 4

1. ✅ Ver: `[SUCCESS] TIER 4 COMPLETADO (GPU)` en log
2. ✅ Commit en git:
   ```cmd
   git add datasets/2026-07/manifest.json "vectores/productos.lance/*"
   git commit -m "TIER 4: Embeddings GPU (28236, 15-30min)"
   ```
3. ✅ Pasar a **TIER 5**: Búsqueda + latencia p95
   Ver `PLAN-TIERS-S2.md`

---

## 💡 Tips

- **No interrumpas** TIER 4 mientras dice `[EMBED]`
- **Cierra** videojuegos/Blender antes de ejecutar
- **Internet OK** para descargar modelo bge-m3 (~500MB primera vez)
- **Espera** 15-30 minutos, **no verifiques cada 10 segundos**

---

## 📞 Próximo paso

Después de TIER 4 exitoso:

```bash
# Ver manifest actualizado
type datasets\2026-07\manifest.json

# Debe incluir:
# "embeddings": {
#   "modelo": "BAAI/bge-m3",
#   "dimensiones": 1024,
#   "filas": 28236,
#   "dispositivo": "CUDA",
#   "batch_size": 128
# }

# Commit
git add datasets/2026-07/manifest.json "vectores/productos.lance/*"
git commit -m "TIER 4: Completado con GPU en 15-30 minutos"

# Siguiente: TIER 5 en PLAN-TIERS-S2.md
```

---

**¿Listo para ejecutar TIER 4?**

👉 Lee `TIER4-GPU-QUICK.md` (5 minutos)  
👉 Ejecuta `python etl/tier4_gpu.py` (15-30 minutos)  
👉 Verifica resultado

Que disfrutes ver 100-200 productos/segundo en GPU vs 4-5 en CPU 🚀
