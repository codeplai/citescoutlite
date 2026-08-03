"""
TIER 2 · T2.2 (S4): saneado de texto del snapshot.

Gate del plan §T2.2: 0 caracteres de reemplazo en `marca`, `nombre` y `pais`.

Se ejecuta con pytest o directamente: python test/test_limpiar_texto.py
"""
import json
from pathlib import Path

from etl.limpiar_texto import (CAMPOS_DEL_GATE, REEMPLAZO, limpiar,
                               limpiar_producto, producto_publicable,
                               tiene_reemplazo)

PRODUCTOS = Path("datasets/2026-07/productos_merged.json")

# La única fila del snapshot cuyo `nombre` trae U+FFFD. Era "Pão integral".
FILA_ROTA = "OFF:7896002308762"


def test_doble_encoding_se_repara_cuando_el_viaje_de_vuelta_es_exacto():
    """Clase A: los bytes siguen ahí, solo mal interpretados."""
    assert limpiar("EspaÃ±a") == "España"
    assert limpiar("cafÃ©") == "café"
    assert limpiar("dâ€™Ivoire") == "d’Ivoire"
    print("PASS: doble-encoding reparado")


def test_texto_legitimo_no_se_toca():
    """El guardia exige una firma de mojibake: sin ella, no se toca nada.

    Es la mitad importante del test. Una función que 'repara' texto sano
    hace más daño que la que no repara nada.
    """
    for sano in ("España", "Pão integral", "café", "arándano", "quinua",
                 "Ω-3", "日本", "L'Éléfàn", "plain ascii"):
        assert limpiar(sano) == sano, sano
    print("PASS: texto legítimo intacto")


def test_u_fffd_no_se_inventa():
    """Clase B: el byte se perdió. Ni se repara ni se borra en silencio."""
    roto = f"P{REEMPLAZO}o integral"
    assert limpiar(roto) == roto, "limpiar() no debe tocar U+FFFD"
    assert tiene_reemplazo(roto)
    # Y en particular NO debe deducir la letra que falta.
    assert limpiar(roto) != "Pão integral"
    print("PASS: U+FFFD ni reparado ni borrado")


def test_reparacion_que_metiera_u_fffd_se_rechaza():
    """Cambiar un error visible por otro peor no es reparar."""
    # 'Ã' suelta: encodea, pero el decode produciría basura o fallaría.
    entrada = "Ã¿"
    salida = limpiar(entrada)
    assert REEMPLAZO not in (salida or "")
    print("PASS: no se acepta una reparación que introduzca U+FFFD")


def test_entradas_no_texto():
    assert limpiar(None) is None
    assert limpiar("") == ""
    assert not tiene_reemplazo(None, "", "sano")
    print("PASS: None y vacío pasan tal cual")


def test_producto_publicable_excluye_solo_por_campos_del_gate():
    """`ingredientes` con U+FFFD no cuesta la exclusión: no se enseña."""
    assert producto_publicable({"nombre": "Pan", "marca": "X", "pais": "PE"})
    assert not producto_publicable({"nombre": f"P{REEMPLAZO}o", "marca": "X"})
    # Fuera del gate -> sigue siendo publicable.
    assert producto_publicable({"nombre": "Pan", "marca": "X",
                                "ingredientes": f"harina{REEMPLAZO}"})
    print(f"PASS: la exclusión mira solo {CAMPOS_DEL_GATE}")


def test_limpiar_producto_no_altera_el_original():
    original = {"nombre": "EspaÃ±a", "marca": "X", "otro": 1}
    copia = limpiar_producto(original)
    assert original["nombre"] == "EspaÃ±a", "limpiar_producto mutó la entrada"
    assert copia["nombre"] == "España"
    assert copia["otro"] == 1
    print("PASS: limpiar_producto no muta la entrada")


def test_gate_sobre_el_snapshot():
    """Gate T2.2: 0 caracteres de reemplazo en lo que se publica."""
    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))

    excluidas = [p["id_fuente"] for p in productos if not producto_publicable(p)]
    assert excluidas == [FILA_ROTA], f"Excluidas inesperadas: {excluidas}"

    for p in productos:
        if not producto_publicable(p):
            continue
        limpio = limpiar_producto(p)
        for campo in CAMPOS_DEL_GATE:
            valor = limpio.get(campo)
            assert not tiene_reemplazo(valor), \
                f"{p['id_fuente']} · {campo} = {valor!r}"

    publicables = len(productos) - len(excluidas)
    print(f"PASS: {publicables:,}/{len(productos):,} publicables · "
          f"0 caracteres de reemplazo · 1 fila excluida y declarada")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
