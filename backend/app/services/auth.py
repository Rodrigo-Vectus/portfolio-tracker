"""Servicio de autenticacion: login, rotacion de refresh y cambio de clave."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)
from app.models import AuditAction, RefreshToken, User
from app.services import audit

settings = get_settings()
log = get_logger("auth")


class AuthError(Exception):
    """Falla de autenticacion. El mensaje es el que ve el usuario."""

    def __init__(self, message: str, code: str = "invalid_credentials") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def authenticate(
    session: AsyncSession, email: str, password: str, request: Request | None = None
) -> User:
    """Valida credenciales.

    El mensaje de error es el mismo para email inexistente, clave incorrecta y
    cuenta desactivada. Distinguirlos le diria a un atacante que direcciones
    estan registradas.
    """
    user = await get_user_by_email(session, email)

    if user is None:
        # Se calcula igual un hash para que el tiempo de respuesta no delate
        # si el email existe.
        hash_password(password)
        await audit.record(
            session,
            AuditAction.LOGIN_FAILED,
            details={"email": email.strip().lower(), "reason": "usuario inexistente"},
            request=request,
        )
        raise AuthError("Email o contrasena incorrectos.")

    if not verify_password(password, user.password_hash):
        await audit.record(
            session,
            AuditAction.LOGIN_FAILED,
            user_id=user.id,
            details={"reason": "contrasena incorrecta"},
            request=request,
        )
        raise AuthError("Email o contrasena incorrectos.")

    if not user.is_active:
        await audit.record(
            session,
            AuditAction.LOGIN_FAILED,
            user_id=user.id,
            details={"reason": "cuenta desactivada"},
            request=request,
        )
        raise AuthError("Email o contrasena incorrectos.")

    # Oportunidad de endurecer el hash sin molestar al usuario.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = datetime.now(UTC)
    await audit.record(session, AuditAction.LOGIN_SUCCESS, user_id=user.id, request=request)
    return user


async def issue_refresh_token(
    session: AsyncSession,
    user: User,
    *,
    family_id: UUID | None = None,
    request: Request | None = None,
) -> str:
    """Crea un refresh token y devuelve el valor en claro (solo se ve aca)."""
    token, token_hash = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            family_id=family_id or uuid4(),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
            user_agent=audit.client_user_agent(request),
            ip_address=audit.client_ip(request),
        )
    )
    return token


async def rotate_refresh_token(
    session: AsyncSession, raw_token: str, request: Request | None = None
) -> tuple[User, str]:
    """Canjea un refresh por uno nuevo.

    Si el token presentado ya habia sido rotado o revocado, se asume que fue
    robado y se revoca **toda la familia**: el atacante y el usuario legitimo
    quedan afuera, y el usuario tiene que volver a ingresar su clave. Es el
    comportamiento correcto: preferimos una molestia a una sesion secuestrada.
    """
    token_hash = hash_refresh_token(raw_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()

    if stored is None:
        raise AuthError("Sesion invalida.", code="invalid_session")

    now = datetime.now(UTC)

    if stored.revoked_at is not None or stored.replaced_by is not None:
        await _revoke_family(session, stored.family_id)
        await audit.record(
            session,
            AuditAction.TOKEN_REUSE_DETECTED,
            user_id=stored.user_id,
            details={"family_id": str(stored.family_id)},
            request=request,
        )
        log.warning("auth.token_reuse", user_id=str(stored.user_id))
        raise AuthError("Sesion invalida. Volve a ingresar.", code="token_reuse")

    if stored.expires_at <= now:
        raise AuthError("La sesion expiro.", code="session_expired")

    user = await session.get(User, stored.user_id)
    if user is None or not user.is_active:
        await _revoke_family(session, stored.family_id)
        raise AuthError("Sesion invalida.", code="invalid_session")

    # Un cambio de contrasena invalida los tokens anteriores.
    if user.tokens_valid_from and stored.created_at < user.tokens_valid_from:
        await _revoke_family(session, stored.family_id)
        raise AuthError("Sesion invalida. Volve a ingresar.", code="invalid_session")

    new_token, new_hash = generate_refresh_token()
    new_row = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        family_id=stored.family_id,
        expires_at=now + timedelta(days=settings.refresh_token_days),
        user_agent=audit.client_user_agent(request),
        ip_address=audit.client_ip(request),
    )
    session.add(new_row)
    await session.flush()

    stored.replaced_by = new_row.id
    stored.revoked_at = now

    await audit.record(session, AuditAction.TOKEN_REFRESHED, user_id=user.id, request=request)
    return user, new_token


async def revoke_refresh_token(session: AsyncSession, raw_token: str) -> UUID | None:
    """Cierra la sesion: revoca la familia completa del token presentado."""
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    stored = result.scalar_one_or_none()
    if stored is None:
        return None
    await _revoke_family(session, stored.family_id)
    return stored.user_id


async def _revoke_family(session: AsyncSession, family_id: UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def revoke_all_sessions(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


async def change_password(
    session: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
    request: Request | None = None,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise AuthError("La contrasena actual no es correcta.", code="wrong_current_password")

    if verify_password(new_password, user.password_hash):
        raise AuthError("La contrasena nueva tiene que ser distinta.", code="same_password")

    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    # Invalida todo lo emitido antes de este instante.
    user.tokens_valid_from = datetime.now(UTC)

    await revoke_all_sessions(session, user.id)
    await audit.record(session, AuditAction.PASSWORD_CHANGED, user_id=user.id, request=request)
