"""Agrega BOND al enum de tipos de activo.

Revision ID: 0006_bond
Revises: 0005_market_data
Create Date: 2026-09-06

El catalogo solo contemplaba CEDEAR, CRYPTO y CASH. Los boletos reales del
broker muestran operaciones sobre AL30 y AL30D, bonos soberanos, que no entran
en ninguna de las tres.

AL30D ademas cotiza en dolares con IVA al 0%, mientras AL30 cotiza en pesos.
Es el caso que `price_currency` y `settlement_currency` se separaron para
soportar y que hasta ahora nunca se habia ejercitado.

Mismo patron que 0004: ADD VALUE necesita COMMIT explicito, y el downgrade
recrea el tipo en vez de quedar vacio.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006_bond"
down_revision: Union[str, None] = "0005_market_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ORIGINALES = ("CEDEAR", "CRYPTO", "CASH")


def upgrade() -> None:
    op.execute("COMMIT")
    op.execute("ALTER TYPE asset_type ADD VALUE IF NOT EXISTS 'BOND'")


def downgrade() -> None:
    # Revertir con activos de tipo BOND cargados los borraria en silencio, y
    # un activo referenciado por operaciones no se puede borrar sin romper el
    # libro. Se aborta con un mensaje claro.
    op.execute(
        """
        DO $$
        DECLARE n integer;
        BEGIN
            SELECT count(*) INTO n FROM asset WHERE asset_type::text = 'BOND';
            IF n > 0 THEN
                RAISE EXCEPTION
                  'Hay % activos de tipo BOND. Revertir los dejaria sin tipo '
                  'valido y pueden tener operaciones asociadas.', n;
            END IF;
        END $$;
        """
    )
    lista = ", ".join(f"'{v}'" for v in ORIGINALES)
    op.execute(f"CREATE TYPE asset_type_old AS ENUM ({lista})")
    op.execute(
        "ALTER TABLE asset ALTER COLUMN asset_type TYPE asset_type_old "
        "USING asset_type::text::asset_type_old"
    )
    op.execute("DROP TYPE asset_type")
    op.execute("ALTER TYPE asset_type_old RENAME TO asset_type")
