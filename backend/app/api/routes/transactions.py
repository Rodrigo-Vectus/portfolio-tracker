"""Operaciones y posiciones.

El recalculo de posiciones es **sincronico**: la operacion, sus lotes y su
entrada de auditoria entran en la misma transaccion de base o no entra
ninguna. Delegar el recalculo al worker haria mas rapida el alta, pero
`GET /positions` podria devolver un numero viejo durante unos segundos sin
decirlo, y presentar un dato desactualizado como actual es exactamente el
error que origino este proyecto.

Con el volumen real (73 operaciones) el costo es imperceptible. Si algun dia
deja de serlo, la salida es mover el recalculo al worker **y marcar el dato
con su `as_of`**, no dejarlo en silencio.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, require_csrf
from app.core.timezones import fecha_de_rueda
from app.db.session import get_session
from app.models import Asset, PositionCache, Portfolio, Transaction, TransactionStatus
from app.schemas.finance import (
    PositionOut,
    TransactionIn,
    TransactionOut,
    TransactionVoidIn,
)
from app.services import transactions as tx_service
from app.services.transactions import TransactionServiceError

router = APIRouter(tags=["operaciones"])

Session = Annotated[AsyncSession, Depends(get_session)]

NO_ENCONTRADO = HTTPException(status.HTTP_404_NOT_FOUND, detail="No encontrado.")


async def _portfolio_propio(
    session: AsyncSession, user_id: UUID, portfolio_id: UUID
) -> Portfolio:
    """Devuelve el portfolio solo si es del usuario autenticado.

    El 404 en lugar del 403 es deliberado: un 403 confirmaria que el portfolio
    existe y solo no es tuyo, y eso permite enumerar recursos ajenos probando
    identificadores.
    """
    result = await session.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == user_id
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise NO_ENCONTRADO
    return portfolio


@router.get(
    "/transactions",
    response_model=list[TransactionOut],
    summary="Listar operaciones de un portfolio",
)
async def list_transactions(
    portfolio_id: UUID,
    user: ActiveUser,
    session: Session,
    incluir_anuladas: bool = False,
) -> list[Transaction]:
    await _portfolio_propio(session, user.id, portfolio_id)

    query = select(Transaction).where(
        Transaction.portfolio_id == portfolio_id,
        # Redundante con el filtro del portfolio, y esta a proposito: si
        # alguna vez alguien cambia el filtro de arriba, este sigue de pie.
        Transaction.user_id == user.id,
    )
    if not incluir_anuladas:
        query = query.where(Transaction.status == TransactionStatus.ACTIVE)

    result = await session.execute(query.order_by(Transaction.executed_at))
    return list(result.scalars().all())


@router.post(
    "/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Registrar una operacion",
)
async def create_transaction(
    payload: TransactionIn,
    user: ActiveUser,
    session: Session,
    request: Request,
) -> Transaction:
    """Registra una operacion y recalcula la posicion en la misma transaccion.

    **Convencion de fechas.** Si `executed_at` no trae zona horaria se
    interpreta en la zona configurada del sistema (por defecto
    `America/Argentina/Buenos_Aires`), no en UTC. Asumir UTC correria una
    compra de las 22:30 al dia siguiente y su rueda saldria mal. Si el cliente
    manda un offset explicito, se respeta tal cual.

    `trade_date` se deriva del dia local, salvo que venga informado.
    """
    await _portfolio_propio(session, user.id, payload.portfolio_id)

    try:
        fila = await tx_service.registrar(
            session,
            user_id=user.id,
            portfolio_id=payload.portfolio_id,
            asset_id=payload.asset_id,
            account_id=payload.account_id,
            tx_type=payload.tx_type,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            price_currency=payload.price_currency,
            settlement_currency=payload.settlement_currency or payload.price_currency,
            commission=payload.commission,
            taxes=payload.taxes,
            fx_rate_used=payload.fx_rate_used,
            fx_source=payload.fx_source,
            executed_at=payload.executed_at,
            # fecha_de_rueda y no .date(): executed_at ya viene normalizado a
            # UTC, y una operacion de las 22:30 de Buenos Aires es 01:30 UTC
            # del dia siguiente. Tomar la fecha en UTC la mandaria a otra
            # rueda y correria todo el agrupamiento por dia.
            trade_date=payload.trade_date or fecha_de_rueda(payload.executed_at),
            notes=payload.notes,
            external_id=payload.external_id,
            request=request,
        )
    except TransactionServiceError as exc:
        # 422 y no 400: la peticion esta bien formada, lo que no cierra es la
        # regla de negocio. El mensaje explica cual, porque "venta invalida" no
        # le sirve a nadie para corregir la carga.
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    await session.commit()
    await session.refresh(fila)
    return fila


@router.post(
    "/transactions/{transaction_id}/void",
    response_model=TransactionOut,
    dependencies=[Depends(require_csrf)],
    summary="Anular una operacion",
)
async def void_transaction(
    transaction_id: UUID,
    payload: TransactionVoidIn,
    user: ActiveUser,
    session: Session,
    request: Request,
) -> Transaction:
    """Anula, nunca borra (D13).

    Puede fallar legitimamente: anular una compra sobre la que despues se
    vendio dejaria una venta descubierta. En ese caso no se anula nada y se
    explica por que, en vez de dejar el libro con una posicion imposible.
    """
    try:
        fila = await tx_service.anular(
            session,
            user_id=user.id,
            transaction_id=transaction_id,
            motivo=payload.motivo,
            request=request,
        )
    except TransactionServiceError as exc:
        await session.rollback()
        mensaje = str(exc)
        if mensaje == "La operacion no existe.":
            raise NO_ENCONTRADO from None
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=mensaje
        ) from None

    await session.commit()
    await session.refresh(fila)
    return fila


@router.get(
    "/positions",
    response_model=list[PositionOut],
    summary="Posiciones de un portfolio",
)
async def list_positions(
    portfolio_id: UUID, user: ActiveUser, session: Session
) -> list[PositionOut]:
    """Posiciones derivadas del libro.

    Sin valor de mercado: en esta fase no hay cotizaciones y no se inventa
    ninguna. La valuacion llega en la Fase 4 con su `as_of` y su fuente.
    """
    await _portfolio_propio(session, user.id, portfolio_id)

    result = await session.execute(
        select(PositionCache, Asset)
        .join(Asset, Asset.id == PositionCache.asset_id)
        .where(
            PositionCache.portfolio_id == portfolio_id,
            PositionCache.user_id == user.id,
        )
        .order_by(Asset.symbol)
    )

    return [
        PositionOut(
            asset_id=pos.asset_id,
            symbol=asset.symbol,
            asset_type=asset.asset_type,
            quantity=pos.quantity,
            average_cost=pos.average_cost,
            open_cost_basis=pos.open_cost_basis,
            realized_pnl=pos.realized_pnl,
            cost_method=pos.cost_method,
            currency=pos.currency,
            last_transaction_at=pos.last_transaction_at,
            computed_at=pos.computed_at,
        )
        for pos, asset in result.all()
    ]
