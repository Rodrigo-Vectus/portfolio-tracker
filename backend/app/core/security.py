"""Primitivas de seguridad: hashing de contrasenas y firma de tokens.

Decisiones y por que:

- **Argon2id** para las contrasenas, no bcrypt. Es el ganador del Password
  Hashing Competition, resiste ataques con GPU mucho mejor y no tiene el
  limite de 72 bytes de bcrypt, que silenciosamente trunca contrasenas largas.

- **Access token corto (15 min) en memoria del navegador.** No se guarda en
  localStorage: cualquier script inyectado en la pagina puede leerlo de ahi.

- **Refresh token largo (7 dias) en cookie httpOnly.** JavaScript no puede
  leerla, asi que un XSS no se lleva la sesion. A cambio queda expuesta a
  CSRF, que se cubre con el token de doble envio (ver `csrf.py`).

- **Comparaciones en tiempo constante** donde se comparan secretos.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings

settings = get_settings()

_hasher = PasswordHasher(
    time_cost=3,        # iteraciones
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

ALGORITHM = "HS256"


# --------------------------------------------------------------------------
# Contrasenas
# --------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True si el hash quedo con parametros mas debiles que los actuales.

    Permite endurecer el costo de Argon2 con el tiempo: al proximo login
    valido, el hash se regenera sin que el usuario note nada.
    """
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, ValueError):
        return True


# --------------------------------------------------------------------------
# Access tokens (JWT)
# --------------------------------------------------------------------------

def create_access_token(user_id: UUID, role: str, issued_at: datetime | None = None) -> str:
    now = issued_at or datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Devuelve el payload o lanza jwt.PyJWTError. No captura: el llamador decide."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("tipo de token incorrecto")
    return payload


# --------------------------------------------------------------------------
# Refresh tokens (opacos, no JWT)
# --------------------------------------------------------------------------

def generate_refresh_token() -> tuple[str, str]:
    """Devuelve (token en claro, hash a persistir).

    El refresh es un valor aleatorio opaco, no un JWT: no necesita llevar
    informacion, y al ser verificable solo contra la base se puede revocar de
    inmediato. Un JWT revocado seguiria siendo criptograficamente valido.
    """
    token = secrets.token_urlsafe(48)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
