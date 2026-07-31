"""
TIER 4 GPU-optimizado: Embeddings con NVIDIA CUDA
ETA: 15-30 min en GPU 8GB | 3-5 min en GPU 12GB+
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
