"""Saldo de caja: puente entre el libro persistido y el dominio.

Como el resto de lo derivado, el saldo **no se guarda**: se calcula al
consultar desde las operaciones. Guardarlo obligaría a mantenerlo sincronizado
en cada alta, anulación y corrección, y basta que falle un camino para que
discrepe del libro sin que nadie lo note.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.cash import SaldoDeCaja, calcular_saldo
from app.models import Asset, Transaction, TransactionStatus
from app.services.mappers import to_domain


async def saldo_de_portfolio(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    currency: str = "ARS",
) -> SaldoDeCaja:
    resultado = await session.execute(
        select(Transaction, Asset.symbol)
        .outerjoin(Asset, Asset.id == Transaction.asset_id)
        .where(
            Transaction.portfolio_id == portfolio_id,
            # Redundante con el filtro del portfolio, y a proposito.
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.ACTIVE,
        )
        .order_by(Transaction.executed_at, Transaction.id)
    )
    # Los movimientos de efectivo no tienen activo: el simbolo queda en CASH
    # para que el dominio pueda describirlos sin inventar un instrumento.
    dominio = [
        to_domain(fila, symbol=symbol or "CASH") for fila, symbol in resultado.all()
    ]
    return calcular_saldo(dominio, currency)
