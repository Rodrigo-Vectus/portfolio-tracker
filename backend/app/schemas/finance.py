"""Contratos de la API financiera.

**Todo importe y cantidad se serializa como string.** No es una rareza: en
JSON los numeros son de doble precision, asi que un `NUMERIC(38,18)` que sale
como numero pierde exactitud en el camino y el navegador recibe algo distinto
de lo que hay en la base. Un string cruza intacto y el frontend decide como
mostrarlo.

Es la misma regla que rige en la base y en el dominio, aplicada al ultimo
tramo. De nada sirve `Decimal` de punta a punta si el JSON lo degrada al
salir.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.timezones import a_utc

from app.models.enums_finance import (
    AccountType,
    AssetType,
    TransactionStatus,
    TransactionType,
)


class DecimalOut(BaseModel):
    """Base para respuestas: los Decimal salen como string."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json")
    def _decimales_como_string(self, value):  # noqa: ANN001, ANN202
        """Decimal a texto en notacion posicional, nunca cientifica.

        `str(Decimal("0.000000000000000000"))` devuelve `"0E-18"`: Python usa
        notacion exponencial cuando el coeficiente es cero. Es un numero
        valido, pero ningun cliente espera leerlo asi, y un formateador que no
        lo reconozca lo muestra crudo en pantalla.

        `format(value, "f")` fuerza la forma posicional sin perder un digito.
        """
        return format(value, "f") if isinstance(value, Decimal) else value


# --------------------------------------------------------------------- activos


class AssetIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    asset_type: AssetType
    currency: str = Field(min_length=2, max_length=8)
    market: str | None = Field(default=None, max_length=16)
    sector: str | None = Field(default=None, max_length=80)
    display_precision: int = Field(default=2, ge=0, le=18)


class AssetOut(DecimalOut):
    id: UUID
    symbol: str
    name: str
    asset_type: AssetType
    currency: str
    market: str | None
    sector: str | None
    display_precision: int
    is_active: bool


# -------------------------------------------------------- cuentas y portfolios


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    account_type: AccountType
    country: str | None = Field(default=None, max_length=2)
    default_currency: str = Field(default="ARS", max_length=8)


class AccountOut(DecimalOut):
    id: UUID
    name: str
    account_type: AccountType
    country: str | None
    default_currency: str
    is_active: bool


class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_currency: str = Field(default="USD", max_length=8)
    is_default: bool = False


class PortfolioOut(DecimalOut):
    id: UUID
    name: str
    base_currency: str
    is_default: bool


# ----------------------------------------------------------------- operaciones


class TransactionIn(BaseModel):
    """Alta de una operacion.

    La cantidad entra como string y siempre positiva. El signo lo lleva
    `tx_type`: aceptar un numero negativo reintroduciria la convencion de la
    planilla anterior, donde una venta era una cantidad negativa y la columna
    de precio de compra guardaba en realidad el precio de venta.
    """

    portfolio_id: UUID
    asset_id: UUID | None = None
    account_id: UUID | None = None
    tx_type: TransactionType
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    price_currency: str = Field(min_length=2, max_length=8)
    settlement_currency: str | None = Field(default=None, max_length=8)
    commission: Decimal = Field(default=Decimal(0), ge=0)
    taxes: Decimal = Field(default=Decimal(0), ge=0)
    fx_rate_used: Decimal | None = Field(default=None, gt=0)
    fx_source: str | None = Field(default=None, max_length=40)
    executed_at: datetime
    trade_date: date | None = None
    notes: str | None = None
    external_id: str | None = Field(default=None, max_length=64)

    @field_validator("executed_at")
    @classmethod
    def _normalizar_zona(cls, value: datetime) -> datetime:
        """Una fecha sin zona se interpreta en la zona configurada del sistema.

        Es la convencion de la API y esta documentada tambien en el endpoint.
        No se asume UTC: una compra de las 22:30 en Buenos Aires quedaria
        fechada al dia siguiente y su `trade_date` saldria en otra rueda.

        Si el cliente manda offset explicito, se respeta.
        """
        return a_utc(value)


class TransactionVoidIn(BaseModel):
    """Anular exige motivo. Sin motivo es un borrado con otro nombre."""

    motivo: str = Field(min_length=3, max_length=255)


class TransactionOut(DecimalOut):
    id: UUID
    portfolio_id: UUID
    asset_id: UUID | None
    account_id: UUID | None
    tx_type: TransactionType
    quantity: Decimal
    unit_price: Decimal
    price_currency: str
    settlement_currency: str
    commission: Decimal
    taxes: Decimal
    gross_amount: Decimal | None
    net_amount: Decimal | None
    fx_rate_used: Decimal | None
    fx_source: str | None
    executed_at: datetime
    trade_date: date
    status: TransactionStatus
    voided_reason: str | None
    notes: str | None


# ------------------------------------------------------------------ posiciones


class PositionOut(DecimalOut):
    """Posición derivada del libro, con su valuación cuando existe.

    **Todo lo de mercado puede venir en `None`, y eso es información.** Un
    `current_value` nulo dice "no sé cuánto vale"; un cero diría "no vale
    nada". No son lo mismo y el frontend los muestra distinto.

    `price_as_of` y `price_is_estimated` viajan siempre con el precio: un
    número de mercado sin su antigüedad es el problema que originó este
    proyecto.
    """

    asset_id: UUID
    symbol: str
    asset_type: AssetType
    quantity: Decimal
    average_cost: Decimal | None
    open_cost_basis: Decimal
    realized_pnl: Decimal
    cost_method: str
    currency: str
    last_transaction_at: datetime | None
    computed_at: datetime | None

    # --- valuación (todo opcional: puede no haber cotización) ---
    current_price: Decimal | None = None
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    price_source: str | None = None
    #: Cuándo se cotizó. Si es una estimación, `price_is_estimated` lo dice.
    price_as_of: datetime | None = None
    price_is_estimated: bool = False
    #: FRESCA | ESTIMADA | VIEJA | SIN_FECHA | AUSENTE
    price_status: str = "AUSENTE"


class TotalOut(BaseModel):
    """Total de la cartera, con su propia declaración de completitud.

    `total` viene en `None` cuando a alguna posición le falta el precio o lo
    tiene viejo. En ese caso `motivo` explica por qué, para que la interfaz
    pueda decirlo en vez de mostrar un espacio vacío.
    """

    model_config = ConfigDict(from_attributes=True)

    total: str | None
    currency: str
    es_completo: bool
    es_estimado: bool
    motivo: str | None
    posiciones_totales: int
    posiciones_sin_precio: int
    posiciones_con_precio_viejo: int
    posiciones_estimadas: int


class PositionsResponse(BaseModel):
    positions: list[PositionOut]
    total: TotalOut
