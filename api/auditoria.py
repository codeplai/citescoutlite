"""
S8.3 - Lectura de la auditoria del panel.

**Primera ruta que exige rol de administrador para leer.** Hasta ahora
`requiere_admin` solo protegia acciones (promover, rechazar); mirar la cola de
revision podia hacerlo cualquiera del equipo. Aqui no: la auditoria dice quien
hizo que y a que hora, y eso es informacion sobre las personas que operan el
sistema, no sobre los datos.
"""

import csv
import io
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from adaptadores.auditoria_panel import EVENTOS, AuditoriaPanel
from api.auth import requiere_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auditoria", tags=["auditoria"])

_repo = AuditoriaPanel()

# Tope del export. No es una cifra de rendimiento sino de honestidad: por
# encima de esto habria que paginar el fichero, y un CSV cortado en silencio
# por la mitad es peor que uno que no se descarga. Ver `_aviso_de_corte`.
MAXIMO_EXPORT = 10_000

COLUMNAS_CSV = ("audit_id", "ocurrido_en", "evento", "usuario_email",
                "usuario_id", "entidad", "entidad_id", "antes", "despues",
                "detalles")


class _Filtros:
    """Los tres filtros de 8.3, compartidos por el listado y el export.

    Van juntos a proposito: si el CSV aceptara otros filtros que la tabla, lo
    que se descarga dejaria de ser lo que se esta viendo, que es justo lo que
    espera quien pulsa "exportar".
    """

    def __init__(
        self,
        evento: Optional[str] = Query(None, description=f"Uno de: {', '.join(EVENTOS)}"),
        usuario_email: Optional[str] = Query(None, description="Parcial, sin distinguir mayusculas"),
        usuario_id: Optional[str] = Query(None, description="Para enlazar desde otras pantallas"),
        desde: Optional[str] = Query(None, description="YYYY-MM-DD, inclusivo"),
        hasta: Optional[str] = Query(None, description="YYYY-MM-DD, inclusivo"),
    ):
        self.evento = evento
        self.usuario_email = usuario_email
        self.usuario_id = usuario_id
        self.desde = desde
        self.hasta = hasta

    def como_dict(self) -> dict[str, Any]:
        return {"evento": self.evento, "usuario_email": self.usuario_email,
                "usuario_id": self.usuario_id,
                "desde": self.desde, "hasta": self.hasta}


@router.get("/eventos")
async def eventos(_admin: dict = Depends(requiere_admin)):
    """Las acciones que se auditan, para el desplegable del filtro.

    Sale de la misma constante que valida las escrituras, y no de una lista
    copiada en el frontend: asi es imposible filtrar por un evento que nunca se
    registra, o que se registre uno que no se puede filtrar.
    """
    return {"eventos": list(EVENTOS)}


@router.get("")
async def listar(
    filtros: _Filtros = Depends(),
    limite: int = Query(50, ge=1, le=200),
    desplazamiento: int = Query(0, ge=0),
    _admin: dict = Depends(requiere_admin),
):
    """Una pagina de la auditoria, con el total para poder paginar."""
    return _repo.leer(**filtros.como_dict(), limite=limite,
                      desplazamiento=desplazamiento)


def _texto(valor: Any) -> str:
    """Un valor de columna listo para CSV.

    Los jsonb van serializados con `ensure_ascii=False`: el destino es Excel,
    no un parser, y `\\u00fa` en una celda no lo lee nadie.
    """
    if valor is None:
        return ""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, default=str)
    return str(valor)


@router.get("/export.csv")
async def exportar(filtros: _Filtros = Depends(),
                   _admin: dict = Depends(requiere_admin)):
    """La misma consulta que el listado, en CSV.

    ## Dos detalles que deciden si el fichero sirve

    1. **BOM al principio.** Excel en Windows abre un CSV sin BOM como
       ANSI: 'Perú' sale 'PerÃº' y una auditoria de CITE llena de mojibake no
       vale como entregable. Los tres bytes del BOM lo arreglan y no molestan a
       nada que lea UTF-8.
    2. **Terminador CRLF**, que es lo que dice el RFC 4180 y lo que Excel
       espera; `csv` en Windows lo pondria igual, pero aqui se escribe a un
       buffer en memoria y hay que decirlo.
    """
    pagina = _repo.leer(**filtros.como_dict(), limite=MAXIMO_EXPORT + 1,
                        desplazamiento=0)
    entradas = pagina["entradas"][:MAXIMO_EXPORT]

    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\r\n")
    escritor.writerow(COLUMNAS_CSV)
    for entrada in entradas:
        escritor.writerow([_texto(entrada.get(c)) for c in COLUMNAS_CSV])

    aviso = _aviso_de_corte(pagina["total"], len(entradas))
    if aviso:
        logger.warning(aviso)

    cuerpo = "﻿" + buffer.getvalue()
    return StreamingResponse(
        io.BytesIO(cuerpo.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="auditoria.csv"',
            # Para que el panel pueda avisar de que el fichero va cortado en
            # vez de que la persona se lo lleve creyendo que esta entero.
            "X-Total-Registros": str(pagina["total"]),
            "X-Registros-Exportados": str(len(entradas)),
        },
    )


def _aviso_de_corte(total: int, exportados: int) -> Optional[str]:
    if total <= exportados:
        return None
    return (f"Export de auditoria cortado: {exportados} de {total} registros. "
            f"Acota el rango de fechas para llevartelo entero.")
