"""
T4.4 — De la categoría que trae OpenFoodFacts a la del Anexo II.

## El problema, medido

`categoria` está al 82,7 % del snapshot, pero con **8.322 valores distintos**
(3.854 solo entre las 14.572 filas que llevan aditivo). Es el mismo desastre que
tuvo `pais` con sus 1.578 variantes para ~100 países.

Lo que salva la situación es la **forma**: no son etiquetas sueltas, son rutas
de taxonomía separadas por comas, de lo general a lo concreto —
`Snacks, Sweet snacks, Biscuits and cakes, Biscuits`. Así que la unidad a mapear
no es la cadena entera sino el **segmento**, y eso cambia el orden de magnitud:

    top 40 cadenas exactas -> 35,2 % de las filas
    top 40 segmentos       -> 56,1 %
    top 60 segmentos       -> 59,6 %

## El techo, que conviene saber antes de empezar

**2.991 filas (20,5 %) no tienen categoría utilizable** —vacía, `undefined` o
solo etiquetas sin traducir—. Ninguna tabla de mapeo las va a alcanzar: el techo
real de este módulo es el 79,5 %, no el 100 %.

## Dos vocabularios, y solo uno se deriva

El Codex y la UE **comparten la raíz de la numeración y divergen en la hoja**:
el `04.1.2.8` que cita `acido1.pptx` es un código del GSFA y **no existe** en las
116 categorías del Anexo II. Son dos sistemas parecidos, no el mismo.

Aquí solo se deriva el **código del Anexo II**, porque es el único que hoy
consume alguien (`EvaluadorUE`). El agente del eCFR quiere un nombre de alimento
en inglés, no un código, así que se devuelve también eso. Y el Codex trabaja con
la categoría de referencia que trae su propia fila curada, así que no necesita
esto todavía.

## Un mapeo es una deducción, y por eso nunca cierra un veredicto

Que «Snacks, Sweet snacks» sea la categoría 15.1 del Anexo II es una lectura
razonable, no un hecho comprobable: los aperitivos podrían caer en 15.1
(a base de patata o cereales) o en 05.2 (confitería). **Por eso el orquestador
degrada a `SI_CONDICIONADO` cualquier veredicto que se apoye en una categoría
deducida aquí.** Es exactamente el asterisco de los PPTX y la nota al pie que
piden confirmar la clasificación exacta antes de cada envío.

El `nivel` de cada entrada dice cuánto se está estirando:

- `directo` — la etiqueta nombra la categoría casi con las mismas palabras
  («yogurts» → 01.4, «vinegars» → 12.3). Poco margen de error.
- `amplio` — la etiqueta cubre varias categorías y se elige la mayoritaria
  («snacks» → 15.1). Aquí es donde el asterisco se gana el sueldo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

#: Segmento de OFF -> (código del Anexo II, término inglés, nivel).
#:
#: Ordenado por frecuencia en el snapshot. Los códigos se validan en test contra
#: las 116 categorías reales del Anexo II: una entrada que apunte a un código
#: inexistente es un error de programación, no un dato dudoso.
#:
#: Hay segmentos en varios idiomas porque el snapshot los trae así («alimentos y
#: bebidas de origen vegetal» es el mismo nodo que «plant based foods and
#: beverages»). Mapear las dos formas sale gratis y recupera cientos de filas.
MAPA: dict[str, tuple[str, str, str]] = {
    # --- lácteos (01) ---
    "yogurts": ("01.4", "yogurt", "directo"),
    "yogurt": ("01.4", "yogurt", "directo"),
    "fermented milk products": ("01.4", "fermented milk product", "directo"),
    "fermented dairy desserts": ("01.4", "fermented dairy dessert", "directo"),
    "dairy desserts": ("01.4", "dairy dessert", "directo"),
    "dairies": ("01.4", "dairy product", "amplio"),
    "milks": ("01.1", "milk", "directo"),
    "cheeses": ("01.7.2", "cheese", "amplio"),
    "creams": ("01.6.3", "cream", "directo"),
    "plant based beverages": ("01.8", "plant-based milk substitute", "amplio"),
    "plant based milks": ("01.8", "plant-based milk substitute", "directo"),

    # --- grasas (02) ---
    "vegetable fats": ("02.1", "vegetable fat", "directo"),
    "olive oils": ("02.1", "olive oil", "directo"),
    "vegetable oils": ("02.1", "vegetable oil", "directo"),
    "margarines": ("02.2.2", "margarine", "directo"),

    # --- helados (03) ---
    "ice creams and sorbets": ("03", "ice cream", "directo"),
    "frozen desserts": ("03", "frozen dessert", "directo"),

    # --- frutas y hortalizas (04) ---
    "fruits and vegetables based foods": ("04.1.2", "fruit and vegetable product", "amplio"),
    "canned foods": ("04.2.3", "canned food", "amplio"),
    "canned vegetables": ("04.2.3", "canned vegetable", "directo"),
    "canned fruits": ("04.2.3", "canned fruit", "directo"),
    "pickles": ("04.2.2", "pickled vegetable", "directo"),
    "dried fruits": ("04.2.1", "dried fruit", "directo"),
    "fruit purees": ("04.2.4.1", "fruit puree", "directo"),
    "compotes": ("04.2.4.2", "compote", "directo"),
    "jams": ("04.2.5.2", "jam", "directo"),
    "marmalades": ("04.2.5.2", "marmalade", "directo"),
    "fruit preparations": ("04.2.4.1", "fruit preparation", "directo"),
    "potato products": ("04.2.6", "potato product", "directo"),

    # --- cacao, confitería (05) ---
    "chocolates": ("05.1", "chocolate", "directo"),
    "cocoa and its products": ("05.1", "cocoa product", "directo"),
    "confectioneries": ("05.2", "confectionery", "directo"),
    "candies": ("05.2", "candy", "directo"),
    "gummi candies": ("05.2", "gummi candy", "directo"),
    "chewing gum": ("05.3", "chewing gum", "directo"),

    # --- cereales (06) ---
    "cereals and their products": ("06.1", "cereal product", "amplio"),
    "breakfast cereals": ("06.3", "breakfast cereal", "directo"),
    "pastas": ("06.4.2", "dry pasta", "directo"),
    "fresh pastas": ("06.4.1", "fresh pasta", "directo"),
    "flours": ("06.2.1", "flour", "directo"),
    "rices": ("06.1", "rice", "directo"),
    "cereals and potatoes": ("06.1", "cereal or potato product", "amplio"),

    # --- panadería (07) ---
    "breads": ("07.1", "bread", "directo"),
    "biscuits and cakes": ("07.2", "biscuit or cake", "directo"),
    "biscuits": ("07.2", "biscuit", "directo"),
    "cakes": ("07.2", "cake", "directo"),
    "pastries": ("07.2", "pastry", "directo"),
    "viennoiserie": ("07.2", "pastry", "directo"),

    # --- carne (08) ---
    "meats": ("08.1.1", "meat", "amplio"),
    "prepared meats": ("08.2.2", "processed meat", "directo"),
    "hams": ("08.2.4.2", "dry-cured ham", "directo"),
    "sausages": ("08.2.2", "sausage", "directo"),

    # --- pescado (09) ---
    "seafood": ("09.2", "processed fish product", "amplio"),
    "fishes": ("09.1.1", "fish", "directo"),
    "canned fishes": ("09.2", "canned fish", "directo"),

    # --- huevos (10) ---
    "eggs": ("10.1", "egg", "directo"),

    # --- azúcares y edulcorantes (11) ---
    "sugars": ("11.1", "sugar", "directo"),
    "syrups": ("11.2", "syrup", "directo"),
    "sweeteners": ("11.4.2", "table-top sweetener", "amplio"),

    # --- condimentos y salsas (12) ---
    "condiments": ("12.6", "condiment", "amplio"),
    "sauces": ("12.6", "sauce", "directo"),
    "dips": ("12.6", "dip sauce", "directo"),
    "ketchup": ("12.6", "ketchup", "directo"),
    "mayonnaises": ("12.6", "mayonnaise", "directo"),
    "mustards": ("12.4", "mustard", "directo"),
    "vinegars": ("12.3", "vinegar", "directo"),
    "salts": ("12.1.1", "salt", "directo"),
    "spices": ("12.2.1", "spice", "directo"),
    "soups": ("12.5", "soup", "directo"),
    "broths": ("12.5", "broth", "directo"),
    "prepared salads": ("12.7", "prepared salad", "directo"),
    "salads": ("12.7", "prepared salad", "amplio"),

    # --- infantil y dietético (13) ---
    "baby food": ("13.1.4", "food for young children", "directo"),
    "baby foods": ("13.1.4", "food for young children", "directo"),
    "infant formulae": ("13.1.1", "infant formula", "directo"),

    # --- bebidas (14) ---
    "waters": ("14.1.1", "water", "directo"),
    "fruit juices": ("14.1.2", "fruit juice", "directo"),
    "juices": ("14.1.2", "juice", "directo"),
    "nectars": ("14.1.3", "fruit nectar", "directo"),
    "sodas": ("14.1.4", "soft drink", "directo"),
    "carbonated drinks": ("14.1.4", "carbonated drink", "directo"),
    "energy drinks": ("14.1.4", "energy drink", "directo"),
    "iced teas": ("14.1.4", "iced tea", "directo"),
    "beverages": ("14.1.4", "beverage", "amplio"),
    "coffees": ("14.1.5.1", "coffee", "directo"),
    "teas": ("14.1.5.2", "tea", "directo"),
    "beers": ("14.2.1", "beer", "directo"),
    "wines": ("14.2.2", "wine", "directo"),
    "spirits": ("14.2.6", "spirit drink", "directo"),

    # --- aperitivos (15) ---
    "salted snacks": ("15.1", "savoury snack", "directo"),
    "appetizers": ("15.1", "savoury snack", "directo"),
    "crisps": ("15.1", "potato crisp", "directo"),
    "chips and fries": ("15.1", "potato crisp", "directo"),
    "nuts": ("15.2", "processed nut", "directo"),
    "snacks": ("15.1", "savoury snack", "amplio"),
    "sweet snacks": ("07.2", "sweet baked snack", "amplio"),

    # --- postres (16) ---
    "desserts": ("16", "dessert", "amplio"),

    # --- complementos alimenticios (17) ---
    "dietary supplements": ("17.1", "food supplement", "directo"),
    "dietary supplement": ("17.1", "food supplement", "directo"),

    # --- variantes en castellano del mismo nodo de la taxonomía ---
    "alimentos y bebidas de origen vegetal": ("18", "plant-based food", "amplio"),
    "bebidas": ("14.1.4", "beverage", "amplio"),
    "lacteos": ("01.4", "dairy product", "amplio"),
    "postres": ("16", "dessert", "amplio"),
    "snacks dulces": ("07.2", "sweet baked snack", "amplio"),
    "galletas": ("07.2", "biscuit", "directo"),
    "salsas": ("12.6", "sauce", "directo"),
    "zumos": ("14.1.2", "fruit juice", "directo"),

    # --- nodos raíz de OFF: no dicen casi nada, pero son mejor que nada ---
    "meals": ("18", "prepared meal", "amplio"),
    "frozen foods": ("18", "frozen prepared food", "amplio"),
    "groceries": ("18", "processed food", "amplio"),
    "plant based foods": ("18", "plant-based food", "amplio"),
    "plant based foods and beverages": ("18", "plant-based food", "amplio"),
    "fermented foods": ("18", "fermented food", "amplio"),
}

Nivel = Literal["directo", "amplio"]

# Etiquetas que OFF usa para decir «no lo sé». Se descartan antes de mapear:
# tratarlas como un segmento más las metería en el ranking de frecuencia y
# darían una cobertura falsa.
NULAS = {"undefined", "unknown", "other", "otros", ""}

_ESPACIOS = re.compile(r"\s+")
_PREFIJO_IDIOMA = re.compile(r"^[a-z]{2}:")


@dataclass(frozen=True)
class Categoria:
    """La categoría de un producto, tal como la ven los tres mercados."""

    codigo_ue: str | None
    termino_en: str | None
    nivel: Nivel | None
    segmento: str | None  # el trozo de la etiqueta que produjo el mapeo
    original: str | None

    @property
    def deducida(self) -> bool:
        """Siempre True cuando hay código: aquí nada se sabe, se deduce."""
        return self.codigo_ue is not None


def normalizar(segmento: str) -> str:
    """`en:baby-food` -> `baby food`. Sin tildes y sin puntuación."""
    s = (segmento or "").strip().lower()
    s = _PREFIJO_IDIOMA.sub("", s).replace("-", " ")
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    return _ESPACIOS.sub(" ", re.sub(r"[^a-z0-9 ]", " ", s)).strip()


def segmentos(categoria: str | None) -> list[str]:
    """La ruta de taxonomía partida y normalizada, **de lo concreto a lo general**.

    OFF la escribe al revés —`Snacks, Sweet snacks, Biscuits`— y el último
    segmento es el más específico, que es el que mejor mapea. Se invierte aquí
    para que quien recorra la lista encuentre primero lo que más dice.
    """
    if not categoria:
        return []
    partes = [normalizar(p) for p in categoria.split(",")]
    return [p for p in reversed(partes) if p and p not in NULAS]


def mapear(categoria: str | None) -> Categoria:
    """La categoría del Anexo II que mejor corresponde, o vacía si no se sabe.

    Se queda con el **primer segmento que mapea empezando por el más
    específico**, y entre dos que mapeen prefiere el `directo` sobre el
    `amplio`: `Snacks, Sweet snacks, Biscuits` tiene que dar 07.2 por
    «biscuits», no 15.1 por «snacks».
    """
    encontrados = [(s, MAPA[s]) for s in segmentos(categoria) if s in MAPA]
    if not encontrados:
        return Categoria(None, None, None, None, categoria)

    directo = next((e for e in encontrados if e[1][2] == "directo"), None)
    segmento, (codigo, termino, nivel) = directo or encontrados[0]
    return Categoria(codigo, termino, nivel, segmento, categoria)
