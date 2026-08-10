"""
S3.5 Trend repository: Save calculated trends to PostgreSQL.

Stores results from motor_tendencias_duckdb.calcular_tendencias()
into the tendencias_insumo table for reuse across runs.
"""

import logging
import psycopg
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class RepositorioTendencias:
    """Store and retrieve trend calculations from PostgreSQL."""

    def __init__(self, db_url: str):
        """Initialize with database URL."""
        self.db_url = db_url

    def guardar_tendencia(self, tendencia: Dict) -> bool:
        """
        Save a single trend calculation to tendencias_insumo.

        Args:
            tendencia: Dict from motor_tendencias_duckdb.calcular_tendencias()
                {
                    "insumo": "quinua",
                    "year_quarter": "2026Q3",
                    "precio_trend": -2.5,
                    "precio_promedio": 4.50,
                    "marcas_nuevas": 2,
                    "marcas_salidas": 0,
                    "volatilidad": 0.18,
                    "promocion_pct": 12.5,
                    "total_products": 15,
                    "timestamp": "2026-08-09T..."
                }

        Returns:
            True if saved successfully
        """
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO tendencias_insumo
                    (insumo, year_quarter, precio_trend, precio_promedio,
                     marcas_nuevas, marcas_salidas, volatilidad, promocion_pct,
                     total_products, calculado_en)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (insumo, year_quarter) DO UPDATE SET
                        precio_trend = EXCLUDED.precio_trend,
                        precio_promedio = EXCLUDED.precio_promedio,
                        marcas_nuevas = EXCLUDED.marcas_nuevas,
                        marcas_salidas = EXCLUDED.marcas_salidas,
                        volatilidad = EXCLUDED.volatilidad,
                        promocion_pct = EXCLUDED.promocion_pct,
                        total_products = EXCLUDED.total_products,
                        calculado_en = EXCLUDED.calculado_en
                """, (
                    tendencia["insumo"],
                    tendencia["year_quarter"],
                    tendencia.get("precio_trend"),
                    tendencia.get("precio_promedio"),
                    tendencia.get("marcas_nuevas", 0),
                    tendencia.get("marcas_salidas", 0),
                    tendencia.get("volatilidad"),
                    tendencia.get("promocion_pct"),
                    tendencia.get("total_products", 0),
                    datetime.now(timezone.utc),
                ))
                conn.commit()
                logger.info(f"✅ Saved trend: {tendencia['insumo']} {tendencia['year_quarter']}")
                return True
        except Exception as e:
            logger.error(f"❌ Error saving trend: {e}")
            return False
        finally:
            conn.close()

    def guardar_tendencias_batch(self, tendencias: List[Dict]) -> int:
        """
        Save multiple trends in a single transaction.

        Args:
            tendencias: List of trend dicts

        Returns:
            Count of successfully saved trends
        """
        saved_count = 0
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                for tendencia in tendencias:
                    try:
                        cur.execute("""
                            INSERT INTO tendencias_insumo
                            (insumo, year_quarter, precio_trend, precio_promedio,
                             marcas_nuevas, marcas_salidas, volatilidad, promocion_pct,
                             total_products, calculado_en)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (insumo, year_quarter) DO UPDATE SET
                                precio_trend = EXCLUDED.precio_trend,
                                precio_promedio = EXCLUDED.precio_promedio,
                                marcas_nuevas = EXCLUDED.marcas_nuevas,
                                marcas_salidas = EXCLUDED.marcas_salidas,
                                volatilidad = EXCLUDED.volatilidad,
                                promocion_pct = EXCLUDED.promocion_pct,
                                total_products = EXCLUDED.total_products,
                                calculado_en = EXCLUDED.calculado_en
                        """, (
                            tendencia["insumo"],
                            tendencia["year_quarter"],
                            tendencia.get("precio_trend"),
                            tendencia.get("precio_promedio"),
                            tendencia.get("marcas_nuevas", 0),
                            tendencia.get("marcas_salidas", 0),
                            tendencia.get("volatilidad"),
                            tendencia.get("promocion_pct"),
                            tendencia.get("total_products", 0),
                            datetime.now(timezone.utc),
                        ))
                        saved_count += 1
                    except Exception as e:
                        logger.warning(f"⚠️  Error saving {tendencia.get('insumo')}: {e}")
            conn.commit()
            logger.info(f"✅ Saved {saved_count}/{len(tendencias)} trends")
            return saved_count
        except Exception as e:
            logger.error(f"❌ Batch save error: {e}")
            return 0
        finally:
            conn.close()

    def obtener_tendencia(self, insumo: str, year_quarter: str) -> Optional[Dict]:
        """Get a specific trend from database."""
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT insumo, year_quarter, precio_trend, precio_promedio,
                           marcas_nuevas, marcas_salidas, volatilidad, promocion_pct,
                           total_products, calculado_en
                    FROM tendencias_insumo
                    WHERE insumo = %s AND year_quarter = %s
                """, (insumo, year_quarter))

                row = cur.fetchone()
                if row:
                    return {
                        "insumo": row[0],
                        "year_quarter": row[1],
                        "precio_trend": float(row[2]) if row[2] else None,
                        "precio_promedio": float(row[3]) if row[3] else None,
                        "marcas_nuevas": row[4],
                        "marcas_salidas": row[5],
                        "volatilidad": float(row[6]) if row[6] else None,
                        "promocion_pct": float(row[7]) if row[7] else None,
                        "total_products": row[8],
                        "calculado_en": row[9].isoformat() if row[9] else None,
                    }
                return None
        except Exception as e:
            logger.error(f"❌ Error fetching trend: {e}")
            return None
        finally:
            conn.close()

    def obtener_tendencias_insumo(self, insumo: str, limit: int = 10) -> List[Dict]:
        """Get trend history for an ingredient, sorted by quarter."""
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT insumo, year_quarter, precio_trend, precio_promedio,
                           marcas_nuevas, marcas_salidas, volatilidad, promocion_pct,
                           total_products, calculado_en
                    FROM tendencias_insumo
                    WHERE insumo = %s
                    ORDER BY year_quarter DESC
                    LIMIT %s
                """, (insumo, limit))

                rows = cur.fetchall()
                return [
                    {
                        "insumo": row[0],
                        "year_quarter": row[1],
                        "precio_trend": float(row[2]) if row[2] else None,
                        "precio_promedio": float(row[3]) if row[3] else None,
                        "marcas_nuevas": row[4],
                        "marcas_salidas": row[5],
                        "volatilidad": float(row[6]) if row[6] else None,
                        "promocion_pct": float(row[7]) if row[7] else None,
                        "total_products": row[8],
                        "calculado_en": row[9].isoformat() if row[9] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"❌ Error fetching trend history: {e}")
            return []
        finally:
            conn.close()

    def obtener_todas_tendencias(self, year_quarter: Optional[str] = None) -> List[Dict]:
        """Get all trends, optionally filtered by quarter."""
        try:
            conn = psycopg.connect(self.db_url)
            with conn.cursor() as cur:
                if year_quarter:
                    cur.execute("""
                        SELECT insumo, year_quarter, precio_trend, precio_promedio,
                               marcas_nuevas, marcas_salidas, volatilidad, promocion_pct,
                               total_products, calculado_en
                        FROM tendencias_insumo
                        WHERE year_quarter = %s
                        ORDER BY insumo
                    """, (year_quarter,))
                else:
                    cur.execute("""
                        SELECT insumo, year_quarter, precio_trend, precio_promedio,
                               marcas_nuevas, marcas_salidas, volatilidad, promocion_pct,
                               total_products, calculado_en
                        FROM tendencias_insumo
                        ORDER BY year_quarter DESC, insumo
                    """)

                rows = cur.fetchall()
                return [
                    {
                        "insumo": row[0],
                        "year_quarter": row[1],
                        "precio_trend": float(row[2]) if row[2] else None,
                        "precio_promedio": float(row[3]) if row[3] else None,
                        "marcas_nuevas": row[4],
                        "marcas_salidas": row[5],
                        "volatilidad": float(row[6]) if row[6] else None,
                        "promocion_pct": float(row[7]) if row[7] else None,
                        "total_products": row[8],
                        "calculado_en": row[9].isoformat() if row[9] else None,
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"❌ Error fetching all trends: {e}")
            return []
        finally:
            conn.close()
