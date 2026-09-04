"""Cotizaciones como concepto del dominio.

Python puro: no sabe de HTTP, ni de proveedores, ni de la base.

La pieza central es `antiguedad`. Todo el proyecto nace de un numero viejo
presentado como actual, asi que la edad de un precio no es un metadato
decorativo: es parte del valor. Un precio sin edad conocida no es un precio
util, es un numero.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from app.domain.money import Money


class Frescura(str, Enum):
    """Cuanto se puede confiar en la edad de un precio."""

    FRESCA = "FRESCA"
    #: Superó el umbral para su tipo de activo. Se muestra, pero marcada.
    VIEJA = "VIEJA"
    #: El proveedor no dijo cuando se cotizó (D33). Sólo se sabe cuándo se
    #: pidió, que no es lo mismo: entre una cosa y la otra puede haber días.
    SIN_FECHA = "SIN_FECHA"
    #: No hay ninguna cotización para este activo.
    AUSENTE = "AUSENTE"


#: Umbral de vejez por tipo de activo, en minutos.
#:
#: Las criptomonedas cotizan 24/7, así que un precio de hace una hora ya es
#: viejo. Los CEDEARs no cotizan de noche ni los fines de semana: un precio del
#: viernes sigue siendo el último real el sábado, y marcarlo como viejo sería
#: ruido. Por eso el umbral es más laxo y la interfaz debe además decir si la
#: rueda está abierta.
UMBRALES = {
    "CRYPTO": timedelta(minutes=30),
    "CEDEAR": timedelta(hours=24),
    "CASH": timedelta(hours=24),
    "FX": timedelta(hours=6),
}


@dataclass(frozen=True, slots=True)
class Cotizacion:
    """Un precio con todo lo necesario para saber si sirve.

    `quoted_at` es cuándo lo dijo el mercado. `fetched_at` es cuándo lo
    pedimos nosotros. **No son lo mismo y no se rellena uno con el otro**
    (D33): si el proveedor no informa el primero, queda en `None`.
    """

    symbol: str
    price: Decimal
    currency: str
    source: str
    fetched_at: datetime
    quoted_at: datetime | None = None
    asset_type: str = "CEDEAR"

    @property
    def money(self) -> Money:
        return Money(self.price, self.currency)

    def antiguedad(self, ahora: datetime) -> timedelta | None:
        """Cuánto hace que el mercado dijo este precio.

        `None` si el proveedor no lo informó. Devolver la antigüedad del
        pedido en su lugar sería responder otra pregunta.
        """
        if self.quoted_at is None:
            return None
        return ahora - self.quoted_at

    def frescura(self, ahora: datetime) -> Frescura:
        if self.quoted_at is None:
            return Frescura.SIN_FECHA
        umbral = UMBRALES.get(self.asset_type, UMBRALES["CEDEAR"])
        return Frescura.FRESCA if (ahora - self.quoted_at) <= umbral else Frescura.VIEJA

    @property
    def es_confiable(self) -> bool:
        """Sólo una cotización con fecha propia y dentro del umbral lo es."""
        return self.quoted_at is not None


@dataclass(frozen=True, slots=True)
class ValorDePosicion:
    """Una posición valuada, con la calidad del dato que la sostiene."""

    symbol: str
    quantity: Decimal
    cotizacion: Cotizacion | None
    frescura: Frescura

    @property
    def valor(self) -> Money | None:
        if self.cotizacion is None:
            return None
        return self.cotizacion.money * self.quantity


@dataclass(frozen=True, slots=True)
class TotalDeCartera:
    """Total de la cartera, con su propia declaración de completitud.

    **El total no se presenta como un número confiable si alguna posición no
    tiene precio fresco** (D34). Una posición vieja marcada se lee como vieja;
    un total con una posición vieja adentro se lee como completo, y ahí está
    el engaño: el color de una fila no viaja hasta la suma.
    """

    total: Money | None
    posiciones_totales: int
    posiciones_sin_precio: int
    posiciones_con_precio_viejo: int
    posiciones_sin_fecha: int
    currency: str

    @property
    def es_completo(self) -> bool:
        return (
            self.posiciones_sin_precio == 0
            and self.posiciones_con_precio_viejo == 0
            and self.posiciones_sin_fecha == 0
        )

    @property
    def motivo_incompleto(self) -> str | None:
        """Por qué el total no es confiable, en palabras."""
        if self.es_completo:
            return None
        partes = []
        if self.posiciones_sin_precio:
            partes.append(f"{self.posiciones_sin_precio} sin cotización")
        if self.posiciones_con_precio_viejo:
            partes.append(f"{self.posiciones_con_precio_viejo} con precio viejo")
        if self.posiciones_sin_fecha:
            partes.append(f"{self.posiciones_sin_fecha} sin fecha de cotización")
        return " · ".join(partes)


def totalizar(
    valores: list[ValorDePosicion], currency: str, ahora: datetime
) -> TotalDeCartera:
    """Suma las posiciones y declara qué tan completa es la suma.

    Si falta una sola cotización el total queda en `None`. Sumar lo que hay e
    informar "total parcial" en letra chica no alcanza: el número igual se
    lee como el valor de la cartera.
    """
    sin_precio = sum(1 for v in valores if v.cotizacion is None)
    viejas = sum(1 for v in valores if v.frescura is Frescura.VIEJA)
    sin_fecha = sum(1 for v in valores if v.frescura is Frescura.SIN_FECHA)

    total: Money | None = None
    if sin_precio == 0 and valores:
        acumulado = Money.zero(currency)
        for v in valores:
            monto = v.valor
            if monto is None:
                acumulado = None  # type: ignore[assignment]
                break
            acumulado = acumulado + monto
        total = acumulado

    completo = sin_precio == 0 and viejas == 0 and sin_fecha == 0
    return TotalDeCartera(
        total=total if completo else None,
        posiciones_totales=len(valores),
        posiciones_sin_precio=sin_precio,
        posiciones_con_precio_viejo=viejas,
        posiciones_sin_fecha=sin_fecha,
        currency=currency,
    )
