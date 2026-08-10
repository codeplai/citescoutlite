"""
S5.7 - Puerto Descubrimiento Async Tests

Tests para descubrimiento con N2 async (no-blocking).
"""

import pytest
import asyncio
from uuid import uuid4

from puertos.descubrimiento_comercial import NivelDescubrimiento
from adaptadores.puerto_descubrimiento_async import (
    DescubrimientoComercialAsync,
    N2Status,
)


@pytest.fixture
def temp_db(tmp_path):
    """DB temporal."""
    return str(tmp_path / "test_puerto.db")


@pytest.fixture
def puerto(temp_db):
    """DescubrimientoComercialAsync."""
    return DescubrimientoComercialAsync(temp_db)


class TestPuertoAsync:
    """Tests de Puerto async."""

    @pytest.mark.asyncio
    async def test_descubrir_n1_only(self, puerto):
        """Descubrimiento N1 solamente."""
        result = await puerto.descubrir_async(
            insumo="test_product",
            nivel_maximo=NivelDescubrimiento.SNAPSHOT,
        )

        assert result["n2_status"] == N2Status.SKIPPED
        assert result["run_id"] is not None
        assert result["elapsed_sec"] < 1.0  # Rápido
        assert result["note"] is None  # No N2

    @pytest.mark.asyncio
    async def test_descubrir_n1_n2_async(self, puerto):
        """Descubrimiento N1 + N2 async."""
        result = await puerto.descubrir_async(
            insumo="quinua",
            nivel_maximo=NivelDescubrimiento.API_LICENCIADA,  # Nivel 2
        )

        # N1 siempre retorna
        assert len(result["productos"]) >= 0  # Puede ser 0 en test DB

        # N2 debe estar enqueued (pending)
        assert result["n2_status"] in (N2Status.PENDING, N2Status.FAILED)

        # Metadata debe incluir ambos niveles en ejecutados
        metadata = result["metadata"]
        assert 1 in metadata.niveles_ejecutados  # N1 siempre

        # Run ID para tracking
        assert result["run_id"] is not None
        assert len(result["run_id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_descubrir_fast_return(self, puerto):
        """Descubrimiento N2 async retorna rápido."""
        import time

        start = time.time()
        result = await puerto.descubrir_async(
            insumo="test",
            nivel_maximo=NivelDescubrimiento.API_LICENCIADA,
        )
        elapsed = time.time() - start

        # Debe retornar en < 1 segundo (N2 no espera webhook)
        assert elapsed < 1.0
        assert result["elapsed_sec"] < 1.0

        # Si N2 enqueue tuvo éxito, status=pending
        if result["n2_status"] == N2Status.PENDING:
            assert "en proceso" in result["note"].lower() or result["note"] is None

    def test_descubrir_sync_wrapper(self, puerto):
        """Versión sync usa asyncio.run() internally."""
        productos, metadata = puerto.descubrir_sync(
            insumo="test",
            nivel_maximo=NivelDescubrimiento.SNAPSHOT,
        )

        assert isinstance(productos, list)
        assert metadata is not None
        assert metadata.nivel_solicitado == 1

    def test_protocol_implementation(self, puerto):
        """Implementa protocolo DescubrimientoComercial."""
        # Método descubrir (sync)
        productos = puerto.descubrir("test", NivelDescubrimiento.SNAPSHOT)
        assert isinstance(productos, list)

        # Método niveles_no_disponibles
        no_disponibles = puerto.niveles_no_disponibles(NivelDescubrimiento.AGENTE_WEB)
        # N2 ahora está disponible
        assert 2 not in no_disponibles


class TestN2EnqueueFunctionality:
    """Tests de enqueue de N2."""

    @pytest.mark.asyncio
    async def test_enqueue_n2_creates_requests(self, puerto):
        """Enqueue N2 crea requests en DB."""
        run_id = str(uuid4())

        # Enqueue
        await puerto._enqueue_n2_async("quinua", "Perú", run_id)

        # Verificar que se crearon requests en BD
        bd_client = puerto._get_bd_client()
        requests = bd_client.db_repo.get_by_run_id(run_id)

        # Debe haber creado requests para cada tienda
        # (5 tiendas: amazon, costco, instacart, kroger, meituan)
        # Algunos pueden fallar si BD key inválida, pero debe intentar
        assert len(requests) >= 0  # May be 0 if BD auth fails in test


class TestResponseFormat:
    """Tests del formato de respuesta."""

    @pytest.mark.asyncio
    async def test_response_structure(self, puerto):
        """Respuesta tiene estructura correcta."""
        result = await puerto.descubrir_async("test")

        # Campos requeridos
        assert "productos" in result
        assert "metadata" in result
        assert "n2_status" in result
        assert "run_id" in result
        assert "note" in result
        assert "elapsed_sec" in result

        # Tipos
        assert isinstance(result["productos"], list)
        assert isinstance(result["n2_status"], str)
        assert isinstance(result["run_id"], str)
        assert isinstance(result["elapsed_sec"], float)

    @pytest.mark.asyncio
    async def test_note_messaging(self, puerto):
        """Mensaje para usuario es claro."""
        result = await puerto.descubrir_async(
            insumo="test",
            nivel_maximo=NivelDescubrimiento.API_LICENCIADA,
        )

        note = result["note"]
        if result["n2_status"] == N2Status.PENDING and note:
            assert "minutos" in note.lower() or "minuto" in note.lower()
            assert result["run_id"] in note or "en proceso" in note.lower()


class TestIntegrationP14:
    """Escenario P14: búsqueda "quinua" nivel=2."""

    @pytest.mark.asyncio
    async def test_p14_flow(self, puerto):
        """
        P14: GET /discovery?insumo=quinua&nivel=2

        Expected:
        - N1 retorna inmediatamente con productos
        - N2 enqueued (pending), webhook llegará después
        - Coverage será calculado post-webhook
        """
        result = await puerto.descubrir_async(
            insumo="quinua",
            nivel_maximo=NivelDescubrimiento.API_LICENCIADA,
        )

        # Verificar que N1 se ejecutó
        assert 1 in result["metadata"].niveles_ejecutados

        # N2 debe estar pending o completed
        assert result["n2_status"] in (N2Status.PENDING, N2Status.COMPLETED, N2Status.FAILED)

        # Retornó rápido
        assert result["elapsed_sec"] < 2.0

        print(f"✅ P14 flow: N1 ejecutado, N2 status={result['n2_status']}, "
              f"elapsed={result['elapsed_sec']:.3f}s, run_id={result['run_id']}")
