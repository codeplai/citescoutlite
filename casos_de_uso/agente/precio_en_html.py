"""
S8 - Rescatar el precio que `trafilatura` tira.

## El problema, medido

`datos_estructurados.py` ya cuenta la mitad de esta historia: el precio no esta
en el texto que devuelve `trafilatura`, pero **si esta en el HTML**. Alli se
resolvio para las tiendas que publican JSON-LD. Las que no lo publican volvieron
a caer en la misma trampa por otra puerta.

Medido el 2026-08-13 sobre las tres tiendas suizas que trajo el agente:

| Tienda | HTML | Importes en el HTML | Importes en el texto de trafilatura |
|---|---|---|---|
| zwicky.swiss | 74.200 chars | `8,05 CHF` | **0** (texto util: 688 chars) |
| green-shop.ch | 542.560 chars | `7.70`, `4.25`, `12.95`, `19.45 CHF` | **0** (texto util: 4.565) |
| wengerfarms.ch | 138.583 chars | ninguno | 0 |

En dos de las tres el precio viajaba en la respuesta que ya se habia
descargado y se tiraba antes de enseñarsela al modelo. El modelo devolvia
`precio=None` **con razon**: nunca lo tuvo delante. Se estaba pagando una
extraccion para preguntarle por un dato que se le habia quitado.

La tercera no tiene precio en la respuesta inicial: lo pinta JavaScript. Esa
necesita un renderizador y este modulo no la arregla — y lo dice devolviendo
que no encontro nada, en vez de fingir.

## Que hace

Compone el texto que se le da al modelo: el de `trafilatura` —que es donde
esta el nombre del producto, y ahi funciona bien— **mas** los fragmentos del
HTML donde aparece un importe. No lo sustituye: lo completa.

## Por que fragmentos y no el HTML entero

Porque el HTML entero no cabe (542 KB frente a los 6.000 caracteres de la
ventana) y porque el precio necesita su contexto para poder leerse: `8,05 CHF`
suelto no dice si es el producto, el envio o el precio por kilo. Se recorta
alrededor de cada importe para que la etiqueta que lo acompaña viaje con el.

## Lo que NO hace: decidir cual es el precio

Este modulo no elige. Recoge los sitios donde hay un importe y deja que el
modelo lea, que es justo para lo que se le paga y lo unico que puede emparejar
un importe con el nombre que tiene al lado. Importa porque los casos reales son
ambiguos: zwicky trae **dos `0,00 CHF` antes** del `8,05` bueno, y green-shop
es una pagina de categoria con cinco precios de cinco productos distintos.

La unica excepcion es el cero, que no se usa como ancla (ver `_ANCLA_UTIL`).
"""

import html as _html
import re

# Monedas que aparecen de verdad en las tiendas de los tres mercados. La lista
# es corta a proposito: cada simbolo que se añade es una forma mas de casar con
# algo que no es un precio.
#
# `Fr.` va SOLO delante del importe ('Fr. 8.05', la forma suiza) y con el punto
# obligatorio. Detras casaria con horas y fechas en aleman —'18.30 Fr' de
# Freitag— y meteria basura como si fuera dinero.
_ANTES = r"CHF|SFr\.|Fr\.|EUR|USD|GBP|PEN|US\$|S/\.?|€|£|\$"
_DETRAS = r"CHF|SFr\.|EUR|USD|GBP|PEN|€|£"

# Un importe con dos decimales y separador de miles opcional: 8,05 / 1.234,50 /
# 19.45. Se exigen los dos decimales porque es lo que distingue un precio de un
# numero cualquiera de la pagina (un peso, un año, una referencia).
_IMPORTE = r"\d{1,3}(?:[.\s]\d{3})*[.,]\d{2}|\d+[.,]\d{2}"

PATRON_IMPORTE = re.compile(
    rf"(?<![A-Za-z0-9])(?:{_ANTES})\s?(?:{_IMPORTE})"
    rf"|(?:{_IMPORTE})\s?(?:{_DETRAS})(?![A-Za-z0-9])",
    re.IGNORECASE)

# Un importe de cero no sirve como ancla. En zwicky aparecen dos `0,00 CHF`
# —envio y descuento— antes del precio real, y anclarse en ellos gastaria la
# ventana en la parte de la pagina que no interesa. Si el unico importe de la
# pagina fuese cero, no hay precio que rescatar.
_ANCLA_UTIL = re.compile(r"[1-9]")

_SCRIPTS = re.compile(r"<(script|style|noscript)\b[^>]*>.*?</\1>",
                      re.IGNORECASE | re.DOTALL)
_ETIQUETAS = re.compile(r"<[^>]+>")
_ESPACIOS = re.compile(r"[ \t\r\f\v]+")

# Cuanto contexto se guarda a cada lado del importe. 200 caracteres cogen la
# etiqueta que lo acompaña ('Preis', 'Versandkosten', 'pro 100 g') y el nombre
# del producto cuando esta en la misma tarjeta, que es lo que permite al modelo
# emparejarlos. Mas ancho empieza a arrastrar la tarjeta siguiente.
VENTANA = 200

# Tope de fragmentos. Una pagina de categoria puede tener decenas de importes y
# la ventana del modelo es finita; con seis entran los primeros productos del
# listado, que son los que el buscador considero mas relevantes.
MAX_FRAGMENTOS = 6

SEPARADOR = "\n\n--- fragmentos de la pagina donde figura un importe ---\n"


def a_texto_plano(html_crudo: str) -> str:
    """El HTML sin etiquetas, como lo leeria una persona.

    Se quitan `<script>` y `<style>` enteros: son ruido para el modelo y su
    contenido minificado esta lleno de numeros que casarian con el patron de
    importe sin ser precios.

    Las lineas en blanco se tiran, y eso no es cosmetica. Una tarjeta de
    producto son decenas de `<div>` y `<span>` anidados, asi que al sustituir
    cada etiqueta por un salto queda un acordeon de lineas vacias: sin
    limpiarlo, la ventana de 200 caracteres alrededor del precio se gastaba
    casi entera en espacios y llegaba al modelo sin el nombre del producto al
    lado, que es justo lo que hay que emparejar.
    """
    if not html_crudo:
        return ""
    sin_scripts = _SCRIPTS.sub(" ", html_crudo)
    sin_etiquetas = _ETIQUETAS.sub("\n", sin_scripts)
    texto = _html.unescape(sin_etiquetas)
    lineas = (_ESPACIOS.sub(" ", linea).strip() for linea in texto.split("\n"))
    return "\n".join(linea for linea in lineas if linea)


def tiene_importe(texto: str) -> bool:
    """Si en ese texto hay algo que se pueda leer como un precio."""
    return any(_ANCLA_UTIL.search(m.group())
               for m in PATRON_IMPORTE.finditer(texto or ""))


def fragmentos_con_importe(html_crudo: str, ventana: int = VENTANA,
                           maximo: int = MAX_FRAGMENTOS) -> list[str]:
    """Trozos del HTML —ya sin etiquetas— alrededor de cada importe.

    Las ventanas que se solapan se funden en una: dos precios juntos en la
    misma tarjeta de producto tienen que leerse juntos, y partirlos en dos
    fragmentos rompe justamente la correspondencia entre nombre e importe.
    """
    plano = a_texto_plano(html_crudo)
    if not plano:
        return []

    tramos: list[list[int]] = []
    for m in PATRON_IMPORTE.finditer(plano):
        if not _ANCLA_UTIL.search(m.group()):
            continue
        inicio, fin = max(0, m.start() - ventana), min(len(plano), m.end() + ventana)
        if tramos and inicio <= tramos[-1][1]:
            tramos[-1][1] = max(tramos[-1][1], fin)
        else:
            tramos.append([inicio, fin])
        if len(tramos) >= maximo:
            break

    return [plano[i:f].strip() for i, f in tramos]


def texto_para_el_modelo(texto_limpio: str, html_crudo: str,
                         limite: int) -> tuple[str, bool]:
    """Lo que se le manda al modelo, y si hubo que rescatar el precio del HTML.

    Devuelve `(texto, rescatado)`. Cuando `rescatado` es True, quien llama
    **tiene que guardar este mismo texto como evidencia**: el grounding check de
    S7 verifica cada valor extraido contra `html_capturado`, y si el precio solo
    aparece en lo que se le enseño al modelo pero no en lo que se guardo, la
    oferta se rechaza por inventada siendo buena. Ese error ya se cometio dos
    veces en este proyecto —con JSON-LD y con VTEX— y las dos veces por guardar
    un recorte distinto del que se leyo.
    """
    texto_limpio = texto_limpio or ""

    # El camino normal: el texto ya trae precio y no hay nada que rescatar.
    if tiene_importe(texto_limpio):
        return texto_limpio[:limite], False

    fragmentos = fragmentos_con_importe(html_crudo)
    if not fragmentos:
        # No hay precio en la respuesta inicial: lo pinta JavaScript. Se
        # devuelve el texto tal cual y el agente fallara honestamente, que es
        # preferible a mandar 6.000 caracteres de HTML por si suena la flauta.
        return texto_limpio[:limite], False

    bloque = SEPARADOR + "\n\n".join(fragmentos)
    # El nombre del producto vive en el texto de trafilatura y el precio en los
    # fragmentos, asi que los dos tienen que caber. Se recorta el texto, no los
    # fragmentos: sin ellos esta llamada no aporta nada sobre la anterior.
    bloque = bloque[:limite]
    return texto_limpio[:max(0, limite - len(bloque))] + bloque, True
