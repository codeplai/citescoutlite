"""
TIER 4 · T4.1 (S4): salida de la etapa 2b.

Lo que la etapa escribe en `etapas_ejecucion.salida_json`. Esa fila **es** la
evidencia de procedencia del mapa: por eso el plan pudo cortar la tabla
`catalogo_comercial` en Postgres (§0) sin perder nada auditable.

Lleva tres cosas que la lista de productos por sí sola no dice:

- `nivel_alcanzado` — hasta dónde se llegó de verdad en la cascada del ADR-001.
- `niveles_no_disponibles` — lo que se pidió y no se pudo servir. Es la línea
  que el informe imprime, y la versión barata de "esto es lo que no miramos".
- `descartadas` — cuántas filas se cayeron y por qué. Que un producto no llegue
  a la tabla nunca debe ser silencioso.
"""

from collections import Counter

from pydantic import BaseModel, Field

from dominio.producto_en_mercado import ProductoEnMercado


class MapaComercial(BaseModel):
    """Los productos reales del mercado para un insumo, con su procedencia."""

    insumo: str
    productos: list[ProductoEnMercado] = Field(default_factory=list)

    nivel_alcanzado: int = Field(
        default=0,
        description="Nivel más alto de DescubrimientoComercial que sí respondió; "
                    "0 si no había adaptador",
    )
    niveles_no_disponibles: list[int] = Field(
        default_factory=list,
        description="Niveles pedidos sin adaptador. En el MVP, [2, 3]",
    )
    descartadas: dict[str, int] = Field(
        default_factory=dict,
        description="Filas no publicadas, por motivo (mojibake, url inválida...)",
    )

    # -- lecturas para el informe y el prompt -------------------------------

    def paises(self) -> dict[str, int]:
        """ISO -> nº de productos, de mayor a menor."""
        cuenta = Counter(iso for p in self.productos for iso in p.paises_iso)
        return dict(cuenta.most_common())

    def marcas(self) -> list[str]:
        """Marcas distintas, ordenadas. Excluye las que no tienen (None)."""
        return sorted({p.marca for p in self.productos if p.marca})

    def sin_marca(self) -> int:
        return sum(1 for p in self.productos if p.marca is None)

    def resumen_para_llm(self, limite: int = 30) -> dict:
        """Versión acotada del mapa para el prompt de la etapa 3.

        No se le pasan los 200 productos: serían ~10k tokens por run para que el
        modelo cite tres. Van los agregados —que es lo que de verdad sostiene una
        afirmación de mercado— y una muestra con sus ids, que es lo que P05
        comprobará en T5.1 que no se inventó.
        """
        return {
            "insumo": self.insumo,
            "total_productos": len(self.productos),
            "paises": self.paises(),
            "marcas": self.marcas()[:40],
            "niveles_no_disponibles": self.niveles_no_disponibles,
            "sin_dato": {
                "presentacion": len(self.productos),
                "precio": len(self.productos),
                "canal": len(self.productos),
            },
            "productos": [
                {"id": p.producto_id, "nombre": p.nombre,
                 "marca": p.marca, "paises_iso": p.paises_iso}
                for p in self.productos[:limite]
            ],
        }
