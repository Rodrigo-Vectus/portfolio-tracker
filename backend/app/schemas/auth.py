"""Contratos de entrada y salida de autenticacion."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole

MIN_PASSWORD_LENGTH = 10


def _validate_password_strength(value: str) -> str:
    """Regla minima: largo y variedad.

    Se prioriza el largo por sobre la exigencia de simbolos raros: una frase
    larga resiste mucho mejor que "P@ss1!" y la gente no necesita anotarla en
    un papel.
    """
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"La contrasena debe tener al menos {MIN_PASSWORD_LENGTH} caracteres.")
    if value.strip() != value:
        raise ValueError("La contrasena no puede empezar ni terminar con espacios.")
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("La contrasena debe combinar letras y numeros.")
    return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(max_length=256)

    @field_validator("new_password")
    @classmethod
    def strong(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    name: str
    role: UserRole
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None = None
    created_at: datetime


class TokenResponse(BaseModel):
    """El access token viaja en el cuerpo; el refresh va en cookie httpOnly.

    `expires_in` esta en segundos para que el cliente pueda programar el
    refresco silencioso antes de que venza.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
