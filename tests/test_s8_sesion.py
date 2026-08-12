"""
S8.1 - `GET /api/sesion`, el endpoint que le dice al panel quién ha entrado.

Existe porque el rol no salía por ningún sitio: `/token` devuelve token y
correo, `/uso` devuelve el plan. Sin rol, la barra lateral no puede decidir qué
entradas enseñar.

Lo que se comprueba aquí es que **no autoriza nada**: devuelve el rol tal como
lo ve el servidor, y quien decide sigue siendo `requiere_admin` en cada
endpoint. Un usuario que se declare admin en el navegador no cambia esto.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import api.main as main
from api.auth import get_current_user

_ID = str(uuid4())
USUARIO = {"sub": _ID, "user_id": _ID, "email": "alguien@cite.gob.pe"}


@pytest.fixture
def cliente():
    main.app.dependency_overrides[get_current_user] = lambda: USUARIO
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()


def test_devuelve_identidad_y_rol(cliente, monkeypatch):
    monkeypatch.setattr(main, "rol_de", lambda _: "admin")

    datos = cliente.get("/api/sesion").json()
    assert datos == {"usuario_id": _ID, "email": "alguien@cite.gob.pe",
                     "rol": "admin"}


def test_el_rol_lo_pone_el_servidor(cliente, monkeypatch):
    """No se lee de la petición: no hay cabecera ni parámetro que lo cambie."""
    monkeypatch.setattr(main, "rol_de", lambda _: "operador")

    respuesta = cliente.get("/api/sesion?rol=admin",
                            headers={"X-Rol": "admin"})
    assert respuesta.json()["rol"] == "operador"


def test_pregunta_por_el_usuario_autenticado(cliente, monkeypatch):
    """El id que se consulta es el del token, no uno de fuera."""
    consultados = []
    monkeypatch.setattr(main, "rol_de",
                        lambda uid: consultados.append(uid) or "operador")

    cliente.get("/api/sesion")
    assert consultados == [_ID]


def test_sin_token_no_hay_sesion():
    """Sin la dependencia sustituida vuelve a exigir autenticación."""
    respuesta = TestClient(main.app).get("/api/sesion")
    assert respuesta.status_code == 401
