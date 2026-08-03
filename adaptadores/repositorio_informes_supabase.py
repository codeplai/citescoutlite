"""
T3.3 - Informes en Storage privado con URL firmada.

Cambia lo que significa "descargar un informe". Hasta S2, GET /informes/{id}
buscaba `informes/{id}.pdf` en disco y lo servia a quien lo pidiera: cualquiera
con un id ajeno se llevaba el PDF (punto 16 de la auditoria). Aqui el PDF vive
en un bucket privado, la fila de `informes` dice de quien es, y lo que se
entrega es una URL firmada de una hora.

El PDF se sigue componiendo con WeasyPrint en local: este adaptador envuelve al
de siempre en vez de duplicar la plantilla, y anade la subida, la firma y el
registro de propiedad.
"""

import uuid
from pathlib import Path

import httpx

from adaptadores.db import pool
from adaptadores.entorno import bucket_informes, cabeceras_servicio, url_supabase
from adaptadores.informe_weasyprint import InformeWeasyPrint
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from puertos.auditoria import Ejecucion
from puertos.repositorio_informes import RepositorioInformes

VIDA_URL_SEGUNDOS = 3600


class RepositorioInformesSupabase(RepositorioInformes):
    def __init__(self, local: InformeWeasyPrint | None = None,
                 vida_url_segundos: int = VIDA_URL_SEGUNDOS):
        self._local = local or InformeWeasyPrint()
        self._vida = vida_url_segundos
        self._bucket = bucket_informes()
        # Cliente persistente, no httpx.post suelto. Cada httpx.post abre
        # conexion nueva y paga un handshake TLS completo contra Sao Paulo;
        # con el cliente reutilizado se paga una vez y las siguientes subidas
        # van sobre keep-alive. Medido en T3.4: era el grueso de los 1.310 ms
        # de sobrecoste del puerto de informes.
        self._http = httpx.Client(
            base_url=f"{url_supabase()}/storage/v1",
            headers=cabeceras_servicio(),
            timeout=60,
        )

    def pide_reformulacion(self, ejecucion: Ejecucion) -> InformeScout:
        # No hay PDF que subir: el run no llego a producir informe.
        return self._local.pide_reformulacion(ejecucion)

    def emitir(self, ejecucion: Ejecucion, insight: InsightDeMercado | None,
               parcial: bool,
               hipotesis: HipotesisFormulacion | None = None,
               dossier: DossierRegulatorio | None = None) -> InformeScout:
        informe = self._local.emitir(ejecucion, insight, parcial,
                                     hipotesis=hipotesis, dossier=dossier)

        ruta_storage = f"{ejecucion.id}.pdf"
        self._subir(Path(informe.ruta_pdf), ruta_storage)
        self._registrar(ejecucion, ruta_storage, parcial)

        # No se firma aqui a proposito. La URL vive una hora y quien la pide es
        # quien descarga, no quien genera: firmar en la emision gastaba un
        # viaje mas en el camino critico del run para producir un enlace que
        # puede caducar antes de usarse. GET /informes/{id} firma al vuelo.
        return informe

    def _subir(self, origen: Path, destino: str) -> None:
        respuesta = self._http.post(
            f"/object/{self._bucket}/{destino}",
            headers={"Content-Type": "application/pdf",
                     # Reemitir el mismo run no debe chocar con el objeto viejo.
                     "x-upsert": "true"},
            content=origen.read_bytes(),
        )
        if respuesta.status_code >= 300:
            raise RuntimeError(
                f"No se pudo subir el informe: {respuesta.status_code} "
                f"{respuesta.text[:200]}")

    def _firmar(self, ruta: str) -> str:
        respuesta = self._http.post(
            f"/object/sign/{self._bucket}/{ruta}",
            headers={"Content-Type": "application/json"},
            json={"expiresIn": self._vida},
        )
        if respuesta.status_code >= 300:
            raise RuntimeError(
                f"No se pudo firmar el informe: {respuesta.status_code} "
                f"{respuesta.text[:200]}")
        # La API devuelve una ruta relativa: /object/sign/<bucket>/<ruta>?token=...
        return f"{url_supabase()}/storage/v1{respuesta.json()['signedURL']}"

    def _registrar(self, ejecucion: Ejecucion, ruta_storage: str,
                   parcial: bool) -> None:
        with pool().connection() as conexion:
            conexion.execute("""
                insert into public.informes
                    (id, ejecucion_id, usuario_id, parcial, ruta_storage)
                values (%s, %s, %s, %s, %s)
            """, (str(uuid.uuid4()), ejecucion.id, ejecucion.usuario_id,
                  parcial, ruta_storage))

    def firmar_de_nuevo(self, ruta_storage: str) -> str:
        """Para GET /informes/{id}: la URL guardada caduca, la fila no."""
        return self._firmar(ruta_storage)
