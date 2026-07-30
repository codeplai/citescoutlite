"""
Motor de tendencias con DuckDB.
Análisis de series temporales de productos en OFF.
Preparado para S4 (etapa 4: Formulación).
"""

import duckdb
from typing import List, Dict, Optional


class MotorTendenciasDuckDB:
    def __init__(self, snapshot_path: str = "datasets/2026-07"):
        self.snapshot_path = snapshot_path
        self.conn = None

    def conectar(self) -> duckdb.DuckDBPyConnection:
        """Conecta a la base de datos DuckDB."""
        if self.conn is None:
            db_path = f"{self.snapshot_path}/datos.duckdb"
            self.conn = duckdb.connect(db_path)
        return self.conn

    def crear_schema_historico(self):
        """Crea tabla de histórico de productos (diferido a S4)."""
        conn = self.conectar()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS historico_productos (
                id_fuente VARCHAR,
                insumo VARCHAR,
                nombre VARCHAR,
                ingredientes VARCHAR,
                fecha DATE,
                trimestre VARCHAR,
                categorias VARCHAR,
                pais VARCHAR
            )
        """)

    def mineria_formulacion(self, insumo: str, limite: int = 5) -> List[str]:
        """
        Extrae hipótesis de formulación del histórico.
        Busca patrones en ingredientes usados con este insumo.
        """
        conn = self.conectar()

        query = f"""
            SELECT DISTINCT ingredientes
            FROM historico_productos
            WHERE insumo = '{insumo}'
            ORDER BY fecha DESC
            LIMIT {limite}
        """

        try:
            resultado = conn.execute(query).fetchall()
            return [r[0] for r in resultado if r[0]]
        except Exception as e:
            print(f"Error en minería de formulación: {e}")
            return []

    def tendencias_por_trimestre(self, insumo: str) -> List[Dict]:
        """
        Calcula tendencias por trimestre: nuevas marcas, cambios de ingredientes.
        Mínimo 8 trimestres para detectar patrones.
        """
        conn = self.conectar()

        query = f"""
            SELECT
                trimestre,
                COUNT(DISTINCT id_fuente) as total_productos,
                COUNT(DISTINCT pais) as paises,
                COUNT(DISTINCT nombre) as nuevos_nombres
            FROM historico_productos
            WHERE insumo = '{insumo}'
            GROUP BY trimestre
            ORDER BY trimestre DESC
            LIMIT 8
        """

        try:
            resultados = conn.execute(query).fetchall()
            return [
                {
                    "trimestre": r[0],
                    "total_productos": r[1],
                    "paises": r[2],
                    "nuevos_nombres": r[3]
                }
                for r in resultados
            ]
        except Exception as e:
            print(f"Error en tendencias: {e}")
            return []

    def cerrar(self):
        """Cierra la conexión."""
        if self.conn:
            self.conn.close()
            self.conn = None


# Stub para S1: solo estructura, sin datos
class MotorTendenciasDuckDBStub(MotorTendenciasDuckDB):
    """Versión stub para demostración sin datos reales."""

    def mineria_formulacion(self, insumo: str, limite: int = 5) -> List[str]:
        return [
            "[S4] Minería de formulación disponible después de 8+ trimestres",
            f"Insumo: {insumo}",
        ]

    def tendencias_por_trimestre(self, insumo: str) -> List[Dict]:
        return [
            {
                "trimestre": "2026-Q3",
                "total_productos": 0,
                "paises": 0,
                "nuevos_nombres": 0
            }
        ]
