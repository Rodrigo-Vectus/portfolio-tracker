"""Pruebas de los endpoints de salud.

`live` no toca dependencias, asi que corre sin base ni Redis. `ready` si las
necesita: se ejecuta dentro del contenedor con `docker compose exec`.
"""

from fastapi.testclient import TestClient


def test_live_responde_ok(client: TestClient) -> None:
    r = client.get("/api/health/live")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_meta_expone_defaults_de_dominio(client: TestClient) -> None:
    r = client.get("/api/meta")
    assert r.status_code == 200
    defaults = r.json()["defaults"]
    # D1: MEP para acciones, USDT para cripto.
    assert defaults["fx_source_equity"] == "MEP"
    assert defaults["fx_source_crypto"] == "USDT"
    # D4: ledger de lotes con promedio ponderado como vista por defecto.
    assert defaults["cost_basis_method"] == "WAC"


def test_ready_reporta_cada_dependencia(client: TestClient) -> None:
    r = client.get("/api/health/ready")
    assert r.status_code in (200, 503)
    checks = r.json()["checks"]
    assert {"postgres", "redis", "migrations"} <= set(checks)
