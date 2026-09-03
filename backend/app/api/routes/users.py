"""Consulta de usuarios.

Alcance deliberadamente chico en esta fase: sirve para comprobar que el
control por rol funciona de punta a punta. La administracion completa
(crear, modificar, desactivar, ver auditoria) es la Fase 7.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser
from app.db.session import get_session
from app.models import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut], summary="Listar usuarios (solo admin)")
async def list_users(
    _: AdminUser,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[UserOut]:
    result = await session.execute(select(User).order_by(User.created_at))
    return [UserOut.model_validate(u) for u in result.scalars().all()]
