from pathlib import Path

from pydantic import BaseModel

from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.insight_mercado import InsightDeMercado


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

    # Tres objetos donde antes habia uno. En el informe gratuito, hipotesis y
    # dossier llegan a None y la SPA pone la tarjeta de paywall en su sitio en
    # vez de dos secciones vacias (T7.1).
    insight: InsightDeMercado | None = None
    hipotesis: HipotesisFormulacion | None = None
    dossier: DossierRegulatorio | None = None
