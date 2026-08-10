"""
S3.5 Motor de tendencias: Análisis determinista de precios y marcas.

Calcula para cada insumo/trimestre:
- % cambio de precio vs trimestre anterior
- Marcas nuevas (EANs que entraron)
- Marcas que salieron
- Volatilidad de stock (Coefficient of Variation)
- % de productos con promoción

Datos origen: shelf_facts_quarterly en DuckDB
Datos salida: PostgreSQL table tendencias_insumo
"""

import duckdb
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


class MotorTendenciasDuckDB:
    """
    Deterministic trend analysis from Shelf Radar quarterly data.

    No LLM, no proxies: pure statistical calculations.
    """

    def __init__(self, duckdb_path: str = "shelf_facts.duckdb"):
        """Initialize with path to DuckDB file."""
        self.duckdb_path = Path(duckdb_path)
        self.conn: Optional[duckdb.DuckDBPyConnection] = None

    def conectar(self) -> duckdb.DuckDBPyConnection:
        """Get or create DuckDB connection."""
        if self.conn is None:
            if not self.duckdb_path.exists():
                raise FileNotFoundError(f"DuckDB file not found: {self.duckdb_path}")
            self.conn = duckdb.connect(str(self.duckdb_path))
        return self.conn

    def get_available_quarters(self, insumo: str) -> List[str]:
        """Get sorted list of available quarters for an ingredient."""
        conn = self.conectar()
        try:
            result = conn.execute("""
                SELECT DISTINCT year_quarter
                FROM shelf_facts_quarterly
                WHERE insumo = ?
                ORDER BY year_quarter ASC
            """, (insumo,)).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Error fetching quarters for {insumo}: {e}")
            return []

    def calcular_tendencias(self, insumo: str, ano_base: int = 2026) -> Optional[Dict]:
        """
        Calculate trends for an ingredient across available quarters.

        Args:
            insumo: Ingredient name (e.g., 'quinua')
            ano_base: Base year (default 2026)

        Returns:
            {
                "insumo": "quinua",
                "year_quarter": "2026Q3",
                "precio_trend": -5.2,  # % change vs previous quarter
                "marcas_nuevas": 2,
                "marcas_salidas": 1,
                "volatilidad": 0.23,  # CV (std/mean) of stock
                "promocion_pct": 15.5,  # % products with promotions
                "precio_promedio": 4.75,
                "timestamp": "2026-08-09T..."
            }
        """
        conn = self.conectar()

        try:
            # Get all quarters for this ingredient, sorted
            quarters = self.get_available_quarters(insumo)
            if not quarters:
                logger.warning(f"No data found for {insumo}")
                return None

            # Get latest quarter
            latest_quarter = quarters[-1]

            # Get previous quarter (for % change calculation)
            prev_quarter = quarters[-2] if len(quarters) > 1 else None

            # Current quarter metrics
            current_data = conn.execute("""
                SELECT
                    COUNT(DISTINCT producto_ean) as total_products,
                    COUNT(DISTINCT CASE WHEN promociones_count > 0 THEN producto_ean END) as promos_count,
                    AVG(precio_promedio) as precio_prom,
                    AVG(stock_promedio) as stock_prom,
                    STDDEV_POP(stock_promedio) as stock_stddev
                FROM shelf_facts_quarterly
                WHERE insumo = ? AND year_quarter = ?
            """, (insumo, latest_quarter)).fetchone()

            if not current_data:
                logger.warning(f"No data for {insumo} in {latest_quarter}")
                return None

            (total_products, promos_count, precio_prom, stock_prom,
             stock_stddev) = current_data

            # Calculate volatility (Coefficient of Variation)
            volatilidad = 0.0
            if stock_prom and stock_prom > 0:
                volatilidad = (stock_stddev or 0) / stock_prom

            # Calculate promotion percentage
            promocion_pct = 0.0
            if total_products > 0:
                promocion_pct = (promos_count / total_products) * 100

            # Calculate price change vs previous quarter
            precio_trend = 0.0
            if prev_quarter:
                prev_precio = conn.execute("""
                    SELECT AVG(precio_promedio)
                    FROM shelf_facts_quarterly
                    WHERE insumo = ? AND year_quarter = ?
                """, (insumo, prev_quarter)).fetchone()

                if prev_precio and prev_precio[0]:
                    prev_prom = prev_precio[0]
                    precio_trend = ((precio_prom - prev_prom) / prev_prom) * 100

            # Calculate new brands (EANs that exist now but not in previous quarter)
            marcas_nuevas = 0
            marcas_salidas = 0
            if prev_quarter:
                # Get EANs in current quarter
                current_eans = conn.execute("""
                    SELECT DISTINCT producto_ean
                    FROM shelf_facts_quarterly
                    WHERE insumo = ? AND year_quarter = ?
                """, (insumo, latest_quarter)).fetchall()
                current_eans_set = {row[0] for row in current_eans}

                # Get EANs in previous quarter
                prev_eans = conn.execute("""
                    SELECT DISTINCT producto_ean
                    FROM shelf_facts_quarterly
                    WHERE insumo = ? AND year_quarter = ?
                """, (insumo, prev_quarter)).fetchall()
                prev_eans_set = {row[0] for row in prev_eans}

                marcas_nuevas = len(current_eans_set - prev_eans_set)
                marcas_salidas = len(prev_eans_set - current_eans_set)

            return {
                "insumo": insumo,
                "year_quarter": latest_quarter,
                "precio_trend": round(precio_trend, 2),  # % change
                "precio_promedio": round(precio_prom, 2),
                "marcas_nuevas": marcas_nuevas,
                "marcas_salidas": marcas_salidas,
                "volatilidad": round(volatilidad, 4),  # CV
                "promocion_pct": round(promocion_pct, 2),
                "total_products": total_products,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error calculating trends for {insumo}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def calcular_todas_tendencias(self, ano_base: int = 2026) -> List[Dict]:
        """
        Calculate trends for all available ingredients.

        Returns:
            List of trend dicts (one per ingredient)
        """
        conn = self.conectar()

        try:
            # Get unique ingredients
            insumos = conn.execute("""
                SELECT DISTINCT insumo
                FROM shelf_facts_quarterly
                ORDER BY insumo
            """).fetchall()

            resultados = []
            for (insumo,) in insumos:
                tendencia = self.calcular_tendencias(insumo, ano_base)
                if tendencia:
                    resultados.append(tendencia)

            return resultados

        except Exception as e:
            logger.error(f"Error calculating all trends: {e}")
            return []

    def cerrar(self):
        """Close DuckDB connection."""
        if self.conn:
            self.conn.close()
            self.conn = None


# Backward compatibility for S1/S2
class MotorTendenciasDuckDBStub(MotorTendenciasDuckDB):
    """Stub version for testing without data."""

    def get_available_quarters(self, insumo: str) -> List[str]:
        return ["2026Q2", "2026Q3"]

    def calcular_tendencias(self, insumo: str, ano_base: int = 2026) -> Optional[Dict]:
        return {
            "insumo": insumo,
            "year_quarter": "2026Q3",
            "precio_trend": -2.5,
            "precio_promedio": 4.50,
            "marcas_nuevas": 2,
            "marcas_salidas": 0,
            "volatilidad": 0.18,
            "promocion_pct": 12.5,
            "total_products": 15,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
