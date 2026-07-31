"""
Merge y deduplicación de datasets OFF + USDA.
TIER 3 - T3.1-T3.2: Limpieza de datos
"""
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime

class MergeDatasets:
    """Merge y deduplicación de OFF + USDA."""

    def __init__(self, dataset_dir: str = "datasets/2026-07"):
        self.dataset_dir = Path(dataset_dir)
        self.off_file = self.dataset_dir / "off_productos.json"
        self.usda_file = self.dataset_dir / "usda_productos.json"
        self.output_file = self.dataset_dir / "productos_merged.json"
        self.log_file = self.dataset_dir / "merge.log"

    def log(self, msg: str):
        """Registra mensaje en log."""
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] {msg}"
        print(line)
        with open(self.log_file, "a") as f:
            f.write(line + "\n")

    def cargar_productos(self) -> tuple:
        """Carga productos de OFF y USDA."""
        self.log("=" * 70)
        self.log("TIER 3: Merge y Deduplicación")
        self.log("=" * 70)

        # Cargar OFF
        try:
            with open(self.off_file, encoding='utf-8') as f:
                productos_off = json.load(f)
            self.log(f"[LOAD] OFF: {len(productos_off)} productos")
        except Exception as e:
            self.log(f"[ERROR] Cargando OFF: {e}")
            return None, None

        # Cargar USDA
        try:
            with open(self.usda_file, encoding='utf-8') as f:
                data = json.load(f)
                # Si está saltado (contiene "estado": "SALTADO"), retornar lista vacía
                if isinstance(data, dict) and data.get("estado") == "SALTADO":
                    productos_usda = []
                else:
                    productos_usda = data if isinstance(data, list) else data.get("productos", [])
            self.log(f"[LOAD] USDA: {len(productos_usda)} productos")
        except Exception as e:
            self.log(f"[WARN] USDA no disponible: {e}")
            productos_usda = []

        return productos_off, productos_usda

    def similar_product(self, p1: Dict, p2: Dict) -> bool:
        """
        Detecta duplicados por marca + nombre (heurística simple).
        Para datos reales de OFF, esto es suficiente.
        """
        # Obtener marca (normalizar)
        marca1 = (p1.get("marca") or "").lower().strip()
        marca2 = (p2.get("marca") or "").lower().strip()

        if not marca1 or not marca2:
            return False

        if marca1 != marca2:
            return False

        # Primeros 20 caracteres del nombre (normalizar)
        nombre1 = (p1.get("nombre") or "")[:20].lower().strip()
        nombre2 = (p2.get("nombre") or "")[:20].lower().strip()

        return nombre1 == nombre2

    def merge_y_dedup(self, productos_off: List[Dict], productos_usda: List[Dict]) -> List[Dict]:
        """
        Merge OFF + USDA, elimina duplicados.
        Prioridad: mantener todos de OFF, agregar USDA sin duplicados.
        """
        self.log(f"[MERGE] Iniciando merge y deduplicación...")

        # Empezar con todos los productos de OFF
        merged = productos_off.copy()
        duplicados = 0

        # Agregar productos de USDA que no están duplicados
        for p_usda in productos_usda:
            is_dup = False
            for p_off in productos_off:
                if self.similar_product(p_usda, p_off):
                    is_dup = True
                    duplicados += 1
                    break

            if not is_dup:
                merged.append(p_usda)

        self.log(f"[MERGE] Duplicados removidos: {duplicados}")
        self.log(f"[MERGE] Total final: {len(merged)}")

        return merged

    def validar_productos(self, productos: List[Dict]) -> bool:
        """Valida producto merged."""
        # Validación mínima
        if len(productos) < 50:
            self.log(f"[ERROR] Insuficientes productos: {len(productos)}")
            return False

        # Verificar estructura
        sample = productos[0]
        campos_requeridos = ["id_fuente", "nombre", "ingredientes", "url", "fecha_dato"]
        for campo in campos_requeridos:
            if campo not in sample:
                self.log(f"[ERROR] Falta campo '{campo}' en estructura")
                return False

        self.log(f"[VALID] Estructura OK")
        self.log(f"[VALID] Total validado: {len(productos)}")
        return True

    def guardar_productos(self, productos: List[Dict]) -> bool:
        """Guarda productos merged a JSON."""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(productos, f, ensure_ascii=False, indent=2)

            self.log(f"[SAVE] Guardado: {self.output_file}")
            self.log(f"[SAVE] Total: {len(productos)} productos")

            # Log de estadísticas
            off_count = len([p for p in productos if p["id_fuente"].startswith("OFF")])
            usda_count = len([p for p in productos if p["id_fuente"].startswith("USDA")])

            self.log(f"[STATS] Composición:")
            self.log(f"        OFF:  {off_count}")
            self.log(f"        USDA: {usda_count}")

            return True
        except Exception as e:
            self.log(f"[ERROR] Guardando: {e}")
            return False

    def ejecutar(self) -> bool:
        """Ejecuta pipeline completo."""
        # 1. Cargar
        productos_off, productos_usda = self.cargar_productos()
        if productos_off is None:
            return False

        # 2. Merge y dedup
        merged = self.merge_y_dedup(productos_off, productos_usda)

        # 3. Validar
        if not self.validar_productos(merged):
            return False

        # 4. Guardar
        if not self.guardar_productos(merged):
            return False

        self.log(f"[SUCCESS] TIER 3 completado")
        self.log("=" * 70)
        return True


if __name__ == "__main__":
    import sys
    merger = MergeDatasets()
    success = merger.ejecutar()
    sys.exit(0 if success else 1)
