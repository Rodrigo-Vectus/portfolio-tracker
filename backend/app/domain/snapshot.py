"""Fotografía diaria de la cartera.

Un snapshot es el valor de la cartera **en un día**, guardado para poder
dibujar su evolución. Como todo lo derivado, es caché reconstruible: si
discrepa del libro, el que está mal es el snapshot.

**Lo que un snapshot no puede hacer, y conviene saber antes de usarlo.**

Reconstruir la serie hacia atrás requiere el precio de cada activo en cada día
pasado, y hoy el sistema sólo guarda la última cotización de cada uno. Los
proveedores gratuitos disponibles devuelven el precio de ahora, no el
histórico.

Por eso la serie **arranca el día que se empieza a tomar snapshots** y crece
hacia adelante. Rellenar los días anteriores con el precio de hoy daría una
línea plana que parece historia y no lo es: exactamente el tipo de número
inventado que este proyecto existe para no mostrar.

Python puro: sin base de datos, sin red.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.market import Frescura, ValorDePosicion

ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """El valor de la cartera en una fecha, con la calidad del dato detrás.

    `is_estimated` marca que alguna posición se valuó con un precio cuya
    antigüedad se dedujo en vez de conocerse. El gráfico puede dibujar esos
    puntos distinto, y sin la marca no habría forma de distinguirlos después.
    """

    snapshot_date: date
    total_value: Decimal | None
    open_cost_basis: Decimal
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    cash_balance: Decimal
    currency: str
    is_estimated: bool
    posiciones: int
    posiciones_sin_precio: int
    motivo: str | None

    @property
    def es_completo(self) -> bool:
        return self.total_value is not None and self.posiciones_sin_precio == 0


def construir_snapshot(
    *,
    fecha: date,
    valores: list[ValorDePosicion],
    costo_abierto: Decimal,
    realizado: Decimal,
    caja: Decimal,
    currency: str,
) -> Snapshot:
    """Arma la foto del día a partir de las posiciones ya valuadas.

    Si a alguna posición le falta el precio, `total_value` queda en `None` y se
    guarda igual con el motivo. Un hueco declarado en la serie es información:
    dice que ese día no se pudo valuar. Un cero sería una caída a cero que
    nunca ocurrió.
    """
    sin_precio = sum(1 for v in valores if v.cotizacion is None)
    estimadas = sum(
        1 for v in valores if v.frescura in (Frescura.ESTIMADA, Frescura.SIN_FECHA)
    )
    viejas = sum(1 for v in valores if v.frescura is Frescura.VIEJA)

    total: Decimal | None = None
    if sin_precio == 0:
        acumulado = ZERO
        for v in valores:
            monto = v.valor
            if monto is None:
                acumulado = None  # type: ignore[assignment]
                break
            acumulado += monto.amount
        total = acumulado

    partes = []
    if sin_precio:
        partes.append(f"{sin_precio} sin cotización")
    if viejas:
        partes.append(f"{viejas} con precio viejo")
    if estimadas:
        partes.append(f"{estimadas} con antigüedad estimada")

    return Snapshot(
        snapshot_date=fecha,
        total_value=total,
        open_cost_basis=costo_abierto,
        unrealized_pnl=(total - costo_abierto) if total is not None else None,
        realized_pnl=realizado,
        cash_balance=caja,
        currency=currency,
        # Basta una estimación o un precio viejo para que el punto no sea un
        # hecho verificado.
        is_estimated=bool(estimadas or viejas),
        posiciones=len(valores),
        posiciones_sin_precio=sin_precio,
        motivo=" · ".join(partes) if partes else None,
    )


@dataclass(frozen=True, slots=True)
class PuntoDeSerie:
    """Un punto del gráfico de evolución."""

    fecha: date
    valor: Decimal | None
    aporte: Decimal
    is_estimated: bool


def serie_de_evolucion(snapshots: list[Snapshot]) -> list[PuntoDeSerie]:
    """Convierte los snapshots en la serie que dibuja el gráfico.

    Los días sin valor **no se interpolan**. Una línea que cruza por encima de
    un hueco afirma que ese día la cartera valía el promedio de sus vecinos, y
    eso no se sabe. El gráfico corta y muestra el corte.
    """
    return [
        PuntoDeSerie(
            fecha=s.snapshot_date,
            valor=s.total_value,
            aporte=s.open_cost_basis,
            is_estimated=s.is_estimated,
        )
        for s in sorted(snapshots, key=lambda s: s.snapshot_date)
    ]
