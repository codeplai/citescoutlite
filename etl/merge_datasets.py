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
        self.terminados_file = self.dataset_dir / "off_terminados.json"
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

    def cargar_terminados(self) -> List[Dict]:
        """Productos terminados de `etl.cargar_off_terminados`.

        Fuente opcional: si el archivo no existe, el merge es el de S2 y no
        pasa nada. Se anade aparte y no dentro de `off_productos.json` porque
        aquel es el filtrado del export masivo y su SHA256 esta en el manifest;
        mezclarlos dejaria el manifest describiendo un archivo que ya no es el
        que se descargo.
        """
        if not self.terminados_file.exists():
            self.log("[LOAD] Terminados: no hay archivo, se omite la fuente")
            return []
        try:
            with open(self.terminados_file, encoding='utf-8') as f:
                productos = json.load(f)
            self.log(f"[LOAD] Terminados: {len(productos)} productos")
            return productos
        except Exception as e:
            self.log(f"[WARN] Terminados no legibles: {e}")
            return []

    @staticmethod
    def clave_dedup(p: Dict) -> tuple | None:
        """
        Clave de duplicado: marca + primeros 20 caracteres del nombre.

        Devuelve None si el producto no tiene marca, en cuyo caso no se
        considera duplicado de nada (no hay con qué compararlo con confianza).
        """
        marca = (p.get("marca") or "").lower().strip()
        if not marca:
            return None
        return (marca, (p.get("nombre") or "")[:20].lower().strip())

    def similar_product(self, p1: Dict, p2: Dict) -> bool:
        """Compara dos productos por la clave de deduplicación."""
        clave1 = self.clave_dedup(p1)
        return clave1 is not None and clave1 == self.clave_dedup(p2)

    def merge_y_dedup(self, productos_off: List[Dict], productos_usda: List[Dict],
                      productos_terminados: List[Dict] = None) -> List[Dict]:
        """
        Merge OFF + USDA + terminados, elimina duplicados.
        Prioridad: mantener todos de OFF, agregar el resto sin duplicados.
        """
        self.log(f"[MERGE] Iniciando merge y deduplicación...")

        # Empezar con todos los productos de OFF
        merged = productos_off.copy()
        duplicados = 0

        # Índice de claves de OFF. El bucle anidado original hacía
        # len(OFF) x len(USDA) comparaciones (28.236 x 990 = 28M); con un set
        # el merge es lineal y las mismas reglas de duplicado se conservan.
        claves_off = {c for c in (self.clave_dedup(p) for p in productos_off)
                      if c is not None}

        for p_usda in productos_usda:
            clave = self.clave_dedup(p_usda)
            if clave is not None and clave in claves_off:
                duplicados += 1
                continue
            merged.append(p_usda)

        self.log(f"[MERGE] Duplicados OFF/USDA removidos: {duplicados}")

        # Los terminados salen de la MISMA fuente que `off_productos.json`, asi
        # que un producto puede estar ya en el snapshot con su codigo de barras
        # identico. `clave_dedup` no lo detecta —devuelve None en cuanto falta
        # la marca, y entonces "no es duplicado de nada"—, de modo que sin este
        # segundo filtro por `id_fuente` el merge duplicaria filas con el mismo
        # codigo. `indexar_incremental` las descartaria despues al indexar, pero
        # `productos_merged.json` y el manifest quedarian contando de mas.
        repetidos_id = 0
        if productos_terminados:
            ids_previos = {p["id_fuente"] for p in merged}
            claves_previas = {c for c in (self.clave_dedup(p) for p in merged)
                              if c is not None}
            nuevos = 0
            for p in productos_terminados:
                if p["id_fuente"] in ids_previos:
                    repetidos_id += 1
                    continue
                clave = self.clave_dedup(p)
                if clave is not None and clave in claves_previas:
                    duplicados += 1
                    continue
                merged.append(p)
                ids_previos.add(p["id_fuente"])
                if clave is not None:
                    claves_previas.add(clave)
                nuevos += 1
            self.log(f"[MERGE] Terminados: {nuevos} nuevos, "
                     f"{repetidos_id} ya estaban por id_fuente")

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
        productos_terminados = self.cargar_terminados()

        # 2. Merge y dedup
        merged = self.merge_y_dedup(productos_off, productos_usda,
                                    productos_terminados)

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
