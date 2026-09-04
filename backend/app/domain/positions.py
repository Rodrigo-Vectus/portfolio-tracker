"""Operaciones -> posicion.

La posicion es una **funcion pura del historial**. No se edita, no se ingresa,
no se corrige a mano. Si el numero esta mal, esta mal una operacion.

Lo que esta clase NO tiene, a proposito: `current_price`, `current_value` y
`unrealized_pnl`. La especificacion original los persistia en la entidad
`Position`, contradiciendo su propio principio rector y reintroduciendo el
precio guardado que envejece en silencio, que es el error que origino todo el
proyecto. El valor actual se resuelve en tiempo de consulta contra la ultima
cotizacion valida, y viaja con su `as_of`. Eso es Fase 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.cost_basis import (
    CostMethod,
    LotLedger,
    build_lots,
    realized,
)
from app.domain.ledger import Transaction, TxType, active_sorted, assert_same_currency
from app.domain.money import Money

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Position:
    symbol: str
    currency: str
    quantity: Decimal
    open_cost_basis: Money
    realized_pnl: Money
    method: CostMethod
    lots: LotLedger

    @property
    def average_cost(self) -> Money | None:
        """Costo unitario promedio de lo abierto. None si no hay tenencia.

        Devuelve None y no cero: una posicion cerrada no tiene precio promedio,
        y un cero se leeria como "me costo nada".
        """
        if self.quantity == ZERO:
            return None
        return self.open_cost_basis.divide(self.quantity)

    @property
    def is_open(self) -> bool:
        return self.quantity > ZERO


def build_position(
    transactions: list[Transaction],
    method: CostMethod = CostMethod.WAC,
) -> Position:
    """Reconstruye la posicion de un activo desde cero.

    `open_cost_basis` es el costo base de los lotes abiertos. Es la candidata
    (1) de FINANCIAL_ENGINE.md 3.4, y se llama asi y no "capital invertido"
    justamente porque hay tres definiciones incompatibles y la del Excel
    (compras menos ventas) se achica al vender e infla el porcentaje.
    """
    ordenadas = active_sorted(transactions)
    if not ordenadas:
        raise ValueError("No hay operaciones activas para construir la posicion.")

    simbolos = {t.symbol for t in ordenadas}
    if len(simbolos) > 1:
        raise ValueError(f"Operaciones de varios activos: {sorted(simbolos)}.")

    currency = assert_same_currency(ordenadas)
    symbol = simbolos.pop()

    ledger = build_lots(ordenadas)
    cantidad = ledger.quantity
    pnl = realized(ordenadas, method)

    if method is CostMethod.FIFO:
        costo_abierto = sum(
            (lot.quantity_open * lot.unit_cost for lot in ledger.lots), ZERO
        )
    else:
        costo_abierto = _wac_open_cost(ordenadas)

    return Position(
        symbol=symbol,
        currency=currency,
        quantity=cantidad,
        open_cost_basis=Money(costo_abierto, currency),
        realized_pnl=pnl,
        method=method,
        lots=ledger,
    )


def _wac_open_cost(transactions: list[Transaction]) -> Decimal:
    """Costo base remanente segun promedio ponderado movil."""
    cantidad = ZERO
    costo = ZERO
    for tx in transactions:
        if tx.tx_type is TxType.BUY:
            cantidad += tx.quantity
            costo += tx.quantity * tx.unit_price + tx.commission + tx.taxes
        elif tx.tx_type is TxType.SELL:
            ppc = costo / cantidad
            costo -= tx.quantity * ppc
            cantidad -= tx.quantity
    return costo


def build_positions(
    transactions: list[Transaction],
    method: CostMethod = CostMethod.WAC,
) -> dict[str, Position]:
    """Posiciones de una cartera completa, una por simbolo."""
    por_simbolo: dict[str, list[Transaction]] = {}
    for tx in active_sorted(transactions):
        por_simbolo.setdefault(tx.symbol, []).append(tx)
    return {s: build_position(txs, method) for s, txs in por_simbolo.items()}
