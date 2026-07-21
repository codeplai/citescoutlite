from pathlib import Path
from pydantic import BaseModel

class InformeScout(BaseModel):
    parcial: bool
    snapshot_version: str
    ruta_pdf: Path | None
