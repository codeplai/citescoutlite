"""
El CSV que abre Excel sin pelearse.

Vive aparte porque lo usan la auditoria (8.3) y los costes (8.2), y los dos
detalles que deciden si el fichero sirve son faciles de olvidar en uno de los
dos sitios:

1. **BOM al principio.** Excel en Windows abre un CSV sin BOM como ANSI:
   'Costeño' sale 'CosteÃ±o' y un entregable de CITE lleno de mojibake no vale.
   Los tres bytes del BOM lo arreglan y no molestan a nada que lea UTF-8.
2. **Terminador CRLF**, que es lo que dice el RFC 4180 y lo que Excel espera.
   `csv` lo pondria solo si escribiera a un fichero abierto en modo texto en
   Windows; aqui se escribe a un buffer en memoria y hay que decirlo.
"""

import csv
import io
import json
from typing import Any, Iterable, Optional, Sequence

from fastapi.responses import StreamingResponse

BOM = "﻿"


def texto_de(valor: Any) -> str:
    """Un valor listo para una celda.

    None va como celda vacia y no como el texto 'None', que es lo que sale de
    un `str()` descuidado y lo que despues alguien suma en Excel.

    Los dicts y listas se serializan con `ensure_ascii=False`: el destino es
    una persona mirando una celda, no un parser, y `\\u00fa` no lo lee nadie.
    """
    if valor is None:
        return ""
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False, default=str)
    return str(valor)


def respuesta_csv(nombre_fichero: str, columnas: Sequence[str],
                  filas: Iterable[dict[str, Any]],
                  cabeceras_extra: Optional[dict[str, str]] = None
                  ) -> StreamingResponse:
    """Una descarga de CSV a partir de una lista de dicts."""
    buffer = io.StringIO()
    escritor = csv.writer(buffer, lineterminator="\r\n")
    escritor.writerow(columnas)
    for fila in filas:
        escritor.writerow([texto_de(fila.get(c)) for c in columnas])

    cuerpo = BOM + buffer.getvalue()
    return StreamingResponse(
        io.BytesIO(cuerpo.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{nombre_fichero}"',
            **(cabeceras_extra or {}),
        },
    )
