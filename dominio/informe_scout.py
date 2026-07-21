from pathlib import Path
from pydantic import BaseModel

class InformeScout(BaseModel):
    parcial: bool
    snapshot_version: str
    ruta_pdf: Path | None
    ejecucion_id: str | None = None
    markdown_content: str | None = None
