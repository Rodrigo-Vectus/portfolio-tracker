"""El libro de operaciones: tipos, entidad y validaciones.

Reglas que este modulo hace cumplir:

- La cantidad **siempre es positiva**. El signo lo lleva el tipo de operacion,
  no el numero. En el Excel anterior las ventas eran cantidades negativas en la
  misma tabla, y la columna "Precio Compra" contenia en realidad el precio de
  venta: la columna mentia. Aca eso no se puede escribir.
- El libro es inmutable (D13). Una operacion no se edita ni se borra: se anula
  (`VOIDED`) y se crea la correccion. Por eso `Transaction` es `frozen`.
- Las operaciones anuladas no participan de ningun calculo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from app.domain.money import Money, Numeric, to_decimal


class LedgerError(Exception):
    """Operacion invalida."""


class InsufficientHoldings(LedgerError):
    """Se intento vender mas de lo que hay.

    Decision de Fase 2: el motor **siempre** rechaza. Nunca produce una
    cantidad negativa. Que hace el importador con esta excepcion (rechazar la
    fila, rechazar el lote o marcar) es decision de la Fase 2.5.

    Precedente real: la fila 44 del Excel vendia 25 AAPL con una tenencia de
    13, y nada lo detectaba.
    """

    def __init__(self, symbol: str, requested: Decimal, available: Decimal) -> None:
        self.symbol = symbol
        self.requested = requested
        self.available = available
        super().__init__(
            f"{symbol}: se intenta vender {requested} y hay {available} disponibles."
        )


class TxType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    FEE = "FEE"
    DIVIDEND = "DIVIDEND"
    TRANSFER = "TRANSFER"


class TxStatus(str, Enum):
    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"


#: Tipos que mueven la tenencia de un activo.
POSITION_TYPES = frozenset({TxType.BUY, TxType.SELL})


@dataclass(frozen=True, slots=True)
class Transaction:
    """Un hecho historico. Inmutable.

    `commission` y `taxes` van en campos separados (D6): la comision suma al
    costo base en una compra y resta del producido en una venta; los derechos
    de mercado e IVA se guardan aparte para poder reportarlos.
    """

    tx_id: str
    symbol: str
    tx_type: TxType
    quantity: Decimal
    unit_price: Decimal
    currency: str
    executed_at: datetime
    trade_date: date
    commission: Decimal = field(default_factory=lambda: Decimal(0))
    taxes: Decimal = field(default_factory=lambda: Decimal(0))
    status: TxStatus = TxStatus.ACTIVE

    def __post_init__(self) -> None:
        for name in ("quantity", "unit_price", "commission", "taxes"):
            object.__setattr__(
                self, name, to_decimal(getattr(self, name), field=name)
            )

        if not self.symbol or not self.symbol.strip():
            raise LedgerError("symbol: no puede estar vacio.")
        object.__setattr__(self, "symbol", self.symbol.strip().upper())
        object.__setattr__(self, "currency", self.currency.strip().upper())

        if self.tx_type in POSITION_TYPES:
            if self.quantity <= 0:
                raise LedgerError(
                    f"{self.tx_id}: la cantidad debe ser positiva. El signo lo "
                    f"lleva el tipo de operacion, no el numero "
                    f"(recibido {self.quantity})."
                )
            if self.unit_price < 0:
                raise LedgerError(
                    f"{self.tx_id}: el precio unitario no puede ser negativo."
                )

        if self.commission < 0:
            raise LedgerError(f"{self.tx_id}: la comision no puede ser negativa.")
        if self.taxes < 0:
            raise LedgerError(f"{self.tx_id}: los impuestos no pueden ser negativos.")

    @property
    def is_active(self) -> bool:
        return self.status is TxStatus.ACTIVE

    @property
    def gross(self) -> Money:
        """cantidad x precio, sin comisiones ni impuestos."""
        return Money(self.quantity * self.unit_price, self.currency)

    @property
    def cost_with_fees(self) -> Money:
        """Costo total de una compra: bruto + comision + impuestos (D6)."""
        return Money(
            self.quantity * self.unit_price + self.commission + self.taxes,
            self.currency,
        )

    @property
    def proceeds_net(self) -> Money:
        """Producido de una venta: bruto - comision - impuestos (D6)."""
        return Money(
            self.quantity * self.unit_price - self.commission - self.taxes,
            self.currency,
        )


def active_sorted(transactions: list[Transaction]) -> list[Transaction]:
    """Operaciones ACTIVE en orden cronologico determinista.

    El desempate por `tx_id` importa: dos operaciones del mismo instante deben
    consumir lotes siempre en el mismo orden, o el resultado realizado cambia
    entre corridas sin que nadie lo note.
    """
    activas = [t for t in transactions if t.is_active]
    return sorted(activas, key=lambda t: (t.executed_at, t.tx_id))


def assert_same_currency(transactions: list[Transaction]) -> str:
    """Todas las operaciones de un activo deben estar en la misma moneda.

    La conversion entre monedas necesita un tipo de cambio con su fecha (D2), y
    eso vive fuera del ledger. Mezclarlas aca seria repetir el error E1.
    """
    monedas = {t.currency for t in transactions}
    if len(monedas) > 1:
        raise LedgerError(
            f"Operaciones en monedas distintas: {sorted(monedas)}. "
            "La conversion requiere FX explicito con su fecha (D2)."
        )
    return monedas.pop() if monedas else ""
