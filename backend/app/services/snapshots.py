"""Toma y consulta de snapshots diarios.

El snapshot de hoy se calcula con las posiciones y las cotizaciones actuales.
**No se puede reconstruir hacia atrás**: eso exigiría el precio de cada activo
en cada día pasado, y el sistema sólo guarda la última cotización de cada uno.
Los proveedores gratuitos disponibles no devuelven histórico.

La serie arranca el día que se empieza a tomar snapshots y crece hacia
adelante. Rellenar los días anteriores con el precio de hoy daría una línea
plana que parece historia y no lo es.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.market import Frescura
from app.domain.snapshot import Snapshot, construir_snapshot
from app.models import Asset, Portfolio
from app.models.market import PortfolioSnapshot, PriceBarDaily, PriceQuote
from app.services.cash import saldo_de_portfolio
from app.services.valuation import valuar_portfolio

log = get_logger("snapshots")
ZERO = Decimal(0)


async def guardar_cierres_del_dia(session: AsyncSession, fecha: date | None = None) -> int:
    """Copia la última cotización de cada activo a la serie diaria.

    Se ejecuta después del cierre de rueda. Si vuelve a correr el mismo día
    pisa el valor en vez de duplicarlo: el último precio del día es el cierre.
    """
    fecha = fecha or datetime.now(UTC).date()

    resultado = await session.execute(
        select(PriceQuote, Asset).join(Asset, Asset.id == PriceQuote.asset_id)
    )
    guardados = 0
    for quote, asset in resultado.all():
        await session.execute(
            insert(PriceBarDaily)
            .values(
                asset_id=asset.id,
                trade_date=fecha,
                close=quote.price,
                currency=quote.currency,
                source=quote.source,
                # Si el proveedor no informó la hora, el cierre hereda esa
                # limitación en vez de perderla al pasar a la serie.
                is_estimated=quote.quoted_at is None,
            )
            .on_conflict_do_update(
                constraint="uq_price_bar_daily_asset_id",
                set_={
                    "close": quote.price,
                    "is_estimated": quote.quoted_at is None,
                    "updated_at": datetime.now(UTC),
                },
            )
        )
        guardados += 1

    log.info("snapshots.cierres_guardados", fecha=str(fecha), activos=guardados)
    return guardados


async def tomar_snapshot(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    fecha: date | None = None,
) -> Snapshot:
    """Calcula y guarda la foto de hoy.

    Si vuelve a correr el mismo día, la pisa. El último cálculo del día es el
    que vale: si a media mañana faltaba una cotización y a la tarde llegó, el
    snapshot bueno es el de la tarde.
    """
    fecha = fecha or datetime.now(UTC).date()

    valuadas, total = await valuar_portfolio(
        session, user_id=user_id, portfolio_id=portfolio_id
    )
    valores = [v for _, _, v in valuadas]
    costo = sum((p.open_cost_basis for p, _, _ in valuadas), ZERO)
    realizado = sum((p.realized_pnl for p, _, _ in valuadas), ZERO)

    saldo = await saldo_de_portfolio(
        session, user_id=user_id, portfolio_id=portfolio_id,
        currency=total.currency if total.currency != "MIXTA" else "ARS",
    )

    snap = construir_snapshot(
        fecha=fecha,
        valores=valores,
        costo_abierto=costo,
        realizado=realizado,
        caja=saldo.saldo,
        currency=total.currency,
    )

    await session.execute(
        insert(PortfolioSnapshot)
        .values(
            user_id=user_id,
            portfolio_id=portfolio_id,
            snapshot_date=fecha,
            total_value=snap.total_value,
            open_cost_basis=snap.open_cost_basis,
            unrealized_pnl=snap.unrealized_pnl,
            realized_pnl=snap.realized_pnl,
            cash_balance=snap.cash_balance,
            currency=snap.currency,
            is_estimated=snap.is_estimated,
            posiciones=snap.posiciones,
            posiciones_sin_precio=snap.posiciones_sin_precio,
            motivo=snap.motivo,
            computed_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            constraint="uq_portfolio_snapshot_portfolio_id",
            set_={
                "total_value": snap.total_value,
                "open_cost_basis": snap.open_cost_basis,
                "unrealized_pnl": snap.unrealized_pnl,
                "realized_pnl": snap.realized_pnl,
                "cash_balance": snap.cash_balance,
                "is_estimated": snap.is_estimated,
                "posiciones": snap.posiciones,
                "posiciones_sin_precio": snap.posiciones_sin_precio,
                "motivo": snap.motivo,
                "computed_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            },
        )
    )
    return snap


async def tomar_snapshots_de_todos(session: AsyncSession) -> int:
    """Snapshot diario de cada portfolio. Es lo que corre el worker."""
    portfolios = (await session.execute(select(Portfolio))).scalars().all()
    for p in portfolios:
        await tomar_snapshot(session, user_id=p.user_id, portfolio_id=p.id)
    log.info("snapshots.tomados", portfolios=len(portfolios))
    return len(portfolios)


async def serie(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    desde: date | None = None,
) -> list[PortfolioSnapshot]:
    """Serie de snapshots, del más viejo al más nuevo."""
    query = select(PortfolioSnapshot).where(
        PortfolioSnapshot.portfolio_id == portfolio_id,
        PortfolioSnapshot.user_id == user_id,
    )
    if desde:
        query = query.where(PortfolioSnapshot.snapshot_date >= desde)

    resultado = await session.execute(query.order_by(PortfolioSnapshot.snapshot_date))
    return list(resultado.scalars().all())
