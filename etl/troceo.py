"""
Troceo de documentos largos en pasajes aptos para embedding.

Lo usan `procesar_ecfr` y `procesar_digesa`. Sin esto, una sección del CFR de
1000 palabras se compara contra una consulta de 2 ("arándano blueberry") y la
similitud coseno sale negativa aunque el documento mencione el término: la
señal se diluye. Troceado, el pasaje que menciona "blueberries" sí puntúa.
"""
import re

MAX_PALABRAS = 180


def normalizar(texto: str) -> str:
    """Reconstruye párrafos: los PDFs y el XML traen cortes de línea duros."""
    texto = re.sub(r"-\n(\w)", r"\1", texto)   # palabras cortadas por guion
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def trocear(texto: str, max_palabras: int = MAX_PALABRAS) -> list[str]:
    """Divide en pasajes cortando en límites de frase, no a mitad de una."""
    frases = re.split(r"(?<=[.;:])\s+", normalizar(texto))
    pasajes, actual = [], []

    for frase in frases:
        actual.append(frase)
        if sum(len(f.split()) for f in actual) >= max_palabras:
            pasajes.append(" ".join(actual))
            actual = []
    if actual:
        pasajes.append(" ".join(actual))

    return [p for p in pasajes if p.strip()]
