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
    with open("datasets/2026-07/productos_merged.json", encoding="utf-8") as f:
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
    # CRITICO para 8GB VRAM: bge-m3 acepta hasta 8192 tokens y la memoria crece
    # con el texto mas largo del batch (causa del OOM al 60% en la corrida anterior).
    # 512 tokens sobra para nombre+ingredientes y reduce memoria y tiempo drasticamente.
    model.max_seq_length = 512
    log(f"[MODEL] OK en {time.time()-start_model:.0f}s (max_seq_length=512)")
except Exception as e:
    log(f"[ERROR] MODEL: {e}")
    sys.exit(1)

# EMBED
# batch_size=32: seguro para GPU de 8GB VRAM junto con max_seq_length=512
batch_size = 32 if device == "cuda" else 4
log(f"[EMBED] Generando 28236 embeddings (batch_size={batch_size})...")
start_emb = time.time()
CKPT_PATH = Path("datasets/2026-07/embeddings_checkpoint.npy")

try:
    texts = [f"{p.get('nombre','')} {p.get('ingredientes','')}" for p in productos]

    # Reanudar desde checkpoint si existe (de una corrida anterior interrumpida)
    embeddings_list = []
    resume_from = 0
    if CKPT_PATH.exists():
        try:
            prev = np.load(CKPT_PATH)
            if prev.ndim == 2 and prev.shape[1] == 1024 and prev.shape[0] <= len(texts):
                embeddings_list = list(prev)
                resume_from = prev.shape[0]
                log(f"[RESUME] Checkpoint encontrado: reanudando desde {resume_from}/{len(texts)}")
            else:
                log("[RESUME] Checkpoint invalido, empezando de cero")
        except Exception as ce:
            log(f"[RESUME] No se pudo leer checkpoint ({ce}), empezando de cero")

    ckpt_interval = 2000  # guardar avance cada ~2000 productos
    last_ckpt = resume_from
    for i in range(resume_from, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        batch_embs = model.encode(batch, batch_size=batch_size, show_progress_bar=False)
        embeddings_list.extend(batch_embs)
        done = min(i + batch_size, len(texts))

        # Checkpoint + limpieza de VRAM
        if done - last_ckpt >= ckpt_interval or done == len(texts):
            np.save(CKPT_PATH, np.array(embeddings_list))
            last_ckpt = done
            if device == "cuda":
                torch.cuda.empty_cache()

        # Log cada ~1000 productos (GPU) o ~100 (CPU) - se activa al cruzar cada umbral
        log_interval = 1000 if device == "cuda" else 100
        if done % log_interval < batch_size or done == len(texts):
            elapsed = time.time() - start_emb
            rate = (done - resume_from) / elapsed if elapsed > 0 else 0
            pct = 100 * done // len(texts)
            eta_min = (len(texts) - done) / rate / 60 if rate > 0 else 0
            log(f"[EMBED] {done}/{len(texts)} ({pct}%) - {rate:.1f} prod/s - ETA {eta_min:.1f} min")

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
    count = table.count_rows()

    # Crear indice vectorial sobre la columna 'embedding' (el default busca 'vector' y falla).
    # Metrica cosine: la recomendada para bge-m3 / busqueda semantica.
    try:
        try:
            from lancedb.index import IvfPq
            table.create_index("embedding", config=IvfPq(distance_type="cosine"))
        except ImportError:
            table.create_index(vector_column_name="embedding", metric="cosine")
        log("[INDEX] Indice vectorial creado sobre 'embedding' (cosine)")
    except Exception as ie:
        # No es fatal: con 28k filas la busqueda exacta sin indice sigue siendo rapida
        log(f"[WARN] Indice ANN no creado ({ie}). La tabla funciona igual con busqueda exacta.")

    log(f"[INDEX] OK en {time.time()-start_idx:.0f}s: {count} filas")
except Exception as e:
    log(f"[ERROR] INDEX: {e}")
    sys.exit(1)

# MANIFEST
log("[MANIFEST] Actualizando...")
try:
    with open("datasets/2026-07/manifest.json", encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["embeddings"] = {
        "modelo": "BAAI/bge-m3",
        "dimensiones": 1024,
        "filas": len(productos),
        "dispositivo": device.upper(),
        "batch_size": batch_size,
        "timestamp": datetime.now().isoformat()
    }

    with open("datasets/2026-07/manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str, ensure_ascii=False)

    log("[MANIFEST] OK")
except Exception as e:
    log(f"[WARN] MANIFEST: {e}")

# Limpiar checkpoint (ya no hace falta: todo quedo indexado en LanceDB)
try:
    if CKPT_PATH.exists():
        CKPT_PATH.unlink()
        log("[CLEANUP] Checkpoint eliminado")
except Exception:
    pass

log("[SUCCESS] TIER 4 COMPLETADO (GPU)")
log("="*70)
sys.exit(0)
