"""Cotizaciones, tipo de cambio y bitacora de proveedores.

Revision ID: 0005_market_data
Revises: 0004_audit_tx
Create Date: 2026-09-04

Tres tablas. Ningun enum nuevo: `rate_type` y `status` van como texto a
proposito, para que agregar una serie de FX o un estado de proveedor no
requiera una migracion.

Nota sobre `price_quote.quoted_at` NULLABLE: es la unica forma honesta de
modelar el dato que devuelve el unico proveedor gratuito de CEDEARs, que no
informa cuando se cotizo. Ponerlo NOT NULL obligaria a rellenarlo con
`fetched_at`, y eso convertiria "cuando lo pedimos" en "cuando lo dijo el
mercado", que es precisamente el error que origino este proyecto.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_market_data"
down_revision: Union[str, None] = "0004_audit_tx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PRICE = sa.Numeric(28, 10)
RATE = sa.Numeric(28, 10)
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
        "price_quote",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("asset_id", UUID_T, nullable=False),
        sa.Column("price", PRICE, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        # NULL cuando el proveedor no lo informa. Ver nota del docstring.
        sa.Column("quoted_at", sa.DateTime(timezone=True)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_at", sa.DateTime(timezone=True)),
        sa.Column("extra", postgresql.JSONB()),
        *_timestamps(),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], ondelete="CASCADE",
                                name="fk_price_quote_asset_id_asset"),
        # Una fila por activo y fuente: permite comparar proveedores y notar
        # cuando uno se queda pegado mientras el otro se mueve.
        sa.UniqueConstraint("asset_id", "source", name="uq_price_quote_asset_id"),
        sa.CheckConstraint("price > 0", name="ck_price_quote_precio_positivo"),
    )
    op.create_index("ix_price_quote_asset_id", "price_quote", ["asset_id"])
    op.create_index("ix_price_quote_fetched_at", "price_quote", ["fetched_at"])

    op.create_table(
        "fx_rate",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("base_currency", sa.String(8), nullable=False),
        sa.Column("quote_currency", sa.String(8), nullable=False),
        sa.Column("rate_type", sa.String(16), nullable=False),
        sa.Column("rate", RATE, nullable=False),
        sa.Column("quoted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        *_timestamps(),
        # Deduplicacion: el worker puede pedir la misma cotizacion varias veces
        # y no debe multiplicar filas de la misma marca temporal.
        sa.UniqueConstraint(
            "base_currency", "quote_currency", "rate_type", "quoted_at",
            name="uq_fx_rate_base_currency",
        ),
        sa.CheckConstraint("rate > 0", name="ck_fx_rate_positivo"),
    )
    op.create_index("ix_fx_rate_trade_date", "fx_rate", ["trade_date"])
    op.create_index("ix_fx_rate_tipo_fecha", "fx_rate", ["rate_type", "quoted_at"])

    op.create_table(
        "provider_log",
        sa.Column("id", UUID_T, primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("error_message", sa.Text()),
        sa.Column("assets_requested", sa.Integer()),
        sa.Column("assets_ok", sa.Integer()),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_provider_log_created_at", "provider_log", ["created_at"])
    op.create_index(
        "ix_provider_log_provider_created", "provider_log", ["provider", "created_at"]
    )

    op.execute(
        "UPDATE app_metadata SET value = '3', updated_at = now() "
        "WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'market data: cotizaciones, tipo de "
        "cambio y bitacora de proveedores', updated_at = now() "
        "WHERE key = 'schema_description'"
    )


def downgrade() -> None:
    op.drop_table("provider_log")
    op.drop_table("fx_rate")
    op.drop_table("price_quote")

    op.execute(
        "UPDATE app_metadata SET value = '2', updated_at = now() "
        "WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'modelo financiero: activos, cuentas, "
        "operaciones y lotes', updated_at = now() WHERE key = 'schema_description'"
    )
