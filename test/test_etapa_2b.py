"""
TIER 4 · T4.1 y T4.2 (S4): la etapa 2b en el DAG.

DoD del plan §T4:
  - Run gratuito -> 4 filas en etapas_ejecucion: '1','2a','2b','3'
  - Run premium  -> 6 filas
  - Mapa de "arándano" con >=5 países ISO distintos y >=10 marcas
  - Duración de 2b < 300 ms y costo_usd = 0

El plan escribe la etapa de búsqueda como '2'; el esquema de S3 y el código la
numeran '2a' (001_esquema_s3.sql:40). Son 4 y 6 filas igual.

La composición corre con dobles del LLM, la caché, la auditoría y los informes,
pero con el **adaptador de descubrimiento real**: lo que se mide aquí es que 2b
está en el DAG y que su fila es honesta, y eso no se puede comprobar con un
doble del propio 2b.

Se ejecuta con pytest o directamente: python test/test_etapa_2b.py
"""
import asyncio
import time
import uuid

from adaptadores.descubrimiento_snapshot import DescubrimientoSnapshot
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.etapas.mapear_comercio import mapear_comercio
from casos_de_uso.evaluar_insumo import generar_dossier, generar_mapa_comercial
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from dominio.insumo import InsumoInterpretado
from dominio.mapa_comercial import MapaComercial
from dominio.producto_existente import ProductoExistente
from dominio.resultado_busqueda import ResultadoBusqueda

MAX_MS_2B = 300


# --- dobles ---------------------------------------------------------------

class _Ejecucion:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.snapshot_version = "2026-07"
        self.insumo_texto = "arándano"
        self.usuario_id = None


class AuditoriaFalsa:
    def __init__(self):
        self.filas: list[dict] = []
        self.estado = None
        self.motivo = None

    def iniciar(self, texto, snapshot_version, usuario_id=None):
        return _Ejecucion()

    def registrar_etapa(self, ejecucion, etapa, entrada, salida, duracion_ms,
                        costo_usd, tokens=0, tokens_entrada=0, tokens_salida=0,
                        modelo=None, cache_hit=False):
        self.filas.append({"etapa": etapa, "salida": salida, "modelo": modelo,
                           "duracion_ms": duracion_ms, "costo_usd": costo_usd,
                           "cache_hit": cache_hit})

    def cerrar(self, ejecucion, estado, motivo_parcial=None):
        self.estado, self.motivo = estado, motivo_parcial

    def etapas(self) -> list[str]:
        return [f["etapa"] for f in self.filas]

    def fila(self, etapa: str) -> dict:
        return next(f for f in self.filas if f["etapa"] == etapa)


class CacheFalsa:
    def obtener(self, clave):
        return None

    def guardar(self, clave, valor, etapa=None, modelo=None, snapshot_version=None):
        pass

    def vaciar_pendientes(self):
        pass


class RedactorFalso:
    """No llama a ningún modelo. Guarda lo que le pasan para poder mirarlo."""

    modelo_por_etapa = {"1": "openai/deepseek-v4-flash", "3": "openai/glm-5.2",
                        "4": "openai/glm-5.2", "5": "openai/glm-5.2"}

    def __init__(self):
        self.mapa_recibido = None

    async def interpretar(self, texto):
        return InsumoInterpretado(insumo_normalizado="arándano", reconocible=True,
                                  sinonimos_busqueda=["arándano", "blueberry"])

    async def redactar_insight(self, productos, mapa=None):
        self.mapa_recibido = mapa
        return InsightDeMercado(cobertura="alta", resumen="r",
                                formatos_comunes=["polvo"], citas=[])

    async def formular_hipotesis(self, productos):
        return HipotesisFormulacion(hipotesis="h", ingredientes_probables=[],
                                    procesos_sugeridos=[], citas=[])

    async def verificar_regulacion(self, insumo, contexto):
        return DossierRegulatorio(restricciones=[], citas=[], sin_dato=True)


class CatalogoFalso:
    def buscar(self, sinonimos, k=30):
        # n_directos > 2 para no disparar el guard técnico, que cambiaría de
        # redactor y confundiría lo que este test mide.
        productos = [
            ProductoExistente(id_fuente=f"OFF:{i}", nombre=f"Blueberry jam {i}",
                              categoria="Jams", usa_insumo_directo=True,
                              ingredientes="blueberry, sugar")
            for i in range(5)
        ]
        return ResultadoBusqueda(productos=productos, n_directos=5)


class InformesFalso:
    def pide_reformulacion(self, ejecucion):
        return InformeScout(parcial=True, snapshot_version="2026-07", ruta_pdf=None)

    def emitir(self, ejecucion, insight, parcial, hipotesis=None, dossier=None,
               mapa=None):
        return InformeScout(parcial=parcial, snapshot_version="2026-07",
                            ruta_pdf=None, insight=insight,
                            hipotesis=hipotesis, dossier=dossier, mapa=mapa)


def _dependencias(con_descubrimiento: bool = True):
    return Dependencias(
        redactor=RedactorFalso(),
        catalogo=CatalogoFalso(),
        cache=CacheFalsa(),
        informes=InformesFalso(),
        auditoria=AuditoriaFalsa(),
        descubrimiento=DescubrimientoSnapshot() if con_descubrimiento else None,
    )


# --- T4.2 · composición ---------------------------------------------------

def test_run_gratuito_deja_cuatro_filas():
    """DoD: gratuito -> '1','2a','2b','3'."""
    d = _dependencias()
    informe = asyncio.run(generar_mapa_comercial("arándano", d))
    assert d.auditoria.etapas() == ["1", "2a", "2b", "3"], d.auditoria.etapas()
    # El mapa llega hasta el informe: es lo que la SPA leera en T4.3b.
    assert informe.mapa is not None and informe.mapa.productos
    print(f"PASS: gratuito -> {d.auditoria.etapas()} · informe con mapa")


def test_run_premium_deja_seis_filas():
    """DoD: premium -> las cuatro anteriores más '4' y '5'."""
    d = _dependencias()
    asyncio.run(generar_dossier("arándano", d))
    assert d.auditoria.etapas() == ["1", "2a", "2b", "3", "4", "5"], d.auditoria.etapas()
    print(f"PASS: premium -> {d.auditoria.etapas()}")


def test_la_fila_de_2b_es_honesta():
    """DoD: 2b < 300 ms, costo 0. Y su `modelo` no nombra un LLM que no corrió."""
    d = _dependencias()
    asyncio.run(generar_mapa_comercial("arándano", d))
    fila = d.auditoria.fila("2b")

    assert fila["costo_usd"] == 0.0, fila["costo_usd"]
    assert fila["duracion_ms"] < MAX_MS_2B, f"{fila['duracion_ms']} ms"
    # Va por etapa_sync justamente por esto: con etapa() la fila diría
    # modelo='glm-5.2' para una etapa que no llama a ningún modelo.
    assert fila["modelo"] == "sync", fila["modelo"]
    print(f"PASS: 2b · {fila['duracion_ms']} ms · costo {fila['costo_usd']} · "
          f"modelo {fila['modelo']!r}")


def test_la_salida_de_2b_es_la_evidencia_de_procedencia():
    """`salida_json` lleva los productos y lo que no se pudo mirar."""
    d = _dependencias()
    asyncio.run(generar_mapa_comercial("arándano", d))
    salida = d.auditoria.fila("2b")["salida"]

    assert salida["niveles_no_disponibles"] == [2, 3]
    assert salida["nivel_alcanzado"] == 1
    assert len(salida["productos"]) >= 50
    primero = salida["productos"][0]
    assert primero["url"] and primero["fecha_dato"], "sin procedencia"
    assert primero["precio_rango"] is None and primero["canal"] is None
    print(f"PASS: salida_json con {len(salida['productos'])} productos y [2, 3]")


def test_el_insight_recibe_el_mapa():
    """T4.2: los países y marcas reales son material de cita."""
    d = _dependencias()
    asyncio.run(generar_mapa_comercial("arándano", d))
    mapa = d.redactor.mapa_recibido

    assert mapa is not None, "la etapa 3 no recibió el mapa"
    assert mapa["total_productos"] >= 50
    assert len(mapa["paises"]) >= 5
    assert len(mapa["marcas"]) >= 10
    assert mapa["niveles_no_disponibles"] == [2, 3]
    # Acotado a propósito: 200 productos serían ~10k tokens por run.
    assert len(mapa["productos"]) <= 30
    assert all(p["id"] for p in mapa["productos"]), "hay productos sin id citable"
    print(f"PASS: insight recibe {len(mapa['paises'])} países, "
          f"{len(mapa['marcas'])} marcas, {len(mapa['productos'])} ids citables")


# --- T4.1 · la etapa suelta -----------------------------------------------

def test_mapa_de_arandano_cumple_el_gate():
    """DoD: >=5 países ISO distintos y >=10 marcas."""
    d = _dependencias()
    interpretado = InsumoInterpretado(insumo_normalizado="arándano",
                                      reconocible=True,
                                      sinonimos_busqueda=["arándano"])
    t0 = time.perf_counter()
    mapa = mapear_comercio(d, interpretado)
    ms = (time.perf_counter() - t0) * 1000

    assert len(mapa.paises()) >= 5, mapa.paises()
    assert len(mapa.marcas()) >= 10, len(mapa.marcas())
    assert isinstance(mapa, MapaComercial)
    print(f"PASS: {len(mapa.productos)} productos · {len(mapa.paises())} países · "
          f"{len(mapa.marcas())} marcas · {ms:.0f} ms")


def test_sin_adaptador_degrada_a_sin_dato_no_a_error():
    """Sin descubrimiento la etapa no revienta: declara los tres niveles."""
    d = _dependencias(con_descubrimiento=False)
    interpretado = InsumoInterpretado(insumo_normalizado="arándano",
                                      reconocible=True,
                                      sinonimos_busqueda=["arándano"])
    mapa = mapear_comercio(d, interpretado)

    assert mapa.productos == []
    assert mapa.nivel_alcanzado == 0
    assert mapa.niveles_no_disponibles == [1, 2, 3]
    print("PASS: sin adaptador -> mapa vacío que declara [1, 2, 3]")


def test_sin_adaptador_el_run_completo_sigue_dejando_cuatro_filas():
    """La fila de 2b existe aunque no haya con qué llenarla, y dice por qué.

    Es la diferencia entre "no hay productos" y "no se miró": sin la fila, las
    dos serían indistinguibles en la auditoría.
    """
    d = _dependencias(con_descubrimiento=False)
    asyncio.run(generar_mapa_comercial("arándano", d))

    assert d.auditoria.etapas() == ["1", "2a", "2b", "3"]
    assert d.auditoria.fila("2b")["salida"]["niveles_no_disponibles"] == [1, 2, 3]
    print("PASS: sin adaptador el DAG conserva sus 4 filas")


def test_resumen_para_llm_no_inventa_el_hueco():
    """Los tres campos vacíos se declaran contados, no se omiten."""
    d = _dependencias()
    interpretado = InsumoInterpretado(insumo_normalizado="arándano",
                                      reconocible=True,
                                      sinonimos_busqueda=["arándano"])
    resumen = mapear_comercio(d, interpretado).resumen_para_llm()

    n = resumen["total_productos"]
    assert resumen["sin_dato"] == {"presentacion": n, "precio": n, "canal": n}
    print(f"PASS: el hueco viaja al prompt como {n} sin dato en los 3 campos")


if __name__ == "__main__":
    for nombre, fn in sorted(list(globals().items())):
        if nombre.startswith("test_") and callable(fn):
            fn()
