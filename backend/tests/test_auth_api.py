"""Pruebas de los endpoints de autenticacion.

Verifican el contrato publico: que codigos devuelve, que cookies emite y que
NO expone. Necesitan PostgreSQL y Redis, asi que corren dentro del
contenedor con `docker compose exec backend pytest`.
"""

import os

import pytest
from fastapi.testclient import TestClient

ADMIN_EMAIL = os.environ.get("INITIAL_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("INITIAL_ADMIN_PASSWORD", "")

pytestmark = pytest.mark.skipif(
    not ADMIN_EMAIL or not ADMIN_PASSWORD,
    reason="requiere INITIAL_ADMIN_EMAIL e INITIAL_ADMIN_PASSWORD",
)


@pytest.fixture(autouse=True)
def sesion_limpia(client: TestClient) -> None:
    """El cliente se comparte entre pruebas; las cookies no deben arrastrarse.

    Sin esto, una prueba que deja una sesion abierta cambia el resultado de la
    siguiente, y las fallas aparecen o desaparecen segun el orden de ejecucion.
    """
    client.cookies.clear()


def test_login_con_clave_incorrecta_devuelve_401(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "noEsLaClave1"})
    assert r.status_code == 401


def test_el_error_no_revela_si_el_email_existe(client: TestClient) -> None:
    a = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": "noEsLaClave1"})
    b = client.post(
        "/api/auth/login", json={"email": "nadie@ejemplo.com", "password": "noEsLaClave1"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_login_correcto_emite_cookies_y_no_filtra_el_hash(client: TestClient) -> None:
    r = client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["access_token"]
    assert "password" not in str(body).lower() or "password_hash" not in str(body)
    assert body["user"]["role"] == "ADMIN"

    cookies = r.headers.get_list("set-cookie")
    refresh = next(c for c in cookies if c.startswith("pt_refresh="))
    csrf = next(c for c in cookies if c.startswith("pt_csrf="))
    # El refresh tiene que ser inaccesible desde JavaScript; el CSRF, legible.
    assert "HttpOnly" in refresh
    assert "HttpOnly" not in csrf


def test_endpoint_protegido_rechaza_sin_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/users").status_code == 401


def test_refresh_sin_csrf_es_rechazado(client: TestClient) -> None:
    """Con la cookie presente pero sin el encabezado, tiene que fallar."""
    login = client.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert login.status_code == 200
    r = client.post("/api/auth/refresh")  # cookies puestas por el cliente, sin header
    assert r.status_code == 403


def test_refresh_con_csrf_rota_el_token(client: TestClient) -> None:
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    csrf = client.cookies.get("pt_csrf")
    anterior = client.cookies.get("pt_refresh")

    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert r.json()["access_token"]
    # Rotacion: el refresh nuevo no puede ser el mismo de antes.
    assert client.cookies.get("pt_refresh") != anterior


def test_el_csrf_se_conserva_entre_refrescos(client: TestClient) -> None:
    """Rotar el CSRF en cada refresco rompe a los clientes que lo cachean.

    Solo debe cambiar al iniciar sesion. Lo que rota es el refresh.
    """
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    csrf = client.cookies.get("pt_csrf")

    client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert client.cookies.get("pt_csrf") == csrf

    # El mismo token sigue siendo valido en el refresco siguiente.
    assert client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 200


def test_reusar_un_refresh_ya_rotado_invalida_la_sesion(client: TestClient) -> None:
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    viejo = client.cookies.get("pt_refresh")

    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": client.cookies.get("pt_csrf")})
    assert r.status_code == 200

    # Un atacante que copio el token viejo intenta usarlo. El CSRF se lee
    # despues del refresco a proposito: la prueba debe fallar por reuso del
    # refresh, no por un CSRF desactualizado (que daria 403 y taparia el 401).
    client.cookies.set("pt_refresh", viejo)
    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": client.cookies.get("pt_csrf")})
    assert r.status_code == 401, "el reuso debe invalidar la sesion, no fallar por CSRF"


def test_tras_el_reuso_la_familia_entera_queda_revocada(client: TestClient) -> None:
    """El token bueno tampoco sirve: se revoca la sesion completa."""
    client.post("/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    viejo = client.cookies.get("pt_refresh")
    csrf = client.cookies.get("pt_csrf")

    client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    bueno = client.cookies.get("pt_refresh")

    client.cookies.set("pt_refresh", viejo)
    client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})  # dispara la alarma

    client.cookies.set("pt_refresh", bueno)
    client.cookies.set("pt_csrf", csrf)
    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 401
