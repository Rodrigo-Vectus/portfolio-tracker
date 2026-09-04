"""Acciones de auditoria de operaciones.

Revision ID: 0004_audit_tx
Revises: 0003_finance
Create Date: 2026-09-04

Agrega TRANSACTION_CREATED, TRANSACTION_VOIDED y POSITIONS_REBUILT al enum
`audit_action`. Sin estos valores, escribir una entrada de bitacoria por una
operacion hace que PostgreSQL rechace el INSERT y **aborte la transaccion
completa**, igual que pasaba con la columna INET y un X-Forwarded-For
invalido: el fallo no aparece donde se origina.

Nota sobre el downgrade. PostgreSQL no permite quitar un valor de un enum:
hay que recrear el tipo entero, reapuntar la columna y borrar el viejo. Se
hace asi en vez de dejar el downgrade vacio, porque un downgrade que no
revierte no sirve como red de seguridad.

Las filas que usen alguno de los valores nuevos bloquean el downgrade a
proposito: borrarlas en silencio seria destruir auditoria, y la bitacora no
se edita ni se borra desde la aplicacion.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0004_audit_tx"
down_revision: Union[str, None] = "0003_finance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NUEVOS = ("TRANSACTION_CREATED", "TRANSACTION_VOIDED", "POSITIONS_REBUILT")

ORIGINALES = (
    "LOGIN_SUCCESS", "LOGIN_FAILED", "LOGOUT", "TOKEN_REFRESHED",
    "TOKEN_REUSE_DETECTED", "PASSWORD_CHANGED", "USER_CREATED",
    "USER_UPDATED", "USER_DEACTIVATED", "USER_ACTIVATED",
)


def upgrade() -> None:
    # ADD VALUE no corre dentro de un bloque transaccional en PostgreSQL
    # anterior a la 12; en la 16 si, pero COMMIT primero lo hace explicito y
    # funciona en ambas.
    op.execute("COMMIT")
    for valor in NUEVOS:
        op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{valor}'")


def downgrade() -> None:
    usados = ", ".join(f"'{v}'" for v in NUEVOS)
    op.execute(
        f"""
        DO $$
        DECLARE n integer;
        BEGIN
            SELECT count(*) INTO n FROM audit_log
             WHERE action::text IN ({usados});
            IF n > 0 THEN
                RAISE EXCEPTION
                  'Hay % entradas de auditoria con acciones de operaciones. '
                  'Revertir borraria auditoria y la bitacora no se borra.', n;
            END IF;
        END $$;
        """
    )

    lista = ", ".join(f"'{v}'" for v in ORIGINALES)
    op.execute(f"CREATE TYPE audit_action_old AS ENUM ({lista})")
    op.execute(
        "ALTER TABLE audit_log ALTER COLUMN action TYPE audit_action_old "
        "USING action::text::audit_action_old"
    )
    op.execute("DROP TYPE audit_action")
    op.execute("ALTER TYPE audit_action_old RENAME TO audit_action")
