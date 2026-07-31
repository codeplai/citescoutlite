"""
Descarga y procesa export masivo de OFF.
TIER 2 - T2.1: Estrategia OPCIÓN B (offline)
"""
import csv
import gzip
import json
import os
import urllib.request
import time
from pathlib import Path
from typing import List, Dict
from datetime import datetime

class DescargarOFFBulk:
    """Descarga y filtra export masivo de OFF."""

    # Insumos piloto S2
    INSUMOS_PILOTO = ["arándano", "palta", "espárrago", "mango", "quinua"]
    INSUMOS_EN = ["blueberry", "avocado", "asparagus", "mango", "quinoa"]

    # URL del export
    OFF_EXPORT_URL = "https://world.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
    OFF_EXPORT_LOCAL = "~/off_export.csv.gz"

    def __init__(self, output_dir: str = "datasets/2026-07"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = self.output_dir / "off_productos.json"
        self.log_file = self.output_dir / "etl_off_bulk.log"

    def log(self, msg: str):
        """Registra mensaje en log."""
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(self.log_file, "a") as f:
            f.write(line + "\n")

    def descargar_export(self) -> Path:
        """
        Descarga export masivo de OFF si no existe.

        Returns:
            Path al archivo .gz descargado
        """
        home = Path.home()
        gz_path = home / "off_export.csv.gz"

        if gz_path.exists():
            size_gb = gz_path.stat().st_size / (1024**3)
            self.log(f"[OFF] Export ya descargado: {gz_path} ({size_gb:.1f} GB)")
            return gz_path

        self.log(f"[OFF] Descargando export masivo (~2GB)...")
        self.log(f"      URL: {self.OFF_EXPORT_URL}")

        try:
            urllib.request.urlretrieve(
                self.OFF_EXPORT_URL,
                gz_path,
                reporthook=self._report_progress
            )
            self.log(f"[OFF] Descarga completada: {gz_path}")
            return gz_path
        except Exception as e:
            self.log(f"[OFF] ERROR descargando: {e}")
            return None

    def _report_progress(self, block_num, block_size, total_size):
        """Callback para mostrar progreso de descarga."""
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, (downloaded * 100) / total_size)
            if percent % 10 == 0:  # Log cada 10%
                self.log(f"      Progreso: {percent:.0f}%")

    def filtrar_insumos(self, gz_path: Path) -> List[Dict]:
        """
        Descomprime y filtra CSV de OFF a los 5 insumos piloto.

        Args:
            gz_path: Path al archivo .gz

        Returns:
            Lista de productos filtrados
        """
        self.log(f"[ETL] Descomprimiendo y filtrando OFF...")

        productos = []
        filas_leidas = 0
        filas_filtradas = 0

        try:
            csv.field_size_limit(int(1e7))  # Aumentar a 10MB
            with gzip.open(gz_path, 'rt', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f, delimiter='\t')

                for row in reader:
                    try:
                        filas_leidas += 1

                        # Log de progreso cada 10k filas
                        if filas_leidas % 10000 == 0:
                            self.log(f"      Leídas {filas_leidas} filas...")

                        # Filtrar: ingredientes contiene algún insumo piloto
                        ingredientes = (row.get('ingredients_text', '') or '').lower()

                        # Buscar en español e inglés
                        tiene_insumo = any(
                            insumo.lower() in ingredientes or insumo_en.lower() in ingredientes
                            for insumo, insumo_en in zip(self.INSUMOS_PILOTO, self.INSUMOS_EN)
                        )

                        if not tiene_insumo or not ingredientes:
                            continue

                        # Validar campos mínimos
                        if not row.get('product_name') or not row.get('url'):
                            continue

                        # Extraer timestamp
                        fecha_ts = None
                        if row.get('last_modified_t'):
                            try:
                                fecha_ts = int(row['last_modified_t'])
                            except:
                                pass

                        if not fecha_ts:
                            continue

                        # Agregar al resultado
                        productos.append({
                            "id_fuente": f"OFF:{row.get('barcode', row.get('code', 'N/A'))}",
                            "nombre": row.get('product_name', 'Unknown'),
                            "categoria": row.get('categories', ''),
                            "ingredientes": ingredientes,
                            "url": row.get('url', ''),
                            "usa_insumo_directo": False,  # Será derivado después
                            "fecha_dato": fecha_ts,
                            "marca": row.get('brands', ''),
                            "pais": row.get('countries', '')
                        })
                        filas_filtradas += 1
                    except Exception as e_row:
                        # Ignorar filas problemáticas
                        continue

        except Exception as e:
            self.log(f"[ETL] ERROR procesando CSV: {e}")
            return []

        self.log(f"[ETL] Procesamiento completado:")
        self.log(f"      Filas leídas: {filas_leidas:,}")
        self.log(f"      Filas filtradas: {filas_filtradas}")

        return productos

    def guardar_productos(self, productos: List[Dict]) -> bool:
        """Guarda productos a JSON."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(productos, f, ensure_ascii=False, indent=2)

            self.log(f"[SAVE] Guardado: {self.output_file}")
            self.log(f"[SAVE] Total: {len(productos)} productos")
            return True
        except Exception as e:
            self.log(f"[SAVE] ERROR: {e}")
            return False

    def validar_productos(self, productos: List[Dict]) -> bool:
        """Valida que los productos son reales (no DEMO)."""

        if len(productos) < 50:
            self.log(f"[WARN] Insuficientes productos: {len(productos)} (mínimo 50)")
            return False

        # Validar que no hay DEMO data
        demo_count = len([p for p in productos if p['id_fuente'].startswith('DEMO')])
        if demo_count > 0:
            self.log(f"[WARN] {demo_count} productos son DEMO data")

        # Validar fechas reales
        fechas_validas = sum(1 for p in productos if p.get('fecha_dato'))
        if fechas_validas != len(productos):
            self.log(f"[WARN] {len(productos) - fechas_validas} sin fecha_dato")

        # Validar URLs
        urls_validas = sum(1 for p in productos if p.get('url'))
        if urls_validas != len(productos):
            self.log(f"[WARN] {len(productos) - urls_validas} sin URL")

        # Estadísticas por insumo
        self.log(f"[STATS] Cobertura por insumo:")
        for insumo, insumo_en in zip(self.INSUMOS_PILOTO, self.INSUMOS_EN):
            count = len([
                p for p in productos
                if (insumo.lower() in p['ingredientes'] or
                    insumo_en.lower() in p['ingredientes'])
            ])
            self.log(f"        {insumo}: {count}")

        self.log(f"[STATS] Total validado: {len(productos)} ✓")
        return True

    def ejecutar(self) -> bool:
        """Ejecuta pipeline completo."""
        self.log("=" * 70)
        self.log("TIER 2 - T2.1: Descarga OFF Masivo (OPCIÓN B)")
        self.log("=" * 70)

        # 1. Descargar
        start = time.time()
        gz_path = self.descargar_export()
        if not gz_path:
            return False

        # 2. Filtrar
        productos = self.filtrar_insumos(gz_path)
        if not productos:
            self.log("[ERROR] No se filtraron productos")
            return False

        # 3. Guardar
        if not self.guardar_productos(productos):
            return False

        # 4. Validar
        if not self.validar_productos(productos):
            return False

        elapsed = time.time() - start
        self.log(f"[SUCCESS] TIER 2-T2.1 completado en {elapsed/60:.1f} minutos")
        self.log("=" * 70)
        return True


if __name__ == "__main__":
    import sys
    descargador = DescargarOFFBulk()
    success = descargador.ejecutar()
    sys.exit(0 if success else 1)
