"""Catalogo de activos, cuentas y portfolios.

Regla de aislamiento que gobierna todo este modulo: **el filtro va por el
usuario autenticado, nunca por un identificador que venga en la peticion**. Un
recurso ajeno tiene que ser indistinguible de uno inexistente, asi que se
devuelve 404 y no 403: un 403 confirmaria que el recurso existe, y eso ya es
informacion.

El catalogo de activos es la excepcion y es deliberada: es compartido. Que
AAPL exista como CEDEAR en BYMA no es informacion privada de nadie. Lo privado
son las cuentas, los portfolios y las operaciones.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, require_csrf
from app.db.session import get_session
from app.models import Account, Asset, Portfolio
from app.schemas.finance import (
    AccountIn,
    AccountOut,
    AssetIn,
    AssetOut,
    PortfolioIn,
    PortfolioOut,
)

router = APIRouter(tags=["portfolio"])

Session = Annotated[AsyncSession, Depends(get_session)]


# --------------------------------------------------------------------- activos


@router.get("/assets", response_model=list[AssetOut], summary="Listar activos")
async def list_assets(_: ActiveUser, session: Session) -> list[Asset]:
    result = await session.execute(
        select(Asset).where(Asset.is_active).order_by(Asset.symbol)
    )
    return list(result.scalars().all())


@router.post(
    "/assets",
    response_model=AssetOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Dar de alta un activo",
)
async def create_asset(payload: AssetIn, _: ActiveUser, session: Session) -> Asset:
    asset = Asset(
        symbol=payload.symbol.strip().upper(),
        name=payload.name.strip(),
        asset_type=payload.asset_type,
        currency=payload.currency.strip().upper(),
        market=payload.market.strip().upper() if payload.market else None,
        sector=payload.sector,
        display_precision=payload.display_precision,
    )
    session.add(asset)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        # La clave natural es (symbol, market, asset_type): AAPL como CEDEAR y
        # AAPL como accion estadounidense son activos distintos.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Ya existe un activo con ese simbolo, mercado y tipo.",
        ) from None
    await session.refresh(asset)
    return asset


# --------------------------------------------------------------------- cuentas


@router.get("/accounts", response_model=list[AccountOut], summary="Listar cuentas")
async def list_accounts(user: ActiveUser, session: Session) -> list[Account]:
    result = await session.execute(
        select(Account).where(Account.user_id == user.id).order_by(Account.name)
    )
    return list(result.scalars().all())


@router.post(
    "/accounts",
    response_model=AccountOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Dar de alta una cuenta",
)
async def create_account(
    payload: AccountIn, user: ActiveUser, session: Session
) -> Account:
    account = Account(
        user_id=user.id,
        name=payload.name.strip(),
        account_type=payload.account_type,
        country=payload.country,
        default_currency=payload.default_currency.strip().upper(),
    )
    session.add(account)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Ya tenes una cuenta con ese nombre."
        ) from None
    await session.refresh(account)
    return account


# ------------------------------------------------------------------ portfolios


@router.get(
    "/portfolios", response_model=list[PortfolioOut], summary="Listar portfolios"
)
async def list_portfolios(user: ActiveUser, session: Session) -> list[Portfolio]:
    result = await session.execute(
        select(Portfolio)
        .where(Portfolio.user_id == user.id)
        .order_by(Portfolio.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/portfolios",
    response_model=PortfolioOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Crear un portfolio",
)
async def create_portfolio(
    payload: PortfolioIn, user: ActiveUser, session: Session
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user.id,
        name=payload.name.strip(),
        base_currency=payload.base_currency.strip().upper(),
        is_default=payload.is_default,
    )
    session.add(portfolio)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="Ya tenes un portfolio con ese nombre."
        ) from None
    await session.refresh(portfolio)
    return portfolio
