"""Dependencias compartidas de la API: usuario actual y control de rol."""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.csrf import verify_csrf
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise CREDENTIALS_ERROR

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR from None

    user = await session.get(User, payload["sub"])
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR

    # Un token emitido antes del ultimo cambio de contrasena no vale, aunque
    # todavia no haya expirado.
    if user.tokens_valid_from is not None:
        issued_at = payload.get("iat", 0)
        if issued_at < user.tokens_valid_from.timestamp():
            raise CREDENTIALS_ERROR

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_active_user(user: CurrentUser) -> User:
    """Usuario que ya completo el cambio de contrasena obligatorio.

    Mientras `must_change_password` este en True, el unico endpoint accesible
    es el de cambio de clave. Sin este corte, el admin sembrado podria operar
    indefinidamente con la contrasena del archivo `.env`.
    """
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenes que cambiar tu contrasena antes de continuar.",
            headers={"X-Password-Change-Required": "true"},
        )
    return user


ActiveUser = Annotated[User, Depends(get_active_user)]


async def require_admin(user: ActiveUser) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta seccion es solo para administradores.",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def require_csrf(request: Request) -> None:
    if not verify_csrf(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token CSRF invalido o ausente.",
        )
