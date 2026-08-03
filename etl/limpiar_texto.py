"""
TIER 2 · T2.2 (S4): saneado de texto del snapshot.

Se aplica **al leer**, como T2.1: no reescribe `productos_merged.json` ni el
índice. `limpiar()` es pura.

El plan §T2.2 supone un caso — `Espa�a` por leer el CSV con la codificación
equivocada — y una cura: "se corrige en la misma función". Medido el snapshot,
son **dos** casos con curas distintas, y solo uno tiene cura:

**A · Doble-encoding, 16 celdas (todas en `ingredientes`).** UTF-8 leído como
cp1252. Cuando los bytes siguen intactos, el viaje de vuelta
`.encode('cp1252').decode('utf-8')` los restituye **exactamente**: eso no es
adivinar, es deshacer una operación conocida.

Pero medido el snapshot, **solo 1 de las 16 se restituye**. Las otras 15 son
`â€ ` — el mojibake de `†` (b'\xe2\x80\xa0'), el asterisco de "orgánico" de las
listas de ingredientes de EE. UU. — y su tercer byte, 0xA0, **el ETL de S2 lo
normalizó a espacio (0x20)** al colapsar blancos. Con el byte cambiado el viaje
de vuelta ya no es exacto: `b'\xe2\x80 '` no es UTF-8 válido. Se podría deducir
que `â€`+espacio era `†` y casi siempre acertaríamos, pero "casi siempre" no es
"exactamente", y esta función solo hace lo segundo. El guardia las rechaza solo,
sin caso especial.

Que queden 15 sin reparar no toca ningún gate: están todas en `ingredientes`,
que no es campo del gate de T2.2 ni del contrato `ProductoEnMercado` de T1.3.
Es deuda declarada, no un descuido.

**B · Carácter de reemplazo U+FFFD, 10 celdas (9 en `ingredientes`, 1 en
`nombre`).** Aquí el decodificador ya descartó el byte y escribió `�`. No hay
viaje de vuelta: la información se perdió en el ETL de S2 y el export original
(~9 GB) ya no está en disco. `OFF:7896002308762` se llama `P�o integral` y
casi con seguridad era `Pão integral`, pero "casi con seguridad" es exactamente
lo que este proyecto promete no meter en un informe. **No se repara.**

Por eso `limpiar()` arregla A y deja B intacto, y `tiene_reemplazo()` existe para
que quien lee decida: la vía limpia para el mapa comercial es excluir esa fila y
declararlo, no rellenar el hueco a ojo.

Una nota sobre por qué B no se puede rescatar ni con maña: el ETL de S2 pasa
`ingredientes` a minúsculas, y minusculizar rompe el mapeo de bytes del
doble-encoding (`Ã±` → `ã±`, que ya no decodifica).

Cierre del gate: `producto_publicable()` deja fuera del mapa comercial la única
fila cuyo `nombre` trae U+FFFD. Es 1 de 29.054, se declara en el reporte, y es
preferible a enseñar `P�o integral` en el PDF o a escribir la `ã` a mano.

Uso como librería:
    from etl.limpiar_texto import limpiar, tiene_reemplazo
    limpiar("cocoa*â€ , dried spinach")   # -> "cocoa*† , dried spinach"

Uso como reporte (gate de T2.2):
    uv run python -m etl.limpiar_texto
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

REEMPLAZO = "�"

# Firmas de doble-encoding. Son secuencias casi imposibles en texto real: `Ã`
# seguida de un carácter alto, `â€` (prefijo de la puntuación tipográfica) o `Â`
# seguida de espacio duro. Se exige una firma antes de intentar la reparación:
# así una cadena legítima nunca entra al viaje de ida y vuelta.
FIRMAS = re.compile(r"Ã[\x80-\xbf¡-ÿ]|â€|Â[\x80-\xa0¡-ÿ]|ã[\x80-\xbf¢]")

# Campos del snapshot que son texto libre.
CAMPOS_TEXTO = ("nombre", "marca", "pais", "categoria", "ingredientes")

# Alcance del gate del plan §T2.2: lo que el usuario ve en la tabla del informe.
CAMPOS_DEL_GATE = ("nombre", "marca", "pais")

MAX_PASADAS = 3  # hay celdas con doble mojibake encadenado


def _reparar(texto: str) -> str:
    """Deshace el doble-encoding si y solo si el viaje de vuelta es exacto."""
    for _ in range(MAX_PASADAS):
        if not FIRMAS.search(texto):
            break
        mejorado = None
        for codec in ("cp1252", "latin-1"):
            try:
                candidato = texto.encode(codec).decode("utf-8")
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
            # Si el viaje de vuelta introduce un U+FFFD, no era reparable:
            # se estaría cambiando un error visible por otro peor.
            if candidato != texto and REEMPLAZO not in candidato:
                mejorado = candidato
                break
        if mejorado is None:
            break
        texto = mejorado
    return texto


def limpiar(texto: str | None) -> str | None:
    """Repara doble-encoding y colapsa espacios. **No toca U+FFFD.**

    `None` y no-cadenas pasan tal cual: esta función no inventa valores ni
    convierte un vacío en una cadena, que es trabajo de P04.
    """
    if not isinstance(texto, str) or not texto:
        return texto
    return " ".join(_reparar(texto).split())


def tiene_reemplazo(*textos: str | None) -> bool:
    """True si alguno trae U+FFFD, es decir, un carácter perdido sin retorno."""
    return any(REEMPLAZO in t for t in textos if isinstance(t, str))


# No-datos disfrazados: la celda tiene contenido, pero el contenido es "no sé".
# El snapshot trae 33 (medidos en T1.1): `null` x24, `N/A` x6, `Unknown` x2,
# `None` x1, repartidos entre `marca`, `categoria` y un `nombre`.
#
# Vive aquí, y no en cada llamante, porque tiene dos usuarios con intereses
# opuestos y la lista **tiene que ser la misma**: el adaptador de T3.2, que los
# convierte a `None` al proyectar, y el validador P04 de T5.1, que falla si
# encuentra alguno en la salida. Si las dos listas divergen, P04 pasa a ser un
# test que se aprueba a sí mismo.
SIN_DATO = frozenset({
    "n/a", "n.a.", "na", "none", "null", "nan", "-", "--", "---", "?", "??",
    "desconocido", "desconocida", "unknown", "sin dato", "sin datos",
    "s/d", "s/n", "no disponible", "not available", "vacio", "vacío",
})


def valor_o_none(texto: str | None) -> str | None:
    """Texto saneado, o `None` si está vacío o es un no-dato disfrazado.

    Convertir `"N/A"` en `None` no es inventar: es reconocer una ausencia que
    venía escrita como si fuera un dato. Lo que sí sería inventar es lo
    contrario, rellenar el `None` con algo.
    """
    limpio = limpiar(texto)
    if not isinstance(limpio, str) or not limpio.strip():
        return None
    return None if limpio.strip().lower() in SIN_DATO else limpio.strip()


def limpiar_producto(producto: dict) -> dict:
    """Copia del producto con los campos de texto saneados."""
    salida = dict(producto)
    for campo in CAMPOS_TEXTO:
        if campo in salida:
            salida[campo] = limpiar(salida[campo])
    return salida


def producto_publicable(producto: dict) -> bool:
    """¿Puede esta fila salir en el mapa comercial?

    False si, ya saneada, algún campo que el informe **enseña** conserva un
    U+FFFD. Es la política que cierra el gate de T2.2: la fila se excluye y se
    declara, en vez de imprimir `P�o integral` o de rellenar la letra a ojo.

    Se comprueba sobre el texto ya limpio, no sobre el crudo: una celda que
    `limpiar()` sí sabe restituir no debe costarle la exclusión a su fila.
    """
    return not tiene_reemplazo(*(limpiar(producto.get(c))
                                 for c in CAMPOS_DEL_GATE))


# ---------------------------------------------------------------------------
# Reporte: mide el gate de T2.2 sobre el snapshot completo.
# ---------------------------------------------------------------------------

DATASET = Path("datasets/2026-07")
PRODUCTOS = DATASET / "productos_merged.json"
REPORTE = DATASET / "mojibake.json"


def main() -> int:
    if not PRODUCTOS.exists():
        print(f"[TEXTO] No existe {PRODUCTOS}")
        return 1

    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))

    reparadas: Counter[str] = Counter()
    irreparables: Counter[str] = Counter()
    filas_irreparables: list[dict] = []
    ejemplos: list[dict] = []

    for p in productos:
        afectada = False
        for campo in CAMPOS_TEXTO:
            antes = p.get(campo)
            if not isinstance(antes, str) or not antes:
                continue

            despues = limpiar(antes)
            if despues != antes and FIRMAS.search(antes):
                reparadas[campo] += 1
                if len(ejemplos) < 12:
                    ejemplos.append({
                        "id": p["id_fuente"], "campo": campo,
                        "antes": antes[:70], "despues": (despues or "")[:70],
                    })

            if tiene_reemplazo(despues):
                irreparables[campo] += 1
                afectada = True

        if afectada:
            filas_irreparables.append({
                "id": p["id_fuente"],
                "campos": [c for c in CAMPOS_TEXTO
                           if tiene_reemplazo(limpiar(p.get(c)))],
                "nombre": p.get("nombre"),
            })

    # El gate solo alcanza a lo que el informe enseña.
    en_gate = sum(irreparables[c] for c in CAMPOS_DEL_GATE)
    filas_gate = [f for f in filas_irreparables
                  if any(c in CAMPOS_DEL_GATE for c in f["campos"])]

    print(f"\n[TEXTO] A · doble-encoding reparado: {sum(reparadas.values())} celdas "
          f"{dict(reparadas)}")
    for e in ejemplos:
        print(f"        {e['id']} · {e['campo']}")
        print(f"          antes:   {e['antes']!r}")
        print(f"          después: {e['despues']!r}")

    print(f"\n[TEXTO] B · U+FFFD irreparable: {sum(irreparables.values())} celdas "
          f"{dict(irreparables)}")
    print(f"        en {len(filas_irreparables)} filas de {len(productos):,}")
    for f in filas_gate:
        print(f"        ← EN EL GATE: {f['id']} · {f['campos']} · {f['nombre']!r}")

    REPORTE.write_text(
        json.dumps({
            "filas": len(productos),
            "doble_encoding_reparado": dict(reparadas),
            "u_fffd_irreparable": dict(irreparables),
            "campos_del_gate": list(CAMPOS_DEL_GATE),
            "celdas_u_fffd_en_el_gate": en_gate,
            "filas_excluidas": [p["id_fuente"] for p in productos
                                if not producto_publicable(p)],
            "filas_afectadas": filas_irreparables,
            "decision": "el doble-encoding se repara porque el viaje de vuelta es "
                        "exacto; U+FFFD no se repara porque el byte se perdió y "
                        "reconstruirlo sería inventar. Las filas afectadas se "
                        "excluyen del mapa comercial y se declaran",
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[TEXTO] Reporte -> {REPORTE}")

    excluidas = [p["id_fuente"] for p in productos if not producto_publicable(p)]
    publicables = len(productos) - len(excluidas)

    print(f"\n[GATE] U+FFFD en {CAMPOS_DEL_GATE} sin política ... "
          f"{en_gate} celdas en {len(excluidas)} filas")
    print(f"[GATE] Filas excluidas por producto_publicable(): {excluidas}")
    print(f"[GATE] Publicables: {publicables:,}/{len(productos):,} "
          f"= {100.0 * publicables / len(productos):.3f} %")
    print(f"[GATE] 0 caracteres U+FFFD en lo que se publica ... PASA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
