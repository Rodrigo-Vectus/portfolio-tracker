"""Modelo financiero: activos, cuentas, operaciones y lotes.

Revision ID: 0003_finance
Revises: 0002_auth
Create Date: 2026-09-04

Diez tablas y seis enums nativos. Ninguna columna de dinero o cantidad usa
DOUBLE PRECISION ni REAL: todo es NUMERIC.

Los enums se crean con `create_type=False` mas `.create(checkfirst=True)`,
igual que en 0002. Sin eso, SQLAlchemy intenta crear el tipo una vez por
columna que lo usa y la segunda falla con "type already exists".
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_finance"
down_revision: Union[str, None] = "0002_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

QUANTITY = sa.Numeric(38, 18)
PRICE = sa.Numeric(28, 10)
AMOUNT = sa.Numeric(38, 18)
RATE = sa.Numeric(28, 10)

UUID_T = postgresql.UUID(as_uuid=True)

ENUMS = {
    "asset_type": ("CEDEAR", "CRYPTO", "CASH"),
    "account_type": ("BROKER", "EXCHANGE", "WALLET"),
    "transaction_type": (
        "BUY", "SELL", "DEPOSIT", "WITHDRAWAL", "FEE", "DIVIDEND", "TRANSFER",
    ),
    "transaction_status": ("ACTIVE", "VOIDED"),
    "corporate_action_type": ("SPLIT", "RATIO_CHANGE", "DIVIDEND"),
    "data_origin": ("INPUT", "MARKET", "COMPUTED"),
}


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    for name in ENUMS:
        _enum(name).create(bind, checkfirst=True)

    # ---------------------------------------------------------------- activos
    op.create_table(
        "asset",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("asset_type", _enum("asset_type"), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("market", sa.String(16)),
        sa.Column("display_precision", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("sector", sa.String(80)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("extra", postgresql.JSONB()),
        *_timestamps(),
        # AAPL como CEDEAR y AAPL como accion estadounidense son activos
        # distintos: el simbolo solo no puede ser la clave.
        sa.UniqueConstraint("symbol", "market", "asset_type",
                            name="uq_asset_symbol_market_type"),
    )
    op.create_index("ix_asset_symbol", "asset", ["symbol"])

    op.create_table(
        "asset_identifier",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("external_symbol", sa.String(64), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="CASCADE",
                                name="fk_asset_identifier_asset_id_asset"),
        sa.UniqueConstraint("provider", "external_symbol",
                            name="uq_asset_identifier_provider"),
    )
    op.create_index("ix_asset_identifier_asset_id", "asset_identifier", ["asset_id"])

    op.create_table(
        "cedear_detail",
        sa.Column("asset_id", UUID_T, primary_key=True),
        sa.Column("underlying_symbol", sa.String(32), nullable=False),
        sa.Column("underlying_market", sa.String(16)),
        sa.Column("underlying_currency", sa.String(8), nullable=False, server_default="USD"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="CASCADE",
                                name="fk_cedear_detail_asset_id_asset"),
    )

    # El ratio es una serie con vigencia, no un campo del activo: pisarlo
    # corrompe retroactivamente todo el historico sin que nadie se entere.
    op.create_table(
        "cedear_ratio",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("ratio_cedears", QUANTITY, nullable=False),
        sa.Column("ratio_shares", QUANTITY, nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source", sa.String(80)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="CASCADE",
                                name="fk_cedear_ratio_asset_id_asset"),
        sa.UniqueConstraint("asset_id", "effective_from", name="uq_cedear_ratio_asset_id"),
    )
    op.create_index("ix_cedear_ratio_asset_id", "cedear_ratio", ["asset_id"])

    op.create_table(
        "corporate_action",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("action_type", _enum("corporate_action_type"), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("factor", RATE),
        sa.Column("amount", AMOUNT),
        sa.Column("currency", sa.String(8)),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(255)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="CASCADE",
                                name="fk_corporate_action_asset_id_asset"),
    )
    op.create_index("ix_corporate_action_asset_id", "corporate_action", ["asset_id"])

    # ------------------------------------------------- cuentas y portfolios
    op.create_table(
        "account",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("user_id", UUID_T, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("account_type", _enum("account_type"), nullable=False),
        sa.Column("country", sa.String(2)),
        sa.Column("default_currency", sa.String(8), nullable=False, server_default="ARS"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE",
                                name="fk_account_user_id_user_account"),
        sa.UniqueConstraint("user_id", "name", name="uq_account_user_id"),
    )
    op.create_index("ix_account_user_id", "account", ["user_id"])

    op.create_table(
        "portfolio",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("user_id", UUID_T, nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base_currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE",
                                name="fk_portfolio_user_id_user_account"),
        sa.UniqueConstraint("user_id", "name", name="uq_portfolio_user_id"),
    )
    op.create_index("ix_portfolio_user_id", "portfolio", ["user_id"])

    # ------------------------------------------------------ libro de ordenes
    op.create_table(
        "transaction",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("user_id", UUID_T, nullable=False),
        sa.Column("portfolio_id", UUID_T, nullable=False),
        sa.Column("account_id", UUID_T),
        sa.Column("asset_id", UUID_T),
        sa.Column("tx_type", _enum("transaction_type"), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False),
        sa.Column("unit_price", PRICE, nullable=False),
        sa.Column("price_currency", sa.String(8), nullable=False),
        sa.Column("settlement_currency", sa.String(8), nullable=False),
        sa.Column("commission", AMOUNT, nullable=False, server_default="0"),
        sa.Column("commission_currency", sa.String(8)),
        sa.Column("taxes", AMOUNT, nullable=False, server_default="0"),
        sa.Column("taxes_currency", sa.String(8)),
        sa.Column("gross_amount", AMOUNT),
        sa.Column("net_amount", AMOUNT),
        sa.Column("fx_rate_used", RATE),
        sa.Column("fx_source", sa.String(40)),
        sa.Column("fx_origin", _enum("data_origin")),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("external_id", sa.String(64)),
        sa.Column("import_batch_id", UUID_T),
        sa.Column("status", _enum("transaction_status"), nullable=False,
                  server_default="ACTIVE"),
        sa.Column("voided_by", UUID_T),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("voided_reason", sa.String(255)),
        sa.Column("created_by", UUID_T),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE",
                                name="fk_transaction_user_id_user_account"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE",
                                name="fk_transaction_portfolio_id_portfolio"),
        # RESTRICT y no CASCADE: borrar una cuenta o un activo no debe poder
        # borrar operaciones. El libro es inmutable.
        sa.ForeignKeyConstraint(["account_id"], ["account.id"], ondelete="RESTRICT",
                                name="fk_transaction_account_id_account"),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="RESTRICT",
                                name="fk_transaction_asset_id_asset"),
        sa.ForeignKeyConstraint(["voided_by"], ["user_account.id"], ondelete="SET NULL",
                                name="fk_transaction_voided_by_user_account"),
        sa.ForeignKeyConstraint(["created_by"], ["user_account.id"], ondelete="SET NULL",
                                name="fk_transaction_created_by_user_account"),
        # La venta como cantidad negativa no debe poder escribirse ni
        # saltandose la aplicacion.
        sa.CheckConstraint("quantity >= 0", name="ck_transaction_quantity_no_negativa"),
        sa.CheckConstraint("commission >= 0", name="ck_transaction_commission_no_negativa"),
        sa.CheckConstraint("taxes >= 0", name="ck_transaction_taxes_no_negativos"),
        # Una anulacion sin motivo es un borrado con otro nombre.
        sa.CheckConstraint("status <> 'VOIDED' OR voided_reason IS NOT NULL",
                           name="ck_transaction_voided_exige_motivo"),
        sa.UniqueConstraint("user_id", "import_batch_id", "external_id",
                            name="uq_transaction_user_id"),
    )
    op.create_index("ix_transaction_user_id", "transaction", ["user_id"])
    op.create_index("ix_transaction_portfolio_id", "transaction", ["portfolio_id"])
    op.create_index("ix_transaction_account_id", "transaction", ["account_id"])
    op.create_index("ix_transaction_asset_id", "transaction", ["asset_id"])
    op.create_index("ix_transaction_trade_date", "transaction", ["trade_date"])
    op.create_index("ix_transaction_status", "transaction", ["status"])
    op.create_index("ix_transaction_import_batch_id", "transaction", ["import_batch_id"])
    # El motor recorre las operaciones de un activo en orden cronologico.
    op.create_index("ix_transaction_portfolio_asset_time", "transaction",
                    ["portfolio_id", "asset_id", "executed_at"])

    # ----------------------------------------- derivados (cache reconstruible)
    op.create_table(
        "cost_lot",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("user_id", UUID_T, nullable=False),
        sa.Column("portfolio_id", UUID_T, nullable=False),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("source_tx_id", UUID_T, nullable=False),
        sa.Column("quantity_original", QUANTITY, nullable=False),
        sa.Column("quantity_open", QUANTITY, nullable=False),
        sa.Column("unit_cost", PRICE, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE",
                                name="fk_cost_lot_user_id_user_account"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE",
                                name="fk_cost_lot_portfolio_id_portfolio"),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="RESTRICT",
                                name="fk_cost_lot_asset_id_asset"),
        sa.ForeignKeyConstraint(["source_tx_id"], ["transaction.id"], ondelete="CASCADE",
                                name="fk_cost_lot_source_tx_id_transaction"),
        # Una compra abre exactamente un lote. Un segundo lote para la misma
        # compra significa que la reconstruccion corrio dos veces sin limpiar.
        sa.UniqueConstraint("source_tx_id", name="uq_cost_lot_source_tx_id"),
        sa.CheckConstraint("quantity_open >= 0", name="ck_cost_lot_quantity_open_no_negativa"),
        sa.CheckConstraint("quantity_open <= quantity_original",
                           name="ck_cost_lot_quantity_open_no_excede_original"),
    )
    op.create_index("ix_cost_lot_user_id", "cost_lot", ["user_id"])
    op.create_index("ix_cost_lot_portfolio_asset_acquired", "cost_lot",
                    ["portfolio_id", "asset_id", "acquired_at"])

    # Sin realized_pnl a proposito: sobre el historico real, el mismo consumo
    # de lotes da 477.475 ARS por costo promedio y 575.975 por FIFO. Una sola
    # columna no puede guardar los dos, y guardarla sin decir de que metodo es
    # convierte un dato ambiguo en un dato aparentemente confiable.
    op.create_table(
        "lot_consumption",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("sell_tx_id", UUID_T, nullable=False),
        sa.Column("cost_lot_id", UUID_T, nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["sell_tx_id"], ["transaction.id"], ondelete="CASCADE",
                                name="fk_lot_consumption_sell_tx_id_transaction"),
        sa.ForeignKeyConstraint(["cost_lot_id"], ["cost_lot.id"], ondelete="CASCADE",
                                name="fk_lot_consumption_cost_lot_id_cost_lot"),
        sa.UniqueConstraint("sell_tx_id", "cost_lot_id", name="uq_lot_consumption_sell_tx_id"),
        sa.CheckConstraint("quantity > 0", name="ck_lot_consumption_quantity_positiva"),
    )
    op.create_index("ix_lot_consumption_sell_tx_id", "lot_consumption", ["sell_tx_id"])
    op.create_index("ix_lot_consumption_cost_lot_id", "lot_consumption", ["cost_lot_id"])

    # Sin current_price, current_value ni unrealized_pnl: solo lo que se
    # deriva de operaciones. El valor actual se resuelve al consultar, contra
    # la ultima cotizacion valida y con su as_of.
    op.create_table(
        "position_cache",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("user_id", UUID_T, nullable=False),
        sa.Column("portfolio_id", UUID_T, nullable=False),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False),
        sa.Column("average_cost", PRICE),
        sa.Column("open_cost_basis", AMOUNT, nullable=False),
        sa.Column("realized_pnl", AMOUNT, nullable=False, server_default="0"),
        sa.Column("cost_method", sa.String(8), nullable=False, server_default="WAC"),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("last_transaction_at", sa.DateTime(timezone=True)),
        sa.Column("computed_at", sa.DateTime(timezone=True)),
        sa.Column("computed_through", sa.Date()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_account.id"], ondelete="CASCADE",
                                name="fk_position_cache_user_id_user_account"),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolio.id"], ondelete="CASCADE",
                                name="fk_position_cache_portfolio_id_portfolio"),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="RESTRICT",
                                name="fk_position_cache_asset_id_asset"),
        sa.UniqueConstraint("portfolio_id", "asset_id", name="uq_position_cache_portfolio_id"),
    )
    op.create_index("ix_position_cache_user_id", "position_cache", ["user_id"])

    op.execute(
        "UPDATE app_metadata SET value = '2', updated_at = now() "
        "WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'modelo financiero: activos, cuentas, "
        "operaciones y lotes', updated_at = now() WHERE key = 'schema_description'"
    )


def downgrade() -> None:
    # Orden inverso al de creacion: las dependientes primero.
    for tabla in (
        "position_cache",
        "lot_consumption",
        "cost_lot",
        "transaction",
        "portfolio",
        "account",
        "corporate_action",
        "cedear_ratio",
        "cedear_detail",
        "asset_identifier",
        "asset",
    ):
        op.drop_table(tabla)

    for name in ENUMS:
        op.execute(f"DROP TYPE IF EXISTS {name}")

    op.execute(
        "UPDATE app_metadata SET value = '1', updated_at = now() WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'usuarios, sesiones y auditoria', "
        "updated_at = now() WHERE key = 'schema_description'"
    )
