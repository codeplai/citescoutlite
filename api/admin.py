"""
S8.5 y S8.9 - Los dos controles del panel: el kill-switch y los planes.

Van juntos porque son la misma pantalla y el mismo permiso, y porque los dos
comparten la regla que hace que el panel sirva de algo: **todo lo que se toca
aqui queda auditado**, con lo que habia antes y lo que quedo despues.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from adaptadores.auditoria_panel import AuditoriaPanel
from adaptadores.configuracion_postgres import MAXIMO_MOTIVO, ConfiguracionPostgres
from adaptadores.repositorio_perfiles import PLANES, RepositorioPerfiles
from api.auth import requiere_admin, usuario_actual_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

_config = ConfiguracionPostgres()
_perfiles = RepositorioPerfiles()
_auditoria = AuditoriaPanel()


class CambioKillSwitch(BaseModel):
    activo: bool
    motivo: Optional[str] = Field(None, max_length=MAXIMO_MOTIVO)


class CambioPlan(BaseModel):
    plan: str


@router.get("/kill-switch")
async def leer_kill_switch(_admin: dict = Depends(requiere_admin)):
    """Estado del interruptor, con quien lo dejo asi y cuando."""
    estado = _config.kill_switch()
    return {
        "activo": estado.activo,
        "motivo": estado.motivo,
        "actualizado_por": estado.actualizado_por,
        "actualizado_en": estado.actualizado_en,
    }


@router.put("/kill-switch")
async def fijar_kill_switch(cambio: CambioKillSwitch,
                            admin: dict = Depends(requiere_admin)):
    """Acciona el interruptor.

    Es idempotente: pedir "apagado" cuando ya lo esta responde 200 y no rompe
    nada. Pero **solo se audita si el estado cambio de verdad**. Un panel que
    refresca cada minuto y reenvia el estado actual llenaria la auditoria de
    entradas que no cuentan nada, y entre ellas se perderia la unica que
    importa: la vez que alguien lo apago.
    """
    antes = _config.kill_switch()

    try:
        despues = _config.fijar_kill_switch(
            cambio.activo, motivo=cambio.motivo,
            por=usuario_actual_id(admin))
    except Exception as e:
        # Al reves que leer, escribir falla hacia arriba: un boton que dice
        # que ha parado el gasto sin haberlo parado es peor que uno que da
        # error.
        logger.error(f"No se pudo fijar el kill-switch: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500,
                            detail="No se pudo guardar el estado del kill-switch")

    if antes.activo != despues.activo:
        _auditoria.registrar(
            "kill_switch_toggled",
            usuario_id=usuario_actual_id(admin), usuario_email=admin.get("email"),
            entidad="sistema_config", entidad_id="kill_switch",
            antes={"activo": antes.activo, "motivo": antes.motivo},
            despues={"activo": despues.activo, "motivo": despues.motivo},
        )

    return {
        "activo": despues.activo,
        "motivo": despues.motivo,
        "actualizado_por": despues.actualizado_por,
        "actualizado_en": despues.actualizado_en,
        "cambio": antes.activo != despues.activo,
    }


@router.get("/usuarios")
async def listar_usuarios(limite: int = Query(200, ge=1, le=500),
                          _admin: dict = Depends(requiere_admin)):
    """Usuarios con su plan, su rol y lo que llevan gastado este mes."""
    return {"usuarios": _perfiles.listar(limite=limite), "planes": list(PLANES)}


@router.put("/usuarios/{usuario_id}/plan")
async def cambiar_plan(usuario_id: str, cambio: CambioPlan,
                       admin: dict = Depends(requiere_admin)):
    """Sube o baja a alguien de plan.

    Cambiar el plan cambia **que etapas se le ejecutan** y **cuanto puede
    gastar al mes** (T6.1), asi que es de las cosas que mas necesitan quedar
    registradas: si alguien aparece de pronto sin acceso a la etapa 5, la
    respuesta tiene que estar en la auditoria y no en la memoria de nadie.
    """
    if cambio.plan not in PLANES:
        raise HTTPException(
            status_code=400,
            detail=f"Plan desconocido: {cambio.plan!r}. Los validos son "
                   f"{', '.join(PLANES)}")

    try:
        resultado = _perfiles.cambiar_plan(usuario_id, cambio.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail="usuario_id no es un uuid")

    if resultado is None:
        raise HTTPException(status_code=404, detail="No existe ese usuario")

    # Igual que con el interruptor: sin cambio real no hay nada que contar.
    if resultado["antes"] != resultado["despues"]:
        _auditoria.registrar(
            "plan_changed",
            usuario_id=usuario_actual_id(admin), usuario_email=admin.get("email"),
            entidad="perfiles", entidad_id=usuario_id,
            antes={"plan": resultado["antes"]},
            despues={"plan": resultado["despues"]},
        )

    return {"usuario_id": usuario_id, **resultado,
            "cambio": resultado["antes"] != resultado["despues"]}
