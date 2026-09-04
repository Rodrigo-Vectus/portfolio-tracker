"""Servicio de market data: consulta proveedores y persiste el resultado.

Lo que este módulo garantiza:

- **Ninguna falla queda en silencio.** Toda llamada deja una fila en
  `provider_log`, haya salido bien o mal. Un proveedor caído no rompe la
  aplicación: deja de actualizar precios, y sin registro eso se vería como una
  cartera que "no se mueve" en vez de como un error.
- **Un proveedor caído no tumba a los demás.** Cada refresco se aísla.
- **Nunca se borra el precio anterior si el refresco falla.** Es preferible un
  precio viejo *marcado como viejo* que ningún precio: la marca ya existe y la
  interfaz la respeta.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.market import Cotizacion
from app.models import Asset, AssetType
from app.models.market import FxRate, PriceQuote, ProviderLog
from app.services.providers import (
    BinanceProvider,
    Data912Provider,
    DolarApiProvider,
    MarketDataProvider,
    ProviderError,
)

log = get_logger("market_data")


async def _registrar(
    session: AsyncSession,
    *,
    provider: str,
    operation: str,
    status: str,
    inicio: datetime,
    pedidos: int | None = None,
    ok: int | None = None,
    error: str | None = None,
) -> None:
    session.add(
        ProviderLog(
            provider=provider,
            operation=operation,
            status=status,
            error_message=error[:2000] if error else None,
            assets_requested=pedidos,
            assets_ok=ok,
            duration_ms=int((datetime.now(UTC) - inicio).total_seconds() * 1000),
            created_at=datetime.now(UTC),
        )
    )


async def _guardar_cotizaciones(
    session: AsyncSession, cotizaciones: list[Cotizacion], por_simbolo: dict[str, Asset]
) -> int:
    """Inserta o actualiza la última cotización de cada activo y fuente.

    Se usa UPSERT sobre `(asset_id, source)`: `price_quote` guarda el precio de
    ahora, no la serie. El histórico va a `price_bar_daily`, en la Fase 5.
    """
    guardadas = 0
    for c in cotizaciones:
        asset = por_simbolo.get(c.symbol)
        if asset is None:
            continue

        await session.execute(
            insert(PriceQuote)
            .values(
                asset_id=asset.id,
                price=c.price,
                currency=c.currency,
                source=c.source,
                quoted_at=c.quoted_at,
                fetched_at=c.fetched_at,
                estimated_at=c.momento_estimado,
            )
            .on_conflict_do_update(
                constraint="uq_price_quote_asset_id",
                set_={
                    "price": c.price,
                    "currency": c.currency,
                    "quoted_at": c.quoted_at,
                    "fetched_at": c.fetched_at,
                    "estimated_at": c.momento_estimado,
                    "updated_at": datetime.now(UTC),
                },
            )
        )
        guardadas += 1
    return guardadas


async def refrescar_activos(
    session: AsyncSession, proveedor: MarketDataProvider, tipo: AssetType
) -> int:
    """Refresca las cotizaciones de todos los activos activos de un tipo.

    Si no hay activos de ese tipo en el catálogo no se llama al proveedor: no
    tiene sentido consultar precios de algo que nadie tiene.
    """
    resultado = await session.execute(
        select(Asset).where(Asset.asset_type == tipo, Asset.is_active)
    )
    activos = list(resultado.scalars().all())
    if not activos:
        log.info("market_data.sin_activos", tipo=tipo.value)
        return 0

    por_simbolo = {a.symbol.upper(): a for a in activos}
    inicio = datetime.now(UTC)

    try:
        cotizaciones = await proveedor.fetch()
    except ProviderError as exc:
        # No se borra nada: el precio anterior sigue disponible y marcado con
        # su antigüedad. Un precio viejo declarado es mejor que ninguno.
        await _registrar(
            session,
            provider=proveedor.nombre,
            operation=f"quotes:{tipo.value}",
            status="ERROR",
            inicio=inicio,
            pedidos=len(activos),
            ok=0,
            error=str(exc),
        )
        return 0

    guardadas = await _guardar_cotizaciones(session, cotizaciones, por_simbolo)

    # Un proveedor que responde 200 pero no trae los símbolos que pedimos es
    # una falla, aunque no lo parezca.
    faltantes = set(por_simbolo) - {c.symbol for c in cotizaciones}
    if faltantes:
        log.warning(
            "market_data.simbolos_faltantes",
            provider=proveedor.nombre,
            faltantes=sorted(faltantes),
        )

    await _registrar(
        session,
        provider=proveedor.nombre,
        operation=f"quotes:{tipo.value}",
        status="OK" if not faltantes else "PARCIAL",
        inicio=inicio,
        pedidos=len(activos),
        ok=guardadas,
    )
    return guardadas


async def refrescar_fx(session: AsyncSession, casas: list[str] | None = None) -> int:
    """Refresca las series de tipo de cambio.

    Se traen todas las casas y no sólo la de D1: cambiar de fuente altera cada
    número histórico en dólares, así que conviene tener las alternativas
    guardadas para poder compararlas (D16).
    """
    casas = casas or ["bolsa", "contadoconliqui", "cripto"]
    guardadas = 0

    for casa in casas:
        proveedor = DolarApiProvider(casa)
        inicio = datetime.now(UTC)
        try:
            cotizaciones = await proveedor.fetch()
        except ProviderError as exc:
            # Cada casa se aísla: que falle una no debe dejar sin actualizar
            # a las otras.
            await _registrar(
                session, provider=proveedor.nombre, operation=f"fx:{casa}",
                status="ERROR", inicio=inicio, pedidos=1, ok=0, error=str(exc),
            )
            continue

        for c in cotizaciones:
            if c.quoted_at is None:
                # Sin fecha del proveedor no se guarda en la serie histórica:
                # una serie temporal sin tiempo no sirve para nada.
                log.warning("market_data.fx_sin_fecha", casa=casa)
                continue

            await session.execute(
                insert(FxRate)
                .values(
                    base_currency="USD",
                    quote_currency="ARS",
                    rate_type=proveedor.rate_type,
                    rate=c.price,
                    quoted_at=c.quoted_at,
                    fetched_at=c.fetched_at,
                    trade_date=c.quoted_at.date(),
                    source=c.source,
                )
                # Si ya está esa marca temporal, no se duplica ni se pisa: el
                # dato histórico no cambia.
                .on_conflict_do_nothing(constraint="uq_fx_rate_base_currency")
            )
            guardadas += 1

        await _registrar(
            session, provider=proveedor.nombre, operation=f"fx:{casa}",
            status="OK", inicio=inicio, pedidos=1, ok=len(cotizaciones),
        )

    return guardadas


async def refrescar_cedears(session: AsyncSession) -> int:
    resultado = await session.execute(
        select(Asset.symbol).where(
            Asset.asset_type == AssetType.CEDEAR, Asset.is_active
        )
    )
    simbolos = [s for (s,) in resultado]
    if not simbolos:
        return 0
    return await refrescar_activos(
        session, Data912Provider(simbolos), AssetType.CEDEAR
    )


async def refrescar_cripto(session: AsyncSession) -> int:
    """Refresca criptomonedas.

    El símbolo del catálogo se usa tal cual como par de Binance: si el activo
    se llama `BTCUSDT`, se pide `BTCUSDT`. Es deliberado y provisorio: cuando
    haga falta traducir símbolos, eso vive en `asset_identifier`, que existe
    desde la Fase 2 justamente para esto.
    """
    resultado = await session.execute(
        select(Asset.symbol).where(
            Asset.asset_type == AssetType.CRYPTO, Asset.is_active
        )
    )
    pares = [s for (s,) in resultado]
    if not pares:
        return 0
    return await refrescar_activos(session, BinanceProvider(pares), AssetType.CRYPTO)
