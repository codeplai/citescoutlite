"""
S8.2 - Cost-meter: en que se va el dinero.

Solo administradores. El desglose enseña **cuanto ha gastado cada usuario**, y
eso es informacion sobre las personas del equipo, no sobre los datos; cada
usuario ve lo suyo en `/uso`, que ya existe desde T6.4 y filtra por su propia
identidad.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from adaptadores.repositorio_costos import MAXIMO_DIAS, RepositorioCostos
from api.auth import requiere_admin
from api.exportacion import respuesta_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/costos", tags=["costos"])

_repo = RepositorioCostos()

# Las tres vistas del mismo periodo. Se exportan por separado y no en un solo
# fichero de tres tablas pegadas: un CSV con tres cabeceras distintas no lo
# abre bien ninguna hoja de calculo.
COLUMNAS = {
    "serie": ("dia", "runs", "costo_usd", "tokens"),
    "etapa": ("etapa", "veces", "cache_hits", "costo_usd", "tokens"),
    "usuario": ("email", "plan", "runs", "costo_usd", "tokens", "usuario_id"),
    "estado": ("motivo", "runs"),
}

_CLAVE_DE = {"serie": "serie", "etapa": "por_etapa",
             "usuario": "por_usuario", "estado": "por_estado"}


@router.get("")
async def resumen(dias: int = Query(30, ge=1, le=MAXIMO_DIAS),
                  _admin: dict = Depends(requiere_admin)):
    """Todo el cost-meter en una llamada.

    Va junto y no en cuatro endpoints porque el panel lo enseña a la vez: con
    llamadas separadas, un refresco a medias dejaria la serie de una ventana y
    el desglose de otra, y las cifras dejarian de cuadrar entre si delante de
    quien las esta leyendo.
    """
    try:
        return _repo.resumen(dias=dias)
    except Exception as e:
        logger.error(f"Error calculando costes: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="No se pudo calcular el gasto")


@router.get("/export.csv")
async def exportar(dias: int = Query(30, ge=1, le=MAXIMO_DIAS),
                   detalle: str = Query("serie",
                                        description="serie, etapa, usuario o estado"),
                   _admin: dict = Depends(requiere_admin)):
    """Una de las cuatro vistas, en CSV, sobre el mismo periodo que la pantalla."""
    if detalle not in COLUMNAS:
        raise HTTPException(
            status_code=400,
            detail=f"Detalle desconocido: {detalle!r}. Los validos son "
                   f"{', '.join(COLUMNAS)}")

    datos = _repo.resumen(dias=dias)
    filas = datos[_CLAVE_DE[detalle]]

    return respuesta_csv(f"costos-{detalle}-{dias}d.csv",
                         COLUMNAS[detalle], filas,
                         {"X-Registros-Exportados": str(len(filas))})
