from pathlib import Path
from pydantic import BaseModel

class InformeScout(BaseModel):
    parcial: bool
    snapshot_version: str
    ruta_pdf: Path | None
    ejecucion_id: str | None = None
    markdown_content: str | None = None
    # Con el bucket privado el PDF ya no se sirve por ruta: se entrega una URL
    # firmada de vida corta. ruta_pdf se conserva porque la rama sqlite (plan B
    # de la demo) sigue escribiendo el archivo en disco.
    url_firmada: str | None = None
