"""Baseline del esquema.

Crea unicamente `app_metadata`, una tabla de infraestructura donde el sistema
deja constancia de en que fase esta el esquema y cuando se inicializo. No es
logica de negocio: sirve para verificar de punta a punta que la cadena de
migraciones funciona antes de escribir el primer modelo real (Fase 2).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_metadata",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.bulk_insert(
        sa.table(
            "app_metadata",
            sa.column("key", sa.String),
            sa.column("value", sa.Text),
        ),
        [
            {"key": "schema_phase", "value": "0"},
            {"key": "schema_description", "value": "baseline — sin modelos de negocio"},
        ],
    )


def downgrade() -> None:
    op.drop_table("app_metadata")
