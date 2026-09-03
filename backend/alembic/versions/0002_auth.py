"""Usuarios, refresh tokens y bitacora de auditoria.

Revision ID: 0002_auth
Revises: 0001_baseline
Create Date: 2026-09-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_auth"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_role = postgresql.ENUM("ADMIN", "USER", name="user_role", create_type=False)
    user_role.create(op.get_bind(), checkfirst=True)

    audit_action = postgresql.ENUM(
        "LOGIN_SUCCESS", "LOGIN_FAILED", "LOGOUT", "TOKEN_REFRESHED",
        "TOKEN_REUSE_DETECTED", "PASSWORD_CHANGED", "USER_CREATED",
        "USER_UPDATED", "USER_DEACTIVATED", "USER_ACTIVATED",
        name="audit_action", create_type=False,
    )
    audit_action.create(op.get_bind(), checkfirst=True)

    # "user" es palabra reservada en PostgreSQL: la tabla se llama user_account.
    op.create_table(
        "user_account",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("tokens_valid_from", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_user_account_email", "user_account", ["email"], unique=True)

    op.create_table(
        "refresh_token",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by", postgresql.UUID(as_uuid=True)),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_account.id"],
            name="fk_refresh_token_user_id_user_account", ondelete="CASCADE",
        ),
    )
    op.create_index("ix_refresh_token_token_hash", "refresh_token", ["token_hash"], unique=True)
    op.create_index("ix_refresh_token_user_id", "refresh_token", ["user_id"])
    op.create_index("ix_refresh_token_family_id", "refresh_token", ["family_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("entity_type", sa.String(64)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("ip_address", postgresql.INET()),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        # SET NULL, no CASCADE: borrar un usuario no debe borrar su rastro.
        sa.ForeignKeyConstraint(
            ["user_id"], ["user_account.id"],
            name="fk_audit_log_user_id_user_account", ondelete="SET NULL",
        ),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.execute(
        "UPDATE app_metadata SET value = '1', updated_at = now() WHERE key = 'schema_phase'"
    )
    op.execute(
        "UPDATE app_metadata SET value = 'usuarios, sesiones y auditoria', "
        "updated_at = now() WHERE key = 'schema_description'"
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("refresh_token")
    op.drop_table("user_account")
    op.execute("DROP TYPE IF EXISTS audit_action")
    op.execute("DROP TYPE IF EXISTS user_role")
    op.execute(
        "UPDATE app_metadata SET value = '0', updated_at = now() WHERE key = 'schema_phase'"
    )
