"""El libro de operaciones.

Es la unica fuente de verdad del sistema. Posiciones, lotes y snapshots se
reconstruyen desde aca y ninguno de ellos es autoridad.

Dos reglas que esta tabla hace cumplir por estructura:

1. **La cantidad es siempre positiva.** El signo lo lleva `tx_type`. En la
   planilla anterior las ventas eran cantidades negativas en la misma tabla y
   la columna "Precio Compra" contenia en realidad el precio de venta: la
   columna mentia, y nadie podia notarlo mirando una fila.
2. **Nada se borra.** Una correccion es una anulacion mas una operacion nueva
   (D13). El `CHECK` obliga a que toda anulacion tenga motivo escrito.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums_finance import DataOrigin, TransactionStatus, TransactionType
from app.models.mixins import TimestampMixin

QUANTITY = Numeric(38, 18)
PRICE = Numeric(28, 10)
AMOUNT = Numeric(38, 18)
RATE = Numeric(28, 10)


class Transaction(Base, TimestampMixin):
    __tablename__ = "transaction"
    __table_args__ = (
        # La cantidad negativa como convencion de venta no debe poder
        # escribirse ni siquiera saltandose la aplicacion.
        CheckConstraint("quantity >= 0", name="quantity_no_negativa"),
        CheckConstraint("commission >= 0", name="commission_no_negativa"),
        CheckConstraint("taxes >= 0", name="taxes_no_negativos"),
        # Una anulacion sin motivo es una operacion borrada con otro nombre.
        CheckConstraint(
            "status <> 'VOIDED' OR voided_reason IS NOT NULL",
            name="voided_exige_motivo",
        ),
        # Idempotencia del importador: el mismo renglon del mismo lote no
        # puede entrar dos veces.
        UniqueConstraint(
            "user_id", "import_batch_id", "external_id", name="uq_transaction_user_id"
        ),
        # El motor recorre las operaciones de un activo en orden cronologico:
        # este es el indice que sostiene la reconstruccion de posiciones.
        Index("ix_transaction_portfolio_asset_time", "portfolio_id", "asset_id", "executed_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)

    # `user_id` esta aca aunque sea derivable del portfolio: toda consulta
    # financiera filtra por el usuario autenticado, y ese filtro no debe
    # depender de un join que alguien pueda olvidar.
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("portfolio.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    account_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("account.id", ondelete="RESTRICT"), index=True
    )
    # Nulo en las operaciones que no tocan un activo: un deposito de efectivo,
    # una comision de mantenimiento.
    asset_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="RESTRICT"), index=True
    )

    tx_type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type", native_enum=True), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(PRICE, nullable=False)

    # La moneda del precio puede diferir de la de liquidacion: un CEDEAR se
    # compra en ARS pero se piensa en USD; una cripto se paga con USDT.
    price_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    settlement_currency: Mapped[str] = mapped_column(String(8), nullable=False)

    # D6: la comision afecta el costo base y va en la operacion. Los derechos
    # de mercado e IVA van aparte para poder reportarlos por separado.
    commission: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=0)
    commission_currency: Mapped[str | None] = mapped_column(String(8))
    taxes: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=0)
    taxes_currency: Mapped[str | None] = mapped_column(String(8))

    gross_amount: Mapped[Decimal | None] = mapped_column(AMOUNT)
    net_amount: Mapped[Decimal | None] = mapped_column(AMOUNT)

    # Congela el tipo de cambio del momento: es un dato historico irrepetible.
    # Para la importacion del historico va el valor que el usuario registro,
    # con origen INPUT (D16).
    fx_rate_used: Mapped[Decimal | None] = mapped_column(RATE)
    fx_source: Mapped[str | None] = mapped_column(String(40))
    fx_origin: Mapped[DataOrigin | None] = mapped_column(
        Enum(DataOrigin, name="data_origin", native_enum=True)
    )

    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Dia de rueda en horario de Buenos Aires. Los CEDEARs cotizan en rueda y
    # las criptomonedas 24/7: sin este campo, una operacion de las 22:30 cae
    # en el dia equivocado al agrupar.
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    notes: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(64))
    import_batch_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), index=True)

    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, name="transaction_status", native_enum=True),
        nullable=False, default=TransactionStatus.ACTIVE, index=True,
    )
    voided_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="SET NULL")
    )
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    voided_reason: Mapped[str | None] = mapped_column(String(255))

    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="SET NULL")
    )

    def __repr__(self) -> str:
        return f"<Transaction {self.tx_type} {self.quantity} @ {self.unit_price}>"
