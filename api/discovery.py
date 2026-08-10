"""
S5.7 - Discovery Endpoint (Async N2)

GET /api/discovery?insumo=quinua&nivel=2

Retorna N1 inmediatamente, N2 enqueued para webhook.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from puertos.descubrimiento_comercial import NivelDescubrimiento
from adaptadores.puerto_descubrimiento_async import DescubrimientoComercialAsync
from dominio.producto_en_mercado import ProductoEnMercado

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["discovery"])

# Singleton
_discovery = None


def get_discovery() -> DescubrimientoComercialAsync:
    """Lazy init de discovery adaptador."""
    global _discovery
    if _discovery is None:
        _discovery = DescubrimientoComercialAsync()
    return _discovery


class DiscoveryResponse(BaseModel):
    """Respuesta del endpoint de descubrimiento."""
    insumo: str
    productos: list[ProductoEnMercado]
    n1_count: int
    n2_count: int
    n2_status: str  # 'completed', 'pending', 'failed', 'skipped'
    run_id: str
    note: Optional[str] = None
    elapsed_sec: float


@router.get("/discovery", response_model=DiscoveryResponse)
async def discovery_endpoint(
    insumo: str = Query(..., description="Producto a buscar (ej: 'quinua')"),
    nivel: int = Query(1, description="Nivel máximo (1=N1, 2=N1+N2, 3=N1+N2+N3)"),
    pais: str = Query("Perú", description="País para contexto"),
) -> DiscoveryResponse:
    """
    Descubrimiento comercial con cascada N1→N2→N3.

    **Flujo:**
    - N1 (Snapshot): Retornado inmediatamente (~50-100ms)
    - N2 (Bright Data): Enqueued, webhook llegará en 1-5min
    - N3 (Agente): Si hay gaps

    **Respuesta:**
    ```json
    {
        "insumo": "quinua",
        "productos": [...],  // N1 + N2 completados
        "n1_count": 72,
        "n2_count": 0,        // 0 si aún pending
        "n2_status": "pending",
        "run_id": "uuid",
        "note": "N2 en proceso, recarga en 1-5 min",
        "elapsed_sec": 0.083
    }
    ```

    **Niveles:**
    - nivel=1: Solo N1 (snapshot local)
    - nivel=2: N1 + N2 (Bright Data async, anti-bot tiendas)
    - nivel=3: N1 + N2 + N3 (Web agent si hay gaps)

    **Cliente:**
    - Mostrar productos N1 inmediatamente
    - Poll cada 30s si n2_status='pending'
    - Cuando n2_status='completed', mostrar N2 productos
    """
    try:
        # Convertir nivel a NivelDescubrimiento
        nivel_enum = NivelDescubrimiento(nivel)

        # Llamar descubrimiento async
        discovery = get_discovery()
        result = await discovery.descubrir_async(insumo, pais, nivel_enum)

        # Construir respuesta
        productos = result["productos"]
        n1_productos = productos  # En este punto, solo N1
        n2_count = 0  # N2 llega via webhook después

        return DiscoveryResponse(
            insumo=insumo,
            productos=productos,
            n1_count=len(n1_productos),
            n2_count=n2_count,
            n2_status=result["n2_status"],
            run_id=result["run_id"],
            note=result["note"],
            elapsed_sec=result["elapsed_sec"],
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid nivel: {nivel}. Must be 1, 2, or 3",
        )
    except Exception as e:
        logger.error(f"Discovery error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Discovery failed: {str(e)}",
        )


@router.get("/discovery/{run_id}/status")
async def discovery_status(run_id: str):
    """
    Chequear status de un discovery run.

    Si n2_status='completed', N2 datos están en DB.
    Cliente puede hacer query a /api/products/{run_id} para verlos.
    """
    # TODO: Implementar en 5.8 con P14 tests
    return {
        "run_id": run_id,
        "status": "pending",  # Mock
        "note": "Use /discovery/{run_id}/products para obtener datos N2 cuando completed",
    }
