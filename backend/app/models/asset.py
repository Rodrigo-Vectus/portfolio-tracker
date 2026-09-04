"""Catalogo de activos.

El catalogo vive **fuera** de la tabla de operaciones. En la planilla anterior
vivia adentro, y el resultado fue previsible: MELI figuraba con sector
`Beverages` en seis filas y `Software & IT Services` en ocho, MSFT estaba
escrito `MICROSFT` en las doce filas, y SPY y QQQ tenian el nombre del ETF en
la columna de sector. Cuando el catalogo es una columna repetida, cada fila es
una oportunidad de contradecir a las demas.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums_finance import AssetType, CorporateActionType
from app.models.mixins import TimestampMixin

# Escalas declaradas una sola vez. 18 decimales en cantidades por las
# criptomonedas; los importes comparten la escala para que ninguna operacion
# intermedia pierda precision por el camino. El redondeo es una decision de
# presentacion y ocurre en el borde de la API, nunca en la base.
QUANTITY = Numeric(38, 18)
PRICE = Numeric(28, 10)
AMOUNT = Numeric(38, 18)
RATE = Numeric(28, 10)


class Asset(Base, TimestampMixin):
    """Un instrumento negociable.

    `symbol` **no** puede ser unico global: AAPL como CEDEAR que cotiza en
    BYMA y AAPL como accion estadounidense son activos distintos, con precio,
    moneda y mercado distintos. La clave natural es la terna.
    """

    __tablename__ = "asset"
    __table_args__ = (
        UniqueConstraint("symbol", "market", "asset_type", name="uq_asset_symbol_market_type"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="asset_type", native_enum=True), nullable=False
    )

    # En que moneda cotiza el activo. Un CEDEAR cotiza en ARS aunque se piense
    # en dolares: son dos conceptos distintos y confundirlos fue el error de
    # fondo de la planilla anterior.
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    market: Mapped[str | None] = mapped_column(String(16))

    # Decimales con los que se muestra. No se usa para calcular.
    display_precision: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    sector: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    def __repr__(self) -> str:
        return f"<Asset {self.symbol} {self.asset_type} {self.market}>"


class AssetIdentifier(Base, TimestampMixin):
    """Como llama cada proveedor a este activo.

    Es uno a muchos y no un campo unico: AAPL es `AAPL.BA` en un proveedor y
    `AAPL` en otro; Bitcoin es `bitcoin` en uno y `BTCUSDT` en otro. Un solo
    `provider_symbol` obliga a elegir proveedor en el modelo de datos, que es
    exactamente lo que la interfaz de proveedor existe para evitar.
    """

    __tablename__ = "asset_identifier"
    __table_args__ = (
        UniqueConstraint("provider", "external_symbol", name="uq_asset_identifier_provider"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    external_symbol: Mapped[str] = mapped_column(String(64), nullable=False)

    # Orden de preferencia cuando hay varios proveedores para el mismo activo.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)


class CedearDetail(Base, TimestampMixin):
    """Que hay atras de un CEDEAR.

    Uno a uno con `asset`: la PK es la FK. Un CEDEAR de AAPL representa una
    fraccion de la accion de AAPL en Nasdaq, y ese vinculo hace falta para
    calcular el valor teorico (D5) y para procesar acciones societarias.
    """

    __tablename__ = "cedear_detail"

    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="CASCADE"), primary_key=True
    )
    underlying_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    underlying_market: Mapped[str | None] = mapped_column(String(16))
    underlying_currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")


class CedearRatio(Base, TimestampMixin):
    """Cuantos CEDEARs equivalen a cuantas acciones, **con vigencia**.

    Es una serie temporal y no un campo del activo (Regla 14). Un ratio
    sobrescribible corrompe retroactivamente todas las valuaciones historicas
    sin que nadie se entere: el numero de ayer se recalcula con el ratio de
    hoy y nada avisa.

    `effective_to` nulo significa vigente. El solapamiento no se puede impedir
    con un UNIQUE simple, asi que lo valida el servicio al insertar.
    """

    __tablename__ = "cedear_ratio"
    __table_args__ = (
        UniqueConstraint("asset_id", "effective_from", name="uq_cedear_ratio_asset_id"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    ratio_cedears: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    ratio_shares: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str | None] = mapped_column(String(80))


class CorporateAction(Base, TimestampMixin):
    """Splits, cambios de ratio y dividendos.

    La tabla existe desde la Fase 2 aunque el procesamiento llegue despues.
    Crearla mas adelante obligaria a rehacer el historico: un split no
    aplicado hace que la cantidad y el precio de las operaciones anteriores
    dejen de tener sentido, y para entonces ya no se sabe cuales corregir.
    """

    __tablename__ = "corporate_action"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    asset_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("asset.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action_type: Mapped[CorporateActionType] = mapped_column(
        Enum(CorporateActionType, name="corporate_action_type", native_enum=True),
        nullable=False,
    )
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    factor: Mapped[Decimal | None] = mapped_column(RATE)
    amount: Mapped[Decimal | None] = mapped_column(AMOUNT)
    currency: Mapped[str | None] = mapped_column(String(8))

    # Marca si ya se proceso. Arranca en false y nadie lo pone en true todavia.
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(255))
