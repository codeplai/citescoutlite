"""
TIER 4 Mejorado - Embeddings con logging de progreso
"""
import json
import time
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    import lancedb
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError as e:
    print(f"ERROR: Falta dependencia: {e}")
    exit(1)


def log_msg(msg):
    """Log con buffer inmediato."""
    timestamp = datetime.now().isoformat()
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    sys.stderr.write(line + "\n")
    sys.stderr.flush()


def main():
    dataset_dir = Path("datasets/2026-07")
    input_file = dataset_dir / "productos_merged.json"
    output_dir = Path("vectores")
    log_file = dataset_dir / "embeddings.log"

    log_msg("=" * 70)
    log_msg("TIER 4: Embeddings masivos (bge-m3)")
    log_msg("=" * 70)

    # 1. Cargar productos
    log_msg("[LOAD] Cargando productos...")
    try:
        with open(input_file, encoding='utf-8') as f:
            productos = json.load(f)
        log_msg(f"[LOAD] Cargados {len(productos)} productos")
    except Exception as e:
        log_msg(f"[ERROR] Cargando: {e}")
        return False

    # 2. Cargar modelo
    log_msg("[MODEL] Cargando BAAI/bge-m3...")
    try:
        modelo = SentenceTransformer("BAAI/bge-m3")
        log_msg("[MODEL] Listo. Dimensiones: 1024")
    except Exception as e:
        log_msg(f"[ERROR] Modelo: {e}")
        return False

    # 3. Generar embeddings CON PROGRESO
    log_msg("[EMBED] Generando embeddings (batch_size=8)...")
    start = time.time()
    try:
        textos = [f"{p.get('nombre', '')} {p.get('ingredientes', '')}" for p in productos]

        # Generar en lotes pequeños y registrar progreso
        all_embeddings = []
        batch_size = 8
        total_batches = (len(textos) + batch_size - 1) // batch_size

        for batch_idx in range(0, len(textos), batch_size):
            batch_texts = textos[batch_idx:batch_idx + batch_size]
            batch_embs = modelo.encode(batch_texts, batch_size=batch_size, show_progress_bar=False)
            all_embeddings.extend(batch_embs)

            # Registrar progreso cada 1000 productos
            processed = min(batch_idx + batch_size, len(textos))
            if processed % 1000 == 0 or batch_idx == 0:
                elapsed = time.time() - start
                rate = processed / elapsed if elapsed > 0 else 0
                log_msg(f"[EMBED] Progreso: {processed}/{len(textos)} ({100*processed//len(textos)}%) - {rate:.0f} prod/s")

        embeddings = np.array(all_embeddings)
        elapsed = time.time() - start
        log_msg(f"[EMBED] Completado en {elapsed:.0f}s ({len(productos)/elapsed:.0f} prod/s)")
    except Exception as e:
        log_msg(f"[ERROR] Embeddings: {e}")
        return False

    # 4. Preparar datos
    log_msg("[PREP] Preparando datos para LanceDB...")
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
            "fuente": p["id_fuente"].split(":")[0],
            "embedding": emb.tolist()
        })
    log_msg(f"[PREP] {len(data)} registros preparados")

    # 5. Indexar
    log_msg("[INDEX] Conectando a LanceDB...")
    try:
        db = lancedb.connect(str(output_dir))

        # Eliminar tabla anterior
        try:
            db.drop_table("productos")
        except:
            pass

        log_msg("[INDEX] Creando tabla...")
        table = db.create_table("productos", data=data, mode="create")

        log_msg("[INDEX] Creando indice vectorial...")
        table.create_index()

        count = table.count_rows()
        log_msg(f"[INDEX] OK: {count} filas indexadas")
    except Exception as e:
        log_msg(f"[ERROR] Indexacion: {e}")
        return False

    # 6. Manifest
    log_msg("[MANIFEST] Actualizando...")
    try:
        manifest_path = dataset_dir / "manifest.json"
        with open(manifest_path, encoding='utf-8') as f:
            manifest = json.load(f)

        manifest["embeddings"] = {
            "modelo": "BAAI/bge-m3",
            "dimensiones": 1024,
            "filas": len(productos),
            "timestamp": datetime.now().isoformat()
        }

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, default=str)

        log_msg("[MANIFEST] OK")
    except Exception as e:
        log_msg(f"[WARN] Manifest: {e}")

    log_msg("[SUCCESS] TIER 4 completado")
    log_msg("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
