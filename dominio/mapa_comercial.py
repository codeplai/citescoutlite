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
from typing import Optional

from pydantic import BaseModel, Field

from dominio.oferta_comercial import OfertaComercial
from dominio.precio_materia_prima import PrecioMateriaPrima
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

    # S2 INTEG.3: Metadata de cascada (niveles ejecutados, gaps, staging info)
    niveles_ejecutados: list[int] = Field(
        default_factory=list,
        description="[1], [1,2], o [1,2,3] según lo que se ejecutó",
    )
    has_gaps: bool = Field(
        default=False,
        description="True si hay cobertura insuficiente (< 3 productos, < 2 países/marcas)",
    )
    productos_n3_staging: int = Field(
        default=0,
        description="Productos encontrados por agente (N3) en staging_agente (sin promocionar)",
    )

    #: Precio del insumo como MATERIA PRIMA en el mercado mayorista.
    #:
    #: Va aparte de `productos` a propósito y no como una columna suya: son dos
    #: preguntas distintas. `ProductoEnMercado.precio_rango` es el precio de
    #: góndola del producto terminado y sigue vacío; esto es a cuánto está el
    #: kilo del insumo. Juntarlos daría a entender que el precio de góndola
    #: existe y está detrás del plan de pago.
    precios_materia_prima: list[PrecioMateriaPrima] = Field(
        default_factory=list,
        description="Observaciones de precio mayorista (MIDAGRI). [] = el "
                    "boletín no publica precio para este insumo",
    )

    #: Precio de GÓNDOLA del producto terminado, tienda por tienda.
    #:
    #: Va en su propia lista y no dentro de `productos` porque responde otra
    #: pregunta. `productos` viene de OpenFoodFacts y dice qué existe y con qué
    #: composición; esto dice a cuánto se vende hoy y dónde. Fundirlas dejaría
    #: la mitad de las columnas vacías en cada fila y, peor, haría creer que
    #: son comparables entre sí.
    #:
    #: Una lista por mercado, no una sola con una columna `pais`: las tablas se
    #: leen por separado —cuánto cuesta aquí frente a cuánto cuesta allá— y
    #: mezclarlas obligaría a filtrar para leer cualquiera de ellas.
    ofertas_peru: list[OfertaComercial] = Field(
        default_factory=list,
        description="Ofertas de las cadenas peruanas (VTEX). [] = no se "
                    "consultaron o ninguna tenía el insumo",
    )

    #: Lo mismo para el mercado de destino. Ojo: **no salen de la misma clase de
    #: fuente**, y por eso no se pueden juntar aunque el modelo sea el mismo.
    #:
    #: Perú se lee de un API público de catálogo: segundos, gratis, exacto.
    #: Alemania va por agente —búsqueda web más extracción con modelo— porque
    #: ninguna cadena alemana publica precio sin credencial (medido; ver
    #: `adaptadores/catalogo_alemania.py`). Eso significa minutos, coste por
    #: consulta y cobertura irregular. La columna `procedencia` de cada fila lo
    #: dice ('vtex:Metro' frente a 'agente:REWE') precisamente para que quien
    #: lea el informe no trate las dos mitades como si valieran lo mismo.
    ofertas_alemania: list[OfertaComercial] = Field(
        default_factory=list,
        description="Ofertas de tiendas alemanas (agente). [] = no se "
                    "consultaron, no había término alemán, o no se encontró nada",
    )

    #: Segundo mercado de destino, y también por agente. Se sondearon Migros,
    #: Coop, Farmy, Rappn y Piccantino el 2026-08-13: solo la última publica
    #: precio de forma abierta, y es una tienda gourmet de nicho, así que
    #: construir «Suiza» sobre ella sola habría rotulado como precio del país
    #: el precio de una tienda. Ver `adaptadores/catalogo_suiza.py`.
    #:
    #: Su lista propia por el mismo motivo que Alemania: son tres preguntas
    #: —cuánto cuesta aquí, cuánto en el primer destino europeo, cuánto en el
    #: segundo— y una sola tabla con columna `pais` obligaría a filtrar para
    #: leer cualquiera de las tres.
    #:
    #: Ojo con la moneda: **el BCRP no publica serie de franco suizo** (barridas
    #: PD04630PD-PD04680PD). El precio en soles de estas filas sale del respaldo
    #: no oficial de `tipo_cambio.py`, no del banco central, y la tabla lo dice
    #: fila a fila a través de `OfertaComercial.conversion.fuente`.
    ofertas_suiza: list[OfertaComercial] = Field(
        default_factory=list,
        description="Ofertas de tiendas suizas (agente). [] = no se "
                    "consultaron, no había término alemán, o no se encontró nada",
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
            # Se cuenta lo que de verdad falta, no el total. Estaba fijado a
            # len(productos) porque en el MVP los tres campos eran siempre
            # None; desde el merge de N2 hay filas con precio de gondola real,
            # y declararlas como "sin dato" seria decirle al modelo que no
            # mire un dato que si tiene.
            "sin_dato": {
                "presentacion": sum(1 for p in self.productos if p.presentacion is None),
                "precio": sum(1 for p in self.productos if p.precio_rango is None),
                "canal": sum(1 for p in self.productos if p.canal is None),
            },
            "productos": [
                {"id": p.producto_id, "nombre": p.nombre,
                 "marca": p.marca, "paises_iso": p.paises_iso}
                for p in self.productos[:limite]
            ],
        }
