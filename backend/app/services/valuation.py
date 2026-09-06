"""Valuación de posiciones contra la última cotización conocida.

Ésta es la capa que el proyecto existe para hacer bien.

El Excel guardaba el precio actual en la misma fila que la operación, escrito
a mano, y con el tiempo esa columna envejecía sin que nada avisara. Acá el
precio **no se guarda junto a la posición**: se busca al consultar, y viaja
siempre con su antigüedad y su fuente.

Tres reglas que se cumplen sin excepción:

- Si no hay cotización, la posición se devuelve **sin valor**, no en cero.
- La antigüedad viaja siempre, incluso cuando es una estimación.
- El total de la cartera declara su propia completitud (D34-bis).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.market import (
    Cotizacion,
    Frescura,
    TotalDeCartera,
    ValorDePosicion,
    totalizar,
)
from app.models import Asset, PositionCache
from app.models.market import PriceQuote


async def _cotizaciones_por_activo(
    session: AsyncSession, asset_ids: list[UUID]
) -> dict[UUID, tuple[PriceQuote, Asset]]:
    """Última cotización de cada activo.

    Si hubiera más de una fuente para el mismo activo se toma la más reciente
    por `fetched_at`. Que exista más de una es deseable: permite notar cuando
    un proveedor se queda pegado mientras el otro se mueve.
    """
    if not asset_ids:
        return {}

    resultado = await session.execute(
        select(PriceQuote, Asset)
        .join(Asset, Asset.id == PriceQuote.asset_id)
        .where(PriceQuote.asset_id.in_(asset_ids))
        .order_by(PriceQuote.asset_id, PriceQuote.fetched_at.desc())
    )
    por_activo: dict[UUID, tuple[PriceQuote, Asset]] = {}
    for quote, asset in resultado.all():
        por_activo.setdefault(quote.asset_id, (quote, asset))
    return por_activo


def _a_dominio(quote: PriceQuote, asset: Asset) -> Cotizacion:
    return Cotizacion(
        symbol=asset.symbol,
        price=quote.price,
        currency=quote.currency,
        source=quote.source,
        fetched_at=quote.fetched_at,
        quoted_at=quote.quoted_at,
        momento_estimado=quote.estimated_at,
        asset_type=asset.asset_type.value,
    )


async def valuar_portfolio(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    ahora: datetime | None = None,
) -> tuple[list[tuple[PositionCache, Asset, ValorDePosicion]], TotalDeCartera]:
    """Devuelve las posiciones valuadas y el total con su completitud.

    El filtro por `user_id` es redundante con el del portfolio y está a
    propósito: toda consulta financiera filtra por el usuario autenticado, y
    ese filtro no debería depender de un join que alguien olvide escribir.
    """
    ahora = ahora or datetime.now(UTC)

    resultado = await session.execute(
        select(PositionCache, Asset)
        .join(Asset, Asset.id == PositionCache.asset_id)
        .where(
            PositionCache.portfolio_id == portfolio_id,
            PositionCache.user_id == user_id,
            # Una posición cerrada no se valúa: no hay nada que valer.
            PositionCache.quantity > 0,
        )
        .order_by(Asset.symbol)
    )
    filas = resultado.all()
    if not filas:
        return [], totalizar([], "ARS", ahora)

    cotizaciones = await _cotizaciones_por_activo(
        session, [pos.asset_id for pos, _ in filas]
    )

    valuadas: list[tuple[PositionCache, Asset, ValorDePosicion]] = []
    valores: list[ValorDePosicion] = []

    for pos, asset in filas:
        par = cotizaciones.get(pos.asset_id)
        cotizacion = _a_dominio(*par) if par else None
        frescura = (
            cotizacion.frescura(ahora) if cotizacion is not None else Frescura.AUSENTE
        )
        valor = ValorDePosicion(
            symbol=asset.symbol,
            quantity=pos.quantity,
            cotizacion=cotizacion,
            frescura=frescura,
        )
        valuadas.append((pos, asset, valor))
        valores.append(valor)

    # Moneda del total: la de las posiciones, no una elegida por defecto.
    # Cuando haya activos en más de una moneda esto va a necesitar FX, y la
    # conversión tiene que ser explícita y fechada (D2), no implícita acá.
    monedas = {p.currency for p, _, _ in valuadas}
    moneda = monedas.pop() if len(monedas) == 1 else "MIXTA"

    return valuadas, totalizar(valores, moneda, ahora)


def resultado_no_realizado(
    posicion: PositionCache, valor: ValorDePosicion
) -> Decimal | None:
    """valor actual − costo base de lo abierto.

    `None` cuando no hay cotización. Devolver cero diría que no ganaste ni
    perdiste, que es una afirmación distinta de "no sé cuánto vale".
    """
    monto = valor.valor
    if monto is None:
        return None
    return monto.amount - posicion.open_cost_basis
