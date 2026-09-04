"""Derivados del libro: lotes, consumo y cache de posiciones.

**Nada de esto es autoridad.** Las tres tablas son cache reconstruible desde
`transaction`, y debe existir siempre un comando que las rehaga desde cero. Si
un numero de aca discrepa del libro, el que esta mal es este, no el libro.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin

QUANTITY = Numeric(38, 18)
PRICE = Numeric(28, 10)
AMOUNT = Numeric(38, 18)


class CostLot(Base, TimestampMixin):
    """Un lote abierto por una compra.

    `unit_cost` ya incluye la comision y los impuestos prorrateados (D6). Se
    guarda el costo unitario y no el total para que el consumo parcial no
    tenga que dividir dos veces.
    """

    __tablename__ = "cost_lot"
    __table_args__ = (
        CheckConstraint("quantity_open >= 0", name="quantity_open_no_negativa"),
        CheckConstraint(
            "quantity_open <= quantity_original", name="quantity_open_no_excede_original"
        ),
        Index("ix_cost_lot_portfolio_asset_acquired", "portfolio_id", "asset_id", "acquired_at"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False
    )
    # Una compra abre exactamente un lote: la relacion es uno a uno y el
    # UNIQUE lo garantiza. Si aparece un segundo lote para la misma compra, la
    # reconstruccion corrio dos veces sin limpiar.
    source_tx_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("transaction.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )

    quantity_original: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    quantity_open: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(PRICE, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LotConsumption(Base, TimestampMixin):
    """Cuanto de que lote consumio una venta.

    **No guarda resultado realizado, a proposito.** Es un cambio respecto del
    diseno registrado en `DATA_MODEL.md` B.6, y la razon es concreta: sobre
    las operaciones reales del historico, el mismo consumo de lotes produce
    477.475 ARS por costo promedio y 575.975 por FIFO. Una sola columna no
    puede guardar los dos numeros, y guardarla sin decir de que metodo es
    convierte un dato ambiguo en un dato aparentemente confiable.

    Lo que si es univoco es **que lote se agoto y en que orden**, y eso es lo
    que se guarda. El resultado de cada metodo lo calcula
    `app/domain/cost_basis.py` sobre esta misma secuencia.
    """

    __tablename__ = "lot_consumption"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positiva"),
        UniqueConstraint("sell_tx_id", "cost_lot_id", name="uq_lot_consumption_sell_tx_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    sell_tx_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("transaction.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    cost_lot_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("cost_lot.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)

    # Orden de consumo dentro de la misma venta. Sin esto no se puede
    # reproducir la secuencia exacta al auditar un resultado.
    sequence: Mapped[int] = mapped_column(nullable=False, default=0)


class PositionCache(Base, TimestampMixin):
    """Posicion materializada. Cache, nunca autoridad.

    **No persiste `current_price`, `current_value` ni `unrealized_pnl`.** Esa
    era la entidad `Position` de la especificacion original, y mezclaba dato
    ingresado, dato de mercado y dato calculado en una sola fila. Es el mismo
    problema de la planilla con mas pasos: un precio guardado que envejece en
    silencio y que nadie mira dos veces.

    Solo vive aca lo que se deriva de operaciones, que cambia unicamente
    cuando cambia una operacion. El valor actual se resuelve en tiempo de
    consulta contra la ultima cotizacion valida y viaja con su `as_of`.
    """

    __tablename__ = "position_cache"
    __table_args__ = (
        UniqueConstraint("portfolio_id", "asset_id", name="uq_position_cache_portfolio_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    portfolio_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("portfolio.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="RESTRICT"), nullable=False
    )

    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    average_cost: Mapped[Decimal | None] = mapped_column(PRICE)

    # Costo base de los lotes abiertos. Se llama asi y no "capital invertido"
    # porque hay tres definiciones incompatibles de esa frase y dan tres
    # porcentajes distintos: la de la planilla (compras menos ventas) se
    # achica al vender e infla el rendimiento sola.
    open_cost_basis: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False)

    realized_pnl: Mapped[Decimal] = mapped_column(AMOUNT, nullable=False, default=0)
    # De que metodo es el realizado guardado. Sin esto el numero es ambiguo.
    cost_method: Mapped[str] = mapped_column(String(8), nullable=False, default="WAC")
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    last_transaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    computed_through: Mapped[date | None] = mapped_column(Date)
