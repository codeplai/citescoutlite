"""
T3.4 - Cuanto cuesta mover el estado de aplicacion a Supabase.

Gate: **sobrecoste < 1 s por run**.

El run completo no sirve para medirlo tal cual: lo dominan la carga del modelo
de embeddings y la busqueda en LanceDB, que tardan ~20 s y son identicas en las
dos ramas. Un segundo de diferencia se pierde en ese ruido. Asi que se mide de
dos maneras y se reportan las dos:

  a) **Tiempo de estado**: se envuelven los puertos Auditoria y CacheLLM en un
     cronometro y se suma el tiempo pasado dentro de sus metodos. Es la cifra
     limpia: mide exactamente lo que cambia entre sqlite y Supabase.
  b) **Reloj de pared** del run entero, como referencia.

El cache LLM se calienta antes en las dos ramas, para que ninguna pague
llamadas al modelo durante la medicion.

No corre en la suite por defecto: necesita red y credenciales.
"""

import asyncio
import os
import statistics
import tempfile
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv()

INSUMO = "cascara de cacao"
SNAPSHOT = "2026-07"
REPETICIONES = 3
GATE_SOBRECOSTE_S = 1.0

pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or os.getenv("AGROSCOUT_OFFLINE") == "1",
    reason="Necesita credenciales de Supabase y red; no corre en modo offline",
)


class Cronometro:
    """Envuelve un puerto y acumula el tiempo pasado dentro de sus metodos.

    Delega todo por __getattr__, asi que no hay que conocer la interfaz: sirve
    igual para Auditoria que para CacheLLM y no se queda desactualizado cuando
    T5 o T6 anadan metodos.
    """

    def __init__(self, envuelto):
        self._envuelto = envuelto
        self.segundos = 0.0

    def __getattr__(self, nombre):
        atributo = getattr(self._envuelto, nombre)
        if not callable(atributo):
            return atributo

        def medido(*args, **kwargs):
            inicio = time.perf_counter()
            try:
                return atributo(*args, **kwargs)
            finally:
                self.segundos += time.perf_counter() - inicio

        return medido


def _dependencias(catalogo, auditoria, cache, informes):  # noqa: D103
    from adaptadores.redactor_glm import RedactorGLM
    from adaptadores.verificador_openfda import VerificadorOpenFDA
    from adaptadores.verificador_rag import VerificadorRAG
    from casos_de_uso.dependencias import Dependencias

    return Dependencias(
        redactor=RedactorGLM(api_key=os.getenv("HUAWEI_MAAS_API_KEY", ""),
                             base_url=os.getenv("HUAWEI_MAAS_BASE_URL")),
        catalogo=catalogo,
        cache=cache,
        informes=informes,
        auditoria=auditoria,
        # Offline: los verificadores no deben meter latencia de red ajena a la
        # comparacion. La etapa 3 sigue resolviendose por cache.
        verificador_fda=VerificadorOpenFDA(offline=True),
        verificador_rag=VerificadorRAG(offline=True),
        snapshot_version=SNAPSHOT,
    )


async def _medir(catalogo, construir, usuario_id, repeticiones):
    """Devuelve (mediana_tiempo_estado, mediana_reloj_pared) en segundos."""
    from casos_de_uso.evaluar_insumo import evaluar_insumo

    # Los adaptadores se construyen UNA vez, como en api/main.py: el pool de
    # psycopg y el cliente httpx son de proceso, y rehacerlos en cada vuelta
    # pagaria un handshake por run que en produccion no existe.
    auditoria, cache, informes = construir()

    auditoria_s, cache_s, informes_s, pared = [], [], [], []
    for i in range(repeticiones + 1):
        cronos = (Cronometro(auditoria), Cronometro(cache), Cronometro(informes))
        d = _dependencias(catalogo, *cronos)

        inicio = time.perf_counter()
        await evaluar_insumo(INSUMO, d, usuario_id)
        transcurrido = time.perf_counter() - inicio

        # La primera vuelta calienta el cache y no se cuenta.
        if i > 0:
            auditoria_s.append(cronos[0].segundos)
            cache_s.append(cronos[1].segundos)
            informes_s.append(cronos[2].segundos)
            pared.append(transcurrido)

    return {
        "auditoria": statistics.median(auditoria_s),
        "cache": statistics.median(cache_s),
        "informes": statistics.median(informes_s),
        "total": statistics.median(auditoria_s) + statistics.median(cache_s)
                 + statistics.median(informes_s),
        "pared": statistics.median(pared),
    }


def test_sobrecoste_de_estado_bajo_un_segundo():
    # asyncio.run en vez de pytest-asyncio: el proyecto no lo declara como
    # dependencia y no merece anadirlo por un solo test.
    asyncio.run(_comparar_ramas())


async def _comparar_ramas():
    from adaptadores.auditoria_postgres import AuditoriaPostgres
    from adaptadores.auditoria_sqlite import AuditoriaSQLite
    from adaptadores.busqueda_lancedb import BusquedaLanceDB
    from adaptadores.cache_postgres import CachePostgres
    from adaptadores.cache_sqlite import CacheSQLite
    from adaptadores.db import pool
    from adaptadores.informe_weasyprint import InformeWeasyPrint
    from adaptadores.repositorio_informes_supabase import RepositorioInformesSupabase

    # Un solo catalogo para las dos ramas: cargar el modelo de embeddings dos
    # veces meteria en la comparacion un coste que no es de la base de datos.
    catalogo = BusquedaLanceDB()

    with pool().connection() as conexion:
        usuario_id = str(conexion.execute(
            "select id from auth.users where email = %s",
            (os.getenv("USUARIO_PROVISIONAL_EMAIL", "admin@cite.gob.pe"),)
        ).fetchone()[0])

    # Archivo aparte: agroscout.db esta versionado y la medicion escribe una
    # ejecucion por vuelta. Sin esto, cada pasada deja un binario de 1 MB
    # modificado en git.
    with tempfile.TemporaryDirectory() as temporal:
        db_temporal = str(Path(temporal) / "sobrecoste.db")
        local = await _medir(
            catalogo,
            lambda: (AuditoriaSQLite(db_temporal), CacheSQLite(db_temporal),
                     InformeWeasyPrint()),
            usuario_id, REPETICIONES)

    remoto = await _medir(
        catalogo,
        lambda: (AuditoriaPostgres(), CachePostgres(), RepositorioInformesSupabase()),
        usuario_id, REPETICIONES)

    sobrecoste = remoto["total"] - local["total"]

    print(f"\n  {'puerto':12} {'sqlite':>10} {'supabase':>10} {'delta':>10}")
    for puerto in ("auditoria", "cache", "informes", "total"):
        print(f"  {puerto:12} {local[puerto]*1000:9.0f}ms {remoto[puerto]*1000:9.0f}ms "
              f"{(remoto[puerto]-local[puerto])*1000:+9.0f}ms")
    print(f"  reloj de pared {local['pared']:7.2f}s   {remoto['pared']:7.2f}s   "
          f"{remoto['pared']-local['pared']:+7.2f}s")

    assert sobrecoste < GATE_SOBRECOSTE_S, (
        f"El estado en Supabase anade {sobrecoste:.2f} s por run, por encima "
        f"del gate de {GATE_SOBRECOSTE_S} s. Mitigaciones del plan: dejar el "
        f"cache LLM en SQLite local, o agrupar mas escrituras.")
