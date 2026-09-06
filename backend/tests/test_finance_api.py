"""Pruebas de la API financiera.

Dos grupos. El primero verifica que registrar operaciones produzca la posicion
correcta de punta a punta: HTTP, servicio, dominio y base.

El segundo verifica la regla C.1 de la especificacion: un usuario solo accede
a lo suyo. Estas pruebas **no se podian escribir antes**, porque hacian falta
dos usuarios reales y la suite corria contra la base de produccion.

Sobre el 404: cuando el recurso es de otro se devuelve 404 y no 403. Un 403
confirmaria que el recurso existe y solo no es tuyo, y con eso se pueden
enumerar carteras ajenas probando identificadores.
"""

from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


class Sesion:
    """Cliente autenticado. Agrupa token y CSRF para no repetirlos."""

    def __init__(self, client: TestClient, email: str, password: str) -> None:
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        self.client = client
        self.token = r.json()["access_token"]
        self.csrf = client.cookies.get("pt_csrf")

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "X-CSRF-Token": self.csrf}

    def post(self, url: str, **kw):
        return self.client.post(url, headers=self.headers, **kw)

    def get(self, url: str, **kw):
        return self.client.get(url, headers=self.headers, **kw)


@pytest.fixture
def sesion(client: TestClient, usuario) -> Sesion:
    return Sesion(client, *usuario)


def _alta_activo(s: Sesion, symbol: str = "AAPL"):
    r = s.post(
        "/api/assets",
        json={
            "symbol": symbol,
            "name": f"CEDEAR {symbol}",
            "asset_type": "CEDEAR",
            "currency": "ARS",
            "market": "BYMA",
        },
    )
    # El catalogo es compartido: si otra prueba ya creo el activo, se reutiliza.
    if r.status_code == 409:
        listado = s.get("/api/assets").json()
        return next(a for a in listado if a["symbol"] == symbol)
    assert r.status_code == 201, r.text
    return r.json()


def _alta_portfolio(s: Sesion, nombre: str = "Principal"):
    r = s.post("/api/portfolios", json={"name": nombre, "base_currency": "USD"})
    assert r.status_code == 201, r.text
    return r.json()


def _operacion(s: Sesion, portfolio, asset, tipo, cantidad, precio, dia, **extra):
    cuerpo = {
        "portfolio_id": portfolio["id"],
        "asset_id": asset["id"],
        "tx_type": tipo,
        "quantity": str(cantidad),
        "unit_price": str(precio),
        "price_currency": "ARS",
        "executed_at": datetime(2025, 6, dia, 12, 0).isoformat(),
    }
    cuerpo.update(extra)
    return s.post("/api/transactions", json=cuerpo)


# ------------------------------------------------------- registrar y posicion


def _posiciones(s: Sesion, portfolio) -> list:
    return s.get(f"/api/positions?portfolio_id={portfolio['id']}").json()["positions"]


def _total(s: Sesion, portfolio) -> dict:
    return s.get(f"/api/positions?portfolio_id={portfolio['id']}").json()["total"]


def test_una_compra_produce_la_posicion(sesion: Sesion) -> None:
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)

    assert _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1).status_code == 201

    posiciones = _posiciones(sesion, portfolio)
    assert len(posiciones) == 1
    assert Decimal(posiciones[0]["quantity"]) == Decimal(10)
    assert Decimal(posiciones[0]["open_cost_basis"]) == Decimal(1000)
    assert Decimal(posiciones[0]["average_cost"]) == Decimal(100)


def test_sin_cotizacion_el_valor_es_nulo_y_no_cero(sesion: Sesion) -> None:
    """"No sé cuánto vale" y "no vale nada" son afirmaciones distintas.

    Un cero en la columna de valor actual se lee como una pérdida total. Por
    eso el campo viene en `null` y el frontend lo muestra como un guion.
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1)

    p = _posiciones(sesion, portfolio)[0]
    assert p["current_price"] is None
    assert p["current_value"] is None
    assert p["unrealized_pnl"] is None
    assert p["price_status"] == "AUSENTE"
    # El costo, que sale del libro y no del mercado, sí está.
    assert Decimal(p["open_cost_basis"]) == Decimal(1000)


def test_sin_cotizacion_el_total_no_se_muestra_y_explica_por_que(
    sesion: Sesion,
) -> None:
    """Un total incompleto se lee como completo. Por eso no se entrega."""
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1)

    t = _total(sesion, portfolio)
    assert t["total"] is None
    assert not t["es_completo"]
    assert t["posiciones_sin_precio"] == 1
    assert "sin cotización" in t["motivo"]


def test_una_posicion_cerrada_no_aparece_en_el_listado(sesion: Sesion) -> None:
    """No hay nada que valuar cuando no queda tenencia."""
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1)
    _operacion(sesion, portfolio, activo, "SELL", 10, 150, 2)

    assert _posiciones(sesion, portfolio) == []
    assert _total(sesion, portfolio)["posiciones_totales"] == 0


def test_los_decimales_viajan_como_string(sesion: Sesion) -> None:
    """Un NUMERIC(38,18) serializado como numero JSON pierde exactitud.

    JSON usa doble precision: el navegador recibiria algo distinto de lo que
    hay en la base sin que nada avise.
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    _operacion(sesion, portfolio, activo, "BUY", 3, "100.333333333", 1)

    posicion = _posiciones(sesion, portfolio)[0]
    assert isinstance(posicion["quantity"], str)
    assert isinstance(posicion["open_cost_basis"], str)


def test_compra_venta_deja_la_posicion_y_el_realizado(sesion: Sesion) -> None:
    """Compra 10 @ 100, compra 10 @ 200, vende 12 @ 250.

        costo total = 3.000 ; cantidad 20 ; ppc = 150
        realizado   = 12 x (250 - 150) = 1.200
        remanente   = 8 unidades ; costo 3.000 - 1.800 = 1.200
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)

    _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1)
    _operacion(sesion, portfolio, activo, "BUY", 10, 200, 2)
    assert _operacion(sesion, portfolio, activo, "SELL", 12, 250, 3).status_code == 201

    posicion = _posiciones(sesion, portfolio)[0]
    assert Decimal(posicion["quantity"]) == Decimal(8)
    assert Decimal(posicion["realized_pnl"]) == Decimal(1200)
    assert Decimal(posicion["open_cost_basis"]) == Decimal(1200)


def test_vender_mas_de_lo_que_hay_es_rechazado(sesion: Sesion) -> None:
    """La fila 44 de la planilla vendia 25 con una tenencia de 13.

    Nada lo detectaba y la posicion quedo mal seis meses. Aca la operacion se
    rechaza y el libro no se toca.
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    _operacion(sesion, portfolio, activo, "BUY", 13, 100, 1)

    r = _operacion(sesion, portfolio, activo, "SELL", 25, 150, 2)
    assert r.status_code == 422
    assert "13" in r.json()["detail"]

    # El rechazo no debe dejar rastro: la tenencia sigue intacta.
    posicion = _posiciones(sesion, portfolio)[0]
    assert Decimal(posicion["quantity"]) == Decimal(13)
    operaciones = sesion.get(f"/api/transactions?portfolio_id={portfolio['id']}").json()
    assert len(operaciones) == 1


def test_la_cantidad_negativa_se_rechaza_en_el_contrato(sesion: Sesion) -> None:
    """El signo lo lleva el tipo de operacion, nunca el numero."""
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    r = _operacion(sesion, portfolio, activo, "SELL", -5, 100, 1)
    assert r.status_code == 422


def test_se_mezclan_fechas_con_y_sin_zona(sesion: Sesion) -> None:
    """Regresion: el historial sale de la base con zona y el JSON puede no traerla.

    Ordenarlas juntas rompia el motor de lotes. La primera operacion nunca lo
    disparaba porque no habia historial contra el cual comparar; recien
    fallaba en la segunda.
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)

    sin_zona = _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1)
    assert sin_zona.status_code == 201, sin_zona.text

    con_zona = _operacion(
        sesion, portfolio, activo, "BUY", 5, 200, 2,
        executed_at="2025-06-02T12:00:00-03:00",
    )
    assert con_zona.status_code == 201, con_zona.text

    tercera = _operacion(sesion, portfolio, activo, "SELL", 3, 300, 3)
    assert tercera.status_code == 201, tercera.text

    posicion = _posiciones(sesion, portfolio)[0]
    assert Decimal(posicion["quantity"]) == Decimal(12)


def test_una_operacion_de_la_noche_queda_en_la_rueda_correcta(sesion: Sesion) -> None:
    """22:30 en Buenos Aires es 01:30 UTC del dia siguiente.

    La rueda tiene que seguir siendo la del dia local, o el agrupamiento por
    dia queda corrido en todas las operaciones de la tarde-noche.
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    r = _operacion(
        sesion, portfolio, activo, "BUY", 1, 100, 1,
        executed_at="2025-06-02T22:30:00",
    )
    assert r.status_code == 201, r.text
    assert r.json()["trade_date"] == "2025-06-02"


# ------------------------------------------------------------------- anulacion


def test_anular_exige_motivo_y_recalcula(sesion: Sesion) -> None:
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    compra = _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1).json()
    _operacion(sesion, portfolio, activo, "BUY", 5, 200, 2)

    sin_motivo = sesion.post(f"/api/transactions/{compra['id']}/void", json={})
    assert sin_motivo.status_code == 422

    r = sesion.post(
        f"/api/transactions/{compra['id']}/void",
        json={"motivo": "cargada dos veces por error"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "VOIDED"
    assert r.json()["voided_reason"] == "cargada dos veces por error"

    # La operacion no se borra: sigue consultable pidiendo las anuladas.
    activas = sesion.get(f"/api/transactions?portfolio_id={portfolio['id']}").json()
    todas = sesion.get(
        f"/api/transactions?portfolio_id={portfolio['id']}&incluir_anuladas=true"
    ).json()
    assert len(activas) == 1
    assert len(todas) == 2

    posicion = _posiciones(sesion, portfolio)[0]
    assert Decimal(posicion["quantity"]) == Decimal(5)


def test_no_se_puede_anular_una_compra_que_dejaria_una_venta_descubierta(
    sesion: Sesion,
) -> None:
    """Anular hacia atras puede invalidar el historial posterior.

    Cuando pasa, no se anula nada: es preferible negarse a dejar el libro con
    una posicion imposible.
    """
    activo = _alta_activo(sesion)
    portfolio = _alta_portfolio(sesion)
    compra = _operacion(sesion, portfolio, activo, "BUY", 10, 100, 1).json()
    _operacion(sesion, portfolio, activo, "SELL", 8, 150, 2)

    r = sesion.post(
        f"/api/transactions/{compra['id']}/void", json={"motivo": "prueba de anulacion"}
    )
    assert r.status_code == 422
    assert "historial posterior" in r.json()["detail"]

    # Nada cambio.
    posicion = _posiciones(sesion, portfolio)[0]
    assert Decimal(posicion["quantity"]) == Decimal(2)


# --------------------------------------------- aislamiento entre usuarios (C.1)


def test_un_usuario_no_ve_el_portfolio_de_otro(client: TestClient, usuario, admin) -> None:
    """Regla C.1. El ajeno responde 404, no 403.

    Se usa un ADMIN como segundo usuario a proposito: administrar la
    plataforma no da acceso funcional a las carteras privadas. El
    administrador administra usuarios, no inversiones ajenas.
    """
    a = Sesion(client, *usuario)
    activo = _alta_activo(a)
    portfolio_de_a = _alta_portfolio(a, "Cartera de A")
    _operacion(a, portfolio_de_a, activo, "BUY", 10, 100, 1)

    client.cookies.clear()
    b = Sesion(client, *admin)

    assert b.get(f"/api/positions?portfolio_id={portfolio_de_a['id']}").status_code == 404
    assert (
        b.get(f"/api/transactions?portfolio_id={portfolio_de_a['id']}").status_code == 404
    )
    # El listado propio de B no incluye nada de A.
    assert b.get("/api/portfolios").json() == []


def test_un_usuario_no_puede_operar_en_el_portfolio_de_otro(
    client: TestClient, usuario, admin
) -> None:
    a = Sesion(client, *usuario)
    activo = _alta_activo(a)
    portfolio_de_a = _alta_portfolio(a, "Cartera de A")

    client.cookies.clear()
    b = Sesion(client, *admin)

    r = _operacion(b, portfolio_de_a, activo, "BUY", 1, 100, 1)
    assert r.status_code == 404

    client.cookies.clear()
    a2 = Sesion(client, *usuario)
    assert a2.get(f"/api/transactions?portfolio_id={portfolio_de_a['id']}").json() == []


def test_un_usuario_no_puede_anular_la_operacion_de_otro(
    client: TestClient, usuario, admin
) -> None:
    a = Sesion(client, *usuario)
    activo = _alta_activo(a)
    portfolio_de_a = _alta_portfolio(a, "Cartera de A")
    operacion = _operacion(a, portfolio_de_a, activo, "BUY", 10, 100, 1).json()

    client.cookies.clear()
    b = Sesion(client, *admin)

    r = b.post(
        f"/api/transactions/{operacion['id']}/void", json={"motivo": "no deberia poder"}
    )
    assert r.status_code == 404

    client.cookies.clear()
    a2 = Sesion(client, *usuario)
    todas = a2.get(
        f"/api/transactions?portfolio_id={portfolio_de_a['id']}&incluir_anuladas=true"
    ).json()
    assert todas[0]["status"] == "ACTIVE"


def test_las_cuentas_son_privadas(client: TestClient, usuario, admin) -> None:
    a = Sesion(client, *usuario)
    r = a.post("/api/accounts", json={"name": "IOL", "account_type": "BROKER"})
    assert r.status_code == 201, r.text

    client.cookies.clear()
    b = Sesion(client, *admin)
    assert b.get("/api/accounts").json() == []


def test_operar_sin_csrf_es_rechazado(client: TestClient, usuario) -> None:
    """El token de sesion no alcanza: escribir exige tambien el CSRF."""
    s = Sesion(client, *usuario)
    portfolio = _alta_portfolio(s)
    r = client.post(
        "/api/transactions",
        headers={"Authorization": f"Bearer {s.token}"},  # sin X-CSRF-Token
        json={
            "portfolio_id": portfolio["id"],
            "tx_type": "DEPOSIT",
            "quantity": "1",
            "unit_price": "1000",
            "price_currency": "ARS",
            "executed_at": datetime(2025, 6, 1, 12, 0).isoformat(),
        },
    )
    assert r.status_code == 403
