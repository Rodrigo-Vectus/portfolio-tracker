"""Materializacion de lotes, consumos y posiciones.

Las tres tablas que escribe este modulo son **cache reconstruible**. Ninguna
es autoridad. Por eso la estrategia es siempre la misma: borrar lo derivado y
recalcularlo entero desde el libro, en vez de intentar parchearlo.

Parece derrochador y es deliberado. Un recalculo incremental tiene que acertar
en cada camino posible (alta, anulacion, correccion retroactiva, importacion),
y basta que falle en uno para que el cache empiece a discrepar del libro sin
que nadie lo note: los numeros siguen pareciendo razonables. Borrar y rehacer
tiene un solo camino, y ese camino esta cubierto por los casos verificados a
mano del dominio.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.cost_basis import CostMethod, build_lots, realized
from app.domain.ledger import Transaction as DomainTx
from app.models import (
    Asset,
    CostLot,
    LotConsumption,
    PositionCache,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.services.mappers import to_domain

log = get_logger("positions")

ZERO = Decimal(0)
POSITION_TYPES = {TransactionType.BUY, TransactionType.SELL}


async def _historial(
    session: AsyncSession, portfolio_id: UUID, asset_id: UUID
) -> list[Transaction]:
    result = await session.execute(
        select(Transaction)
        .where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset_id,
            Transaction.status == TransactionStatus.ACTIVE,
            Transaction.tx_type.in_(POSITION_TYPES),
        )
        .order_by(Transaction.executed_at, Transaction.id)
    )
    return list(result.scalars().all())


async def _borrar_derivados(
    session: AsyncSession, portfolio_id: UUID, asset_id: UUID
) -> None:
    """Elimina lotes, consumos y cache de un activo.

    Los consumos se borran primero: la FK a `cost_lot` es CASCADE, pero
    depender de eso haria que el orden de las sentencias importe segun como se
    configure la base. Explicito es mas aburrido y mas seguro.
    """
    lotes = await session.execute(
        select(CostLot.id).where(
            CostLot.portfolio_id == portfolio_id, CostLot.asset_id == asset_id
        )
    )
    ids = [row[0] for row in lotes]
    if ids:
        await session.execute(
            delete(LotConsumption).where(LotConsumption.cost_lot_id.in_(ids))
        )
        await session.execute(delete(CostLot).where(CostLot.id.in_(ids)))

    await session.execute(
        delete(PositionCache).where(
            PositionCache.portfolio_id == portfolio_id,
            PositionCache.asset_id == asset_id,
        )
    )


async def rebuild_asset(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    asset: Asset,
    method: CostMethod = CostMethod.WAC,
) -> PositionCache | None:
    """Recalcula lotes, consumos y posicion de un activo desde cero.

    No hace commit. Quien llama decide el alcance de la transaccion, porque
    registrar una operacion y materializar sus lotes tienen que entrar juntos
    o no entrar.

    Devuelve `None` si el activo no tiene historial: en ese caso lo correcto
    es que no exista una fila de posicion, no que exista una en cero. Una
    posicion en cero y una posicion inexistente no son lo mismo.
    """
    await _borrar_derivados(session, portfolio_id, asset.id)

    filas = await _historial(session, portfolio_id, asset.id)
    if not filas:
        return None

    por_tx = {str(f.id): f for f in filas}
    dominio: list[DomainTx] = [to_domain(f, symbol=asset.symbol) for f in filas]

    ledger = build_lots(dominio)
    pnl = realized(dominio, method)

    # Los lotes primero: los consumos los referencian.
    lote_por_clave: dict[str, CostLot] = {}
    for lote in ledger.lots:
        origen = por_tx[lote.source_tx_id]
        fila = CostLot(
            user_id=user_id,
            portfolio_id=portfolio_id,
            asset_id=asset.id,
            source_tx_id=origen.id,
            quantity_original=lote.quantity_original,
            quantity_open=lote.quantity_open,
            unit_cost=lote.unit_cost,
            currency=lote.currency,
            acquired_at=lote.acquired_at,
            closed_at=datetime.now(UTC) if lote.is_closed else None,
        )
        session.add(fila)
        lote_por_clave[lote.lot_id] = fila
    await session.flush()

    orden: dict[str, int] = {}
    for consumo in ledger.consumptions:
        secuencia = orden.get(consumo.sell_tx_id, 0)
        orden[consumo.sell_tx_id] = secuencia + 1
        session.add(
            LotConsumption(
                sell_tx_id=por_tx[consumo.sell_tx_id].id,
                cost_lot_id=lote_por_clave[consumo.lot_id].id,
                quantity=consumo.quantity,
                sequence=secuencia,
            )
        )

    cantidad = ledger.quantity
    costo_abierto = sum(
        (lote.quantity_open * lote.unit_cost for lote in ledger.lots), ZERO
    )
    if method is CostMethod.WAC and cantidad > ZERO:
        # Con WAC el costo remanente es el promedio movil, no la suma de los
        # lotes: los dos metodos dejan abierto lo mismo en cantidad, pero no
        # en costo.
        costo_abierto = _costo_abierto_wac(dominio)

    posicion = PositionCache(
        user_id=user_id,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=cantidad,
        # None y no cero: una posicion cerrada no tiene precio promedio, y un
        # cero se leeria como "me costo nada".
        average_cost=(costo_abierto / cantidad) if cantidad > ZERO else None,
        open_cost_basis=costo_abierto,
        realized_pnl=pnl.amount,
        cost_method=method.value,
        currency=pnl.currency,
        last_transaction_at=filas[-1].executed_at,
        computed_at=datetime.now(UTC),
        computed_through=filas[-1].trade_date,
    )
    session.add(posicion)
    await session.flush()
    return posicion


def _costo_abierto_wac(transacciones: list[DomainTx]) -> Decimal:
    cantidad = ZERO
    costo = ZERO
    for tx in transacciones:
        if tx.tx_type.value == "BUY":
            cantidad += tx.quantity
            costo += tx.quantity * tx.unit_price + tx.commission + tx.taxes
        elif tx.tx_type.value == "SELL":
            ppc = costo / cantidad
            costo -= tx.quantity * ppc
            cantidad -= tx.quantity
    return costo


async def rebuild_portfolio(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    method: CostMethod = CostMethod.WAC,
) -> int:
    """Reconstruye todas las posiciones de un portfolio.

    Es el comando de reconstruccion total que la arquitectura exige que exista
    siempre. Si alguna vez el cache y el libro discrepan, esto los reconcilia
    tomando el libro como verdad.
    """
    activos = await session.execute(
        select(Asset)
        .join(Transaction, Transaction.asset_id == Asset.id)
        .where(Transaction.portfolio_id == portfolio_id)
        .distinct()
    )
    total = 0
    for asset in activos.scalars().all():
        await rebuild_asset(
            session,
            user_id=user_id,
            portfolio_id=portfolio_id,
            asset=asset,
            method=method,
        )
        total += 1

    log.info(
        "positions.rebuilt",
        portfolio_id=str(portfolio_id),
        activos=total,
        method=method.value,
    )
    return total
