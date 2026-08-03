"""
TIER 4 · Nivel A (S4): lectura del texto de ingredientes.

Lo que estos tests protegen no es el parseo, es la frontera entre **leer** y
**deducir**:

  - un aditivo escrito en la etiqueta se puede afirmar;
  - un alérgeno solo se puede afirmar si la etiqueta lo declara.

La segunda mitad es la que importa. Deducir "lleva leche, luego es alérgeno" es
inventar un dato de seguridad alimentaria, y es justo el tipo de invento que P04
persigue en el resto del sistema.

Se ejecuta con pytest o directamente: python test/test_analizar_ingredientes.py
"""
import json
from pathlib import Path

from etl.analizar_ingredientes import (aditivos, alergenos_declarados, contar,
                                       separar)

PRODUCTOS = Path("datasets/2026-07/productos_merged.json")


# --- leer -----------------------------------------------------------------

def test_aditivos_por_nombre_con_su_numero_e():
    texto = "organic oats, pectin, citric acid, soy lecithin, sea salt"
    assert aditivos(texto) == ["Lecitina (E322)", "Pectina (E440)",
                               "Ácido cítrico (E330)"]
    print("PASS: aditivos leídos con su número E")


def test_aditivos_en_espanol_y_con_tildes():
    """La tabla se pliega igual que el dato: 'Ácido Cítrico' tiene que casar."""
    assert aditivos("harina, PECTINA, Ácido Cítrico") == \
        ["Pectina (E440)", "Ácido cítrico (E330)"]
    print("PASS: aditivos en español y con tildes")


def test_aditivos_sin_repetir():
    texto = "citric acid, water, citric acid, acido citrico"
    assert aditivos(texto) == ["Ácido cítrico (E330)"]
    print("PASS: el mismo aditivo no se cuenta dos veces")


def test_separar_respeta_los_subcompuestos():
    """Partir a lo bruto rompe la fórmula y se ve roto en la lista."""
    assert separar("agua, azúcar, pectina") == ["agua", "azúcar", "pectina"]
    # Lo que un corte ingenuo convertiría en "harina (trigo" y "hierro)".
    assert separar("harina (trigo, hierro), agua") == \
        ["harina (trigo, hierro)", "agua"]
    # Anidamiento de dos niveles, habitual en etiquetas de EE. UU.
    assert separar("relleno [fruta (fresa, mora), azúcar], sal") == \
        ["relleno [fruta (fresa, mora), azúcar]", "sal"]
    print("PASS: el corte respeta paréntesis y corchetes")


def test_separar_limpia_los_restos_de_puntuacion():
    assert separar("agua, azúcar.") == ["agua", "azúcar"]
    assert separar("agua,, , azúcar") == ["agua", "azúcar"]
    assert separar("  ") == [] and separar(None) == []
    print("PASS: sin ítems vacíos ni puntuación colgando")


def test_separar_aguanta_un_parentesis_sin_cerrar():
    """Las etiquetas vienen sucias; un texto roto no debe tragarse la lista."""
    assert separar("harina (trigo, agua") == ["harina (trigo, agua"]
    assert separar("harina) , agua") == ["harina)", "agua"]
    print("PASS: paréntesis descuadrados no rompen el corte")


def test_el_contador_es_el_largo_de_la_lista():
    """Un solo número para una sola lista.

    Si `contar` y `separar` usaran reglas distintas, la ficha enseñaría "47"
    encima de una lista de 20 ítems y ninguno de los dos números seria creible.
    """
    for texto in ("agua, azúcar, pectina",
                  "harina (trigo, hierro), agua",
                  "relleno [fruta (fresa, mora), azúcar], sal, agua"):
        assert contar(texto) == len(separar(texto)), texto
    assert contar(None) is None and contar("   ") is None
    print("PASS: contar() == len(separar())")


# --- no deducir -----------------------------------------------------------

def test_alergeno_solo_si_la_etiqueta_lo_declara():
    """La mitad importante del módulo."""
    # Declarado: se puede afirmar.
    assert alergenos_declarados("oats, milk. Contains: milk, soy") == \
        ["Leche", "Soya"]
    assert alergenos_declarados("avena. Contiene: leche y trigo") == \
        ["Leche", "Trigo"]

    # Presente como ingrediente pero SIN declaración: no se afirma nada.
    assert alergenos_declarados("wheat flour, milk, soy lecithin") == []
    print("PASS: solo se recogen alérgenos declarados")


def test_may_contain_tambien_es_una_declaracion():
    assert alergenos_declarados("oats. May contain peanuts") == ["Maní"]
    assert alergenos_declarados("avena. Puede contener maní") == ["Maní"]
    print("PASS: 'may contain' cuenta como declaración")


def test_sin_texto_no_hay_nada_que_leer():
    for vacio in (None, "", "   "):
        assert aditivos(vacio) == [] and alergenos_declarados(vacio) == []
    print("PASS: sin texto, listas vacías")


def test_texto_sin_aditivos_devuelve_vacio():
    """Un falso positivo aquí mete un aditivo en un producto que no lo lleva."""
    assert aditivos("arándanos, azúcar, agua") == []
    assert aditivos("blueberries, sugar, water") == []
    print("PASS: producto limpio, sin aditivos inventados")


# --- sobre el snapshot real ----------------------------------------------

def test_cobertura_sobre_el_snapshot():
    """El campo está al 100 %: es lo que hace barato todo este nivel."""
    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))
    con_texto = [p for p in productos if (p.get("ingredientes") or "").strip()]
    assert len(con_texto) == len(productos), \
        f"solo {len(con_texto)}/{len(productos)} traen ingredientes"

    muestra = productos[:3000]
    con_ad = sum(1 for p in muestra if aditivos(p["ingredientes"]))
    con_al = sum(1 for p in muestra if alergenos_declarados(p["ingredientes"]))

    # Si el detector dejara de encontrar nada, estos numeros caerian a cero y el
    # nivel A se quedaria en una columna de texto sin leer.
    assert con_ad > len(muestra) * 0.30, f"solo {con_ad} con aditivos"
    print(f"PASS: 100 % con texto · {con_ad}/{len(muestra)} con aditivos · "
          f"{con_al} con alérgenos declarados")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
