"""Pruebas de los endpoints de autenticacion.

Verifican el contrato publico: que codigos devuelve, que cookies emite y que
NO expone.

Cada prueba usa **su propio usuario**, creado por la fixture `usuario` con una
contrasena generada en el momento. Antes dependian del administrador sembrado
y de `INITIAL_ADMIN_PASSWORD`, y eso las rompio el dia que el usuario cambio
su contrasena, que era exactamente lo que el sistema le exigia hacer. Ademas
los intentos fallidos se acumulaban entre corridas, asi que la suite daba
resultados distintos segun cuando se corriera.

Corren contra la base de pruebas. Ver `scripts/test.sh`.
"""

from fastapi.testclient import TestClient


def _login(client: TestClient, credenciales: tuple[str, str]):
    email, password = credenciales
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_con_clave_incorrecta_devuelve_401(client: TestClient, usuario) -> None:
    email, _ = usuario
    r = client.post("/api/auth/login", json={"email": email, "password": "noEsLaClave1"})
    assert r.status_code == 401


def test_el_error_no_revela_si_el_email_existe(client: TestClient, usuario) -> None:
    """Un email que existe y uno que no deben ser indistinguibles.

    Mismo codigo y mismo mensaje. El backend calcula un hash igual cuando el
    email no existe, para que el tiempo de respuesta tampoco delate cuales
    cuentas existen.
    """
    email, _ = usuario
    a = client.post("/api/auth/login", json={"email": email, "password": "noEsLaClave1"})
    b = client.post(
        "/api/auth/login",
        json={"email": "nadie-inexistente@example.com", "password": "noEsLaClave1"},
    )
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_login_correcto_emite_cookies_y_no_filtra_el_hash(
    client: TestClient, usuario
) -> None:
    r = _login(client, usuario)
    assert r.status_code == 200, r.text

    body = r.json()
    assert body["access_token"]
    assert "password_hash" not in str(body)
    assert body["user"]["role"] == "USER"

    cookies = r.headers.get_list("set-cookie")
    refresh = next(c for c in cookies if c.startswith("pt_refresh="))
    csrf = next(c for c in cookies if c.startswith("pt_csrf="))
    # El refresh tiene que ser inaccesible desde JavaScript; el CSRF, legible.
    assert "HttpOnly" in refresh
    assert "HttpOnly" not in csrf


def test_el_rol_admin_se_refleja_en_la_respuesta(client: TestClient, admin) -> None:
    r = _login(client, admin)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "ADMIN"


def test_endpoint_protegido_rechaza_sin_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/users").status_code == 401


def test_un_usuario_comun_no_puede_listar_usuarios(client: TestClient, usuario) -> None:
    """El rol se verifica en el servidor, no en la interfaz.

    Que el frontend esconda el item del menu no protege nada: el endpoint
    tiene que rechazarlo igual.
    """
    token = _login(client, usuario).json()["access_token"]
    r = client.get("/api/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_bloqueo_por_intentos_fallidos(client: TestClient, usuario) -> None:
    """Tras agotar los intentos, el login responde 429 aunque la clave sea buena.

    Se prueba con un usuario propio y descartable: hacerlo contra una cuenta
    real la deja bloqueada quince minutos, que es lo que venia pasando.
    """
    from app.core.config import get_settings

    email, password = usuario
    intentos = get_settings().login_max_attempts

    for _ in range(intentos):
        client.post("/api/auth/login", json={"email": email, "password": "noEsLaClave1"})

    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 429


def test_refresh_sin_csrf_es_rechazado(client: TestClient, usuario) -> None:
    """Con la cookie presente pero sin el encabezado, tiene que fallar."""
    assert _login(client, usuario).status_code == 200
    r = client.post("/api/auth/refresh")  # cookies puestas por el cliente, sin header
    assert r.status_code == 403


def test_refresh_con_csrf_rota_el_token(client: TestClient, usuario) -> None:
    _login(client, usuario)
    csrf = client.cookies.get("pt_csrf")
    anterior = client.cookies.get("pt_refresh")

    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    assert r.json()["access_token"]
    # Rotacion: el refresh nuevo no puede ser el mismo de antes.
    assert client.cookies.get("pt_refresh") != anterior


def test_el_csrf_se_conserva_entre_refrescos(client: TestClient, usuario) -> None:
    """Rotar el CSRF en cada refresco rompe a los clientes que lo cachean.

    Solo debe cambiar al iniciar sesion. Lo que rota es el refresh.
    """
    _login(client, usuario)
    csrf = client.cookies.get("pt_csrf")

    client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf})
    assert client.cookies.get("pt_csrf") == csrf

    # El mismo token sigue siendo valido en el refresco siguiente.
    assert client.post("/api/auth/refresh", headers={"X-CSRF-Token": csrf}).status_code == 200


def test_reusar_un_refresh_ya_rotado_invalida_la_sesion(
    client: TestClient, usuario
) -> None:
    _login(client, usuario)
    viejo = client.cookies.get("pt_refresh")

    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": client.cookies.get("pt_csrf")})
    assert r.status_code == 200

    # Un atacante que copio el token viejo intenta usarlo. El CSRF se lee
    # despues del refresco a proposito: la prueba debe fallar por reuso del
    # refresh, no por un CSRF desactualizado (que daria 403 y taparia el 401).
    client.cookies.set("pt_refresh", viejo)
    r = client.post("/api/auth/refresh", headers={"X-CSRF-Token": client.cookies.get("pt_csrf")})
    assert r.status_code == 401, "el reuso debe invalidar la sesion, no fallar por CSRF"


def test_tras_el_reuso_la_familia_entera_queda_revocada(
    client: TestClient, usuario
) -> None:
    """El token bueno tampoco sirve: se revoca la sesion completa."""
    _login(client, usuario)
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
