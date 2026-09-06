"""Saldo de caja.

Casos verificados a mano, con la aritmética en cada docstring. Sin base de
datos: el dominio es Python puro.

El saldo importa más de lo que parece. Es la única forma de saber cuánta plata
tenés sin invertir, y `aporte_neto` es el flujo que va a necesitar el XIRR.
"""

from datetime import date, datetime
from decimal import Decimal

from app.domain.cash import calcular_saldo, monedas_con_movimientos
from app.domain.ledger import Transaction, TxStatus, TxType


def tx(
    tx_id: str,
    tipo: TxType,
    cantidad: str,
    precio: str,
    dia: int,
    comision: str = "0",
    symbol: str = "AAPL",
    moneda: str = "ARS",
    status: TxStatus = TxStatus.ACTIVE,
) -> Transaction:
    return Transaction(
        tx_id=tx_id, symbol=symbol, tx_type=tipo, quantity=cantidad,
        unit_price=precio, currency=moneda,
        executed_at=datetime(2025, 6, dia, 12, 0), trade_date=date(2025, 6, dia),
        commission=comision, status=status,
    )


def deposito(tx_id: str, monto: str, dia: int, moneda: str = "ARS") -> Transaction:
    """Un depósito se carga con cantidad 1 y el monto en el precio."""
    return tx(tx_id, TxType.DEPOSIT, "1", monto, dia, symbol="CASH", moneda=moneda)


def test_un_deposito_es_todo_el_saldo() -> None:
    s = calcular_saldo([deposito("d1", "100000", 1)])
    assert s.saldo == Decimal(100000)
    assert s.depositos == Decimal(100000)
    assert s.aporte_neto == Decimal(100000)


def test_una_compra_consume_efectivo() -> None:
    """Depósito 100.000, compra 4 × 20.000 = 80.000. Queda 20.000."""
    ops = [deposito("d1", "100000", 1), tx("c1", TxType.BUY, "4", "20000", 2)]
    s = calcular_saldo(ops)
    assert s.saldo == Decimal(20000)
    assert s.invertido == Decimal(80000)


def test_la_comision_de_compra_tambien_sale_de_la_caja() -> None:
    """No es sólo cantidad × precio: la comisión también se paga.

        depósito 100.000 − (4 × 20.000 + 500) = 19.500
    """
    ops = [
        deposito("d1", "100000", 1),
        tx("c1", TxType.BUY, "4", "20000", 2, comision="500"),
    ]
    assert calcular_saldo(ops).saldo == Decimal(19500)


def test_la_comision_de_venta_se_descuenta_de_lo_que_entra() -> None:
    """Al vender entra el bruto menos la comisión, no el bruto entero.

        100.000 − 80.000 + (2 × 25.000 − 300) = 69.700
    """
    ops = [
        deposito("d1", "100000", 1),
        tx("c1", TxType.BUY, "4", "20000", 2),
        tx("v1", TxType.SELL, "2", "25000", 3, comision="300"),
    ]
    s = calcular_saldo(ops)
    assert s.saldo == Decimal(69700)
    assert s.recuperado == Decimal(49700)


def test_un_retiro_baja_el_aporte_neto() -> None:
    """Depositar 100.000 y retirar 30.000 deja un aporte neto de 70.000.

    `aporte_neto` responde "cuánto puse de mi bolsillo", que es distinto del
    costo de las posiciones abiertas y del capital neto aportado.
    """
    ops = [
        deposito("d1", "100000", 1),
        tx("w1", TxType.WITHDRAWAL, "1", "30000", 2, symbol="CASH"),
    ]
    s = calcular_saldo(ops)
    assert s.saldo == Decimal(70000)
    assert s.aporte_neto == Decimal(70000)
    assert s.retiros == Decimal(30000)


def test_un_dividendo_entra_a_la_caja() -> None:
    ops = [deposito("d1", "1000", 1), tx("dv", TxType.DIVIDEND, "1", "500", 2)]
    s = calcular_saldo(ops)
    assert s.saldo == Decimal(1500)
    assert s.dividendos == Decimal(500)


def test_una_transferencia_no_cambia_el_saldo_total() -> None:
    """Mover plata entre cuentas propias cambia dónde está, no cuánto hay."""
    ops = [
        deposito("d1", "100000", 1),
        tx("t1", TxType.TRANSFER, "1", "50000", 2, symbol="CASH"),
    ]
    assert calcular_saldo(ops).saldo == Decimal(100000)


def test_el_saldo_puede_quedar_negativo_y_se_avisa() -> None:
    """Comprar sin haber registrado el depósito deja saldo negativo.

    **No se impide.** El libro registra lo que pasó; forzar el orden de carga
    haría que el usuario invente un depósito para poder anotar una compra que
    sí ocurrió. Se muestra y se avisa.
    """
    s = calcular_saldo([tx("c1", TxType.BUY, "4", "20000", 1)])
    assert s.saldo == Decimal(-80000)
    assert s.es_negativo


def test_las_operaciones_anuladas_no_afectan_la_caja() -> None:
    ops = [
        deposito("d1", "100000", 1),
        tx("c1", TxType.BUY, "4", "20000", 2, status=TxStatus.VOIDED),
    ]
    assert calcular_saldo(ops).saldo == Decimal(100000)


def test_cada_moneda_tiene_su_saldo() -> None:
    """No se mezclan pesos y dólares.

    Sumarlos requeriría convertir, y la conversión necesita un tipo de cambio
    con su fecha (D2). No se hace implícitamente.
    """
    ops = [deposito("d1", "100000", 1), deposito("d2", "500", 2, moneda="USD")]
    assert calcular_saldo(ops, "ARS").saldo == Decimal(100000)
    assert calcular_saldo(ops, "USD").saldo == Decimal(500)
    assert monedas_con_movimientos(ops) == ["ARS", "USD"]


def test_el_saldo_posterior_permite_auditar_movimiento_por_movimiento() -> None:
    """Cada movimiento guarda el saldo que dejó.

    Sin eso, un saldo final equivocado obliga a recalcular todo a mano para
    encontrar dónde se desvió.
    """
    ops = [
        deposito("d1", "100000", 1),
        tx("c1", TxType.BUY, "2", "20000", 2),
        tx("v1", TxType.SELL, "1", "25000", 3),
    ]
    saldos = [m.saldo_posterior for m in calcular_saldo(ops).movimientos]
    assert saldos == [Decimal(100000), Decimal(60000), Decimal(85000)]
