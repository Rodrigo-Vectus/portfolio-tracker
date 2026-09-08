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

from dataclasses import dataclass
from datetime import UTC, date, datetime
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
from app.domain.fx import SerieFx, SinTipoDeCambio
from app.models import Asset, CostLot, PositionCache
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


# --------------------------------------------------------------- moneda dura


@dataclass(frozen=True, slots=True)
class ValorEnMonedaDura:
    """Una posición expresada en moneda dura.

    `costo` sale de convertir **cada lote al tipo de cambio de su propia
    fecha** (D2). `valor_actual` usa el de hoy. Esa asimetría es la corrección
    del error que originó el proyecto: convertir las dos puntas con el mismo
    dólar hacía que el resultado en dólares fuera idéntico al de pesos.

    Cualquier campo puede venir en `None`: falta la cotización del activo, o
    falta el tipo de cambio de alguna fecha. El motivo viaja con el resultado.
    """

    symbol: str
    costo: Decimal | None
    valor_actual: Decimal | None
    no_realizado: Decimal | None
    currency: str
    motivo: str | None = None


async def _lotes_abiertos(
    session: AsyncSession, portfolio_id: UUID, asset_id: UUID
) -> list[CostLot]:
    resultado = await session.execute(
        select(CostLot).where(
            CostLot.portfolio_id == portfolio_id,
            CostLot.asset_id == asset_id,
            CostLot.quantity_open > 0,
        )
    )
    return list(resultado.scalars().all())


async def valuar_en_moneda_dura(
    session: AsyncSession,
    *,
    portfolio_id: UUID,
    asset_id: UUID,
    symbol: str,
    valor_actual_local: Decimal | None,
    serie: SerieFx,
    hoy: date,
    currency: str = "USD",
) -> ValorEnMonedaDura:
    """Convierte el costo y el valor de una posición a moneda dura.

    El costo se recorre **lote por lote** y no como total: cada lote se
    adquirió en una fecha distinta y con un dólar distinto. Convertir el total
    al dólar de hoy daría un costo que cambia cada mañana aunque no hayas
    operado, y un costo histórico no puede depender de la cotización de esta
    mañana.
    """
    lotes = await _lotes_abiertos(session, portfolio_id, asset_id)

    costo: Decimal | None = ZERO
    try:
        for lote in lotes:
            fecha = lote.acquired_at.date()
            costo += serie.convertir(
                lote.quantity_open * lote.unit_cost, fecha, a=currency
            ).monto
    except SinTipoDeCambio as exc:
        return ValorEnMonedaDura(
            symbol=symbol,
            costo=None,
            valor_actual=None,
            no_realizado=None,
            currency=currency,
            motivo=str(exc),
        )

    if valor_actual_local is None:
        return ValorEnMonedaDura(
            symbol=symbol,
            costo=costo,
            valor_actual=None,
            no_realizado=None,
            currency=currency,
            motivo="No hay cotización del activo.",
        )

    try:
        valor = serie.convertir(valor_actual_local, hoy, a=currency).monto
    except SinTipoDeCambio as exc:
        return ValorEnMonedaDura(
            symbol=symbol,
            costo=costo,
            valor_actual=None,
            no_realizado=None,
            currency=currency,
            motivo=f"Sin tipo de cambio de hoy: {exc}",
        )

    return ValorEnMonedaDura(
        symbol=symbol,
        costo=costo,
        valor_actual=valor,
        no_realizado=valor - costo,
        currency=currency,
    )
