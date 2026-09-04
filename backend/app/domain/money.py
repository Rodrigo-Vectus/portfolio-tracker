"""Cantidades y montos con moneda. Nunca float.

Un `float` en una aplicacion financiera es un bug que aparece en el decimal 12
seis meses despues. Este modulo hace imposible construir un importe desde un
float: el constructor lo rechaza en vez de convertirlo en silencio.

`Money` tambien impide sumar pesos con dolares. No es purismo: el error E1 del
Excel anterior fue exactamente eso, mezclar unidades sin que nada avisara.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Union

Numeric = Union[int, str, Decimal]


class MoneyError(Exception):
    """Error de construccion u operacion sobre importes."""


def to_decimal(value: Numeric, *, field: str = "valor") -> Decimal:
    """Convierte a Decimal exacto. Rechaza float explicitamente.

    Se aceptan int, str y Decimal. Un float se rechaza porque su conversion es
    silenciosamente inexacta: Decimal(0.1) es 0.1000000000000000055511151231...
    """
    if isinstance(value, float):
        raise MoneyError(
            f"{field}: no se admite float. Usar str o Decimal "
            f"(recibido {value!r})."
        )
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        try:
            return Decimal(value)
        except Exception as exc:  # noqa: BLE001
            raise MoneyError(f"{field}: no es un numero valido ({value!r}).") from exc
    raise MoneyError(f"{field}: tipo no admitido ({type(value).__name__}).")


@dataclass(frozen=True, slots=True)
class Money:
    """Un importe con su moneda. Inmutable.

    No redondea nunca. El redondeo es una decision de presentacion y ocurre en
    el borde de la API, jamas dentro del calculo.
    """

    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_decimal(self.amount, field="amount"))
        if not self.currency or not self.currency.strip():
            raise MoneyError("currency: no puede estar vacia.")
        object.__setattr__(self, "currency", self.currency.strip().upper())

    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(Decimal(0), currency)

    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise MoneyError(
                f"No se pueden operar {self.currency} y {other.currency}. "
                "La conversion necesita un tipo de cambio explicito con su fecha."
            )

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, factor: Numeric) -> Money:
        return Money(self.amount * to_decimal(factor, field="factor"), self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def divide(self, divisor: Numeric) -> Money:
        """Division exacta. No redondea: el resultado puede tener muchos decimales."""
        d = to_decimal(divisor, field="divisor")
        if d == 0:
            raise MoneyError("Division por cero.")
        return Money(self.amount / d, self.currency)

    def is_zero(self) -> bool:
        return self.amount == 0

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
