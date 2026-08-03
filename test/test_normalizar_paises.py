"""
TIER 2 · T2.1 (S4): normalización de país a ISO-3166 alpha-2.

Gates del plan §T2.1: >=95 % de las 29.054 filas con al menos un ISO, 0 filas con
prefijo `en:` crudo, reporte de no mapeados con <=200 variantes.

Se ejecuta con pytest o directamente: python test/test_normalizar_paises.py
"""
import json
from pathlib import Path

from etl.normalizar_paises import ISO_ALPHA2, no_mapeados, normalizar

PRODUCTOS = Path("datasets/2026-07/productos_merged.json")

MIN_PCT_CON_ISO = 95.0
MAX_VARIANTES_SUELTAS = 200

# Los 5 valores más frecuentes que significan Estados Unidos. Entre los cinco
# suman 14.261 de las 29.054 filas: si estos cinco no colapsan, el mapa por país
# de la demo sale ilegible y da igual lo que haga el resto de la tabla.
ALIAS_EEUU = [
    "United States",         # 9.986 filas
    "en:United States",      # 1.633
    "en:us",                 # 1.005
    "United States, World",  #   852
    "en:united-states",      #   785
]


def test_cinco_alias_de_eeuu_colapsan_a_us():
    """DoD de TIER 2: los 5 alias de Estados Unidos -> todos US."""
    for alias in ALIAS_EEUU:
        assert normalizar(alias) == ["US"], f"{alias!r} -> {normalizar(alias)!r}"
    print(f"PASS: {len(ALIAS_EEUU)} alias de EE. UU. -> ['US']")


def test_world_se_descarta_pero_el_pais_se_conserva():
    """Regla 4: `world` no es un país; el resto del multivalor sí."""
    assert normalizar("United States, World") == ["US"]
    assert normalizar("World") == []
    assert normalizar("en:world") == []
    # Supranacional: mismo tratamiento que `world`.
    assert normalizar("European Union") == []
    print("PASS: world y european union descartados sin perder el país vecino")


def test_prefijos_anidados():
    """El snapshot trae `en:en:us` y `fr:en:fr`: el pelado va hasta punto fijo.

    Con un solo paso, `en:en:us` quedaría en `en:us` y fallaría el gate de
    0 filas con prefijo crudo.
    """
    assert normalizar("en:en:us") == ["US"]
    assert normalizar("fr:en:fr") == ["FR"]
    assert normalizar("fr:fr:france") == ["FR"]
    print("PASS: prefijos anidados pelados hasta punto fijo")


def test_multivalor_ordenado_y_sin_repetir():
    assert normalizar("France, Spain") == ["ES", "FR"]
    # El mismo país por dos caminos distintos no se duplica.
    assert normalizar("Germany, en:de, Deutschland") == ["DE"]
    print("PASS: multivalor ordenado, sin duplicados")


def test_no_se_adivina():
    """Regla 5: sin correspondencia, fuera de la lista. No se inventa un país."""
    # `en` es un código de idioma, no de país: no debe colarse como 'EN'.
    assert normalizar("en") == []
    assert "EN" not in ISO_ALPHA2
    # Históricos sin ISO vigente.
    assert normalizar("Yugoslavia") == []
    assert normalizar("East Germany") == []
    # Ambiguo: Saint-Martin (MF) o la región peruana de San Martín.
    assert normalizar("San Martin") == []
    # Y lo que se descarta queda registrado para el reporte, no se pierde.
    assert no_mapeados("Yugoslavia") == ["yugoslavia"]
    print("PASS: lo desconocido no se adivina y queda en el reporte")


def test_alias_con_tilde_casan():
    """La tabla se pliega con la misma función que el dato.

    Escribir "España" o "Türkiye" en el diccionario tiene que funcionar igual
    que escribir "espana". Sin plegar las claves, un alias con tilde no casa
    nunca y falla en silencio.
    """
    assert normalizar("España") == ["ES"]
    assert normalizar("Türkiye") == ["TR"]
    assert normalizar("Österreich") == ["AT"]
    print("PASS: alias con tilde casan")


def test_entradas_vacias():
    for vacio in (None, "", "   ", ","):
        assert normalizar(vacio) == [], f"{vacio!r}"
    print("PASS: entradas vacías -> []")


def test_gate_cobertura_sobre_el_snapshot():
    """Gate T2.1 sobre las 29.054 filas reales."""
    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))
    total = len(productos)

    con_iso = 0
    crudos = 0
    sueltas = set()

    for p in productos:
        bruto = p.get("pais")
        isos = normalizar(bruto)
        if isos:
            con_iso += 1
            for iso in isos:
                assert iso in ISO_ALPHA2, f"{iso} no es ISO-3166 alpha-2"
        sueltas.update(no_mapeados(bruto))
        if any(":" in iso for iso in isos):
            crudos += 1

    pct = 100.0 * con_iso / total
    assert pct >= MIN_PCT_CON_ISO, f"Solo {pct:.2f} % con ISO"
    assert crudos == 0, f"{crudos} filas con prefijo crudo"
    assert len(sueltas) <= MAX_VARIANTES_SUELTAS, f"{len(sueltas)} variantes sueltas"

    print(f"PASS: {con_iso:,}/{total:,} = {pct:.2f} % con ISO · "
          f"0 crudos · {len(sueltas)} variantes sueltas")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
