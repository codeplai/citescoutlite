"""
TIER 3 · INTEG.1 (S2): Cascada N1→N2→N3 completa del puerto DescubrimientoComercial.

Implementa niveles 1, 2, 3 en cascada con `nivel_maximo`:
  - N1 (SNAPSHOT): LanceDB local (rápido, sin costo)
  - N2 (API_LICENCIADA): Bright Data (datos de web scraping, costo $)
  - N3 (AGENTE_WEB): Agente investigador comercial (búsqueda web + extracción, costo $$)

Si `nivel_maximo=1`: solo N1.
Si `nivel_maximo=2`: N1 + N2.
Si `nivel_maximo=3`: N1 + N2 + N3 (si hay gaps).

N3 va a staging_agente (cuarentena) sin promoción automática.

S5.2: N2 ahora usa Bright Data API con webhook async.
"""

import asyncio
import datetime
import logging
from typing import Optional
from dataclasses import dataclass
from uuid import uuid4

from dominio.producto_en_mercado import ProductoEnMercado
from puertos.descubrimiento_comercial import (
    DescubrimientoComercial,
    NivelDescubrimiento,
)
from .descubrimiento_snapshot import (
    DescubrimientoSnapshot,
    _get_tabla,
    _reset_cache,
)
from .bright_data_api import BrightDataClient
from .bright_data_requests import BrightDataRequestStatus
from .sweep_attempts import SweepAttemptsRepository
from .cobertura_calculator import CoberturaCalculator
from .catalogo_dedup import CatalogoDedup
from .entorno import ruta_db_sqlite
from casos_de_uso.agente import AgenteInvestigadorComercial, AgenteResultado

logger = logging.getLogger(__name__)


@dataclass
class DescubrimientoCascadaMetadata:
    """Metadata sobre qué niveles se ejecutaron."""
    nivel_solicitado: int
    niveles_ejecutados: list[int]
    niveles_no_disponibles: list[int]
    productos_n1: int = 0
    productos_n2: int = 0
    productos_n3_staging: int = 0
    has_gaps: bool = False
    gap_reason: Optional[str] = None


class DescubrimientoCascada:
    """
    Adaptador que implementa la cascada completa N1→N2→N3.
    """

    # Tiendas N2 soportadas por Bright Data
    TIENDAS_N2 = ["amazon", "costco", "instacart", "kroger", "meituan"]

    def __init__(self, db_path: str = "data/shelf_facts.duckdb"):
        self.db_path = db_path
        self.snapshot = DescubrimientoSnapshot(db_path)
        self.agente = None  # Lazy init
        self.bd_client = None  # Lazy init Bright Data
        self.sweep_repo = None  # Lazy init
        self.coverage_calc = None  # Lazy init
        self.metadata = None
        # El catalogo donde el webhook de Bright Data deja lo de N2. Lazy como
        # los de arriba y por el mismo motivo: construir CatalogoDedup crea sus
        # tablas, asi que hacerlo aqui haria que instanciar la cascada tocase
        # disco. Con eso, cualquier test que la construya escribia en el
        # agroscout.db versionado y lo dejaba modificado en git.
        self.catalogo_dedup = None  # Lazy init
        # Filas que no llegaron al mapa, por motivo. Lo lee mapear_comercio.
        self.descartadas: dict[str, int] = {}

    async def _get_agente(self) -> AgenteInvestigadorComercial:
        """Lazy initialization del agente."""
        if self.agente is None:
            self.agente = AgenteInvestigadorComercial()
        return self.agente

    def _get_bd_client(self) -> BrightDataClient:
        """Lazy initialization de cliente Bright Data."""
        if self.bd_client is None:
            self.bd_client = BrightDataClient()
        return self.bd_client

    def _get_sweep_repo(self) -> SweepAttemptsRepository:
        """Lazy initialization de sweep repository."""
        if self.sweep_repo is None:
            self.sweep_repo = SweepAttemptsRepository()
        return self.sweep_repo

    def _get_coverage_calc(self) -> CoberturaCalculator:
        """Lazy initialization de coverage calculator."""
        if self.coverage_calc is None:
            self.coverage_calc = CoberturaCalculator()
        return self.coverage_calc

    def _has_gaps(self, productos: list[ProductoEnMercado], insumo: str) -> bool:
        """
        Detecta si hay 'gaps' (cobertura insuficiente).
        Criterios:
          - Menos de 3 productos encontrados
          - Pocos países representados
          - Poca variedad de marcas
        """
        if len(productos) == 0:
            return True
        if len(productos) < 3:
            return True

        # Contar países únicos
        paises = set(p.pais for p in productos if p.pais)
        if len(paises) < 2:
            return True

        # Contar marcas únicas
        marcas = set(p.marca for p in productos if p.marca)
        if len(marcas) < 2:
            return True

        return False

    async def descubrir_n3(
        self, insumo: str, pais: str
    ) -> tuple[AgenteResultado, list[dict]]:
        """
        Ejecuta N3: agente investigador comercial.
        Retorna: (resultado_agente, lista_para_staging_agente)
        """
        agente = await self._get_agente()

        try:
            resultado = await asyncio.wait_for(
                agente.ejecutar(insumo, pais),
                timeout=120,  # 2 minutos total
            )

            # Convertir AgenteResultado a lista de dicts para staging
            staging_items = []
            for extraccion in resultado.productos_encontrados:
                staging_items.append({
                    "insumo": insumo,
                    "pais": pais,
                    "producto_json": extraccion.producto.model_dump(),
                    "fuente_url": extraccion.fuente_url,
                    "html_capturado": extraccion.html_capturado,
                    "provenance": "agente",
                    "no_verificado": True,  # Requiere promoción manual
                    "timestamp": extraccion.timestamp.isoformat(),
                    "modelo_usado": extraccion.modelo_usado,
                })

            return resultado, staging_items

        except asyncio.TimeoutError:
            raise TimeoutError(f"Agente N3 timeout después de 120s para '{insumo}' en {pais}")
        except Exception as e:
            raise RuntimeError(f"Agente N3 error: {e}")

    async def descubrir_n2(self, insumo: str, pais: str, run_id: str, timeout_sec: int = 30) -> list[ProductoEnMercado]:
        """
        N2: Bright Data (API licenciada).

        Enqueue scraping para tiendas anti-bot, espera webhook async.
        Si timeout: retorna parcial con status='deferred'.

        Args:
            insumo: Producto a buscar
            pais: País (para contexto)
            run_id: ID del discovery run (agrupa todos los requests)
            timeout_sec: Timeout esperando webhooks (default 30s)

        Returns:
            Lista de ProductoEnMercado encontrados por Bright Data
        """
        resultados = []
        run_id = run_id or str(uuid4())

        try:
            bd_client = self._get_bd_client()

            # Enqueue requests a Bright Data para cada tienda N2
            logger.info(f"N2: Enqueuing Bright Data requests para {len(self.TIENDAS_N2)} tiendas: {insumo}")

            for tienda_id in self.TIENDAS_N2:
                url = bd_client.TIENDAS_N2.get(tienda_id, "")
                if not url:
                    logger.warning(f"N2: Tienda {tienda_id} sin URL configurada")
                    continue

                try:
                    bd_req = bd_client.enqueue_scrape(
                        url=url,
                        query=insumo,
                        tienda_id=tienda_id,
                        run_id=run_id,
                    )
                    logger.info(f"N2: Enqueued {tienda_id}: snapshot_id={bd_req.snapshot_id}")
                except Exception as e:
                    logger.error(f"N2: Error enqueuing {tienda_id}: {e}")

            # Esperar webhooks hasta timeout_sec
            logger.info(f"N2: Waiting up to {timeout_sec}s for webhooks...")
            start_time = datetime.datetime.utcnow()

            while True:
                # Chequear requests completados
                completed_reqs = bd_client.db_repo.get_completed_by_run_id(run_id)

                if completed_reqs:
                    logger.info(f"N2: Received {len(completed_reqs)} webhook(s)")
                    # El parseo del JSON de Bright Data ya lo hizo el webhook
                    # (_process_bd_data_to_catalog), que ademas dedupe por
                    # (ean, sku, tienda). Aqui solo hay que recoger lo que dejo
                    # en el catalogo y darle forma de fila del mapa comercial.
                    resultados = self._recoger_n2_del_catalogo(insumo)
                    logger.info(f"N2: {len(resultados)} productos recogidos del catálogo")
                    break

                # Timeout check
                elapsed = (datetime.datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout_sec:
                    logger.warning(f"N2: Timeout {timeout_sec}s exceeded; marking as deferred")
                    pending = bd_client.get_pending_by_run(run_id)
                    for req in pending:
                        req.status = BrightDataRequestStatus.DEFERRED
                        bd_client.db_repo.save(req)
                    break

                # Wait a bit before retrying
                await asyncio.sleep(1)

            return resultados

        except Exception as e:
            logger.error(f"N2: Unexpected error: {e}")
            return []

    def _get_catalogo_dedup(self) -> CatalogoDedup:
        """Catálogo de N2, creado al primer uso.

        Por ruta_db_sqlite() y no por self.db_path: ese es el DuckDB del
        snapshot y esto es SQLite. Asi se lee del mismo archivo que escribe el
        webhook, tambien cuando AGROSCOUT_DB_PATH apunta a otro sitio.
        """
        if self.catalogo_dedup is None:
            self.catalogo_dedup = CatalogoDedup(ruta_db_sqlite())
        return self.catalogo_dedup

    def _recoger_n2_del_catalogo(self, insumo: str) -> list[ProductoEnMercado]:
        """Lee del catálogo lo que dejó el webhook y lo pasa a ProductoEnMercado.

        Se filtra por transporte para no arrastrar lo que hayan escrito N1 o
        Scrapling para el mismo insumo: esta funcion responde "que trajo N2".

        Las filas sin URL se descartan y se cuentan: `url` es obligatoria y
        HttpUrl en el modelo del mapa, y una fila sin procedencia comprobable no
        puede publicarse. Que se caiga una fila nunca debe ser silencioso.
        """
        productos: list[ProductoEnMercado] = []
        sin_url = 0

        for pc in self._get_catalogo_dedup().get_by_insumo(insumo, transporte="N2_BRIGHT_DATA"):
            if not pc.url:
                sin_url += 1
                continue

            try:
                productos.append(ProductoEnMercado(
                    insumo=insumo,
                    # Mismo formato que 'OFF:00000036': prefijo de fuente y, en
                    # este caso, la tienda, porque el mismo EAN aparece en varias.
                    producto_id=f"BD:{pc.tienda_id}:{pc.ean}",
                    nombre=pc.nombre,
                    marca=pc.marca.valor if pc.marca else None,
                    # Precio de gondola de verdad. Es el hueco que el modelo
                    # declaraba como "siempre None en el MVP" y que N2 llena.
                    precio_rango=pc.precio.valor if pc.precio else None,
                    fuente="BRIGHT_DATA",
                    url=pc.url,
                    fecha_dato=pc.updated_at.date(),
                ))
            except Exception as e:
                # Tipicamente una URL que no valida contra HttpUrl.
                sin_url += 1
                logger.warning(f"N2: fila descartada ({pc.ean}/{pc.tienda_id}): {e}")

        if sin_url:
            self.descartadas["n2_url_invalida"] = (
                self.descartadas.get("n2_url_invalida", 0) + sin_url)
            logger.info(f"N2: {sin_url} filas descartadas por URL ausente o inválida")

        return productos

    async def _save_coverage_metadata(self, sweep_id: str, insumo: str) -> None:
        """
        S5.6: Calcular y guardar cobertura metadata del sweep.
        Llamado al final de descubrir().
        """
        try:
            calc = self._get_coverage_calc()
            metadata = calc.calculate_and_save(sweep_id, insumo)
            if metadata:
                logger.info(
                    f"Coverage saved: {insumo} {metadata.coverage_pct}% "
                    f"({metadata.verified}/{metadata.in_scope}), publishable={metadata.publishable}"
                )
        except Exception as e:
            logger.error(f"Error saving coverage metadata: {e}")

    def descubrir_n1(self, insumo: str) -> list[ProductoEnMercado]:
        """
        N1: Snapshot LanceDB (ya implementado).
        """
        return self.snapshot.descubrir(insumo, NivelDescubrimiento.SNAPSHOT)

    async def descubrir(
        self,
        insumo: str,
        pais: str = "Perú",
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
        run_id: str = None,
    ) -> tuple[list[ProductoEnMercado], DescubrimientoCascadaMetadata]:
        """
        Descubre productos en cascada N1→N2→N3.

        Retorna: (productos_directos, metadata_con_staging_info)
        """
        resultados = []
        niveles_ejecutados = []
        staging_items = []
        agente_resultado = None
        run_id = run_id or str(uuid4())

        # N1: Siempre
        try:
            n1_data = self.descubrir_n1(insumo)
            resultados.extend(n1_data)
            niveles_ejecutados.append(1)
        except Exception as e:
            logger.error(f"N1 error: {e}")

        # N2: Si nivel >= 2
        if nivel_maximo >= NivelDescubrimiento.API_LICENCIADA:
            try:
                n2_data = await self.descubrir_n2(insumo, pais, run_id=run_id)
                resultados.extend(n2_data)
                if n2_data:
                    niveles_ejecutados.append(2)
            except Exception as e:
                logger.error(f"N2 error: {e}")

        # N3: Si nivel >= 3 y hay gaps
        has_gaps = self._has_gaps(resultados, insumo)
        if nivel_maximo >= NivelDescubrimiento.AGENTE_WEB and has_gaps:
            try:
                agente_resultado, staging_items = await self.descubrir_n3(insumo, pais)
                if staging_items:
                    niveles_ejecutados.append(3)
            except Exception as e:
                print(f"⚠️  N3 error: {e}")

        # Metadata
        niveles_no_disponibles = [
            n for n in [1, 2, 3]
            if n <= nivel_maximo and n not in niveles_ejecutados
        ]

        self.metadata = DescubrimientoCascadaMetadata(
            nivel_solicitado=nivel_maximo,
            niveles_ejecutados=niveles_ejecutados,
            niveles_no_disponibles=niveles_no_disponibles,
            productos_n1=len([p for p in resultados]),
            productos_n3_staging=len(staging_items),
            has_gaps=has_gaps,
            gap_reason="Cobertura insuficiente (< 3 productos o < 2 países/marcas)"
            if has_gaps
            else None,
        )

        # S5.6: Guardar cobertura metadata
        try:
            await self._save_coverage_metadata(run_id, insumo)
        except Exception as e:
            logger.error(f"Failed to save coverage metadata: {e}")

        return resultados, self.metadata

    def niveles_no_disponibles(
        self, nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT
    ) -> list[int]:
        """Retorna niveles no implementados aún."""
        no_disponibles = []
        if nivel_maximo >= NivelDescubrimiento.API_LICENCIADA:
            no_disponibles.append(2)  # N2 es stub
        # N1 siempre disponible
        return no_disponibles

    def descubrir_sync(
        self,
        insumo: str,
        pais: str = "Perú",
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> tuple[list[ProductoEnMercado], DescubrimientoCascadaMetadata]:
        """
        Versión sincrónica de descubrir() para etapa 2b.
        Usa asyncio.run() internamente para ejecutar N3 si es necesario.
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self.descubrir(insumo, pais, nivel_maximo)
            )
        finally:
            loop.close()

    async def close(self) -> None:
        """Cierra recursos."""
        if self.agente:
            await self.agente.close()


# Singleton de instancia
_cascada = None


def get_descubrimiento_cascada(db_path: str = "data/shelf_facts.duckdb"):
    """Retorna singleton de DescubrimientoCascada."""
    global _cascada
    if _cascada is None:
        _cascada = DescubrimientoCascada(db_path)
    return _cascada


async def descubrir_cascada(
    insumo: str,
    pais: str = "Perú",
    nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
) -> tuple[list[ProductoEnMercado], DescubrimientoCascadaMetadata]:
    """
    Función helper: descubre en cascada usando singleton.
    """
    cascada = get_descubrimiento_cascada()
    return await cascada.descubrir(insumo, pais, nivel_maximo)
