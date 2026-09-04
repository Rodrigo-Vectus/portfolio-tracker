"""Alta y anulacion de operaciones.

Dos reglas gobiernan este modulo:

**Se valida contra el dominio antes de escribir.** Una operacion se construye
primero como objeto del dominio y se prueba contra el historial existente. Si
el motor la rechaza, no se toca la base. El orden inverso (escribir y despues
revisar) deja el libro sucio cuando algo falla a mitad de camino.

**Nada se borra (D13).** Corregir es anular con motivo y crear la operacion
nueva. Es la unica forma de poder reconstruir despues que se sabia en cada
momento, y de que una correccion quede auditada en vez de desaparecer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cost_basis import build_lots
from app.domain.ledger import InsufficientHoldings, LedgerError
from app.models import (
    Asset,
    AuditAction,
    Portfolio,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.services import audit
from app.services.mappers import to_domain
from app.services.positions import rebuild_asset

POSITION_TYPES = {TransactionType.BUY, TransactionType.SELL}


class TransactionServiceError(Exception):
    """Error de negocio al registrar o anular una operacion."""


async def _assert_owned_portfolio(
    session: AsyncSession, user_id: UUID, portfolio_id: UUID
) -> Portfolio:
    """Confirma que el portfolio es del usuario autenticado.

    El filtro va por `user_id` **y** por `portfolio_id`, no solo por el id que
    viene en la peticion. Un portfolio ajeno tiene que ser indistinguible de
    uno inexistente: por eso se devuelve el mismo error en los dos casos, y la
    capa HTTP lo traduce a 404. Un 403 confirmaria que el recurso existe.
    """
    result = await session.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == user_id
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise TransactionServiceError("El portfolio no existe.")
    return portfolio


async def _historial(
    session: AsyncSession, portfolio_id: UUID, asset_id: UUID
) -> list[Transaction]:
    """Operaciones ACTIVE de un activo, en orden cronologico."""
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset_id,
            Transaction.status == TransactionStatus.ACTIVE,
        )
        .order_by(Transaction.executed_at, Transaction.id)
    )
    return list(result.scalars().all())


async def registrar(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    asset_id: UUID | None,
    account_id: UUID | None,
    tx_type: TransactionType,
    quantity: Decimal,
    unit_price: Decimal,
    price_currency: str,
    settlement_currency: str,
    executed_at: datetime,
    trade_date,
    commission: Decimal = Decimal(0),
    taxes: Decimal = Decimal(0),
    fx_rate_used: Decimal | None = None,
    fx_source: str | None = None,
    notes: str | None = None,
    external_id: str | None = None,
    import_batch_id: UUID | None = None,
    request: Request | None = None,
) -> Transaction:
    """Registra una operacion, validandola antes de persistirla.

    No hace commit: se suma a la transaccion de base en curso, para que la
    operacion, sus lotes y su entrada de auditoria entren o no entren juntas.
    Una operacion registrada cuyos lotes no se escribieron es peor que un
    error: es un libro que discrepa consigo mismo.
    """
    await _assert_owned_portfolio(session, user_id, portfolio_id)

    if tx_type in POSITION_TYPES and asset_id is None:
        raise TransactionServiceError(
            f"Una operacion de tipo {tx_type.value} necesita un activo."
        )

    fila = Transaction(
        user_id=user_id,
        portfolio_id=portfolio_id,
        account_id=account_id,
        asset_id=asset_id,
        tx_type=tx_type,
        quantity=quantity,
        unit_price=unit_price,
        price_currency=price_currency.upper(),
        settlement_currency=settlement_currency.upper(),
        commission=commission,
        taxes=taxes,
        commission_currency=price_currency.upper() if commission else None,
        taxes_currency=price_currency.upper() if taxes else None,
        gross_amount=quantity * unit_price,
        net_amount=(
            quantity * unit_price + commission + taxes
            if tx_type is TransactionType.BUY
            else quantity * unit_price - commission - taxes
        ),
        fx_rate_used=fx_rate_used,
        fx_source=fx_source,
        executed_at=executed_at,
        trade_date=trade_date,
        notes=notes,
        external_id=external_id,
        import_batch_id=import_batch_id,
        status=TransactionStatus.ACTIVE,
        created_by=user_id,
    )

    if tx_type in POSITION_TYPES:
        asset = await session.get(Asset, asset_id)
        if asset is None:
            raise TransactionServiceError("El activo no existe.")

        # La validacion corre sobre el historial completo mas la operacion
        # nueva. Una venta valida hoy puede dejar de serlo si antes se anulo
        # una compra, asi que no alcanza con mirar la tenencia actual.
        historial = await _historial(session, portfolio_id, asset_id)
        candidato = [to_domain(f, symbol=asset.symbol) for f in historial]
        fila.id = fila.id or None
        session.add(fila)
        await session.flush()  # asigna el id sin cerrar la transaccion
        candidato.append(to_domain(fila, symbol=asset.symbol))

        try:
            build_lots(candidato)
        except InsufficientHoldings as exc:
            raise TransactionServiceError(str(exc)) from None
        except LedgerError as exc:
            raise TransactionServiceError(str(exc)) from None

        await rebuild_asset(session, user_id=user_id, portfolio_id=portfolio_id, asset=asset)
    else:
        session.add(fila)
        await session.flush()

    await audit.record(
        session,
        AuditAction.TRANSACTION_CREATED,
        user_id=user_id,
        entity_type="transaction",
        entity_id=str(fila.id),
        details={"tipo": tx_type.value, "cantidad": str(quantity)},
        request=request,
    )
    return fila


async def anular(
    session: AsyncSession,
    *,
    user_id: UUID,
    transaction_id: UUID,
    motivo: str,
    request: Request | None = None,
) -> Transaction:
    """Anula una operacion y recalcula todo lo que dependia de ella.

    El motivo es obligatorio y la base tambien lo exige con un CHECK: una
    anulacion sin motivo es un borrado con otro nombre.

    Anular puede volver invalido el historial posterior, por ejemplo si se
    anula una compra sobre la que despues se vendio. En ese caso la operacion
    falla entera y se explica por que, en vez de dejar una posicion negativa.
    """
    result = await session.execute(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        )
    )
    fila = result.scalar_one_or_none()
    if fila is None:
        raise TransactionServiceError("La operacion no existe.")
    if fila.status is TransactionStatus.VOIDED:
        raise TransactionServiceError("La operacion ya estaba anulada.")
    if not motivo or not motivo.strip():
        raise TransactionServiceError("Anular exige un motivo.")

    fila.status = TransactionStatus.VOIDED
    fila.voided_by = user_id
    fila.voided_at = datetime.now(UTC)
    fila.voided_reason = motivo.strip()[:255]
    await session.flush()

    if fila.tx_type in POSITION_TYPES and fila.asset_id is not None:
        asset = await session.get(Asset, fila.asset_id)
        historial = await _historial(session, fila.portfolio_id, fila.asset_id)
        try:
            build_lots([to_domain(f, symbol=asset.symbol) for f in historial])
        except InsufficientHoldings as exc:
            raise TransactionServiceError(
                f"No se puede anular: el historial posterior quedaria invalido. {exc}"
            ) from None
        await rebuild_asset(
            session, user_id=user_id, portfolio_id=fila.portfolio_id, asset=asset
        )

    await audit.record(
        session,
        AuditAction.TRANSACTION_VOIDED,
        user_id=user_id,
        entity_type="transaction",
        entity_id=str(fila.id),
        details={"motivo": fila.voided_reason},
        request=request,
    )
    return fila
