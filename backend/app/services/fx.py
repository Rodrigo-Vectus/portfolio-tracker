"""Series de tipo de cambio desde la base.

Carga las cotizaciones guardadas por el worker y arma la `SerieFx` que el
dominio sabe consultar.

Se trae **toda** la serie de una vez y no una consulta por fecha: valuar una
cartera de veinte posiciones con cinco lotes cada una haría cien consultas
para leer una tabla que tiene unas pocas filas por mes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.fx import CotizacionFx, SerieFx
from app.models.market import FxRate

#: Tipo de cambio por defecto para valuar (D1: MEP para acciones).
RATE_TYPE_POR_DEFECTO = "MEP"


async def cargar_serie(
    session: AsyncSession,
    *,
    rate_type: str = RATE_TYPE_POR_DEFECTO,
    base: str = "USD",
    quote: str = "ARS",
) -> SerieFx:
    """Serie histórica completa de un tipo de cambio.

    Si hay más de una cotización el mismo día se conserva la última: es la que
    más se acerca al cierre.
    """
    resultado = await session.execute(
        select(FxRate)
        .where(
            FxRate.base_currency == base.upper(),
            FxRate.quote_currency == quote.upper(),
            FxRate.rate_type == rate_type.upper(),
        )
        .order_by(FxRate.trade_date, FxRate.quoted_at)
    )

    por_dia: dict = {}
    for fila in resultado.scalars().all():
        por_dia[fila.trade_date] = CotizacionFx(
            fecha=fila.trade_date,
            rate=fila.rate,
            rate_type=fila.rate_type,
            source=fila.source,
        )

    return SerieFx(list(por_dia.values()), quote_currency=quote)
