"""Historico diario de precios y de la cartera.

Revision ID: 0008_snapshots
Revises: 0007_price_factor
Create Date: 2026-09-08

Dos tablas:

`price_bar_daily` guarda el cierre de cada activo por dia. Esta separada de
`price_quote` porque son cosas distintas: una es el precio de ahora con
retencion corta, la otra es la serie permanente. Mezclarlas en una sola tabla
con solo un timestamp hace lenta la consulta de un anio y vuelve imposible la
deduplicacion.

`portfolio_snapshot` guarda el valor de la cartera por dia. Es cache
reconstruible desde el libro mas los precios, nunca autoridad.

**`total_value` es NULLABLE y eso es deliberado.** Si un dia le falta la
cotizacion a alguna posicion, el snapshot se guarda igual con el valor en NULL
y el motivo escrito. Un hueco declarado dice "ese dia no se pudo valuar"; un
cero diria que la cartera valia cero, que es una afirmacion distinta y falsa.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_snapshots"
down_revision: Union[str, None] = "0007_price_factor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRICE = sa.Numeric(28, 10)
AMOUNT = sa.Numeric(38, 18)
QUANTITY = sa.Numeric(38, 18)
UUID_T = postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    op.create_table(
        "price_bar_daily",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("close", PRICE, nullable=False),
        sa.Column("open", PRICE),
        sa.Column("high", PRICE),
        sa.Column("low", PRICE),
        sa.Column("volume", QUANTITY),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        # El cierre puede provenir de un precio cuya hora se dedujo del
        # horario de rueda. Se marca para no confundirlo con un dato del
        # proveedor.
        sa.Column("is_estimated", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="CASCADE",
                                name="fk_price_bar_daily_asset_id_asset"),
        # Deduplicacion por dia y fuente: el worker puede correr varias veces.
        sa.UniqueConstraint("asset_id", "trade_date", "source",
                            name="uq_price_bar_daily_asset_id"),
        sa.CheckConstraint("close > 0", name="ck_price_bar_daily_close_positivo"),
    )
    op.create_index("ix_price_bar_daily_asset_fecha", "price_bar_daily",
                    ["asset_id", "trade_date"])
    op.create_index("ix_price_bar_daily_trade_date", "price_bar_daily", ["trade_date"])

    op.create_table(
        "portfolio_snapshot",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("user_id", UUID_T, nullable=False),
        sa.Column("portfolio_id", UUID_T, nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        # NULL cuando falto la cotizacion de alguna posicion. Ver el docstring.
        sa.Column("total_value", AMOUNT),
        sa.Column("open_cost_basis", AMOUNT, nullable=False),
        sa.Column("unrealized_pnl", AMOUNT),
        sa.Column("realized_pnl", AMOUNT, nullable=False, server_default="0"),
        sa.Column("cash_balance", AMOUNT, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("is_estimated", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("posiciones", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("posiciones_sin_precio", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("motivo", sa.Text()),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE",
                                name="fk_portfolio_snapshot_user_id_user_account"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE",
                                name="fk_portfolio_snapshot_portfolio_id_portfolio"),
        # Un snapshot por cartera y por dia: volver a correr el dia lo pisa en
        # vez de duplicarlo.
        sa.UniqueConstraint("portfolio_id", "snapshot_date",
                            name="uq_portfolio_snapshot_portfolio_id"),
    )
    op.create_index("ix_portfolio_snapshot_user_id", "portfolio_snapshot", ["user_id"])
    op.create_index("ix_portfolio_snapshot_portfolio_fecha", "portfolio_snapshot",
                    ["portfolio_id", "snapshot_date"])

    op.execute(
        "UPDATE app_metadata SET value = '5', updated_at = now() "
        "WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'historico diario de precios y "
        "snapshots de cartera', updated_at = now() WHERE key = 'schema_description'"
    )


def downgrade() -> None:
    op.drop_table("portfolio_snapshot")
    op.drop_table("price_bar_daily")

    op.execute(
        "UPDATE app_metadata SET value = '3', updated_at = now() "
        "WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'market data: cotizaciones, tipo de "
        "cambio y bitacora de proveedores', updated_at = now() "
        "WHERE key = 'schema_description'"
    )
