"""Casos financieros verificados a mano.

Cada caso trae la aritmetica en el docstring. La razon esta en el historial del
proyecto: un error en el motor de lotes **no se nota**, porque los numeros
siguen pareciendo razonables. Un test que solo comprueba que el codigo corre
sin excepciones no sirve para nada aca.

No requieren PostgreSQL ni Redis: el dominio es Python puro.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.domain.cost_basis import (
    CostMethod,
    build_lots,
    realized_fifo,
    realized_wac,
)
from app.domain.ledger import (
    InsufficientHoldings,
    LedgerError,
    Transaction,
    TxStatus,
    TxType,
)
from app.domain.money import Money, MoneyError
from app.domain.positions import build_position

ARS = "ARS"


def tx(
    tx_id: str,
    tipo: TxType,
    cantidad: str,
    precio: str,
    dia: int,
    comision: str = "0",
    impuestos: str = "0",
    status: TxStatus = TxStatus.ACTIVE,
    symbol: str = "AAPL",
) -> Transaction:
    return Transaction(
        tx_id=tx_id,
        symbol=symbol,
        tx_type=tipo,
        quantity=cantidad,
        unit_price=precio,
        currency=ARS,
        executed_at=datetime(2025, 6, dia, 12, 0),
        trade_date=date(2025, 6, dia),
        commission=comision,
        taxes=impuestos,
        status=status,
    )


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------


def test_money_rechaza_float() -> None:
    """Regla 2: nunca float. Decimal(0.1) no es 0,1 y eso aparece meses despues."""
    with pytest.raises(MoneyError, match="no se admite float"):
        Money(0.1, ARS)


def test_money_no_suma_monedas_distintas() -> None:
    """Sumar ARS con USD sin FX explicito es el error E1 del Excel."""
    with pytest.raises(MoneyError, match="tipo de cambio"):
        Money("100", "ARS") + Money("100", "USD")


def test_money_no_redondea() -> None:
    """1000 / 3 debe conservar todos los decimales; el redondeo es presentacion."""
    resultado = Money("1000", ARS).divide(3)
    assert resultado.amount == Decimal("1000") / Decimal(3)


# --------------------------------------------------------------------------
# Ledger
# --------------------------------------------------------------------------


def test_la_cantidad_negativa_se_rechaza() -> None:
    """El Excel cargaba las ventas como cantidad negativa. Aca no se puede."""
    with pytest.raises(LedgerError, match="cantidad debe ser positiva"):
        tx("t1", TxType.SELL, "-10", "100", 1)


def test_la_comision_negativa_se_rechaza() -> None:
    with pytest.raises(LedgerError, match="comision no puede ser negativa"):
        tx("t1", TxType.BUY, "10", "100", 1, comision="-5")


def test_las_operaciones_anuladas_no_cuentan() -> None:
    """D13: una operacion se anula, no se borra, y deja de afectar el calculo.

    Compra 10 @ 100 (ACTIVE) + compra 10 @ 500 (VOIDED) -> tenencia 10, costo 1000.
    """
    ops = [
        tx("t1", TxType.BUY, "10", "100", 1),
        tx("t2", TxType.BUY, "10", "500", 2, status=TxStatus.VOIDED),
    ]
    pos = build_position(ops, CostMethod.WAC)
    assert pos.quantity == Decimal(10)
    assert pos.open_cost_basis.amount == Decimal(1000)


# --------------------------------------------------------------------------
# FIFO vs WAC — el caso central
# --------------------------------------------------------------------------


def _historial_dos_lotes() -> list[Transaction]:
    """Compra 10 @ 100, compra 10 @ 200, vende 12 @ 250. Sin comisiones."""
    return [
        tx("c1", TxType.BUY, "10", "100", 1),
        tx("c2", TxType.BUY, "10", "200", 2),
        tx("v1", TxType.SELL, "12", "250", 3),
    ]


def test_realizado_wac() -> None:
    """Costo promedio movil.

        costo total  = 10x100 + 10x200 = 3.000 ; cantidad 20 ; ppc = 150
        realizado    = 12 x (250 - 150) = 1.200
    """
    assert realized_wac(_historial_dos_lotes()).amount == Decimal(1200)


def test_realizado_fifo() -> None:
    """Se consume primero el lote mas viejo.

        10 del lote a 100 -> 10 x (250 - 100) = 1.500
         2 del lote a 200 ->  2 x (250 - 200) =   100
        realizado                              = 1.600
    """
    assert realized_fifo(_historial_dos_lotes()).amount == Decimal(1600)


def test_fifo_y_wac_difieren_sobre_el_mismo_historial() -> None:
    """400 de diferencia sobre las mismas tres operaciones.

    Es la version chica de los 287.567 ARS (41,6%) del historial real. Si este
    test alguna vez da cero, uno de los dos metodos dejo de calcularse.
    """
    ops = _historial_dos_lotes()
    assert realized_fifo(ops).amount - realized_wac(ops).amount == Decimal(400)


def test_costo_abierto_depende_del_metodo() -> None:
    """Quedan 8 unidades.

        WAC  : 3.000 - 12 x 150 = 1.200  (ppc 150)
        FIFO : las 8 restantes son del lote de 200 -> 1.600
    """
    ops = _historial_dos_lotes()
    assert build_position(ops, CostMethod.WAC).open_cost_basis.amount == Decimal(1200)
    assert build_position(ops, CostMethod.FIFO).open_cost_basis.amount == Decimal(1600)
    assert build_position(ops, CostMethod.WAC).quantity == Decimal(8)


# --------------------------------------------------------------------------
# Comisiones (D6)
# --------------------------------------------------------------------------


def test_la_comision_de_compra_suma_al_costo_del_lote() -> None:
    """Compra 10 @ 100 con comision 50 -> costo 1.050, unitario 105."""
    ledger = build_lots([tx("c1", TxType.BUY, "10", "100", 1, comision="50")])
    assert ledger.lots[0].unit_cost == Decimal("105")


def test_la_comision_de_venta_resta_del_realizado() -> None:
    """Compra 10 @ 100 comision 50 ; vende 5 @ 200 comision 20.

        costo unitario = (1.000 + 50) / 10 = 105
        realizado      = 5 x (200 - 105) - 20 = 475 - 20 = 455
    """
    ops = [
        tx("c1", TxType.BUY, "10", "100", 1, comision="50"),
        tx("v1", TxType.SELL, "5", "200", 2, comision="20"),
    ]
    assert realized_fifo(ops).amount == Decimal(455)
    assert realized_wac(ops).amount == Decimal(455)


def test_la_comision_de_venta_se_resta_una_sola_vez() -> None:
    """Una venta que consume dos lotes no paga la comision dos veces.

        compra 5 @ 100, compra 5 @ 100, vende 10 @ 150 comision 30
        realizado = 10 x (150 - 100) - 30 = 470
    """
    ops = [
        tx("c1", TxType.BUY, "5", "100", 1),
        tx("c2", TxType.BUY, "5", "100", 2),
        tx("v1", TxType.SELL, "10", "150", 3, comision="30"),
    ]
    assert realized_fifo(ops).amount == Decimal(470)


# --------------------------------------------------------------------------
# Venta que excede la tenencia
# --------------------------------------------------------------------------


def test_vender_mas_de_lo_que_hay_es_un_error() -> None:
    """La fila 44 del Excel: venta de 25 con tenencia de 13.

    El motor rechaza siempre. Nunca produce cantidad negativa.
    """
    ops = [
        tx("c1", TxType.BUY, "13", "100", 1),
        tx("v1", TxType.SELL, "25", "150", 2),
    ]
    with pytest.raises(InsufficientHoldings) as exc:
        realized_fifo(ops)
    assert exc.value.requested == Decimal(25)
    assert exc.value.available == Decimal(13)

    with pytest.raises(InsufficientHoldings):
        realized_wac(ops)
    with pytest.raises(InsufficientHoldings):
        build_lots(ops)


# --------------------------------------------------------------------------
# Posicion
# --------------------------------------------------------------------------


def test_posicion_cerrada_no_tiene_precio_promedio() -> None:
    """Cerrar toda la posicion deja average_cost en None, no en cero.

    Un cero se leeria como "me costo nada".
    """
    ops = [
        tx("c1", TxType.BUY, "10", "100", 1),
        tx("v1", TxType.SELL, "10", "150", 2),
    ]
    pos = build_position(ops, CostMethod.WAC)
    assert pos.quantity == Decimal(0)
    assert pos.average_cost is None
    assert pos.realized_pnl.amount == Decimal(500)


def test_la_posicion_es_reconstruible_y_determinista() -> None:
    """Misma entrada, mismo resultado. Los lotes son cache, no autoridad."""
    ops = _historial_dos_lotes()
    a = build_position(ops, CostMethod.FIFO)
    b = build_position(list(reversed(ops)), CostMethod.FIFO)
    assert a.quantity == b.quantity
    assert a.realized_pnl.amount == b.realized_pnl.amount
    assert a.open_cost_basis.amount == b.open_cost_basis.amount


def test_el_consumo_de_lotes_queda_registrado() -> None:
    """La venta de 12 consume 10 del primer lote y 2 del segundo."""
    ledger = build_lots(_historial_dos_lotes())
    consumos = [(c.lot_id, c.quantity) for c in ledger.consumptions]
    assert consumos == [("lot:c1", Decimal(10)), ("lot:c2", Decimal(2))]
    assert ledger.quantity == Decimal(8)


def test_el_mensaje_de_tenencia_insuficiente_es_legible() -> None:
    """Las columnas son NUMERIC(38,18) y el mensaje lo lee una persona.

    "hay 10.000000000000000000 disponibles" obliga a contar ceros para
    entender qué dice. El valor comparado sigue siendo el Decimal exacto: lo
    que cambia es sólo cómo se escribe.
    """
    ops = [
        tx("c1", TxType.BUY, "10", "100", 1),
        tx("v1", TxType.SELL, "25", "150", 2),
    ]
    with pytest.raises(InsufficientHoldings) as exc:
        realized_fifo(ops)

    mensaje = str(exc.value)
    assert "hay 10 disponibles" in mensaje
    assert "10.000000" not in mensaje


def test_el_mensaje_conserva_los_decimales_que_importan() -> None:
    """Recortar ceros de relleno no es lo mismo que redondear.

    Media unidad de una cripto tiene que seguir viéndose como 0,5.
    """
    ops = [
        tx("c1", TxType.BUY, "0.25", "100", 1, symbol="BTC"),
        tx("v1", TxType.SELL, "0.5", "150", 2, symbol="BTC"),
    ]
    with pytest.raises(InsufficientHoldings) as exc:
        realized_fifo(ops)
    assert "vender 0.5" in str(exc.value)
    assert "hay 0.25" in str(exc.value)
