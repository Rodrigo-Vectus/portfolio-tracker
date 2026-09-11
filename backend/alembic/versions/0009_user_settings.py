"""Preferencias de visualizacion por usuario.

Revision ID: 0009_user_settings
Revises: 0008_snapshots
Create Date: 2026-09-11

El selector de moneda de Portfolio funcionaba pero se olvidaba al recargar, y
no habia donde guardarlo: las preferencias existian solo a nivel de
instalacion, en el `.env`.

Se resuelve con una tabla y no con almacenamiento del navegador por dos
motivos. Uno, hay otras dos preferencias esperando el mismo lugar (metodo de
costo y fuente de tipo de cambio), y resolver una con el navegador y las otras
con una tabla dejaria dos mecanismos para lo mismo. Dos, el navegador no
acompana al usuario entre dispositivos.

`display_currency` es **nullable** y eso es la decision de la migracion: null
significa "no elegi nada" y entonces vale el default del `.env`. Copiar el
default en la fila lo congelaria, y el usuario que nunca toco nada se quedaria
con el valor viejo si manana cambia la configuracion.

Se crea con una sola columna. El metodo de costo y la fuente de FX estan
previstos pero no aprobados; agregarlos ahora seria implementar lo que todavia
no se decidio. Sumar una columna nullable despues es trivial.

**El downgrade borra las preferencias.** No hay nada derivado de ellas: son
elecciones de visualizacion, no datos financieros. Ningun numero cambia.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_user_settings"
down_revision: Union[str, None] = "0008_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # CASCADE: las preferencias de un usuario borrado no le sirven a nadie.
        # Es lo contrario de `audit_log`, que usa SET NULL porque el rastro de
        # lo que alguien hizo tiene que sobrevivir a la cuenta.
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_account.id"],
            name=op.f("fk_user_settings_user_id_user_account"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_settings")),
    )


def downgrade() -> None:
    op.drop_table("user_settings")
