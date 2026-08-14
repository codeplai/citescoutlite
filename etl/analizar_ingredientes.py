"""
TIER 4 · Nivel A (S4): lectura del texto de ingredientes.

Se aplica **al leer**, como la normalización de país (T2.1) y el saneado de
texto (T2.2). Funciones puras, sin red y sin coste: todo sale del campo
`ingredientes` que el ETL de S2 ya proyectó al índice y que está al **100 %** de
las 29.054 filas (mediana de 258 caracteres y 13 ingredientes por producto).

Por qué importa: es el campo que un tecnólogo de alimentos mira primero, y hasta
ahora el mapa comercial no lo enseñaba. La tabla decía marca, país y tres
columnas vacías.

**La distinción que sostiene este módulo: leer no es deducir.**

- `aditivos()` **lee**. Si el texto dice "pectin", el producto lleva pectina.
  Se devuelve lo que aparece escrito, con su número E cuando es estándar.
- `alergenos_declarados()` **solo recoge declaraciones explícitas** ("Contains:
  milk", "Contiene: leche"), que son el 5,8 % de las filas. Para el resto
  devuelve `[]`, y `[]` significa **"la etiqueta no lo declara"**, nunca "no
  tiene alérgenos". Deducir alergenicidad de un ingrediente sería inventar un
  dato de seguridad alimentaria, que es la peor clase de dato que se puede
  inventar.

El nombre del aditivo es además la llave del corpus regulatorio de S2. El plan
§R4 da por perdido el eCFR porque "es Title 21, aditivos" y no cubre arándano,
palta ni quinua. No cubre los insumos, pero **sí cubre la pectina y el sorbato
de potasio**: con los aditivos extraídos, esos 734 pasajes vuelven a servir.
"""

import re
import unicodedata

# Aditivos por su nombre en la etiqueta. El numero E se incluye cuando es el
# estandar del Codex: es lo que permite cruzarlos con el corpus regulatorio.
#
# Las etiquetas de EE. UU. —que son la mayoria del snapshot— escriben el nombre
# y casi nunca el numero: solo el 4,1 % de las filas trae un `E` explicito. Por
# eso se busca por nombre y no por codigo.
ADITIVOS: dict[str, tuple[str, str]] = {
    # patron -> (nombre canonico, numero E)
    "citric acid": ("Ácido cítrico", "E330"),
    "acido citrico": ("Ácido cítrico", "E330"),
    "ascorbic acid": ("Ácido ascórbico", "E300"),
    "acido ascorbico": ("Ácido ascórbico", "E300"),
    "malic acid": ("Ácido málico", "E296"),
    "acido malico": ("Ácido málico", "E296"),
    "lactic acid": ("Ácido láctico", "E270"),
    "acido lactico": ("Ácido láctico", "E270"),
    "lecithin": ("Lecitina", "E322"),
    "lecitina": ("Lecitina", "E322"),
    "pectin": ("Pectina", "E440"),
    "pectina": ("Pectina", "E440"),
    "xanthan": ("Goma xantana", "E415"),
    "goma xantana": ("Goma xantana", "E415"),
    "guar gum": ("Goma guar", "E412"),
    "goma guar": ("Goma guar", "E412"),
    "locust bean gum": ("Goma garrofín", "E410"),
    "carrageenan": ("Carragenina", "E407"),
    "carragenina": ("Carragenina", "E407"),
    "gellan": ("Goma gellan", "E418"),
    "potassium sorbate": ("Sorbato de potasio", "E202"),
    "sorbato de potasio": ("Sorbato de potasio", "E202"),
    # El acido sorbico y el EDTA entran en T6, y su ausencia era un agujero
    # real: son los dos aditivos de `acido1.pptx` y `acido2.pptx`, o sea los
    # casos de referencia del proyecto entero, y **una etiqueta que los
    # declarara salia sin aditivos**. No aparecian porque esta tabla se
    # construyo por frecuencia en el snapshot y ninguno de los dos es frecuente
    # ahi; eso mide lo que vende OpenFoodFacts, no lo que le interesa a quien
    # exporta.
    "sorbic acid": ("Ácido sórbico", "E200"),
    "acido sorbico": ("Ácido sórbico", "E200"),
    "calcium sorbate": ("Sorbato de calcio", "E203"),
    # Los dos EDTA van separados y con su numero propio: el calcico disodico
    # (E385) y el disodico (E386) no son el mismo aditivo ni tienen las mismas
    # autorizaciones. Un patron generico 'edta' casaria con los dos y elegiria
    # uno al azar, que en una tabla regulatoria es peor que no reconocer nada.
    "calcium disodium edta": ("EDTA cálcico disódico", "E385"),
    "edta calcico disodico": ("EDTA cálcico disódico", "E385"),
    "disodium edta": ("EDTA disódico", "E386"),
    "edta disodico": ("EDTA disódico", "E386"),
    "sodium benzoate": ("Benzoato de sodio", "E211"),
    "benzoato de sodio": ("Benzoato de sodio", "E211"),
    "calcium propionate": ("Propionato de calcio", "E282"),
    "sulfur dioxide": ("Dióxido de azufre", "E220"),
    "sulfite": ("Sulfitos", "E220"),
    "sulfito": ("Sulfitos", "E220"),
    "tocopherol": ("Tocoferoles", "E306"),
    "tocoferol": ("Tocoferoles", "E306"),
    "mono- and diglycerides": ("Mono y diglicéridos", "E471"),
    "monoglycerides": ("Mono y diglicéridos", "E471"),
    "cellulose gum": ("Carboximetilcelulosa", "E466"),
    "carboxymethyl cellulose": ("Carboximetilcelulosa", "E466"),
    "sodium citrate": ("Citrato de sodio", "E331"),
    "citrato de sodio": ("Citrato de sodio", "E331"),
    "calcium carbonate": ("Carbonato de calcio", "E170"),
    "sodium bicarbonate": ("Bicarbonato de sodio", "E500"),
    "bicarbonato de sodio": ("Bicarbonato de sodio", "E500"),
    "annatto": ("Achiote (annatto)", "E160b"),
    "achiote": ("Achiote (annatto)", "E160b"),
    "caramel color": ("Caramelo", "E150"),
    "titanium dioxide": ("Dióxido de titanio", "E171"),
    "beta-carotene": ("Betacaroteno", "E160a"),
    "betacaroteno": ("Betacaroteno", "E160a"),
    "sucralose": ("Sucralosa", "E955"),
    "sucralosa": ("Sucralosa", "E955"),
    "aspartame": ("Aspartamo", "E951"),
    "aspartamo": ("Aspartamo", "E951"),
    "stevia": ("Glucósidos de esteviol", "E960"),
    "steviol": ("Glucósidos de esteviol", "E960"),
    "acesulfame": ("Acesulfamo K", "E950"),
    "sodium phosphate": ("Fosfatos de sodio", "E339"),
    "potassium chloride": ("Cloruro de potasio", "E508"),
}

# Alergenos, para normalizar lo que venga tras "Contains:" / "Contiene:".
# La lista es la de los alergenos de declaracion obligatoria; los nombres son
# los que aparecen en las etiquetas.
ALERGENOS: dict[str, str] = {
    "milk": "Leche", "leche": "Leche", "dairy": "Leche", "lacteo": "Leche",
    "egg": "Huevo", "huevo": "Huevo",
    "soy": "Soya", "soya": "Soya", "soja": "Soya", "soybean": "Soya",
    "wheat": "Trigo", "trigo": "Trigo",
    "gluten": "Gluten",
    "peanut": "Maní", "mani": "Maní", "cacahuate": "Maní",
    "tree nut": "Frutos secos", "nuts": "Frutos secos",
    "almond": "Frutos secos", "almendra": "Frutos secos",
    "cashew": "Frutos secos", "walnut": "Frutos secos",
    "hazelnut": "Frutos secos", "pecan": "Frutos secos",
    "fish": "Pescado", "pescado": "Pescado",
    "shellfish": "Mariscos", "marisco": "Mariscos", "crustacean": "Mariscos",
    "sesame": "Ajonjolí", "ajonjoli": "Ajonjolí", "sesamo": "Ajonjolí",
    "sulfite": "Sulfitos", "sulfito": "Sulfitos",
}

# Solo declaraciones explicitas. Deducir el alergeno del ingrediente seria
# inventar un dato de seguridad alimentaria.
_DECLARACION = re.compile(
    r"(?:contains|contiene|may contain|puede contener|elaborado en)\s*:?\s*"
    r"([^.;]{1,200})", re.IGNORECASE)

_ABREN, _CIERRAN = "([{", ")]}"

# Aditivos declarados por CODIGO en vez de por nombre.
#
# La tabla ADITIVOS de arriba lee nombres, que es como escriben las etiquetas
# anglosajonas del snapshot. **Las peruanas no.** Medido el 2026-08-14 sobre las
# ofertas de gondola de las cadenas peruanas: de 30 fichas con lista de
# ingredientes, **21 declaran sus aditivos por codigo INS** y el lector por
# nombre no encontraba ni uno.
#
#     "Leudante sin 500(ii), Regulador de la acidez sin 341(i), sin 450(i)..."
#     -> aditivos() devolvia []
#
# El codigo INS del Codex y el numero E de la UE son **la misma numeracion**:
# INS 500 es E500. Lo que cambia es el prefijo y que la UE no autoriza todo lo
# que el Codex lista. Aqui solo se lee el numero; que ese aditivo este o no
# autorizado lo responden los tres evaluadores, que es su trabajo.
#
# `SIN` es como se escribe INS en castellano en muchas etiquetas peruanas
# ("Sistema Internacional de Numeracion"). Se acepta, y por eso el patron exige
# un numero detras: sin esa condicion, la palabra "sin" de "sin azucar" casaria.
_CODIGO_ADITIVO = re.compile(
    r"\b(?:INS|SIN|E)\s*\.?\s*(\d{3})\s*(?:\(\s*([a-z]{1,4})\s*\)|([a-z]{1,4})\b)?",
    re.IGNORECASE)

# Numeros que NO son aditivos aunque aparezcan tras un prefijo valido. Se dejan
# fuera porque el rango de aditivos del Codex empieza en 100.
_RANGO_VALIDO = range(100, 1600)

# Los dos sufijos de un codigo de aditivo NO significan lo mismo, y tratarlos
# igual rompe la busqueda en el corpus:
#
#   LETRA   E150a, E150b, E150c, E150d son **cuatro aditivos distintos** (cuatro
#           caramelos, obtenidos por procesos distintos). E553a y E553b, igual.
#           La letra es parte del identificador y se queda.
#
#   ROMANO  E500(i) es carbonato de sodio y E500(ii) bicarbonato: son
#           especificaciones del MISMO aditivo, y el Anexo II las agrupa bajo
#           «E 500». El corpus normaliza quitandolas, asi que emitirlas pegadas
#           —«E500i»— produce una clave que no casa con nada.
#
# La etiqueta escribe las dos formas sin parentesis ("INS 322i", "INS 150d") y
# hay que decidir cual es cual. No hay ambiguedad real: los romanos de aditivos
# solo usan i/v/x y las variantes por letra solo a-h.
_ROMANOS = re.compile(r"^[ivx]+$")


def _plegar(texto: str) -> str:
    """Minúsculas y sin tildes, para que 'Ácido Cítrico' case con la tabla."""
    texto = texto.lower()
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def separar(texto: str | None) -> list[str]:
    """Los ingredientes de la etiqueta, uno por elemento.

    Parte por comas **solo fuera de paréntesis**. Un corte a lo bruto rompe los
    subcompuestos —"harina (trigo, hierro)" se convertiría en "harina (trigo" y
    "hierro)"—, que es tolerable para contar por encima pero no para enseñar una
    lista: ahí se ve roto y además miente sobre la fórmula.
    """
    if not texto or not texto.strip():
        return []

    partes, actual, profundidad = [], [], 0
    for caracter in texto:
        if caracter in _ABREN:
            profundidad += 1
        elif caracter in _CIERRAN:
            profundidad = max(0, profundidad - 1)

        if caracter in ",;" and profundidad == 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(caracter)
    partes.append("".join(actual))

    return [p.strip(" .·-_") for p in partes if p.strip(" .·-_")]


def contar(texto: str | None) -> int | None:
    """Cuántos ingredientes declara la etiqueta. `None` si no hay texto.

    Es `len(separar(...))` a propósito: el número que se enseña junto a la lista
    tiene que ser el número de elementos de esa lista. Dos formas de contar lo
    mismo acaban discrepando en pantalla.
    """
    if not texto or not texto.strip():
        return None
    return len(separar(texto))


def aditivos(texto: str | None) -> list[str]:
    """Aditivos que **aparecen escritos** en la etiqueta, con su número E.

    Devuelve `["Pectina (E440)", ...]`, sin repetir y ordenado. Esto es leer,
    no deducir: si el texto dice "pectin", el producto lleva pectina.
    """
    if not texto:
        return []
    plegado = _plegar(texto)
    encontrados: dict[str, str] = {}
    for patron, (nombre, numero) in ADITIVOS.items():
        # Frontera de palabra: sin esto "sulfite" casaria dentro de otras
        # palabras y "stevia" dentro de nombres de marca.
        if re.search(rf"\b{re.escape(patron)}", plegado):
            encontrados[nombre] = numero
    return sorted(f"{n} ({e})" for n, e in encontrados.items())


def codigos_aditivos(texto: str | None) -> list[str]:
    """Aditivos declarados por **código**, normalizados a número E: `['E500', ...]`.

    Complementa a `aditivos()`, que lee nombres. Las dos hacen falta porque las
    etiquetas no escriben igual en todas partes: el snapshot de OpenFoodFacts es
    anglosajón y pone «potassium sorbate»; una galleta peruana pone
    «Conservante sin 202». Leer solo una de las dos formas deja fuera media
    góndola.

    Las letras se conservan y los romanos van entre paréntesis: ver `_ROMANOS`
    para por qué esa distinción no es cosmética. `INS 322i`, `INS 322(i)` y
    `E 322 (i)` salen los tres como `E322(i)`.

    **No devuelve nombres**: este módulo es puro y no consulta corpus. Quien
    quiera el nombre del E500 lo resuelve contra la Parte B del Anexo II, que
    para eso trae 321 pares número→nombre.
    """
    if not texto:
        return []

    encontrados: list[str] = []
    for numero, entre_parentesis, pegado in _CODIGO_ADITIVO.findall(texto):
        if int(numero) not in _RANGO_VALIDO:
            continue

        sufijo = (entre_parentesis or pegado or "").lower()
        if not sufijo:
            codigo = f"E{numero}"
        elif _ROMANOS.match(sufijo):
            codigo = f"E{numero}({sufijo})"
        elif sufijo in "abcdefgh" and len(sufijo) == 1:
            # Las variantes por letra del Codex no pasan de la 'h' (E150a-d,
            # E160a-f, E161a-g, E553a-b, E960a-d). Aceptar cualquier letra
            # convertía «E 330 y E 202» en «E330y»: la conjunción castellana
            # se pegaba al código y producía un aditivo que no existe.
            codigo = f"E{numero}{sufijo}"
        else:
            # Ni romano ni variante: es la palabra siguiente pegada al número
            # («500 mg», «160 gramos», «330 y»). Se toma el número a secas.
            codigo = f"E{numero}"

        if codigo not in encontrados:
            encontrados.append(codigo)

    return sorted(encontrados)


def alergenos_declarados(texto: str | None) -> list[str]:
    """Alérgenos que la etiqueta **declara**, no los que se podrían deducir.

    `[]` significa "la etiqueta no los declara en este texto", que no es lo
    mismo que "no tiene". Quien lea la tabla tiene que poder distinguirlo, así
    que la interfaz lo escribe como *sin declaración* y no como *ninguno*.
    """
    if not texto:
        return []
    encontrados: set[str] = set()
    for declaracion in _DECLARACION.findall(texto):
        plegado = _plegar(declaracion)
        for patron, nombre in ALERGENOS.items():
            if re.search(rf"\b{re.escape(patron)}", plegado):
                encontrados.add(nombre)
    return sorted(encontrados)
