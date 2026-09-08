"""Snapshots diarios de la cartera.

Python puro: sin base de datos.

El punto de estas pruebas es lo que el snapshot hace cuando **falta** un dato.
Un día sin valuación tiene que quedar como hueco declarado, no como un cero:
un cero en la serie dibuja una caída a cero que nunca ocurrió.
"""

from datetime import date, datetime
from decimal import Decimal

from app.domain.market import Cotizacion, Frescura, ValorDePosicion
from app.domain.snapshot import construir_snapshot, serie_de_evolucion

HOY = date(2026, 9, 8)
AHORA = datetime(2026, 9, 8, 20, 0)


def valor(symbol: str, cantidad: str, precio: str | None, frescura: Frescura):
    cot = (
        None
        if precio is None
        else Cotizacion(
            symbol=symbol, price=Decimal(precio), currency="ARS", source="prueba",
            fetched_at=AHORA, quoted_at=AHORA, asset_type="CEDEAR",
        )
    )
    return ValorDePosicion(
        symbol=symbol, quantity=Decimal(cantidad), cotizacion=cot, frescura=frescura
    )


def snap(valores, costo="1000", realizado="0", caja="0"):
    return construir_snapshot(
        fecha=HOY, valores=valores, costo_abierto=Decimal(costo),
        realizado=Decimal(realizado), caja=Decimal(caja), currency="ARS",
    )


def test_con_todo_cotizado_el_snapshot_es_completo() -> None:
    s = snap([valor("AAPL", "10", "100", Frescura.FRESCA)], costo="800")
    assert s.total_value == Decimal(1000)
    assert s.unrealized_pnl == Decimal(200)
    assert s.es_completo
    assert not s.is_estimated
    assert s.motivo is None


def test_una_posicion_sin_precio_deja_el_valor_en_nulo() -> None:
    """Un hueco declarado dice "ese día no se pudo valuar".

    Un cero diría que la cartera valía cero, que es una afirmación distinta y
    falsa.
    """
    s = snap([
        valor("AAPL", "10", "100", Frescura.FRESCA),
        valor("MELI", "5", None, Frescura.AUSENTE),
    ])
    assert s.total_value is None
    assert s.unrealized_pnl is None
    assert not s.es_completo
    assert s.posiciones_sin_precio == 1
    assert "1 sin cotización" in s.motivo


def test_una_antiguedad_estimada_marca_el_punto() -> None:
    """El gráfico puede dibujar distinto los puntos estimados.

    Sin la marca no habría forma de distinguirlos después: la serie quedaría
    con puntos que parecen medidos y son deducidos.
    """
    s = snap([valor("AAPL", "10", "100", Frescura.ESTIMADA)])
    assert s.total_value == Decimal(1000)
    assert s.is_estimated
    assert "antigüedad estimada" in s.motivo


def test_un_precio_viejo_tambien_marca_el_punto() -> None:
    s = snap([valor("AAPL", "10", "100", Frescura.VIEJA)])
    assert s.is_estimated
    assert "precio viejo" in s.motivo


def test_el_snapshot_guarda_la_caja_y_el_realizado() -> None:
    """El valor de la cartera no incluye el efectivo: son dos números.

    Sumarlos daría el patrimonio total, que es otra cosa y merece su propia
    columna en vez de esconderse dentro del valor de las posiciones.
    """
    s = snap([valor("AAPL", "10", "100", Frescura.FRESCA)], realizado="250", caja="5000")
    assert s.total_value == Decimal(1000)
    assert s.cash_balance == Decimal(5000)
    assert s.realized_pnl == Decimal(250)


def test_una_cartera_vacia_no_finge_un_valor() -> None:
    s = snap([], costo="0")
    assert s.posiciones == 0
    assert s.total_value == Decimal(0)


def test_la_serie_no_interpola_los_huecos() -> None:
    """Una línea que cruza un hueco afirma que ese día la cartera valía el
    promedio de sus vecinos, y eso no se sabe. El gráfico corta y lo muestra.
    """
    s1 = construir_snapshot(
        fecha=date(2026, 9, 6), valores=[valor("AAPL", "10", "100", Frescura.FRESCA)],
        costo_abierto=Decimal(800), realizado=Decimal(0), caja=Decimal(0),
        currency="ARS",
    )
    s2 = construir_snapshot(
        fecha=date(2026, 9, 7), valores=[valor("AAPL", "10", None, Frescura.AUSENTE)],
        costo_abierto=Decimal(800), realizado=Decimal(0), caja=Decimal(0),
        currency="ARS",
    )
    s3 = construir_snapshot(
        fecha=date(2026, 9, 8), valores=[valor("AAPL", "10", "120", Frescura.FRESCA)],
        costo_abierto=Decimal(800), realizado=Decimal(0), caja=Decimal(0),
        currency="ARS",
    )

    puntos = serie_de_evolucion([s3, s1, s2])
    assert [p.fecha.day for p in puntos] == [6, 7, 8]
    assert [p.valor for p in puntos] == [Decimal(1000), None, Decimal(1200)]


def test_la_serie_se_ordena_por_fecha() -> None:
    """Los snapshots pueden llegar en cualquier orden desde la base."""
    fechas = [date(2026, 9, d) for d in (8, 6, 7)]
    snaps = [
        construir_snapshot(
            fecha=f, valores=[], costo_abierto=Decimal(0), realizado=Decimal(0),
            caja=Decimal(0), currency="ARS",
        )
        for f in fechas
    ]
    assert [p.fecha.day for p in serie_de_evolucion(snaps)] == [6, 7, 8]
