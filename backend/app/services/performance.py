"""Rendimiento de la cartera: arma los flujos y delega el cálculo.

El dominio no sabe de base de datos, así que este módulo traduce: convierte
depósitos, retiros y valor actual en flujos fechados, y le pide la tasa al
motor.

**Qué es un flujo y qué no.** El XIRR mide el rendimiento de *tu plata*, así
que sólo cuenta lo que cruza la frontera entre vos y el broker: depósitos y
retiros. Comprar y vender no son flujos: mueven valor de un lado al otro
dentro de la misma cartera, y contarlos falsearía la tasa.

El valor actual entra como un flujo positivo final: es lo que recibirías si
liquidaras hoy, y sin él la tasa mediría sólo lo que ya cobraste.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.performance import (
    Flujo,
    PuntoDeTwr,
    ResultadoTwr,
    RoiDePosicion,
    XirrNoConverge,
    roi_de_posicion,
    twr,
    xirr,
)
from app.models import (
    PortfolioSnapshot,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.services.valuation import valuar_portfolio

ZERO = Decimal(0)

#: Sólo lo que entra o sale de la cartera. Ver el docstring del módulo.
FLUJOS_EXTERNOS = {
    TransactionType.DEPOSIT: -1,   # sale de tu bolsillo
    TransactionType.WITHDRAWAL: +1,  # vuelve a tu bolsillo
}


class RendimientoDeCartera:
    """Resultado del cálculo, con el motivo cuando algo no se pudo calcular."""

    def __init__(
        self,
        *,
        posiciones: list[RoiDePosicion],
        realizado: Decimal,
        no_realizado: Decimal | None,
        valor_actual: Decimal | None,
        aporte_neto: Decimal,
        currency: str,
        xirr_anual: Decimal | None,
        xirr_motivo: str | None,
        twr: ResultadoTwr,
    ) -> None:
        self.posiciones = posiciones
        self.realizado = realizado
        self.no_realizado = no_realizado
        self.valor_actual = valor_actual
        self.aporte_neto = aporte_neto
        self.currency = currency
        self.xirr_anual = xirr_anual
        self.xirr_motivo = xirr_motivo
        self.twr = twr

    @property
    def resultado_total(self) -> Decimal | None:
        """Realizado más no realizado. `None` si falta alguna cotización."""
        if self.no_realizado is None:
            return None
        return self.realizado + self.no_realizado


async def _flujos_externos(
    session: AsyncSession, user_id: UUID, portfolio_id: UUID, currency: str
) -> list[tuple[date, Decimal]]:
    resultado = await session.execute(
        select(Transaction)
        .where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.user_id == user_id,
            Transaction.status == TransactionStatus.ACTIVE,
            Transaction.tx_type.in_(FLUJOS_EXTERNOS),
            Transaction.price_currency == currency.upper(),
        )
        .order_by(Transaction.executed_at)
    )
    return [
        (fila.trade_date, Decimal(FLUJOS_EXTERNOS[fila.tx_type]) * fila.unit_price)
        for fila in resultado.scalars().all()
    ]


async def _puntos_de_twr(
    session: AsyncSession,
    user_id: UUID,
    portfolio_id: UUID,
    externos: list[tuple[date, Decimal]],
) -> list[PuntoDeTwr]:
    """Convierte snapshots y flujos en la serie que encadena el TWR.

    **El patrimonio es posiciones más caja.** `total_value` guarda sólo las
    posiciones; los depósitos entran a la caja. Medir el rendimiento contra un
    denominador que excluye la caja haría que un depósito sin invertir
    aparezca como flujo sin contrapartida.

    Cada flujo se imputa al primer snapshot **en o después** de su fecha: es el
    tramo durante el cual la plata estuvo adentro.
    """
    resultado = await session.execute(
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.portfolio_id == portfolio_id,
            PortfolioSnapshot.user_id == user_id,
        )
        .order_by(PortfolioSnapshot.snapshot_date)
    )
    filas = list(resultado.scalars().all())
    if not filas:
        return []

    # `externos` viene con el signo del inversor (un depósito es negativo
    # porque sale de su bolsillo). Para el TWR importa lo que entra a la
    # cartera, así que se invierte.
    pendientes = sorted(((f, -m) for f, m in externos), key=lambda x: x[0])

    puntos: list[PuntoDeTwr] = []
    i = 0
    for n, fila in enumerate(filas):
        # Al primer snapshot no se le imputa nada: lo anterior ya está adentro
        # de su propio patrimonio.
        desde = filas[n - 1].snapshot_date if n > 0 else None
        flujo = ZERO
        while i < len(pendientes) and pendientes[i][0] <= fila.snapshot_date:
            fecha, monto = pendientes[i]
            if desde is not None and fecha > desde:
                flujo += monto
            i += 1

        patrimonio = (
            fila.total_value + fila.cash_balance
            if fila.total_value is not None
            else None
        )
        puntos.append(
            PuntoDeTwr(
                fecha=fila.snapshot_date,
                patrimonio=patrimonio,
                flujo=flujo,
                caja=fila.cash_balance,
            )
        )

    return puntos


async def rendimiento_de_portfolio(
    session: AsyncSession,
    *,
    user_id: UUID,
    portfolio_id: UUID,
    currency: str = "ARS",
) -> RendimientoDeCartera:
    valuadas, total = await valuar_portfolio(
        session, user_id=user_id, portfolio_id=portfolio_id
    )

    posiciones: list[RoiDePosicion] = []
    realizado = ZERO
    no_realizado: Decimal | None = ZERO
    valor_actual: Decimal | None = ZERO

    for pos, asset, valor in valuadas:
        monto = valor.valor
        r = roi_de_posicion(
            asset.symbol, pos.open_cost_basis, monto.amount if monto else None
        )
        posiciones.append(r)
        realizado += pos.realized_pnl

        # Basta que falte una cotización para que el total deje de existir.
        # Sumar sólo las que tienen precio daría un número que parece el
        # resultado completo.
        if r.no_realizado is None:
            no_realizado = None
            valor_actual = None
        elif no_realizado is not None and valor_actual is not None:
            no_realizado += r.no_realizado
            valor_actual += r.valor_actual or ZERO

    externos = await _flujos_externos(session, user_id, portfolio_id, currency)
    aporte_neto = -sum((m for _, m in externos), ZERO)

    tasa: Decimal | None = None
    motivo: str | None = None

    if not externos:
        motivo = (
            "No hay depósitos ni retiros registrados. El XIRR mide el "
            "rendimiento de la plata que pusiste, así que necesita saber "
            "cuándo la pusiste."
        )
    elif valor_actual is None:
        motivo = (
            "Falta la cotización de alguna posición, así que no se sabe cuánto "
            "vale la cartera hoy."
        )
    else:
        flujos = [Flujo(f, m) for f, m in externos]
        # El valor actual cierra la serie: es lo que recibirías si liquidaras
        # hoy. Sin él la tasa mediría sólo lo ya cobrado.
        flujos.append(Flujo(datetime.now(UTC).date(), valor_actual))
        try:
            tasa = xirr(flujos)
        except XirrNoConverge as exc:
            motivo = str(exc)

    puntos = await _puntos_de_twr(session, user_id, portfolio_id, externos)

    return RendimientoDeCartera(
        posiciones=posiciones,
        realizado=realizado,
        no_realizado=no_realizado,
        valor_actual=valor_actual,
        aporte_neto=aporte_neto,
        currency=total.currency,
        xirr_anual=tasa,
        xirr_motivo=motivo,
        twr=twr(puntos),
    )
