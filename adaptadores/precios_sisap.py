"""
Lectura del snapshot de precios mayoristas (MIDAGRI · SISAP).

Lee `datasets/precios-sisap/precios.json`, que produce
`etl.cargar_precios_sisap`. Sin red y sin coste, como el resto de lecturas del
mapa comercial: la demo tiene que correr con `AGROSCOUT_OFFLINE=1`.

Devuelve **la observación más reciente de cada variedad**, no la serie entera.
Para el informe, "palta fuerte a S/ 3,85 el 24 de julio, +5,1 % en la semana" es
lo accionable; la serie completa está en el snapshot para quien la quiera.
"""

import json
import unicodedata
from pathlib import Path

from pydantic import ValidationError

from dominio.precio_materia_prima import PrecioMateriaPrima

SNAPSHOT = Path("datasets/precios-sisap/precios.json")


def _plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar insumos.

    La etapa 1 devuelve el insumo tal como lo normaliza el modelo —`"Palta"`,
    con mayúscula— y el snapshot lo guarda en minúscula. Comparando cadenas
    crudas no casa nunca **y no avisa**: el bloque de precio sale vacío como si
    MIDAGRI no publicara el dato, que es justo la conclusión contraria.
    """
    texto = (texto or "").strip().lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


class PreciosSISAP:
    """Precios de materia prima leídos del snapshot local."""

    def __init__(self, ruta: Path | str = SNAPSHOT):
        self.ruta = Path(ruta)
        self._cache: list[PrecioMateriaPrima] | None = None
        #: Registros del snapshot que no pasaron el contrato, por motivo.
        self.descartadas: dict[str, int] = {}

    def _cargar(self) -> list[PrecioMateriaPrima]:
        if self._cache is not None:
            return self._cache

        self._cache = []
        if not self.ruta.exists():
            return self._cache

        try:
            crudo = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"[PRECIOS] snapshot ilegible: {type(e).__name__}")
            return self._cache

        for registro in crudo.get("registros", []):
            try:
                self._cache.append(PrecioMateriaPrima(**registro))
            except ValidationError:
                # Una fila mal parseada del PDF no puede tumbar la etapa; se
                # cuenta, porque descartar en silencio es lo que no vale.
                motivo = "no_cumple_contrato"
                self.descartadas[motivo] = self.descartadas.get(motivo, 0) + 1
        return self._cache

    def para_insumo(self, insumo: str) -> list[PrecioMateriaPrima]:
        """El precio más reciente de cada variedad del insumo, de mayor a menor.

        Si el insumo no está en el boletín devuelve `[]`, que significa "no se
        publica precio mayorista para esto" y no "vale cero". Le pasa a la quinua
        —que el boletín diario de Lima no cubre— y al arándano, que es cultivo de
        exportación y no pasa por estos mercados.
        """
        buscado = _plegar(insumo)
        candidatos = [p for p in self._cargar() if _plegar(p.insumo) == buscado]
        if not candidatos:
            return []

        ultimo: dict[tuple[str, str], PrecioMateriaPrima] = {}
        for p in candidatos:
            clave = (p.producto, p.mercado)
            if clave not in ultimo or p.fecha > ultimo[clave].fecha:
                ultimo[clave] = p
        return sorted(ultimo.values(), key=lambda p: -p.precio_soles_kg)

    def insumos_cubiertos(self) -> list[str]:
        return sorted({p.insumo for p in self._cargar()})
