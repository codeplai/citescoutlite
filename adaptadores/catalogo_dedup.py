"""
S5.5 - Catálogo Dedup Repository

Maneja deduplicación por (EAN, SKU) con merge inteligente.
Procedencia tracking: cada field mantiene su source.
Conflictos: N1 gana, logged en audit_log.
"""

import logging
import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Optional, Tuple
from enum import Enum

from dominio.producto_catalogo import ProductoCatalogo, DeduplicationConflict
from .audit_log import AuditLogRepository, AuditLogEntry, AuditLogLevel

logger = logging.getLogger(__name__)


class MergeStrategy(str, Enum):
    """Estrategia de merge para conflictos."""
    N1_WINS = "n1_wins"        # N1 gana en todo
    UNION = "union"            # Merge campos (N1 priority en conflictos)
    LATEST = "latest"          # Timestamp más reciente gana


class CatalogoDedup:
    """Repositorio de catálogo con dedup por (EAN, SKU)."""

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS catalogo_productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ean TEXT NOT NULL,
        sku TEXT NOT NULL,
        nombre TEXT NOT NULL,
        marca_valor TEXT,
        marca_source TEXT,
        descripcion_valor TEXT,
        descripcion_source TEXT,
        categoria_valor TEXT,
        categoria_source TEXT,
        precio_valor TEXT,
        precio_source TEXT,
        stock_valor TEXT,
        stock_source TEXT,
        moneda_valor TEXT,
        moneda_source TEXT,
        tienda_id TEXT NOT NULL,
        transporte TEXT NOT NULL,
        url TEXT NOT NULL,
        insumo_query TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        conflict_log TEXT,
        UNIQUE(ean, sku, tienda_id)
    );
    CREATE INDEX IF NOT EXISTS idx_catalogo_ean ON catalogo_productos(ean);
    CREATE INDEX IF NOT EXISTS idx_catalogo_sku ON catalogo_productos(sku);
    CREATE INDEX IF NOT EXISTS idx_catalogo_tienda ON catalogo_productos(tienda_id);
    CREATE INDEX IF NOT EXISTS idx_catalogo_insumo ON catalogo_productos(insumo_query);

    CREATE TABLE IF NOT EXISTS dedup_conflicts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        field TEXT NOT NULL,
        ean TEXT NOT NULL,
        sku TEXT NOT NULL,
        existing_value TEXT,
        existing_source TEXT,
        new_value TEXT,
        new_source TEXT,
        resolution TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_conflicts_ean ON dedup_conflicts(ean);
    """

    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self.audit_repo = AuditLogRepository(db_path)
        self._ensure_schema()

    def _ensure_schema(self):
        """Crear tablas si no existen."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            for stmt in self.SCHEMA.split(";"):
                if stmt.strip():
                    conn.execute(stmt)

    def save_or_merge(
        self,
        producto: ProductoCatalogo,
        strategy: MergeStrategy = MergeStrategy.UNION,
    ) -> Tuple[ProductoCatalogo, Optional[list[DeduplicationConflict]]]:
        """
        Guardar o mergear producto.

        Args:
            producto: Nuevo producto a guardar
            strategy: Estrategia de merge en conflictos

        Returns:
            (producto_final, lista_de_conflictos)
        """
        # Buscar existente
        existing = self._get_by_ean_sku(producto.ean, producto.sku, producto.tienda_id)

        if existing is None:
            # Nuevo: solo guardar
            self._insert_producto(producto)
            logger.info(f"Catálogo: New product EAN={producto.ean}, SKU={producto.sku}")
            return producto, None

        # Existe: mergear
        merged, conflicts = self._merge_productos(existing, producto, strategy)
        self._update_producto(merged)

        logger.info(
            f"Catálogo: Merged EAN={merged.ean}, SKU={merged.sku}, "
            f"conflicts={len(conflicts) if conflicts else 0}"
        )

        # Log conflicts en audit_log
        if conflicts:
            for conflict in conflicts:
                self._log_conflict(conflict)

        return merged, conflicts

    def _get_by_ean_sku(
        self,
        ean: str,
        sku: str,
        tienda_id: str,
    ) -> Optional[ProductoCatalogo]:
        """Obtener producto existente."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM catalogo_productos
                WHERE ean = ? AND sku = ? AND tienda_id = ?
            """, (ean, sku, tienda_id)).fetchone()

            if row is None:
                return None

            return self._row_to_producto(row)

    def _merge_productos(
        self,
        existing: ProductoCatalogo,
        new: ProductoCatalogo,
        strategy: MergeStrategy,
    ) -> Tuple[ProductoCatalogo, list[DeduplicationConflict]]:
        """
        Mergear dos productos.

        Estrategia UNION (default):
        - Si new field es null: mantener existing
        - Si new field no es null:
          - Si existing field es null: usar new (merge)
          - Si ambos no null: N1 gana, log conflict
        """
        conflicts = []
        merged = existing.model_copy(deep=True)
        merged.updated_at = datetime.utcnow()

        # Campos con procedencia para mergear
        fields_to_merge = [
            "marca", "descripcion", "categoria",
            "precio", "stock", "moneda"
        ]

        for field_name in fields_to_merge:
            existing_field = getattr(existing, field_name)
            new_field = getattr(new, field_name)

            if new_field is None or new_field.valor is None:
                # Nuevo no aporta, mantener existing
                continue

            if existing_field is None or existing_field.valor is None:
                # Existing no tiene, usar new (merge)
                setattr(merged, field_name, new_field)
            else:
                # Ambos tienen datos: conflict
                # Solución: N1 gana si N1, sino new gana
                is_new_n1 = new_field.source and "N1" in new_field.source
                is_existing_n1 = existing_field.source and "N1" in existing_field.source

                if is_existing_n1 and not is_new_n1:
                    # Existing es N1, new no → N1 gana (mantener existing)
                    conflict = DeduplicationConflict(
                        field=field_name,
                        ean=existing.ean,
                        sku=existing.sku,
                        existing_value=existing_field.valor,
                        existing_source=existing_field.source,
                        new_value=new_field.valor,
                        new_source=new_field.source,
                        resolution="kept_existing",
                    )
                    conflicts.append(conflict)
                else:
                    # New gana (o ambos N1/N2, newer wins)
                    setattr(merged, field_name, new_field)
                    conflict = DeduplicationConflict(
                        field=field_name,
                        ean=existing.ean,
                        sku=existing.sku,
                        existing_value=existing_field.valor,
                        existing_source=existing_field.source,
                        new_value=new_field.valor,
                        new_source=new_field.source,
                        resolution="merged",
                    )
                    conflicts.append(conflict)

        # Log de conflicto en metadata
        if conflicts:
            conflict_summary = "; ".join(
                f"{c.field}: {c.existing_source}→{c.new_source}"
                for c in conflicts
            )
            merged.conflict_log = conflict_summary

        return merged, conflicts

    def _insert_producto(self, producto: ProductoCatalogo) -> None:
        """Guardar nuevo producto."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                INSERT INTO catalogo_productos
                (ean, sku, nombre, marca_valor, marca_source,
                 descripcion_valor, descripcion_source, categoria_valor, categoria_source,
                 precio_valor, precio_source, stock_valor, stock_source,
                 moneda_valor, moneda_source, tienda_id, transporte, url, insumo_query,
                 created_at, updated_at, conflict_log)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, self._producto_to_row(producto))

    def _update_producto(self, producto: ProductoCatalogo) -> None:
        """Actualizar producto existente."""
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = self._producto_to_row(producto)
            conn.execute("""
                UPDATE catalogo_productos
                SET nombre=?, marca_valor=?, marca_source=?,
                    descripcion_valor=?, descripcion_source=?, categoria_valor=?, categoria_source=?,
                    precio_valor=?, precio_source=?, stock_valor=?, stock_source=?,
                    moneda_valor=?, moneda_source=?, transporte=?, url=?, updated_at=?, conflict_log=?
                WHERE ean=? AND sku=? AND tienda_id=?
            """, (
                row[2], row[3], row[4],  # nombre, marca_valor, marca_source
                row[5], row[6], row[7], row[8],  # descripcion_valor, source, categoria_valor, source
                row[9], row[10], row[11], row[12],  # precio_valor, source, stock_valor, source
                row[13], row[14], row[15], row[16],  # moneda_valor, source, transporte, url
                row[19], row[20],  # updated_at, conflict_log
                row[0], row[1], row[16],  # ean, sku, tienda_id
            ))

    def _producto_to_row(self, p: ProductoCatalogo) -> tuple:
        """Convertir ProductoCatalogo a tupla para DB."""
        return (
            p.ean, p.sku, p.nombre,
            p.marca.valor if p.marca else None,
            p.marca.source if p.marca else None,
            p.descripcion.valor if p.descripcion else None,
            p.descripcion.source if p.descripcion else None,
            p.categoria.valor if p.categoria else None,
            p.categoria.source if p.categoria else None,
            p.precio.valor if p.precio else None,
            p.precio.source if p.precio else None,
            p.stock.valor if p.stock else None,
            p.stock.source if p.stock else None,
            p.moneda.valor if p.moneda else None,
            p.moneda.source if p.moneda else None,
            p.tienda_id,
            p.transporte,
            p.url,
            p.insumo_query,
            p.created_at.isoformat(),
            p.updated_at.isoformat(),
            p.conflict_log,
        )

    def _row_to_producto(self, row: sqlite3.Row) -> ProductoCatalogo:
        """Convertir row a ProductoCatalogo."""
        from dominio.producto_catalogo import FieldWithSource

        return ProductoCatalogo(
            ean=row["ean"],
            sku=row["sku"],
            nombre=row["nombre"],
            marca=FieldWithSource(valor=row["marca_valor"], source=row["marca_source"]) if row["marca_valor"] else None,
            descripcion=FieldWithSource(valor=row["descripcion_valor"], source=row["descripcion_source"]) if row["descripcion_valor"] else None,
            categoria=FieldWithSource(valor=row["categoria_valor"], source=row["categoria_source"]) if row["categoria_valor"] else None,
            precio=FieldWithSource(valor=row["precio_valor"], source=row["precio_source"]) if row["precio_valor"] else None,
            stock=FieldWithSource(valor=row["stock_valor"], source=row["stock_source"]) if row["stock_valor"] else None,
            moneda=FieldWithSource(valor=row["moneda_valor"], source=row["moneda_source"]) if row["moneda_valor"] else None,
            tienda_id=row["tienda_id"],
            transporte=row["transporte"],
            url=row["url"],
            insumo_query=row["insumo_query"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            conflict_log=row["conflict_log"],
        )

    def _log_conflict(self, conflict: DeduplicationConflict) -> None:
        """Registrar conflicto en audit_log."""
        self.audit_repo.log(AuditLogEntry(
            level=AuditLogLevel.INFO,
            component="dedup",
            message=f"Conflict: {conflict.field} EAN={conflict.ean} ({conflict.existing_source}→{conflict.new_source})",
            data={
                "field": conflict.field,
                "ean": conflict.ean,
                "sku": conflict.sku,
                "existing": f"{conflict.existing_value}@{conflict.existing_source}",
                "new": f"{conflict.new_value}@{conflict.new_source}",
                "resolution": conflict.resolution,
            },
        ))

    def get_by_ean(self, ean: str) -> list[ProductoCatalogo]:
        """Obtener todos los productos con un EAN (puede haber múltiples por tienda/SKU)."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM catalogo_productos WHERE ean = ? ORDER BY tienda_id, sku
            """, (ean,)).fetchall()
            return [self._row_to_producto(row) for row in rows]

    def get_stats(self) -> dict:
        """Estadísticas del catálogo."""
        with closing(sqlite3.connect(self.db_path)) as conn:
            total = conn.execute("SELECT COUNT(*) FROM catalogo_productos").fetchone()[0]
            unique_eans = conn.execute("SELECT COUNT(DISTINCT ean) FROM catalogo_productos").fetchone()[0]
            with_conflicts = conn.execute(
                "SELECT COUNT(*) FROM catalogo_productos WHERE conflict_log IS NOT NULL"
            ).fetchone()[0]

            return {
                "total_productos": total,
                "unique_eans": unique_eans,
                "productos_con_conflictos": with_conflicts,
                "merge_rate_pct": (with_conflicts / total * 100) if total > 0 else 0,
            }
