"""Frescura de las cotizaciones y totalización de la cartera.

Acá vive la regla que originó el proyecto: **nunca presentar un precio viejo
como actual**. Estas pruebas existen para que esa regla sea verificable y no
una intención escrita en un documento.

Python puro. Sin red, sin base.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.market import (
    Cotizacion,
    Frescura,
    ValorDePosicion,
    totalizar,
)

AHORA = datetime(2026, 9, 4, 20, 0, tzinfo=UTC)


def cotiz(precio: str, *, hace: timedelta | None = None, tipo: str = "CEDEAR"):
    return Cotizacion(
        symbol="AAPL",
        price=Decimal(precio),
        currency="ARS",
        source="prueba",
        fetched_at=AHORA,
        quoted_at=None if hace is None else AHORA - hace,
        asset_type=tipo,
    )


def pos(cantidad: str, cotizacion, frescura: Frescura) -> ValorDePosicion:
    return ValorDePosicion(
        symbol="AAPL",
        quantity=Decimal(cantidad),
        cotizacion=cotizacion,
        frescura=frescura,
    )


# ------------------------------------------------------------------ frescura


def test_sin_fecha_del_proveedor_no_se_puede_saber_la_antiguedad() -> None:
    """`antiguedad()` devuelve None, no la antigüedad del pedido.

    Responder con `ahora - fetched_at` contestaría otra pregunta: cuánto hace
    que preguntamos, no cuánto hace que el mercado lo dijo. Entre las dos
    puede haber un fin de semana.
    """
    c = cotiz("20960")
    assert c.antiguedad(AHORA) is None
    assert c.frescura(AHORA) is Frescura.SIN_FECHA
    assert not c.es_confiable


def test_una_cotizacion_dentro_del_umbral_es_fresca() -> None:
    c = cotiz("20960", hace=timedelta(hours=2))
    assert c.frescura(AHORA) is Frescura.FRESCA
    assert c.antiguedad(AHORA) == timedelta(hours=2)


def test_una_cotizacion_pasado_el_umbral_es_vieja() -> None:
    assert cotiz("20960", hace=timedelta(days=2)).frescura(AHORA) is Frescura.VIEJA


# ------------------------------------------------- total de cartera (D34)


def test_el_total_se_calcula_cuando_todo_esta_fresco() -> None:
    valores = [
        pos("10", cotiz("20960", hace=timedelta(hours=1)), Frescura.FRESCA),
        pos("5", cotiz("25000", hace=timedelta(hours=1)), Frescura.FRESCA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert t.es_completo
    assert t.total is not None
    assert t.total.amount == Decimal(10) * Decimal(20960) + Decimal(5) * Decimal(25000)
    assert t.motivo_incompleto is None


def test_una_sola_posicion_vieja_invalida_el_total() -> None:
    """El color de una fila no viaja hasta la suma.

    Una posición vieja marcada en pantalla se lee como vieja. Un total con una
    posición vieja adentro se lee como completo, y ahí está el engaño. Por eso
    el total no se entrega como número.
    """
    valores = [
        pos("10", cotiz("20960", hace=timedelta(hours=1)), Frescura.FRESCA),
        pos("5", cotiz("25000", hace=timedelta(days=3)), Frescura.VIEJA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert not t.es_completo
    assert t.total is None
    assert "1 con precio viejo" in t.motivo_incompleto


def test_una_posicion_sin_fecha_tambien_invalida_el_total() -> None:
    """Es el caso real de los CEDEARs: data912 no informa cuándo se cotizó."""
    valores = [
        pos("10", cotiz("20960"), Frescura.SIN_FECHA),
        pos("5", cotiz("25000", hace=timedelta(hours=1)), Frescura.FRESCA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert t.total is None
    assert "1 sin fecha de cotización" in t.motivo_incompleto


def test_una_posicion_sin_cotizacion_invalida_el_total() -> None:
    valores = [
        pos("10", cotiz("20960", hace=timedelta(hours=1)), Frescura.FRESCA),
        pos("5", None, Frescura.AUSENTE),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert t.total is None
    assert "1 sin cotización" in t.motivo_incompleto
    assert t.posiciones_sin_precio == 1


def test_el_motivo_acumula_todos_los_problemas() -> None:
    """Decir sólo el primero obligaría a arreglar de a uno para enterarse."""
    valores = [
        pos("1", None, Frescura.AUSENTE),
        pos("1", cotiz("100", hace=timedelta(days=5)), Frescura.VIEJA),
        pos("1", cotiz("100"), Frescura.SIN_FECHA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    motivo = t.motivo_incompleto
    assert "1 sin cotización" in motivo
    assert "1 con precio viejo" in motivo
    assert "1 sin fecha de cotización" in motivo


def test_una_cartera_vacia_no_finge_un_total_en_cero() -> None:
    """Cero pesos y "no hay nada" no son lo mismo."""
    t = totalizar([], "ARS", AHORA)
    assert t.total is None
    assert t.posiciones_totales == 0
