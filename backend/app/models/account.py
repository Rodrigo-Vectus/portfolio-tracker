"""Cuentas y portfolios.

`account` reemplaza el campo `broker` de texto libre de la especificacion
original. Texto libre garantiza "IOL", "iol" e "InvertirOnline" como tres
brokers distintos, que es la misma suciedad que traia la planilla en la
columna de sector.

Cuentas iniciales conocidas (D17): IOL como broker, Binance y BingX como
exchanges. Son filas, no un enum: agregar una cuenta no debe requerir una
migracion.
"""

from uuid import UUID, uuid4

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums_finance import AccountType
from app.models.mixins import TimestampMixin


class Account(Base, TimestampMixin):
    """Donde esta depositado el dinero o el activo."""

    __tablename__ = "account"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_account_user_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        Enum(AccountType, name="account_type", native_enum=True), nullable=False
    )
    country: Mapped[str | None] = mapped_column(String(2))
    default_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="ARS")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Account {self.name} {self.account_type}>"


class Portfolio(Base, TimestampMixin):
    """Agrupacion de operaciones sobre la que se calculan las posiciones.

    Multiples portfolios por usuario figura como futuro en la especificacion y
    la interfaz no lo expone. La columna existe igual desde el primer modelo:
    agregarla despues obligaria a migrar toda la tabla de operaciones, y
    ahora no cuesta nada.
    """

    __tablename__ = "portfolio"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_portfolio_user_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)

    # Moneda de contabilidad del portfolio (D2). No es lo mismo que la moneda
    # de visualizacion, que la elige el usuario y puede cambiar sin afectar
    # ningun calculo guardado.
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    def __repr__(self) -> str:
        return f"<Portfolio {self.name} {self.base_currency}>"
