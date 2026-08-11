"""
S7.6 - Endpoints de la promoción manual (el 20 %).

Ver la cola puede hacerlo cualquiera del equipo; promover y rechazar exige rol
de administrador, porque cambian lo que ve todo el mundo.

Recordatorio de D1: promover marca la fila de staging_agente, no la mueve a
otra tabla.
"""

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from adaptadores.repositorio_promocion import RepositorioPromocion
from api.auth import get_current_user, requiere_admin, usuario_actual_id
from casos_de_uso.promocion import validar_oferta
from dominio.watermark import semilla_semanal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/promociones", tags=["promociones"])

_repo = RepositorioPromocion()


class OfertaEnCola(BaseModel):
    staging_id: str
    insumo: str
    pais: str
    producto: dict[str, Any]
    fuente_url: str
    creado_en: Optional[str] = None
    grounding: Optional[dict[str, Any]] = None
    automatica: Optional[bool] = None
    cubo: Optional[int] = None
    errores: list[dict[str, Any]] = Field(default_factory=list)
    validacion_passed: Optional[bool] = None
    validado_en: Optional[str] = None
    horas_en_cuarentena: Optional[float] = None


class ColaResponse(BaseModel):
    semilla: str
    ofertas: list[OfertaEnCola]
    total: int


class PromocionLote(BaseModel):
    """Bulk action de 7.6: seleccionar varias y promoverlas de una vez."""
    staging_ids: list[str] = Field(min_length=1, max_length=100)


class ResultadoAccion(BaseModel):
    staging_id: str
    ok: bool
    motivo: Optional[str] = None


@router.get("/pendientes", response_model=ColaResponse)
async def cola_pendiente(
    limite: int = Query(50, ge=1, le=200),
    solo_con_errores: bool = Query(False),
    _usuario: dict = Depends(get_current_user),
):
    """Ofertas que esperan revisión humana.

    Incluye tanto las que el watermark mandó al 20 % manual como las que el job
    rechazó por regla: unas y otras siguen en cuarentena y necesitan que
    alguien decida.
    """
    semilla = semilla_semanal()
    try:
        ofertas = _repo.cola_manual(semilla, limite=limite,
                                    solo_con_errores=solo_con_errores)
    except Exception as e:
        logger.error(f"Error leyendo la cola manual: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return ColaResponse(semilla=semilla,
                        ofertas=[OfertaEnCola(**o) for o in ofertas],
                        total=len(ofertas))


def _promover_una(staging_id: str, admin_id: str) -> ResultadoAccion:
    """Promueve una oferta revalidándola antes.

    Se revalida aunque sea una decisión humana: entre que el panel pintó la
    lista y el admin pulsa el botón puede haber pasado tiempo, y lo que
    entonces era fresco puede haber caducado. Los errores no bloquean —para eso
    está la promoción manual, para saltarse reglas a sabiendas— pero quedan
    escritos en promotion_log junto a quién lo hizo.
    """
    try:
        uid = UUID(staging_id)
    except ValueError:
        return ResultadoAccion(staging_id=staging_id, ok=False,
                               motivo="staging_id no es un uuid")

    # promotion_log exige autor cuando el tipo es 'manual'. Si el token no
    # trae identidad, mejor decirlo que reventar con un 500 al construir el
    # UUID unas lineas mas abajo.
    if not admin_id:
        return ResultadoAccion(staging_id=staging_id, ok=False,
                               motivo="No se pudo identificar al administrador")

    ofertas = {str(o["staging_id"]): o for o in _repo.ofertas_en_cuarentena()}
    oferta = ofertas.get(staging_id)
    if oferta is None:
        return ResultadoAccion(staging_id=staging_id, ok=False,
                               motivo="No está en cuarentena (¿ya promovida o caducada?)")

    reglas = _repo.leer_reglas(solo_activas=True)
    resultado = validar_oferta(oferta, reglas)
    _repo.registrar_validacion(uid, resultado.passed, resultado.errores_json(),
                               resultado.reglas_evaluadas)

    if _repo.promover(uid, "manual_human", resultado.reglas_evaluadas,
                      promoted_by=UUID(admin_id)):
        return ResultadoAccion(staging_id=staging_id, ok=True)

    return ResultadoAccion(staging_id=staging_id, ok=False,
                           motivo="Otro proceso la promovió antes")


@router.post("/{staging_id}/promover", response_model=ResultadoAccion)
async def promover(staging_id: str, admin: dict = Depends(requiere_admin)):
    return _promover_una(staging_id, usuario_actual_id(admin))


@router.post("/promover-lote", response_model=list[ResultadoAccion])
async def promover_lote(lote: PromocionLote, admin: dict = Depends(requiere_admin)):
    """Bulk action. Cada oferta se resuelve por separado.

    Una que falle no cancela el resto: con 20 ofertas por noche, obligar a
    repetir la selección entera porque una caducó haría la pantalla inservible.
    """
    admin_id = usuario_actual_id(admin)
    return [_promover_una(sid, admin_id) for sid in lote.staging_ids]


@router.post("/{staging_id}/rechazar", response_model=ResultadoAccion)
async def rechazar(staging_id: str, admin: dict = Depends(requiere_admin)):
    """Marca la oferta como rechazada a mano.

    No borra la fila: el TTL de 24 h de staging_agente se encarga de eso. Lo
    que hace es dejar constancia de que una persona la miró y dijo que no, que
    es lo que distingue "rechazada" de "nadie llegó a revisarla".
    """
    try:
        uid = UUID(staging_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="staging_id no es un uuid")

    admin_id = usuario_actual_id(admin)
    if not admin_id:
        raise HTTPException(status_code=400,
                            detail="No se pudo identificar al administrador")

    _repo.registrar_rechazo(uid, errores=[], reglas=[], promoted_by=UUID(admin_id))
    return ResultadoAccion(staging_id=staging_id, ok=True)


@router.get("/historial")
async def historial(
    dias: int = Query(7, ge=1, le=90),
    limite: int = Query(100, ge=1, le=500),
    _usuario: dict = Depends(get_current_user),
):
    return {"dias": dias, "entradas": _repo.historial(dias=dias, limite=limite)}


@router.get("/resumen")
async def resumen(
    horas: int = Query(24, ge=1, le=720),
    _usuario: dict = Depends(get_current_user),
):
    """"X automáticos, Y manuales, Z rechazados" en las últimas N horas."""
    return _repo.resumen_del_dia(horas=horas)


@router.get("/estadisticas")
async def estadisticas(
    horas: int = Query(24, ge=1, le=720),
    dias: int = Query(7, ge=1, le=90),
    _usuario: dict = Depends(get_current_user),
):
    """Todo lo que pinta el widget de 7.9, en una sola llamada.

    Va junto y no en tres endpoints porque el panel los enseña a la vez: con
    llamadas separadas, un refresco a medias dejaria el porcentaje de una
    ventana y las barras de otra.
    """
    try:
        return {
            "resumen": _repo.resumen_del_dia(horas=horas),
            "tendencia": _repo.tendencia(dias=dias),
        }
    except Exception as e:
        logger.error(f"Error calculando estadísticas de promoción: {e}")
        raise HTTPException(status_code=500, detail=str(e))
