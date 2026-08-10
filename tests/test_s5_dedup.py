"""
S5.5 - EAN Dedup Tests

Tests para lógica de dedup con procedencia y merge.
"""

import pytest
from datetime import datetime
from dominio.producto_catalogo import ProductoCatalogo, FieldWithSource
from adaptadores.catalogo_dedup import CatalogoDedup, MergeStrategy


@pytest.fixture
def temp_db(tmp_path):
    """Crear DB temporal."""
    return str(tmp_path / "test_dedup.db")


@pytest.fixture
def catalogo(temp_db):
    """Instancia de CatalogoDedup."""
    return CatalogoDedup(temp_db)


class TestDedupBasics:
    """Tests básicos de dedup."""

    def test_save_new_product(self, catalogo):
        """Guardar nuevo producto."""
        producto = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-S",
            nombre="Quinoa Orgánica",
            precio=FieldWithSource(valor="12.99", source="N1_VTEX"),
            tienda_id="vitacost",
            transporte="N1_SNAPSHOT",
            url="https://vitacost.com/quinoa",
            insumo_query="quinua",
        )

        merged, conflicts = catalogo.save_or_merge(producto)

        assert merged.ean == "5901234123457"
        assert conflicts is None  # Nuevo, sin conflictos

    def test_merge_same_ean_sku(self, catalogo):
        """Mergear productos con mismo EAN+SKU."""
        # Producto N1 con precio
        p1 = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-S",
            nombre="Quinoa Orgánica",
            precio=FieldWithSource(valor="12.99", source="N1_VTEX"),
            tienda_id="vitacost",
            transporte="N1_SNAPSHOT",
            url="https://vitacost.com/quinoa",
            insumo_query="quinua",
        )

        # Guardar N1
        merged1, conflicts1 = catalogo.save_or_merge(p1)
        assert conflicts1 is None

        # Producto N2 con stock
        p2 = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-S",
            nombre="Quinoa Orgánica",
            stock=FieldWithSource(valor="50", source="N2_BRIGHT_DATA"),
            tienda_id="vitacost",
            transporte="N2_BRIGHT_DATA",
            url="https://bd-api.com/quinoa",
            insumo_query="quinua",
        )

        # Mergear con N2
        merged2, conflicts2 = catalogo.save_or_merge(p2)

        # Debe tener precio de N1 + stock de N2
        assert merged2.precio.valor == "12.99"
        assert merged2.precio.source == "N1_VTEX"
        assert merged2.stock.valor == "50"
        assert merged2.stock.source == "N2_BRIGHT_DATA"
        assert conflicts2 is None  # Sin conflictos (campos diferentes)

    def test_conflict_n1_wins(self, catalogo):
        """Conflicto: N1 gana cuando ambos tienen precio."""
        # N1 con precio
        p1 = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-S",
            nombre="Quinoa",
            precio=FieldWithSource(valor="10.00", source="N1_VTEX"),
            tienda_id="vitacost",
            transporte="N1_SNAPSHOT",
            url="https://vitacost.com",
            insumo_query="quinua",
        )
        catalogo.save_or_merge(p1)

        # N2 con precio diferente
        p2 = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-S",
            nombre="Quinoa",
            precio=FieldWithSource(valor="12.99", source="N2_BRIGHT_DATA"),
            tienda_id="vitacost",
            transporte="N2_BRIGHT_DATA",
            url="https://bd-api.com",
            insumo_query="quinua",
        )
        merged, conflicts = catalogo.save_or_merge(p2)

        # N1 gana (mantiene 10.00)
        assert merged.precio.valor == "10.00"
        assert merged.precio.source == "N1_VTEX"

        # Hay conflicto loguado
        assert conflicts is not None
        assert len(conflicts) == 1
        assert conflicts[0].field == "precio"
        assert conflicts[0].resolution == "kept_existing"

    def test_different_skus_separate_rows(self, catalogo):
        """Mismo EAN pero SKU diferente → filas separadas (tallas)."""
        # Talla S
        p_s = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-S",
            nombre="Quinoa Orgánica S",
            precio=FieldWithSource(valor="12.99", source="N1_VTEX"),
            tienda_id="vitacost",
            transporte="N1_SNAPSHOT",
            url="https://vitacost.com/quinoa-s",
            insumo_query="quinua",
        )

        # Talla M (mismo EAN, SKU diferente)
        p_m = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-001-M",
            nombre="Quinoa Orgánica M",
            precio=FieldWithSource(valor="14.99", source="N1_VTEX"),
            tienda_id="vitacost",
            transporte="N1_SNAPSHOT",
            url="https://vitacost.com/quinoa-m",
            insumo_query="quinua",
        )

        merged_s, _ = catalogo.save_or_merge(p_s)
        merged_m, _ = catalogo.save_or_merge(p_m)

        # Ambas se guardan como filas separadas
        productos = catalogo.get_by_ean("5901234123457")
        assert len(productos) == 2
        skus = {p.sku for p in productos}
        assert skus == {"QUINOA-001-S", "QUINOA-001-M"}


class TestDedupProcedencia:
    """Tests de procedencia tracking."""

    def test_procedencia_tracking(self, catalogo):
        """Cada field mantiene su source."""
        p = ProductoCatalogo(
            ean="123456789",
            sku="SKU-001",
            nombre="Producto",
            marca=FieldWithSource(valor="Brand A", source="N1_VTEX"),
            precio=FieldWithSource(valor="10.00", source="N2_BRIGHT_DATA"),
            stock=FieldWithSource(valor="100", source="N2_BRIGHT_DATA"),
            tienda_id="tienda1",
            transporte="N2_BRIGHT_DATA",
            url="https://example.com",
            insumo_query="producto",
        )

        merged, _ = catalogo.save_or_merge(p)

        assert merged.marca.source == "N1_VTEX"
        assert merged.precio.source == "N2_BRIGHT_DATA"
        assert merged.stock.source == "N2_BRIGHT_DATA"


class TestDedupStats:
    """Tests de estadísticas."""

    def test_catalog_stats(self, catalogo):
        """Estadísticas del catálogo."""
        # Insertar algunos productos
        for i in range(3):
            p = ProductoCatalogo(
                ean=f"EAN-{i:03d}",
                sku=f"SKU-{i:03d}",
                nombre=f"Producto {i}",
                tienda_id="tienda1",
                transporte="N1_SNAPSHOT",
                url="https://example.com",
                insumo_query="test",
            )
            catalogo.save_or_merge(p)

        stats = catalogo.get_stats()
        assert stats["total_productos"] == 3
        assert stats["unique_eans"] == 3
        assert stats["merge_rate_pct"] == 0  # Sin merges aún


class TestIntegrationP14:
    """Scenarios realistas para P14."""

    def test_p14_dedup_scenario(self, catalogo):
        """
        Escenario P14: búsqueda "quinua", N1 + N2.
        - N1 aporta precio
        - N2 aporta stock
        - Dedup une ambos con procedencia
        """
        # N1: Vitacost con precio
        n1_vitacost = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-ORG-1KG",
            nombre="Quinoa Orgánica 1kg",
            precio=FieldWithSource(valor="18.99", source="N1_VTEX"),
            marca=FieldWithSource(valor="NaturesPath", source="N1_VTEX"),
            tienda_id="vitacost",
            transporte="N1_SNAPSHOT",
            url="https://vitacost.com/quinoa",
            insumo_query="quinua",
        )

        # N2: Bright Data con stock
        n2_bright = ProductoCatalogo(
            ean="5901234123457",
            sku="QUINOA-ORG-1KG",
            nombre="Quinoa Orgánica 1kg",
            stock=FieldWithSource(valor="127", source="N2_BRIGHT_DATA"),
            categoria=FieldWithSource(valor="Grains & Seeds", source="N2_BRIGHT_DATA"),
            tienda_id="vitacost",
            transporte="N2_BRIGHT_DATA",
            url="https://bright-data.com/snapshot-123",
            insumo_query="quinua",
        )

        # Guardar N1
        merged1, _ = catalogo.save_or_merge(n1_vitacost)
        assert merged1.precio.valor == "18.99"

        # Mergear con N2
        merged2, conflicts = catalogo.save_or_merge(n2_bright)

        # Resultado final: precio N1 + stock N2
        assert merged2.precio.valor == "18.99"
        assert merged2.precio.source == "N1_VTEX"
        assert merged2.stock.valor == "127"
        assert merged2.stock.source == "N2_BRIGHT_DATA"
        assert merged2.categoria.valor == "Grains & Seeds"
        assert merged2.categoria.source == "N2_BRIGHT_DATA"

        # Sin conflictos (campos complementarios)
        assert conflicts is None

        print("✅ P14 dedup scenario: N1 precio + N2 stock merged correctly")
