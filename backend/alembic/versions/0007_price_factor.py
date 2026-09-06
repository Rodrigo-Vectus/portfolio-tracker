"""Factor de precio del activo.

Revision ID: 0007_price_factor
Revises: 0006_bond
Create Date: 2026-09-06

Los bonos cotizan **por lamina de 100 nominales**, no por unidad. Un boleto
real de AL30 informa precio 10.392 y bruto 10.392 sobre 100 nominales: si el
costo se calcula como cantidad x precio, da 1.039.200, cien veces de mas.

El error no se notaria: el numero queda grande pero plausible, que es
exactamente como se propaga en silencio un error de calculo.

    costo = cantidad x precio / price_factor

`price_factor` es 1 para todo lo demas, asi que el calculo no cambia para
CEDEARs, cripto ni efectivo.

Se modela en el activo y no en la operacion porque es una propiedad del
instrumento: todas las operaciones de AL30 usan la misma convencion.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_price_factor"
down_revision: Union[str, None] = "0006_bond"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset",
        sa.Column(
            "price_factor",
            sa.Numeric(28, 10),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_check_constraint(
        "ck_asset_price_factor_positivo", "asset", "price_factor > 0"
    )
    # Los bonos que ya esten cargados pasan a 100. Es la convencion del
    # mercado, no una suposicion: un bono cotiza por lamina.
    op.execute("UPDATE asset SET price_factor = 100 WHERE asset_type = 'BOND'")


def downgrade() -> None:
    op.drop_constraint("ck_asset_price_factor_positivo", "asset", type_="check")
    op.drop_column("asset", "price_factor")
