"""
S8.3 - La auditoría del panel.

Dos cosas que importan más que el resto y por eso salen primero:

1. **Registrar no puede tumbar la acción que audita.** Si la base falla al
   escribir la fila de auditoría, promover tiene que seguir funcionando.
2. **Es la primera pantalla que exige admin para LEER.** Hasta S8 el rol solo
   cerraba acciones; aquí cierra la lectura, porque la auditoría habla de las
   personas que operan el sistema.

El repositorio se sustituye por un doble: su SQL se prueba contra la base real
en la verificación de la migración, no aquí.
"""

import csv
import io
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import api.auditoria as auditoria
from adaptadores.auditoria_panel import EVENTOS, AuditoriaPanel
from api.auth import requiere_admin

_ID = str(uuid4())
ADMIN = {"sub": _ID, "user_id": _ID, "email": "admin@cite.gob.pe"}
OPERADOR = {"sub": str(uuid4()), "user_id": str(uuid4()),
            "email": "operador@cite.gob.pe"}


class RepoFalso:
    def __init__(self, entradas=None, total=None):
        self._entradas = entradas if entradas is not None else []
        self._total = total
        self.llamadas = []

    def leer(self, **kwargs):
        self.llamadas.append(kwargs)
        limite = kwargs.get("limite", 50)
        return {"total": self._total if self._total is not None else len(self._entradas),
                "entradas": self._entradas[:limite]}


def _entrada(**extra):
    base = {
        "audit_id": 1, "ocurrido_en": "2026-08-12T17:52:22+00:00",
        "evento": "promotion_manual", "usuario_id": _ID,
        "usuario_email": "admin@cite.gob.pe", "entidad": "staging_agente",
        "entidad_id": str(uuid4()),
        "antes": {"promotion_source": None}, "despues": {"promotion_source": "manual_human"},
        "detalles": {"insumo": "quinua", "nombre": "Quinua Costeño 500g"},
    }
    return {**base, **extra}


def montar(repo, es_admin=True) -> TestClient:
    app = FastAPI()
    app.include_router(auditoria.router)
    auditoria._repo = repo

    def _admin():
        if not es_admin:
            raise HTTPException(status_code=403, detail="Requiere rol de administrador")
        return ADMIN

    app.dependency_overrides[requiere_admin] = _admin
    return TestClient(app)


# ---------------------------------------------------------------------------
# La auditoría no tumba la acción que audita
# ---------------------------------------------------------------------------

def test_un_fallo_al_escribir_no_propaga(monkeypatch):
    """Entre no poder anotar una promoción y no poder promover, lo segundo es
    peor: convierte un fallo de un registro accesorio en una caída del panel."""
    def revienta():
        raise RuntimeError("la base no responde")

    monkeypatch.setattr("adaptadores.auditoria_panel.pool", revienta)

    assert AuditoriaPanel().registrar("login", usuario_email="x@cite.gob.pe") is None


def test_el_fallo_se_registra_como_error(monkeypatch, caplog):
    """Que no propague no significa que se pierda en silencio."""
    def revienta():
        raise RuntimeError("la base no responde")

    monkeypatch.setattr("adaptadores.auditoria_panel.pool", revienta)

    with caplog.at_level("ERROR"):
        AuditoriaPanel().registrar("login", usuario_email="x@cite.gob.pe")

    assert any("No se pudo auditar" in r.message for r in caplog.records)


def test_un_evento_desconocido_si_revienta():
    """Aquí sí, y en desarrollo: un evento mal escrito no sale en los filtros
    del panel, así que es como si no se hubiera registrado."""
    with pytest.raises(ValueError, match="desconocido"):
        AuditoriaPanel().registrar("promocion_manual")   # es promotion_manual


@pytest.mark.parametrize("evento", EVENTOS)
def test_los_siete_eventos_de_8_3_son_validos(evento, monkeypatch):
    monkeypatch.setattr("adaptadores.auditoria_panel.pool",
                        lambda: (_ for _ in ()).throw(RuntimeError("sin base")))
    AuditoriaPanel().registrar(evento)   # no lanza ValueError


# ---------------------------------------------------------------------------
# Control de acceso: la primera pantalla de solo-admin
# ---------------------------------------------------------------------------

class TestControlDeAcceso:
    def test_un_operador_no_puede_leer_la_auditoria(self):
        assert montar(RepoFalso(), es_admin=False).get("/api/auditoria").status_code == 403

    def test_un_operador_no_puede_exportarla(self):
        cliente = montar(RepoFalso(), es_admin=False)
        assert cliente.get("/api/auditoria/export.csv").status_code == 403

    def test_un_operador_no_puede_listar_los_eventos(self):
        cliente = montar(RepoFalso(), es_admin=False)
        assert cliente.get("/api/auditoria/eventos").status_code == 403

    def test_un_admin_si(self):
        assert montar(RepoFalso()).get("/api/auditoria").status_code == 200


# ---------------------------------------------------------------------------
# Filtros y paginación
# ---------------------------------------------------------------------------

class TestListado:
    def test_los_filtros_llegan_al_repositorio(self):
        repo = RepoFalso()
        montar(repo).get("/api/auditoria?evento=login&usuario_email=ana"
                         "&desde=2026-08-01&hasta=2026-08-12")

        assert repo.llamadas[0]["evento"] == "login"
        assert repo.llamadas[0]["usuario_email"] == "ana"
        assert repo.llamadas[0]["desde"] == "2026-08-01"
        assert repo.llamadas[0]["hasta"] == "2026-08-12"

    def test_sin_filtros_no_se_inventa_ninguno(self):
        repo = RepoFalso()
        montar(repo).get("/api/auditoria")

        assert all(v is None for k, v in repo.llamadas[0].items()
                   if k not in ("limite", "desplazamiento"))

    def test_el_total_viaja_con_la_pagina(self):
        """En dos llamadas, la página y su contador pueden ser de instantes
        distintos y la paginación salta."""
        repo = RepoFalso([_entrada()], total=417)
        datos = montar(repo).get("/api/auditoria?limite=1").json()

        assert datos["total"] == 417
        assert len(datos["entradas"]) == 1

    def test_el_limite_esta_acotado(self):
        assert montar(RepoFalso()).get("/api/auditoria?limite=5000").status_code == 422

    def test_los_eventos_salen_de_la_misma_constante_que_valida(self):
        """Si la lista del desplegable se copiara aparte, se podría filtrar por
        un evento que nunca se registra."""
        datos = montar(RepoFalso()).get("/api/auditoria/eventos").json()
        assert datos["eventos"] == list(EVENTOS)


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------

class TestExport:
    def test_lleva_bom_para_que_excel_no_rompa_las_tildes(self):
        """Sin BOM, Excel en Windows abre el CSV como ANSI y 'Costeño' sale
        'CosteÃ±o'. Una auditoría de CITE con mojibake no vale de entregable."""
        repo = RepoFalso([_entrada()])
        cuerpo = montar(repo).get("/api/auditoria/export.csv").content

        assert cuerpo.startswith(b"\xef\xbb\xbf")
        assert "Costeño" in cuerpo.decode("utf-8-sig")

    def test_termina_las_lineas_como_manda_el_rfc(self):
        cuerpo = montar(RepoFalso([_entrada()])).get("/api/auditoria/export.csv").content
        assert b"\r\n" in cuerpo

    def test_se_descarga_en_vez_de_abrirse(self):
        r = montar(RepoFalso([_entrada()])).get("/api/auditoria/export.csv")
        assert "attachment" in r.headers["content-disposition"]
        assert "auditoria.csv" in r.headers["content-disposition"]

    def test_las_columnas_son_las_declaradas(self):
        r = montar(RepoFalso([_entrada()])).get("/api/auditoria/export.csv")
        filas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))

        assert tuple(filas[0]) == auditoria.COLUMNAS_CSV
        assert len(filas) == 2

    def test_los_jsonb_van_legibles_y_no_escapados(self):
        r = montar(RepoFalso([_entrada()])).get("/api/auditoria/export.csv")
        filas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
        detalles = filas[1][auditoria.COLUMNAS_CSV.index("detalles")]

        assert "Costeño" in detalles
        assert "\\u" not in detalles

    def test_una_celda_vacia_no_dice_none(self):
        """`None` en una celda de Excel se lee como el texto 'None'."""
        repo = RepoFalso([_entrada(despues=None, entidad_id=None)])
        r = montar(repo).get("/api/auditoria/export.csv")
        filas = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))

        assert filas[1][auditoria.COLUMNAS_CSV.index("despues")] == ""
        assert filas[1][auditoria.COLUMNAS_CSV.index("entidad_id")] == ""

    def test_avisa_por_cabecera_si_el_fichero_va_cortado(self):
        """Quien exporta tiene que poder saber que no se lo lleva entero."""
        repo = RepoFalso([_entrada()], total=99_999)
        r = montar(repo).get("/api/auditoria/export.csv")

        assert r.headers["X-Total-Registros"] == "99999"
        assert int(r.headers["X-Registros-Exportados"]) < 99_999

    def test_el_export_usa_los_mismos_filtros_que_la_tabla(self):
        """Lo que se descarga tiene que ser lo que se está viendo."""
        repo = RepoFalso([_entrada()])
        montar(repo).get("/api/auditoria/export.csv?evento=login&usuario_email=ana")

        assert repo.llamadas[0]["evento"] == "login"
        assert repo.llamadas[0]["usuario_email"] == "ana"
