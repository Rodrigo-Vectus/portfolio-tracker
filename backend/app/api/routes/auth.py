"""Endpoints de autenticacion."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, require_csrf
from app.core.config import get_settings
from app.core.csrf import CSRF_COOKIE_NAME, generate_csrf_token
from app.core.logging import get_logger
from app.core.security import create_access_token
from app.db.redis import get_redis
from app.db.session import get_session
from app.models import AuditAction
from app.schemas.auth import ChangePasswordRequest, LoginRequest, TokenResponse, UserOut
from app.services import audit, auth, rate_limit
from app.services.auth import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
log = get_logger("api.auth")

REFRESH_COOKIE_NAME = "pt_refresh"
# La cookie de refresh solo se manda a /api/auth: ningun otro endpoint la
# necesita, asi que reducir su alcance reduce la superficie expuesta.
REFRESH_COOKIE_PATH = "/api/auth"


def _set_session_cookies(
    response: Response, refresh_token: str, *, keep_csrf: str | None = None
) -> None:
    """Emite las cookies de sesion.

    El refresh **siempre** rota: es un secreto de un solo uso y su rotacion es
    lo que permite detectar un robo.

    El CSRF, en cambio, se conserva durante toda la sesion (`keep_csrf`). No es
    un secreto que se consuma: lo que lo protege es la politica de mismo
    origen, no su rareza, asi que rotarlo no agrega seguridad. Y si rota en
    cada refresco, cualquier cliente que lo lea una sola vez y lo guarde queda
    mandando un valor viejo, con lo que un pedido legitimo termina en 403.
    Solo se genera uno nuevo al iniciar sesion.
    """
    max_age = settings.refresh_token_days * 24 * 3600

    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=max_age,
        httponly=True,          # inaccesible desde JavaScript
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path=REFRESH_COOKIE_PATH,
    )
    # Contraparte legible: el cliente la copia al encabezado X-CSRF-Token.
    response.set_cookie(
        CSRF_COOKIE_NAME,
        keep_csrf or generate_csrf_token(),
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


@router.post("/login", response_model=TokenResponse, summary="Iniciar sesion")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> TokenResponse:
    ip = audit.client_ip(request)

    if await rate_limit.is_locked(redis, payload.email, ip):
        await audit.record(
            session,
            AuditAction.LOGIN_FAILED,
            details={"email": payload.email.lower(), "reason": "bloqueado por intentos"},
            request=request,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Demasiados intentos fallidos. Volve a probar en "
                f"{settings.login_lockout_minutes} minutos."
            ),
        )

    try:
        user = await auth.authenticate(session, payload.email, payload.password, request)
    except AuthError as exc:
        await rate_limit.register_failure(redis, payload.email, ip)
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=exc.message) from None

    await rate_limit.clear(redis, payload.email, ip)
    refresh_token = await auth.issue_refresh_token(session, user, request=request)
    await session.commit()
    await session.refresh(user)

    _set_session_cookies(response, refresh_token)
    log.info("auth.login", user_id=str(user.id), role=user.role)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(require_csrf)],
    summary="Renovar el access token",
)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> TokenResponse:
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="No hay sesion activa.")

    try:
        user, new_refresh = await auth.rotate_refresh_token(session, raw, request)
    except AuthError as exc:
        await session.commit()
        _clear_session_cookies(response)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=exc.message) from None

    await session.commit()
    _set_session_cookies(
        response, new_refresh, keep_csrf=request.cookies.get(CSRF_COOKIE_NAME)
    )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.access_token_minutes * 60,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
    summary="Cerrar sesion",
)
async def logout(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw:
        user_id = await auth.revoke_refresh_token(session, raw)
        if user_id:
            await audit.record(session, AuditAction.LOGOUT, user_id=user_id, request=request)
        await session.commit()
    _clear_session_cookies(response)


@router.get("/me", response_model=UserOut, summary="Usuario autenticado")
async def me(user: CurrentUser) -> UserOut:
    # Usa CurrentUser y no ActiveUser a proposito: alguien obligado a cambiar
    # la contrasena tiene que poder ver quien es mientras lo hace.
    return UserOut.model_validate(user)


@router.post(
    "/change-password",
    response_model=UserOut,
    dependencies=[Depends(require_csrf)],
    summary="Cambiar la contrasena",
)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserOut:
    try:
        await auth.change_password(
            session, user, payload.current_password, payload.new_password, request
        )
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from None

    # El cambio revoca todas las sesiones, incluida esta. Se emite una nueva
    # para no expulsar a quien acaba de cambiar su clave correctamente.
    new_refresh = await auth.issue_refresh_token(session, user, request=request)
    await session.commit()
    await session.refresh(user)

    _set_session_cookies(
        response, new_refresh, keep_csrf=request.cookies.get(CSRF_COOKIE_NAME)
    )
    return UserOut.model_validate(user)
