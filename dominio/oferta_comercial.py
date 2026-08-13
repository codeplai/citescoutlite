"""
Una oferta de gondola: el mismo producto, en una tienda concreta, a un precio.

## Por que no es un `ProductoEnMercado`

`ProductoEnMercado` viene del snapshot de OpenFoodFacts y responde **que
productos existen y con que composicion**: aditivos, ingredientes, alergenos,
paises donde se ha visto. Su `precio_rango` esta vacio para casi todo, porque
un catalogo global no es una lista de precios.

Esto responde otra pregunta: **a cuanto se vende, hoy, en esta tienda**. Tiene
tienda, stock y fecha de captura, y no tiene composicion. Meterlas en el mismo
modelo obligaria a la mitad de los campos a estar vacios siempre y, peor, haria
creer que las dos filas son comparables cuando una es un producto y la otra es
una oferta.

Por eso van en dos listas y se pintan en dos tablas.

## El precio original no se pisa

`precio` y `moneda` son lo que dice la tienda. `precio_pen` es la conversion, y
viaja con la tasa, su fecha y su fuente. Una cifra convertida sin la tasa con
la que se convirtio no es auditable: dentro de un mes nadie podria
reconstruirla, y el informe de CITE tiene que aguantar esa pregunta.

Para una tienda peruana la conversion es la identidad y `precio_pen == precio`.
Se rellena igual, para que la columna en soles nunca tenga huecos y se pueda
ordenar y sumar sin casos especiales.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ConversionMoneda(BaseModel):
    """Con que se paso a soles. Sin esto, la cifra convertida no es citable."""

    tasa: float = Field(description="Soles por unidad de la moneda de origen")
    moneda_origen: str
    fecha_tasa: Optional[str] = Field(
        None,
        description="Fecha del valor publicado, no la de hoy: el BCRP no "
                    "publica fines de semana ni feriados",
    )
    fuente: Optional[str] = None


class EspecificacionNutricional(BaseModel):
    """Lo que la tienda publica en la ficha, tal cual, sin recalcular.

    ## Los valores son texto, no numeros

    La tienda escribe '210.6 kcal', '8.16 g' o '0'. Guardarlos como float
    obligaria a inventar la unidad, y la unidad es parte del dato: '0' de sodio
    no dice si son gramos o miligramos, y decidirlo por nosotros seria
    afirmar algo que la ficha no dice.

    ## Todo esta referido a la PORCION, no a 100 g

    Es como lo publican las cadenas peruanas, y es lo que obliga a llevar
    `porcion` al lado. Sin ella, '210,6 kcal' no se puede comparar con nada:
    puede ser una racion de 30 g o de 60 g. Convertir a 100 g seria mas comodo
    de leer y menos fiel; quien compare tiene que ver la racion.
    """

    porcion: Optional[str] = Field(None, description="Racion de referencia, p. ej. '60 g'")
    porciones_envase: Optional[str] = None

    calorias: Optional[str] = None
    proteinas: Optional[str] = None
    carbohidratos: Optional[str] = None
    grasas: Optional[str] = None
    azucares: Optional[str] = None
    sodio: Optional[str] = None

    alergenos: Optional[str] = None
    #: Advertencia de la propia tienda sobre sus cifras ("Valores Nutricionales
    #: Teoricos"). Se conserva: esconderla presentaria como medido algo que la
    #: ficha marca como estimado.
    nota: Optional[str] = None

    #: Campos por porcion que la ficha trae y no estaban previstos, con su
    #: nombre original. Es preferible enseñarlos a tirarlos en silencio.
    otros: dict[str, str] = Field(default_factory=dict)


class OfertaComercial(BaseModel):
    """Un producto a la venta en una tienda, con su precio y su procedencia."""

    nombre: str
    tienda: str
    fuente_url: str

    precio: Optional[float] = Field(None, description="Tal como lo publica la tienda")
    moneda: Optional[str] = Field(None, description="ISO: PEN, EUR...")
    precio_pen: Optional[float] = Field(
        None, description="El mismo precio en soles. None si no se pudo convertir")
    conversion: Optional[ConversionMoneda] = None

    marca: Optional[str] = None
    #: Codigo de barras. Es lo unico que identifica el MISMO producto en dos
    #: tiendas distintas —el nombre cambia de una a otra—, y por tanto lo unico
    #: que permite decir "esta bolsa cuesta 15,70 aqui y 15,00 alla".
    ean: Optional[str] = None
    unidad: Optional[str] = None
    categoria: Optional[str] = None
    #: Unidades disponibles. None significa que la tienda no lo publica o que
    #: dio una cifra centinela; nunca cero, que si es un dato.
    stock: Optional[int] = None

    #: Tabla nutricional de la ficha. None = la tienda no la publica para este
    #: producto, que es lo normal: de las cuatro cadenas peruanas solo Makro la
    #: trae de forma consistente.
    nutricion: Optional[EspecificacionNutricional] = None

    capturado_en: Optional[str] = Field(
        None, description="Cuando se leyo. Un precio sin fecha no dice nada")

    #: Que fuente lo trajo: 'vtex:Wong', 'agente', ... Va en la fila y no solo
    #: en la cabecera de la tabla porque una misma tabla puede mezclar tiendas
    #: leidas de un catalogo con otras raspadas de su ficha, y no cuestan lo
    #: mismo ni valen lo mismo.
    procedencia: Optional[str] = None
