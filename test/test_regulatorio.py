"""
TIER 6 (S2): corpus regulatorio eCFR + DIGESA indexado en LanceDB.

Requiere haber corrido: etl.procesar_ecfr, etl.procesar_digesa,
etl.procesar_regulatorio.

Se ejecuta con pytest o directamente: python test/test_regulatorio.py
"""
import json
import re
from pathlib import Path

import lancedb

from adaptadores.modelo_embeddings import DIMENSIONES
from adaptadores.verificador_rag import VerificadorRAG

ECFR = Path("datasets/2026-07/ecfr_aditivos.json")
DIGESA = Path("datasets/2026-07/digesa_normas.json")

MIN_DOCS_ECFR = 5
MIN_PALABRAS_DIGESA = 2000


def test_ecfr_minimo_5_documentos():
    """T6.1: >=5 documentos eCFR con cita y URL navegable."""
    docs = json.loads(ECFR.read_text(encoding="utf-8"))
    assert len(docs) >= MIN_DOCS_ECFR, f"Solo {len(docs)} documentos eCFR"

    for d in docs:
        assert d["texto"].strip(), f"{d['id']} sin texto"
        # Las secciones del CFR admiten sufijo de letra: 21 CFR 184.1141a
        assert re.match(r"^21 CFR \d+\.\d+[a-z]?$", d["cita"]), \
            f"Cita inválida: {d['cita']}"
        assert d["fuente_url"].startswith("https://www.ecfr.gov/"), d["fuente_url"]
        # La fecha es la vigencia oficial del título, no la de descarga.
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", d["fecha_publicacion"])

    print(f"PASS: {len(docs)} documentos eCFR con cita y URL")


def test_digesa_minimo_2000_palabras():
    """T6.2: >=2000 palabras de normativa DIGESA extraída de PDFs oficiales."""
    docs = json.loads(DIGESA.read_text(encoding="utf-8"))
    palabras = sum(len(d["texto"].split()) for d in docs)

    assert palabras >= MIN_PALABRAS_DIGESA, f"Solo {palabras} palabras DIGESA"
    for d in docs:
        assert d["fuente_url"].startswith("http://www.digesa.minsa.gob.pe/"), \
            d["fuente_url"]

    print(f"PASS: {palabras} palabras DIGESA en {len(docs)} pasajes")


def test_tabla_regulatorio_con_embeddings():
    """T6.3: tabla `regulatorio` en LanceDB con vectores bge-m3."""
    db = lancedb.connect("vectores")
    nombres = getattr(db.list_tables(), "tables", db.list_tables())
    assert "regulatorio" in nombres, "Falta la tabla regulatorio"

    tabla = db.open_table("regulatorio")
    assert tabla.count_rows() >= MIN_DOCS_ECFR

    fila = tabla.head(1).to_pylist()[0]
    assert len(fila["embedding"]) == DIMENSIONES, "Embedding no es 1024-dim"
    assert fila["fuente_url"], "fuente_url vacía"

    print(f"PASS: tabla regulatorio con {tabla.count_rows()} filas "
          f"({DIMENSIONES}-dim)")


def test_no_cita_normas_de_sustancias_no_relacionadas():
    """
    Regresión del fallo más grave de TIER 6.

    Con solo un umbral de similitud, la consulta por 'mango' recuperaba
    **Manganese sulfate** (+0.28) y 'quinua' recuperaba **Urea** (+0.19): normas
    de sustancias químicas presentadas como contexto regulatorio del insumo.
    El eCFR solo puede citarse si su texto nombra el insumo.
    """
    v = VerificadorRAG()

    for es, en, prohibido in [("mango", "mango", "manganese"),
                              ("quinua", "quinoa", "urea"),
                              ("palta", "avocado", "apricot")]:
        salida = v.verificar(en, es).lower()
        assert prohibido not in salida, (
            f"'{es}' cita una norma sobre '{prohibido}': {salida[:200]}"
        )

    print("PASS: sin normas de sustancias no relacionadas")


def test_ecfr_solo_si_nombra_el_insumo():
    """El arándano sí tiene norma CFR (las mermeladas nombran blueberries)."""
    v = VerificadorRAG()

    salida = v.verificar("blueberry", "arándano")
    assert "21 CFR" in salida, f"Arándano debería citar el CFR: {salida[:200]}"

    # Los insumos que el CFR no nombra deben decirlo explícitamente.
    salida_mango = v.verificar("mango", "mango")
    assert "Sin norma del 21 CFR" in salida_mango or "no contiene normas" in salida_mango

    print("PASS: el eCFR se cita solo cuando nombra el insumo")


if __name__ == "__main__":
    test_ecfr_minimo_5_documentos()
    test_digesa_minimo_2000_palabras()
    test_tabla_regulatorio_con_embeddings()
    test_no_cita_normas_de_sustancias_no_relacionadas()
    test_ecfr_solo_si_nombra_el_insumo()
    print("\nTIER 6: todos los tests PASSED")
