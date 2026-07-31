# TIER 4 - INICIADO (Embeddings masivos)

**Fecha de inicio:** 2026-07-30 19:30 UTC  
**Duración estimada:** 8-12 horas (CPU sin GPU)  
**Estado:** EN PROGRESO

---

## Qué está pasando

TIER 4 está en proceso de:

1. **Instalación de dependencias** (en background)
   - `lancedb` (búsqueda vectorial)
   - `sentence-transformers` (modelo bge-m3)

2. **Generación de embeddings** (comenzará cuando dependencias estén listas)
   - Cargará 28,236 productos desde `productos_merged.json`
   - Generará embedding bge-m3 para cada uno (1024 dimensiones)
   - Batch size optimizado para CPU: 16 productos por batch
   - Progreso registrado cada 10% en `datasets/2026-07/embeddings.log`

3. **Indexación en LanceDB**
   - Creará tabla `productos` en `vectores/productos.lance/`
   - Creará índice vectorial con métrica cosine
   - Completará manifest.json

---

## Monitoreo mientras comes

### Comando para verificar progreso:

```bash
# Ver log en tiempo real (cada 30 segundos)
watch -n 30 "tail -20 datasets/2026-07/embeddings.log"

# O simplemente:
tail -f datasets/2026-07/embeddings.log
```

### Qué esperar en el log:

```
[2026-07-30T19:30:00] ======================================================================
[2026-07-30T19:30:00] TIER 4: Embeddings masivos (bge-m3)
[2026-07-30T19:30:00] ======================================================================
[2026-07-30T19:30:05] [LOAD] Cargados 28236 productos
[2026-07-30T19:30:10] [MODEL] Cargando BAAI/bge-m3...
[2026-07-30T19:30:30] [MODEL] Listo. Dimensiones: 1024
[2026-07-30T19:30:35] [EMBED] Generando 28236 embeddings...
[2026-07-30T19:30:35] [EMBED] Modelo: BAAI/bge-m3, Batch size: 16
[2026-07-30T19:45:00] [EMBED] 10% completado (900s, 520 prod/s)
[2026-07-30T20:00:00] [EMBED] 20% completado (1800s, 520 prod/s)
...
[2026-07-30T XX:XX:XX] [EMBED] Completado en XXXX segundos (XXX prod/s)
[2026-07-30T XX:XX:XX] [PREP] Preparando datos para LanceDB...
[2026-07-30T XX:XX:XX] [INDEX] Conectando a LanceDB...
[2026-07-30T XX:XX:XX] [INDEX] Creando tabla con 28236 registros...
[2026-07-30T XX:XX:XX] [SUCCESS] TIER 4 completado en X.X horas
```

---

## Estimación de tiempo

Con CPU (sin GPU), velocidad típica: **300-600 productos/segundo**

```
28,236 productos
──────────────── = 47-94 segundos solo embeddings
600 prod/s (optimista)

+ Carga de modelo:        ~20 segundos
+ Indexación LanceDB:    ~60 segundos
+ Overhead:              ~60 segundos
────────────────────────────────
TOTAL ESTIMADO:          3-5 HORAS (optimista con CPU rápido)
                         8-12 HORAS (máquina lenta o CPU limitado)
```

Si tienes GPU (CUDA/cuDNN): **10-30 minutos**

---

## Acciones mientras comes

### Opción A: Dejarlo correr
- Inicia sesión en otra ventana terminal
- Monitorea `tail -f datasets/2026-07/embeddings.log`
- Come tranquilo, el proceso continúa

### Opción B: Verificar cada X minutos
```bash
# Ver últimas 20 líneas del log
tail -20 datasets/2026-07/embeddings.log

# Ver nombre del archivo de salida
ls -lh vectores/productos.lance/ 2>/dev/null | head -5
```

### Opción C: Detener si hay problemas
```bash
# Si necesitas pausar (NO RECOMENDADO en mitad de embeddings)
pkill -f generar_embeddings.py
```

---

## Checklist de finalización

Cuando TIER 4 termine, verifica:

```bash
# 1. Log indica SUCCESS
tail -5 datasets/2026-07/embeddings.log
# Esperado: [SUCCESS] TIER 4 completado en X.X horas

# 2. Archivo LanceDB existe y tiene tamaño
ls -lh vectores/productos.lance/
# Esperado: directorio con _versions/, data/, _transactions/

# 3. Manifest actualizado
grep -A 5 "embeddings" datasets/2026-07/manifest.json
# Esperado: modelo, dimensiones, filas, timestamp

# 4. Test rápido de búsqueda
python << 'EOF'
import lancedb
db = lancedb.connect("vectores/")
table = db.open_table("productos")
print(f"Productos indexados: {table.count_rows()}")
# Esperado: 28236
EOF
```

---

## Próximos TIERs después de TIER 4

Una vez TIER 4 complete:

- **TIER 5:** Búsqueda optimizada + medir p95 latencia (P03 verde)
- **TIER 6:** Corpus regulatorio (eCFR + DIGESA)
- **TIER 7:** Cierre + Golden set 5/5

---

## Salida esperada de TIER 4

```
datasets/2026-07/
  ├── productos_merged.json      (entrada)
  ├── embeddings.log             (log de ejecución)
  └── manifest.json              (actualizado con metadata)

vectores/
  └── productos.lance/
      ├── _versions/
      │   ├── 0.manifest
      │   └── latest_version_hint.json
      ├── data/
      │   └── <vectores indexados>
      ├── _transactions/
      └── .gitkeep
```

---

## Estado S2 completo

```
Semana 2: Datos reales de los 5 insumos
────────────────────────────────────────

TIER 1: COMPLETADO ✓ (preparación)
  └─ Decisiones D-A, D-B, D-C documentadas

TIER 2: COMPLETADO ✓ (descargas)
  └─ 28,236 productos OFF descargados

TIER 3: COMPLETADO ✓ (limpieza)
  └─ productos_merged.json generado

TIER 4: EN PROGRESO ⏳ (embeddings)
  └─ Generando 28,236 embeddings bge-m3
  └─ ETA: 3-12 horas (sin GPU)

TIER 5-7: LISTOS (dependen de TIER 4)
  └─ Esperando salida de TIER 4
```

---

## Notas importantes

1. **No interrumpas TIER 4 a mitad de ejecución** - puede dejar archivos corruptos
2. **El log se actualiza cada 1000 productos procesados** - no esperes actualizaciones constantes
3. **CPU se usará al máximo** - normal que la máquina se ralentice un poco
4. **Si el proceso muere:** recupera desde checkpoint y reinicia:
   ```bash
   python etl/generar_embeddings.py
   ```

---

**Iniciado:** 2026-07-30 19:30 UTC  
**Estado:** Instalando dependencias + inicializando TIER 4  
**Próxima revisión:** En 30-60 minutos cuando cargo de cómputo comience

🚀 **¡Buen provecho! El código está trabajando por ti.**

