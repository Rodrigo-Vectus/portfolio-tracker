"""Ledger de lotes y resultado realizado (D4).

Decision de diseno de esta fase, que **cambia `DATA_MODEL.md` §B.6**:

`lot_consumption` guarda **solo el consumo de cantidad**, en orden FIFO, y no
guarda `realized_pnl`. El motivo es que un `realized_pnl` a nivel de lote no
dice de que metodo es, y no puede ser de los dos a la vez: sobre el historial
real, FIFO y WAC difieren 287.567 ARS, un 41,6%. Guardar un numero ambiguo en
la tabla es exactamente como se propaga en silencio un error de lotes.

Que el consumo fisico sea FIFO no es una eleccion de metodo contable: es el
orden en que se agotan los lotes, y es el mismo para todos los metodos. El
resultado realizado de cada metodo se calcula aca, sobre la misma secuencia.

Convencion de comisiones (D6): en una compra suman al costo base del lote; en
una venta restan del producido, una sola vez por venta y no por cada lote
consumido.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from app.domain.ledger import (
    InsufficientHoldings,
    Transaction,
    TxType,
    active_sorted,
    assert_same_currency,
)
from app.domain.money import Money

ZERO = Decimal(0)


class CostMethod(str, Enum):
    WAC = "WAC"
    FIFO = "FIFO"


@dataclass(slots=True)
class CostLot:
    """Un lote abierto por una compra."""

    lot_id: str
    symbol: str
    source_tx_id: str
    quantity_original: Decimal
    quantity_open: Decimal
    unit_cost: Decimal  # incluye comision e impuestos prorrateados (D6)
    currency: str
    acquired_at: datetime

    @property
    def open_cost(self) -> Money:
        return Money(self.quantity_open * self.unit_cost, self.currency)

    @property
    def is_closed(self) -> bool:
        return self.quantity_open == ZERO


@dataclass(frozen=True, slots=True)
class LotConsumption:
    """Cuanto de que lote consumio una venta. Sin resultado: ver el docstring."""

    sell_tx_id: str
    lot_id: str
    quantity: Decimal


@dataclass(slots=True)
class LotLedger:
    lots: list[CostLot] = field(default_factory=list)
    consumptions: list[LotConsumption] = field(default_factory=list)

    @property
    def open_lots(self) -> list[CostLot]:
        return [lot for lot in self.lots if not lot.is_closed]

    @property
    def quantity(self) -> Decimal:
        return sum((lot.quantity_open for lot in self.lots), ZERO)


def build_lots(transactions: list[Transaction]) -> LotLedger:
    """Reconstruye el ledger de lotes desde el historial.

    Funcion pura: mismas operaciones, mismo resultado. Los lotes son cache
    reconstruible, nunca autoridad.
    """
    ordenadas = active_sorted(transactions)
    currency = assert_same_currency(ordenadas)
    ledger = LotLedger()

    for tx in ordenadas:
        if tx.tx_type is TxType.BUY:
            costo_total = tx.quantity * tx.unit_price + tx.commission + tx.taxes
            ledger.lots.append(
                CostLot(
                    lot_id=f"lot:{tx.tx_id}",
                    symbol=tx.symbol,
                    source_tx_id=tx.tx_id,
                    quantity_original=tx.quantity,
                    quantity_open=tx.quantity,
                    unit_cost=costo_total / tx.quantity,
                    currency=currency,
                    acquired_at=tx.executed_at,
                )
            )

        elif tx.tx_type is TxType.SELL:
            disponible = ledger.quantity
            if tx.quantity > disponible:
                raise InsufficientHoldings(tx.symbol, tx.quantity, disponible)

            pendiente = tx.quantity
            for lot in ledger.lots:
                if pendiente == ZERO:
                    break
                if lot.is_closed:
                    continue
                tomado = min(lot.quantity_open, pendiente)
                lot.quantity_open -= tomado
                pendiente -= tomado
                ledger.consumptions.append(
                    LotConsumption(sell_tx_id=tx.tx_id, lot_id=lot.lot_id, quantity=tomado)
                )

    return ledger


def realized_fifo(transactions: list[Transaction]) -> Money:
    """Resultado realizado consumiendo el lote mas antiguo primero."""
    ordenadas = active_sorted(transactions)
    currency = assert_same_currency(ordenadas)
    ledger = LotLedger()
    realizado = ZERO

    for tx in ordenadas:
        if tx.tx_type is TxType.BUY:
            costo_total = tx.quantity * tx.unit_price + tx.commission + tx.taxes
            ledger.lots.append(
                CostLot(
                    lot_id=f"lot:{tx.tx_id}",
                    symbol=tx.symbol,
                    source_tx_id=tx.tx_id,
                    quantity_original=tx.quantity,
                    quantity_open=tx.quantity,
                    unit_cost=costo_total / tx.quantity,
                    currency=currency,
                    acquired_at=tx.executed_at,
                )
            )

        elif tx.tx_type is TxType.SELL:
            disponible = ledger.quantity
            if tx.quantity > disponible:
                raise InsufficientHoldings(tx.symbol, tx.quantity, disponible)

            pendiente = tx.quantity
            for lot in ledger.lots:
                if pendiente == ZERO:
                    break
                if lot.is_closed:
                    continue
                tomado = min(lot.quantity_open, pendiente)
                realizado += tomado * (tx.unit_price - lot.unit_cost)
                lot.quantity_open -= tomado
                pendiente -= tomado
            # La comision de venta se resta una sola vez, no por lote.
            realizado -= tx.commission + tx.taxes

    return Money(realizado, currency)


def realized_wac(transactions: list[Transaction]) -> Money:
    """Resultado realizado con costo promedio ponderado movil.

        al comprar:  cantidad += q ;  costo += q x precio + comision
        al vender:   ppc = costo / cantidad
                     realizado += q_vendida x (precio_venta - ppc) - comision
                     costo     -= q_vendida x ppc
                     cantidad  -= q_vendida
    """
    ordenadas = active_sorted(transactions)
    currency = assert_same_currency(ordenadas)

    cantidad = ZERO
    costo = ZERO
    realizado = ZERO

    for tx in ordenadas:
        if tx.tx_type is TxType.BUY:
            cantidad += tx.quantity
            costo += tx.quantity * tx.unit_price + tx.commission + tx.taxes

        elif tx.tx_type is TxType.SELL:
            if tx.quantity > cantidad:
                raise InsufficientHoldings(tx.symbol, tx.quantity, cantidad)
            ppc = costo / cantidad
            realizado += tx.quantity * (tx.unit_price - ppc) - tx.commission - tx.taxes
            costo -= tx.quantity * ppc
            cantidad -= tx.quantity

    return Money(realizado, currency)


def realized(transactions: list[Transaction], method: CostMethod) -> Money:
    if method is CostMethod.FIFO:
        return realized_fifo(transactions)
    return realized_wac(transactions)
