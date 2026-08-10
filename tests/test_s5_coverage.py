"""
S5.6 - Coverage Metadata Tests

Tests para cálculo y persistencia de cobertura.
"""

import pytest
from datetime import datetime
from uuid import uuid4

from adaptadores.sweep_attempts import (
    SweepAttemptsRepository,
    SweepAttempt,
    SweepAttemptStatus,
)
from adaptadores.cobertura_calculator import CoberturaCalculator
from dominio.cobertura_metadata import CoberturaMetadata


@pytest.fixture
def temp_db(tmp_path):
    """DB temporal."""
    return str(tmp_path / "test_coverage.db")


@pytest.fixture
def sweep_repo(temp_db):
    """SweepAttemptsRepository."""
    return SweepAttemptsRepository(temp_db)


@pytest.fixture
def coverage_calc(temp_db):
    """CoberturaCalculator."""
    return CoberturaCalculator(temp_db)


class TestCoverageCalculation:
    """Tests de cálculo de cobertura."""

    def test_calculate_empty_sweep(self, coverage_calc):
        """Sweep sin attempts."""
        sweep_id = str(uuid4())
        result = coverage_calc.calculate_coverage(sweep_id, "quinua")
        assert result is None

    def test_calculate_simple(self, sweep_repo, coverage_calc):
        """Calcular cobertura simple."""
        sweep_id = "sweep_001"

        # 10 tiendas: 7 ok, 2 blocked_policy, 1 failed
        attempts = [
            SweepAttempt(sweep_id, f"store_{i:02d}", SweepAttemptStatus.OK, "N1_SNAPSHOT", offers_found=20+i)
            for i in range(7)
        ]
        for i in range(2):
            attempts.append(SweepAttempt(sweep_id, f"blocked_{i}", SweepAttemptStatus.BLOCKED_POLICY, "N1_SNAPSHOT"))
        attempts.append(SweepAttempt(sweep_id, "failed_store", SweepAttemptStatus.FAILED, "N1_SNAPSHOT"))

        sweep_repo.save_batch(attempts)

        # Calcular
        metadata = coverage_calc.calculate_coverage(sweep_id, "quinua")

        assert metadata is not None
        assert metadata.in_scope == 10
        assert metadata.verified == 7
        assert metadata.blocked_policy == 2
        assert metadata.failed == 1
        assert metadata.coverage_pct == 70.0
        assert metadata.publishable is True  # 70% > 60%

    def test_coverage_unpublishable(self, sweep_repo, coverage_calc):
        """Cobertura < 60% no publicable."""
        sweep_id = "sweep_low_coverage"

        # 10 tiendas: 5 ok, 5 blocked
        attempts = [
            SweepAttempt(sweep_id, f"ok_{i}", SweepAttemptStatus.OK, "N1_SNAPSHOT", offers_found=10)
            for i in range(5)
        ]
        for i in range(5):
            attempts.append(SweepAttempt(sweep_id, f"blocked_{i}", SweepAttemptStatus.BLOCKED_SERVER, "N1_SNAPSHOT"))

        sweep_repo.save_batch(attempts)

        metadata = coverage_calc.calculate_coverage(sweep_id, "test")

        assert metadata.coverage_pct == 50.0
        assert metadata.publishable is False  # 50% < 60%

    def test_p14_scenario(self, sweep_repo, coverage_calc):
        """
        P14: búsqueda "quinua" con 97 tiendas.
        - 72 ok
        - 15 blocked_policy
        - 5 blocked_server
        - 3 blocked_robots
        - 2 skipped_budget
        Coverage: 72/97 = 74.2%, publishable=true
        """
        sweep_id = "p14_quinua_sweep"

        attempts = []

        # 72 ok
        for i in range(72):
            attempts.append(SweepAttempt(
                sweep_id,
                f"store_ok_{i:03d}",
                SweepAttemptStatus.OK,
                "N1_SNAPSHOT",
                offers_found=25 + i % 20,
            ))

        # 15 blocked_policy
        for i in range(15):
            attempts.append(SweepAttempt(
                sweep_id,
                f"store_policy_{i:02d}",
                SweepAttemptStatus.BLOCKED_POLICY,
                "N1_SNAPSHOT",
            ))

        # 5 blocked_server
        for i in range(5):
            attempts.append(SweepAttempt(
                sweep_id,
                f"store_server_{i:02d}",
                SweepAttemptStatus.BLOCKED_SERVER,
                "N1_SNAPSHOT",
            ))

        # 3 blocked_robots
        for i in range(3):
            attempts.append(SweepAttempt(
                sweep_id,
                f"store_robots_{i:02d}",
                SweepAttemptStatus.BLOCKED_ROBOTS,
                "N1_SNAPSHOT",
            ))

        # 2 skipped_budget
        for i in range(2):
            attempts.append(SweepAttempt(
                sweep_id,
                f"store_budget_{i:02d}",
                SweepAttemptStatus.SKIPPED_BUDGET,
                "N1_SNAPSHOT",
            ))

        sweep_repo.save_batch(attempts)

        # Calcular
        metadata = coverage_calc.calculate_coverage(sweep_id, "quinua")

        # Verificar P14 DoD
        assert metadata.in_scope == 97
        assert metadata.verified == 72
        assert metadata.blocked_policy == 15
        assert metadata.blocked_server == 5
        assert metadata.blocked_robots == 3
        assert metadata.skipped_budget == 2
        assert metadata.coverage_pct == pytest.approx(74.2, abs=0.1)
        assert metadata.publishable is True
        assert "15 tiendas bloqueadas por policy" in metadata.note
        assert "5 tiendas rate-limited" in metadata.note

        print(f"✅ P14 Coverage: {metadata.coverage_pct}% ({metadata.verified}/{metadata.in_scope}), publishable={metadata.publishable}")


class TestCoveragePersistence:
    """Tests de persistencia."""

    def test_save_and_retrieve(self, sweep_repo, coverage_calc):
        """Guardar y recuperar cobertura."""
        sweep_id = "sweep_persist"

        # Crear algunos attempts
        attempts = [
            SweepAttempt(sweep_id, f"store_{i}", SweepAttemptStatus.OK, "N1_SNAPSHOT", offers_found=20)
            for i in range(8)
        ]
        for i in range(2):
            attempts.append(SweepAttempt(sweep_id, f"blocked_{i}", SweepAttemptStatus.BLOCKED_POLICY, "N1_SNAPSHOT"))

        sweep_repo.save_batch(attempts)

        # Calcular y guardar
        metadata = coverage_calc.calculate_coverage(sweep_id, "test_insumo")
        coverage_calc.save_coverage(metadata)

        # Recuperar
        retrieved = coverage_calc.get_coverage(sweep_id)

        assert retrieved is not None
        assert retrieved.sweep_id == sweep_id
        assert retrieved.insumo == "test_insumo"
        assert retrieved.coverage_pct == 80.0
        assert retrieved.publishable is True

    def test_calculate_and_save_atomic(self, sweep_repo, coverage_calc):
        """calculate_and_save en una operación."""
        sweep_id = "sweep_atomic"

        attempts = [
            SweepAttempt(sweep_id, f"store_{i}", SweepAttemptStatus.OK, "N1_SNAPSHOT")
            for i in range(10)
        ]
        sweep_repo.save_batch(attempts)

        # Una sola llamada
        metadata = coverage_calc.calculate_and_save(sweep_id, "test")

        assert metadata is not None
        assert metadata.coverage_pct == 100.0

        # Verificar que se guardó
        retrieved = coverage_calc.get_coverage(sweep_id)
        assert retrieved is not None
        assert retrieved.created_at is not None


class TestCoverageMetadata:
    """Tests del modelo CoberturaMetadata."""

    def test_metadata_to_dict(self):
        """Serializar metadata a diccionario."""
        metadata = CoberturaMetadata(
            sweep_id="sweep_001",
            insumo="quinua",
            in_scope=97,
            verified=72,
            blocked_policy=15,
            blocked_server=5,
            blocked_robots=3,
            skipped_budget=2,
            circuit_open=0,
            deferred=0,
            failed=0,
            out_of_scope=0,
        )

        data = metadata.to_dict()

        assert data["sweep_id"] == "sweep_001"
        assert data["coverage_pct"] == pytest.approx(74.2, abs=0.1)
        assert data["publishable"] is True
        assert "created_at" in data

    def test_metadata_calculations(self):
        """Verificar cálculos automáticos."""
        metadata = CoberturaMetadata(
            sweep_id="test",
            insumo="test",
            in_scope=100,
            verified=45,
            blocked_policy=30,
            blocked_server=15,
            blocked_robots=10,
            skipped_budget=0,
            circuit_open=0,
            deferred=0,
            failed=0,
            out_of_scope=0,
        )

        assert metadata.coverage_pct == 45.0
        assert metadata.publishable is False  # 45% < 60%

    def test_metadata_note_generation(self):
        """Verificar que se genere nota explicativa."""
        metadata = CoberturaMetadata(
            sweep_id="test",
            insumo="test",
            in_scope=100,
            verified=70,
            blocked_policy=20,
            blocked_server=5,
            blocked_robots=5,
            skipped_budget=0,
            circuit_open=0,
            deferred=0,
            failed=0,
            out_of_scope=0,
        )

        assert metadata.note is not None
        assert "20 tiendas bloqueadas por policy" in metadata.note
        assert "5 tiendas rate-limited" in metadata.note
        assert "5 tiendas robots.txt" in metadata.note
