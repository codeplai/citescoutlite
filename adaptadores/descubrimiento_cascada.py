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
"""

import asyncio
import datetime
from typing import Optional
from dataclasses import dataclass

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
from casos_de_uso.agente import AgenteInvestigadorComercial, AgenteResultado


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

    def __init__(self, db_path: str = "data/shelf_facts.duckdb"):
        self.db_path = db_path
        self.snapshot = DescubrimientoSnapshot(db_path)
        self.agente = None  # Lazy init
        self.metadata = None

    async def _get_agente(self) -> AgenteInvestigadorComercial:
        """Lazy initialization del agente."""
        if self.agente is None:
            self.agente = AgenteInvestigadorComercial()
        return self.agente

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

    def descubrir_n2(self, insumo: str, pais: str) -> list[ProductoEnMercado]:
        """
        N2: Bright Data (API licenciada).
        Por ahora: stub que retorna lista vacía.
        En producción: llamar a Bright Data API con datos reales de tiendas.xlsx
        """
        # TODO(s2.5): Integrar Bright Data API
        # Por ahora, retornar vacío (N2 no disponible aún)
        return []

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
    ) -> tuple[list[ProductoEnMercado], DescubrimientoCascadaMetadata]:
        """
        Descubre productos en cascada N1→N2→N3.

        Retorna: (productos_directos, metadata_con_staging_info)
        """
        resultados = []
        niveles_ejecutados = []
        staging_items = []
        agente_resultado = None

        # N1: Siempre
        try:
            n1_data = self.descubrir_n1(insumo)
            resultados.extend(n1_data)
            niveles_ejecutados.append(1)
        except Exception as e:
            print(f"⚠️  N1 error: {e}")

        # N2: Si nivel >= 2
        if nivel_maximo >= NivelDescubrimiento.API_LICENCIADA:
            try:
                n2_data = self.descubrir_n2(insumo, pais)
                resultados.extend(n2_data)
                if n2_data:
                    niveles_ejecutados.append(2)
            except Exception as e:
                print(f"⚠️  N2 error: {e}")

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
