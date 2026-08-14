"""
TIER 3 · T3.2 (S4): nivel 1 del puerto `DescubrimientoComercial`.

Implementa **solo `SNAPSHOT`**: consulta el índice LanceDB que ya existe, aplica
la normalización de país de T2.1 y el saneado de texto de T2.2, y proyecta a
`ProductoEnMercado`. Los niveles 2 y 3 no tienen adaptador; se declaran.

**Filtro léxico, no búsqueda vectorial.** Es la decisión de diseño del módulo y
tiene dos razones:

1. El plan fija la etapa 2b en "milisegundos" y `costo_usd = 0`. Una búsqueda
   semántica exige cargar bge-m3 (1024 dim); el filtro sobre el índice devuelve
   200 filas en ~33 ms sin modelo.
2. Para un mapa comercial, "qué marcas y países venden productos con arándano"
   es una pregunta **léxica**, no de vecindad semántica. Un producto sale en la
   tabla porque el arándano está en su nombre o en sus ingredientes, y eso se
   puede comprobar abriendo la URL — que es justo lo que pide el DoD de T4.

Se consulta en dos pasadas para que el orden signifique algo: primero los
productos que **son** del insumo (aparece en `nombre` o `categoria`), después
los que lo **contienen** (aparece en `ingredientes`). Sin esto, el orden es el
del índice y el primer resultado de "arándano" es un suplemento de colágeno que
lo lleva en la lista larga.
"""

import datetime
import re
import unicodedata

import lancedb
from pydantic import ValidationError

from dominio.producto_en_mercado import ProductoEnMercado
from etl.analizar_ingredientes import (aditivos, alergenos_declarados, contar,
                                       separar)
from etl.finalizar_manifest import INSUMOS
from etl.limpiar_texto import limpiar, producto_publicable, valor_o_none
from etl.normalizar_paises import normalizar
from puertos.descubrimiento_comercial import NivelDescubrimiento

# `embedding` queda fuera: 1024 floats por fila que nadie aguas abajo usa.
_COLUMNAS = ["id", "nombre", "categoria", "ingredientes", "url", "fecha_dato",
             "marca", "pais", "fuente"]

_FUENTES_VALIDAS = {"OFF", "USDA"}

# Singleton de proceso, como en busqueda_lancedb: abrir la tabla no es gratis.
_tabla = None


def _get_tabla(db_path: str):
    global _tabla
    if _tabla is None:
        db = lancedb.connect(db_path)
        listado = db.list_tables()
        nombres = getattr(listado, "tables", listado)
        if "productos" not in nombres:
            return None
        _tabla = db.open_table("productos")
    return _tabla


def _reset_cache():
    """Invalida el singleton. Solo para tests."""
    global _tabla
    _tabla = None


def _plegar(texto: str) -> str:
    texto = texto.replace("-", " ").lower().strip()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    return " ".join(texto.split())


# Índice de sinónimos con la clave plegada, para que "arandano" y "Arándano"
# encuentren lo mismo. La tabla es la de etl.finalizar_manifest: es la que ya
# debe coincidir con evals/set_dorado.yaml, y una tercera copia solo serviría
# para divergir.
_SINONIMOS = {_plegar(k): list(v) for k, v in INSUMOS.items()}


def _sinonimos_de(insumo: str) -> list[str]:
    """Sinónimos del insumo piloto; si no es uno de los 5, el literal."""
    return _SINONIMOS.get(_plegar(insumo), [insumo])


# Formas de producto terminado, con cómo se escriben en la góndola.
#
# Hace falta traducir porque `forma_producto` llega en castellano —lo escribió
# quien consulta— y el snapshot es mayoritariamente anglosajón: buscar «barras»
# contra «Quinoa Bars» no encuentra nada, y cero resultados se lee igual que
# «no existe el producto».
#
# Es una lista corta y deliberada, no un diccionario general: cubre las formas
# con las que de verdad se pregunta por un insumo agrícola. Una forma que no
# esté aquí no rompe nada — se cae al comportamiento de siempre, que es buscar
# por el insumo. El día que la etapa 1 devuelva la forma ya traducida, esto
# sobra.
_FORMAS: dict[str, tuple[str, ...]] = {
    "barra": ("barra", "bar", "riegel"),
    "galleta": ("galleta", "cookie", "biscuit"),
    "harina": ("harina", "flour", "mehl"),
    "aceite": ("aceite", "oil"),
    "bebida": ("bebida", "drink", "beverage"),
    "leche": ("leche", "milk"),
    "yogur": ("yogur", "yogurt", "yoghurt"),
    "snack": ("snack",),
    "cereal": ("cereal", "granola", "muesli"),
    "pasta": ("pasta", "noodle", "fideo"),
    "polvo": ("polvo", "powder"),
    "extracto": ("extracto", "extract"),
    "mermelada": ("mermelada", "jam", "preserve"),
    "chocolate": ("chocolate",),
    "capsula": ("capsula", "capsule", "tablet"),
    "infusion": ("infusion", "tea", "te"),
}


def _terminos_de_forma(forma_producto: str | None) -> list[str]:
    """Términos de góndola de la forma pedida. [] si no se pidió ninguna.

    Se busca la forma DENTRO del texto ('barras de quinua' contiene 'barra')
    en vez de partir por palabras, que es lo que hace que el plural funcione
    sin mantener una lista de plurales.
    """
    if not forma_producto:
        return []

    plegado = _plegar(forma_producto)
    for clave, terminos in _FORMAS.items():
        if clave in plegado:
            return list(terminos)
    return []


def _casa_forma(nombre: str | None, terminos: list[str]) -> bool:
    """True si el nombre contiene alguno de los términos como PALABRA.

    El filtro de LanceDB es un LIKE '%bar%', que además de «Quinoa Bars» trae
    «White Quinoa & Barley»: cebada, no barra. La consulta se deja generosa —es
    la que sabe usar el índice— y el recorte fino se hace aquí, donde se puede
    exigir límite de palabra. El sufijo opcional cubre el plural sin mantener
    una lista de plurales.
    """
    if not nombre:
        return False
    plegado = _plegar(nombre)
    return any(re.search(rf"\b{re.escape(t)}(s|es)?\b", plegado)
               for t in terminos)


def _escapar(termino: str) -> str:
    """Deja solo lo que puede ir dentro de un LIKE sin romper la consulta.

    `descubrir()` es la frontera con texto que puede venir de un usuario, así
    que el filtro no se construye por concatenación cruda.
    """
    return re.sub(r"[^\w\s]", "", termino, flags=re.UNICODE).strip()


def _clausula(sinonimos: list[str], campos: tuple[str, ...]) -> str:
    partes = []
    for termino in sinonimos:
        limpio = _escapar(termino)
        if not limpio:
            continue
        for campo in campos:
            partes.append(f"lower({campo}) LIKE '%{limpio.lower()}%'")
    return " OR ".join(partes)


def _a_fecha(valor) -> datetime.date | None:
    """`fecha_dato` es un timestamp Unix int64. Nunca inventa."""
    if not valor:
        return None
    try:
        if isinstance(valor, (int, float)):
            return datetime.datetime.fromtimestamp(valor).date()
        return datetime.datetime.fromisoformat(str(valor)).date()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


class DescubrimientoSnapshot:
    """Nivel 1: el snapshot local. Implementa `DescubrimientoComercial`."""

    #: Único nivel con adaptador real en el MVP.
    NIVEL = NivelDescubrimiento.SNAPSHOT

    def __init__(self, db_path: str = "vectores", limite: int = 200):
        self.db_path = db_path
        self.limite = limite
        #: Filas descartadas en la última llamada, por motivo. Diagnóstico: que
        #: un producto no llegue a la tabla nunca debe ser silencioso.
        self.descartadas: dict[str, int] = {}

    # -- puerto -------------------------------------------------------------

    def descubrir(
        self,
        insumo: str,
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
        forma_producto: str | None = None,
    ) -> list[ProductoEnMercado]:
        """Productos del insumo. Pedir un nivel que no existe **no lanza**.

        `forma_producto` es lo que se pidió de verdad cuando la consulta no era
        el insumo a secas: «barras de quinua» y no «quinua». Cuando viene, se
        antepone una pasada que exige insumo Y forma en el nombre.

        No basta con reordenar lo ya encontrado: buscando solo «quinua» el cupo
        se llena con grano suelto y las barras quedan fuera del corte antes de
        poder subirlas. Medido sobre el snapshot: de las 200 filas que devolvía
        «quinua», 11 eran barras y ninguna estaba entre las diez primeras.

        Las demás pasadas se conservan detrás, así que una forma con pocos
        productos no deja la tabla en tres filas: primero lo que se pidió,
        después el resto del insumo.
        """
        self.descartadas = {}
        tabla = _get_tabla(self.db_path)
        if tabla is None:
            return []

        sinonimos = _sinonimos_de(insumo)
        vistos: set[str] = set()
        filas: list[dict] = []

        por_insumo = _clausula(sinonimos, ("nombre", "categoria"))
        consultas: list[tuple[str, str]] = []

        terminos_forma = _terminos_de_forma(forma_producto)
        if terminos_forma:
            por_forma = _clausula(terminos_forma, ("nombre",))
            if por_insumo and por_forma:
                consultas.append(("insumo+forma", f"({por_insumo}) AND ({por_forma})"))

        # Después los que SON del insumo, y al final los que lo CONTIENEN.
        consultas.append(("es", por_insumo))
        consultas.append(("contiene", _clausula(sinonimos, ("ingredientes",))))

        for etiqueta, donde in consultas:
            if len(filas) >= self.limite:
                break
            if not donde:
                continue
            try:
                encontradas = (
                    tabla.search()
                    .where(f"({donde}) AND fuente != 'DEMO'")
                    .select(_COLUMNAS)
                    .limit(self.limite)
                    .to_list()
                )
            except Exception as e:  # índice ausente o filtro rechazado
                print(f"[2b] Consulta fallida ({etiqueta}): {e}")
                continue

            for fila in encontradas:
                # El LIKE de la pasada de forma es generoso a proposito; aqui
                # se exige que el termino aparezca como palabra.
                if etiqueta == "insumo+forma" and not _casa_forma(
                        fila.get("nombre"), terminos_forma):
                    continue

                clave = fila.get("id")
                if clave and clave not in vistos:
                    vistos.add(clave)
                    filas.append(fila)
                    if len(filas) >= self.limite:
                        break

        return self._proyectar(filas, insumo)

    def niveles_no_disponibles(
        self,
        nivel_maximo: NivelDescubrimiento = NivelDescubrimiento.SNAPSHOT,
    ) -> list[int]:
        """Los niveles pedidos por encima de 1: no hay adaptador para ellos."""
        return [int(n) for n in NivelDescubrimiento
                if self.NIVEL < n <= int(nivel_maximo)]

    # -- proyección ---------------------------------------------------------

    def _descartar(self, motivo: str) -> None:
        self.descartadas[motivo] = self.descartadas.get(motivo, 0) + 1

    def _proyectar(self, filas: list[dict], insumo: str) -> list[ProductoEnMercado]:
        productos: list[ProductoEnMercado] = []

        for fila in filas:
            # T2.2: la fila con U+FFFD en un campo que se enseña no se publica.
            if not producto_publicable(fila):
                self._descartar("mojibake_irreparable")
                continue

            fuente = (fila.get("fuente") or "").strip().upper()
            if fuente not in _FUENTES_VALIDAS:
                self._descartar("fuente_desconocida")
                continue

            fecha = _a_fecha(fila.get("fecha_dato"))
            if fecha is None:
                self._descartar("sin_fecha_dato")
                continue

            nombre = valor_o_none(fila.get("nombre"))
            if nombre is None:
                self._descartar("sin_nombre")
                continue

            # El texto de la etiqueta: 100 % del snapshot lo trae, y es lo que
            # de verdad le sirve a quien formula. Lo que se deriva de él se lee,
            # no se deduce (ver etl/analizar_ingredientes.py).
            texto_ingredientes = valor_o_none(fila.get("ingredientes"))

            try:
                productos.append(ProductoEnMercado(
                    insumo=insumo,
                    producto_id=fila.get("id") or "",
                    nombre=nombre,
                    # `null`, `N/A` y `Unknown` entran como None: son ausencias
                    # escritas como si fueran dato (T1.1 midió 17 en `marca`).
                    marca=valor_o_none(fila.get("marca")),
                    paises_iso=normalizar(limpiar(fila.get("pais"))),
                    ingredientes=texto_ingredientes,
                    lista_ingredientes=separar(texto_ingredientes),
                    n_ingredientes=contar(texto_ingredientes),
                    aditivos=aditivos(texto_ingredientes),
                    alergenos=alergenos_declarados(texto_ingredientes),
                    # presentacion, precio_rango y canal se quedan en None: el
                    # snapshot no los trae y el modelo lo declara.
                    fuente=fuente,
                    url=fila.get("url") or "",
                    fecha_dato=fecha,
                ))
            except ValidationError:
                # Una URL rota no puede tumbar la etapa entera; se cuenta.
                self._descartar("url_invalida")

        return productos
