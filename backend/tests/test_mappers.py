"""Traduccion entre la persistencia y el dominio.

Estas pruebas no necesitan base de datos: se construye una fila del ORM en
memoria y se verifica que el objeto del dominio que sale sea equivalente.

Vale la pena tenerlas porque el mapeo es donde se pierden las cosas en
silencio. Un campo mal traducido no rompe nada: produce un numero distinto
que sigue pareciendo razonable.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.domain.ledger import TxStatus, TxType
from app.models.enums_finance import TransactionStatus, TransactionType
from app.models.transaction import Transaction as OrmTx
from app.services.mappers import to_domain


def fila(**kw) -> OrmTx:
    base = dict(
        tx_type=TransactionType.BUY,
        quantity=Decimal("10"),
        unit_price=Decimal("100.5"),
        price_currency="ARS",
        settlement_currency="ARS",
        commission=Decimal("0"),
        taxes=Decimal("0"),
        executed_at=datetime(2025, 6, 23, 12, 0),
        trade_date=date(2025, 6, 23),
        status=TransactionStatus.ACTIVE,
    )
    base.update(kw)
    f = OrmTx(**base)
    f.id = kw.pop("id", "11111111-1111-1111-1111-111111111111")
    return f


def test_los_decimales_no_se_convierten_a_float() -> None:
    """Si el mapeo pasara por float, 100.5 dejaria de ser exacto."""
    d = to_domain(fila(), symbol="AAPL")
    assert isinstance(d.unit_price, Decimal)
    assert d.unit_price == Decimal("100.5")


def test_el_tipo_y_el_estado_se_traducen() -> None:
    d = to_domain(fila(), symbol="AAPL")
    assert d.tx_type is TxType.BUY
    assert d.status is TxStatus.ACTIVE

    v = to_domain(fila(status=TransactionStatus.VOIDED), symbol="AAPL")
    assert v.status is TxStatus.VOIDED
    assert not v.is_active


def test_la_venta_se_traduce_como_venta_con_cantidad_positiva() -> None:
    """El signo lo lleva el tipo, nunca la cantidad."""
    d = to_domain(fila(tx_type=TransactionType.SELL), symbol="AAPL")
    assert d.tx_type is TxType.SELL
    assert d.quantity == Decimal("10")


def test_la_comision_nula_se_traduce_como_cero() -> None:
    """La columna admite NULL; el dominio exige un numero."""
    d = to_domain(fila(commission=None, taxes=None), symbol="AAPL")
    assert d.commission == Decimal(0)
    assert d.taxes == Decimal(0)


def test_el_simbolo_llega_de_afuera() -> None:
    """No se lee de row.asset: cargar la relacion seria una consulta por fila."""
    d = to_domain(fila(), symbol="meli")
    assert d.symbol == "MELI"


def test_una_fila_con_cantidad_negativa_es_rechazada() -> None:
    """La base ya lo impide con un CHECK; el dominio es la segunda barrera."""
    from app.domain.ledger import LedgerError

    with pytest.raises(LedgerError):
        to_domain(fila(quantity=Decimal("-5")), symbol="AAPL")
