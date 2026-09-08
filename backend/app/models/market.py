"""Cotizaciones, tipo de cambio y bitácora de proveedores.

Tres reglas que estas tablas hacen cumplir:

**Todo precio guarda su origen y sus dos fechas.** `quoted_at` es cuándo lo
dijo el mercado; `fetched_at`, cuándo lo pedimos nosotros. Son distintas y una
no se rellena con la otra. Cuando el proveedor no informa la primera, queda en
NULL y la estimación va en su propio campo.

**Toda falla de proveedor se registra.** Un proveedor que falla en silencio
deja precios viejos sin que nadie se entere, y eso es exactamente el problema
que originó el proyecto.

**Nada de esto es autoridad sobre el libro.** Las cotizaciones son hechos
externos: se guardan, no se calculan.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

PRICE = Numeric(28, 10)
RATE = Numeric(28, 10)
QUANTITY = Numeric(38, 18)
AMOUNT = Numeric(38, 18)


class PriceQuote(Base, TimestampMixin):
    """Última cotización conocida de un activo, por fuente.

    Retención corta: es el precio de ahora, no el histórico. La serie diaria
    va en `price_bar_daily`, que llega en la Fase 5.

    La clave única es `(asset_id, source)`: se conserva una fila por fuente
    para poder comparar proveedores y detectar cuando uno se queda pegado
    mientras el otro se mueve.
    """

    __tablename__ = "price_quote"
    __table_args__ = (
        UniqueConstraint("asset_id", "source", name="uq_price_quote_asset_id"),
        Index("ix_price_quote_fetched_at", "fetched_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)

    # Cuándo lo dijo el mercado. NULL cuando el proveedor no lo informa: no se
    # rellena con `fetched_at`, que responde otra pregunta.
    quoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Cuándo lo pedimos nosotros. Siempre presente.
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Antigüedad inferida desde el horario de rueda cuando falta `quoted_at`.
    # Vive aparte para que una estimación nunca se confunda con un hecho.
    estimated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    extra: Mapped[dict | None] = mapped_column(JSONB)

    def __repr__(self) -> str:
        return f"<PriceQuote {self.asset_id} {self.price} {self.currency}>"


class FxRate(Base, TimestampMixin):
    """Serie histórica de tipo de cambio.

    Era la omisión más grave de la especificación original, que no tenía
    ninguna entidad de tipo de cambio. Sin serie histórica no se puede valuar
    en dólares una compra hecha en pesos, ni separar cuánto se ganó por el
    activo y cuánto por el dólar.

    Se guardan **todas** las series disponibles y no sólo la elegida por D1:
    cambiar de fuente altera todos los números históricos en dólares, así que
    conviene tener las alternativas para poder compararlas (D16).
    """

    __tablename__ = "fx_rate"
    __table_args__ = (
        UniqueConstraint(
            "base_currency", "quote_currency", "rate_type", "quoted_at",
            name="uq_fx_rate_base_currency",
        ),
        Index("ix_fx_rate_tipo_fecha", "rate_type", "quoted_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)

    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    #: OFICIAL | MEP | CCL | CRYPTO | BLUE. Texto y no enum: agregar una serie
    #: nueva no debería requerir una migración.
    rate_type: Mapped[str] = mapped_column(String(16), nullable=False)

    rate: Mapped[Decimal] = mapped_column(RATE, nullable=False)
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)

    def __repr__(self) -> str:
        return f"<FxRate {self.base_currency}/{self.quote_currency} {self.rate_type}>"


class ProviderLog(Base):
    """Bitácora de llamadas a proveedores externos.

    Existe para que ninguna falla quede en silencio. Un proveedor caído no
    rompe la aplicación: deja de actualizar precios, y sin este registro eso
    se vería como una cartera que "no se mueve" en vez de como un error.

    No hereda `TimestampMixin`: le alcanza con `created_at` y no se actualiza
    nunca.
    """

    __tablename__ = "provider_log"
    __table_args__ = (
        Index("ix_provider_log_provider_created", "provider", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    #: OK | HTTP_ERROR | PARSE_ERROR | TIMEOUT
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    http_status: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    assets_requested: Mapped[int | None] = mapped_column(Integer)
    assets_ok: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<ProviderLog {self.provider} {self.operation} {self.status}>"


class PriceBarDaily(Base, TimestampMixin):
    """Cierre diario de un activo. Serie permanente.

    Separada de `price_quote` porque son cosas distintas: una es el precio de
    ahora con retención corta, la otra es el histórico. Mezclarlas en una sola
    tabla con sólo un timestamp hace lenta la consulta de un año y vuelve
    imposible la deduplicación.
    """

    __tablename__ = "price_bar_daily"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "trade_date", "source", name="uq_price_bar_daily_asset_id"
        ),
        Index("ix_price_bar_daily_asset_fecha", "asset_id", "trade_date"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="CASCADE"), nullable=False
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    close: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    open: Mapped[Decimal | None] = mapped_column(PRICE)
    high: Mapped[Decimal | None] = mapped_column(PRICE)
    low: Mapped[Decimal | None] = mapped_column(PRICE)
    volume: Mapped[Decimal | None] = mapped_column(QUANTITY)

    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    #: El cierre puede venir de un precio cuya hora se dedujo del horario de
    #: rueda. Se marca para no confundirlo con un dato informado.
    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PortfolioSnapshot(Base, TimestampMixin):
    """Valor de la cartera en un día. Caché reconstruible, nunca autoridad.

    `total_value` es nullable a propósito: si un día faltó la cotización de
    alguna posición, el snapshot se guarda con el valor en NULL y el motivo
    escrito. Un hueco declarado dice "ese día no se pudo valuar"; un cero
    diría que la cartera valía cero.
    """

    __tablename__ = "portfolio_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "portfolio_id", "snapshot_date", name="uq_portfolio_snapshot_portfolio_id"
        ),
        Index("ix_portfolio_snapshot_portfolio_fecha", "portfolio_id", "snapshot_date"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("portfolio.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)

    total_value: Mapped[Decimal | None] = mapped_column(AMOUNT)
    open_cost_basis: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(AMOUNT)
    realized_pnl: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=0)
    cash_balance: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    is_estimated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    posiciones: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    posiciones_sin_precio: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    motivo: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
