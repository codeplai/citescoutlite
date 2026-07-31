"""
Genera embeddings bge-m3 para productos y los indexa en LanceDB.
TIER 4 - Embeddings masivos
CPU optimizado: batch_size ajustado, sin GPU
"""
import json
import time
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import sys

# Importaciones
try:
    import lancedb
    from sentence_transformers import SentenceTransformer
    import numpy as np
except ImportError as e:
    print(f"ERROR: Falta dependencia: {e}")
    sys.exit(1)


class GenerarEmbeddings:
    """Genera embeddings bge-m3 para productos."""

    # Configuración
    MODELO = "BAAI/bge-m3"
    BATCH_SIZE = 16  # Optimizado para CPU (sin GPU)
    CHECKPOINT_EVERY = 1000  # Guardar checkpoint cada N productos

    def __init__(self, dataset_dir: str = "datasets/2026-07"):
        self.dataset_dir = Path(dataset_dir)
        self.input_file = self.dataset_dir / "productos_merged.json"
        self.output_dir = Path("vectores")
        self.output_dir.mkdir(exist_ok=True)
        self.log_file = self.dataset_dir / "embeddings.log"
        self.checkpoint_file = self.output_dir / "checkpoint.json"

    def log(self, msg: str):
        """Registra mensaje en log con timestamp."""
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(self.log_file, "a") as f:
            f.write(line + "\n")

    def cargar_productos(self) -> List[Dict]:
        """Carga productos desde productos_merged.json."""
        try:
            with open(self.input_file, encoding='utf-8') as f:
                productos = json.load(f)
            self.log(f"[LOAD] Cargados {len(productos)} productos")
            return productos
        except Exception as e:
            self.log(f"[ERROR] Cargando productos: {e}")
            return None

    def cargar_modelo(self) -> SentenceTransformer:
        """Carga modelo bge-m3 (lazy load singleton)."""
        self.log(f"[MODEL] Cargando {self.MODELO}...")
        try:
            modelo = SentenceTransformer(self.MODELO)
            self.log(f"[MODEL] Listo. Dimensiones: 1024")
            return modelo
        except Exception as e:
            self.log(f"[ERROR] Cargando modelo: {e}")
            return None

    def generar_embeddings(self, modelo: SentenceTransformer, productos: List[Dict]) -> List[np.ndarray]:
        """
        Genera embeddings por batch.
        CPU optimizado: batch_size pequeno, progress cada 1000.
        """
        self.log(f"[EMBED] Generando {len(productos)} embeddings...")
        self.log(f"[EMBED] Modelo: {self.MODELO}, Batch size: {self.BATCH_SIZE}")

        embeddings = []
        start_time = time.time()

        # Preparar textos
        textos = [
            f"{p.get('nombre', '')} {p.get('ingredientes', '')}"
            for p in productos
        ]

        # Generar por batch
        total_batches = (len(textos) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        for batch_idx in range(total_batches):
            inicio = batch_idx * self.BATCH_SIZE
            fin = min(inicio + self.BATCH_SIZE, len(textos))
            batch_textos = textos[inicio:fin]

            try:
                batch_embeddings = modelo.encode(
                    batch_textos,
                    batch_size=len(batch_textos),  # Procesar batch como unidad
                    show_progress_bar=False,
                    normalize_embeddings=True
                )
                embeddings.extend(batch_embeddings)

                # Log de progreso
                if (batch_idx + 1) % max(1, total_batches // 10) == 0:
                    progreso = 100 * (batch_idx + 1) / total_batches
                    elapsed = time.time() - start_time
                    tasa = (batch_idx + 1) * self.BATCH_SIZE / elapsed
                    self.log(f"[EMBED] {progreso:.0f}% completado ({elapsed:.0f}s, {tasa:.0f} prod/s)")

            except Exception as e:
                self.log(f"[ERROR] Batch {batch_idx}: {e}")
                return None

        elapsed = time.time() - start_time
        self.log(f"[EMBED] Completado en {elapsed:.0f}s ({len(embeddings)/elapsed:.0f} prod/s)")
        return embeddings

    def preparar_datos_lancedb(self, productos: List[Dict], embeddings: List[np.ndarray]) -> List[Dict]:
        """Prepara datos en formato LanceDB."""
        self.log(f"[PREP] Preparando datos para LanceDB...")

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
                "embedding": emb.tolist()  # Convertir a list para JSON
            })

        self.log(f"[PREP] {len(data)} registros preparados")
        return data

    def indexar_lancedb(self, data: List[Dict]) -> bool:
        """Indexa datos en LanceDB con índice vectorial."""
        self.log(f"[INDEX] Conectando a LanceDB...")

        try:
            db = lancedb.connect(str(self.output_dir))
            self.log(f"[INDEX] Conectado")

            # Eliminar tabla anterior si existe
            try:
                db.drop_table("productos")
                self.log(f"[INDEX] Tabla anterior eliminada")
            except:
                pass

            # Crear tabla
            self.log(f"[INDEX] Creando tabla con {len(data)} registros...")
            start = time.time()

            table = db.create_table("productos", data=data, mode="create")

            elapsed = time.time() - start
            self.log(f"[INDEX] Tabla creada en {elapsed:.0f}s")

            # Crear índice vectorial
            self.log(f"[INDEX] Creando índice vectorial...")
            start = time.time()

            table.create_index()

            elapsed = time.time() - start
            self.log(f"[INDEX] Índice creado en {elapsed:.0f}s")

            # Verificar
            count = table.count_rows()
            self.log(f"[INDEX] Verificacion: {count} filas indexadas")

            return True

        except Exception as e:
            self.log(f"[ERROR] Indexacion: {e}")
            return False

    def actualizar_manifest(self, productos: List[Dict], embeddings: List[np.ndarray]):
        """Actualiza manifest.json con metadata de embeddings."""
        manifest_path = self.dataset_dir / "manifest.json"

        try:
            with open(manifest_path, encoding='utf-8') as f:
                manifest = json.load(f)
        except:
            manifest = {}

        manifest["embeddings"] = {
            "modelo": self.MODELO,
            "dimensiones": 1024,
            "filas": len(productos),
            "timestamp": datetime.now().isoformat(),
            "batch_size": self.BATCH_SIZE
        }

        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, default=str)

        self.log(f"[MANIFEST] Actualizado")

    def ejecutar(self) -> bool:
        """Ejecuta pipeline completo de embeddings."""
        self.log("=" * 70)
        self.log("TIER 4: Embeddings masivos (bge-m3)")
        self.log("=" * 70)
        self.log(f"Inicio: {datetime.now().isoformat()}")

        total_start = time.time()

        # 1. Cargar productos
        productos = self.cargar_productos()
        if not productos:
            return False

        # 2. Cargar modelo
        modelo = self.cargar_modelo()
        if not modelo:
            return False

        # 3. Generar embeddings
        embeddings = self.generar_embeddings(modelo, productos)
        if embeddings is None:
            return False

        # 4. Preparar datos
        data = self.preparar_datos_lancedb(productos, embeddings)

        # 5. Indexar
        if not self.indexar_lancedb(data):
            return False

        # 6. Actualizar manifest
        self.actualizar_manifest(productos, embeddings)

        total_elapsed = time.time() - total_start
        self.log(f"[SUCCESS] TIER 4 completado en {total_elapsed/3600:.1f} horas")
        self.log("=" * 70)
        self.log(f"Fin: {datetime.now().isoformat()}")

        return True


if __name__ == "__main__":
    generador = GenerarEmbeddings()
    success = generador.ejecutar()
    sys.exit(0 if success else 1)
