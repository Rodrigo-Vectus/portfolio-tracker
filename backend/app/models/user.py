"""Usuario de la plataforma."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import UserRole
from app.models.mixins import TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "user_account"  # "user" es palabra reservada en PostgreSQL

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)

    # El email se guarda siempre en minusculas (lo normaliza el servicio).
    # Sin eso, "Rodrigo@..." y "rodrigo@..." serian dos cuentas distintas.
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True),
        default=UserRole.USER,
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Obliga a cambiar la contrasena en el primer ingreso. El admin sembrado
    # arranca en True: la clave del .env nunca debe quedar como definitiva.
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Momento a partir del cual todo token emitido antes queda invalidado.
    # Se actualiza al cambiar la contrasena o al desactivar la cuenta: asi un
    # access token robado deja de servir sin esperar a que expire.
    tokens_valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<User {self.email} {self.role}>"
