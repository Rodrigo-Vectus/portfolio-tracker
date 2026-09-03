"""Refresh tokens persistidos.

El refresh token no se guarda: se guarda su hash. Si alguien se lleva un
volcado de la base, no puede reconstruir sesiones activas.

Cada refresco **rota** el token y marca el anterior como reemplazado. Si un
token ya rotado vuelve a usarse, significa que alguien lo copio: se revoca la
cadena entera de esa sesion. Es el patron de deteccion de reuso.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Agrupa todos los tokens nacidos de un mismo login. Revocar la familia
    # cierra la sesion completa sin tocar las demas del mismo usuario.
    family_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))

    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(INET)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
