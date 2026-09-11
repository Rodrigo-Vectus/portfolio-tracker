"""Preferencias de visualizacion del usuario.

Dos endpoints y una regla: **lo que el usuario no eligio no se guarda**. Una
preferencia ausente viaja en `null`, que aca significa "cada activo en su
propia moneda".

No se hereda del `DEFAULT_DISPLAY_CURRENCY` del `.env`. D55 dice que la
conversion a moneda dura se pide de forma explicita, y hacer que una
preferencia vacia la active por detras seria justo lo contrario.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, require_csrf
from app.db.session import get_session
from app.models import UserSettings
from app.schemas.settings import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])

Session = Annotated[AsyncSession, Depends(get_session)]

# La unica moneda dura en la que el sistema sabe valuar. La serie de FX es
# USD/ARS y la moneda de salida de la conversion esta fija: aceptar cualquier
# codigo dejaria guardar una preferencia que despues nadie puede cumplir.
# Es la misma lista que valida `hard_currency` en /positions.
MONEDAS_DE_VISUALIZACION = ("USD",)


async def _fila(session: AsyncSession, user_id) -> UserSettings | None:
    resultado = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    return resultado.scalar_one_or_none()


def _salida(fila: UserSettings | None) -> SettingsOut:
    return SettingsOut(display_currency=fila.display_currency if fila else None)


@router.get("", response_model=SettingsOut, summary="Preferencias del usuario")
async def get_user_settings(user: ActiveUser, session: Session) -> SettingsOut:
    """Devuelve la preferencia elegida.

    Un `display_currency` en `null` no es un error ni un cero: significa que
    la cartera se muestra con cada activo en su propia moneda.
    """
    return _salida(await _fila(session, user.id))


@router.patch(
    "",
    response_model=SettingsOut,
    dependencies=[Depends(require_csrf)],
    summary="Cambiar preferencias",
)
async def update_user_settings(
    payload: SettingsIn, user: ActiveUser, session: Session
) -> SettingsOut:
    """Guarda la preferencia. `null` vuelve a la moneda original.

    La fila se crea recien cuando hay algo que guardar: un usuario que nunca
    toco nada no necesita ocupar una.
    """
    if (
        payload.display_currency is not None
        and payload.display_currency.upper() not in MONEDAS_DE_VISUALIZACION
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                f"'{payload.display_currency}' no es una moneda de "
                f"visualizacion valida. Las validas son: "
                f"{', '.join(MONEDAS_DE_VISUALIZACION)}."
            ),
        )

    elegida = (
        payload.display_currency.upper()
        if payload.display_currency is not None
        else None
    )

    fila = await _fila(session, user.id)
    if fila is None:
        fila = UserSettings(user_id=user.id, display_currency=elegida)
        session.add(fila)
    else:
        fila.display_currency = elegida

    await session.commit()
    await session.refresh(fila)
    return _salida(fila)
