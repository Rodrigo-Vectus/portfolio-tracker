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
    #: El proveedor no dijo cuándo se cotizó (D33), pero se pudo inferir la
    #: antigüedad desde el horario de rueda. Se muestra y se marca: es un dato
    #: real de fuente conocida con una limitación declarada, que no es lo mismo
    #: que un número presentado como algo que no es.
    ESTIMADA = "ESTIMADA"
    #: Ni fecha del proveedor ni forma de inferirla.
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
    #: Antigüedad inferida cuando el proveedor no informa `quoted_at`. Nunca
    #: se copia a `quoted_at`: son cosas distintas y confundirlas es el error
    #: que este proyecto existe para no repetir.
    momento_estimado: datetime | None = None

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
        """Qué tan confiable es la edad de este precio.

        Cuando el proveedor no informa la fecha se infiere desde el horario de
        rueda (D34-bis). La inferencia igual puede quedar vieja: un precio de
        cierre de hace cinco días es viejo aunque sepamos de qué cierre es.
        """
        momento = self.quoted_at or self.momento_estimado
        if momento is None:
            return Frescura.SIN_FECHA

        umbral = UMBRALES.get(self.asset_type, UMBRALES["CEDEAR"])
        if (ahora - momento) > umbral:
            return Frescura.VIEJA
        return Frescura.FRESCA if self.quoted_at is not None else Frescura.ESTIMADA

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

    Regla vigente (D34-bis): el total **no se muestra** si a alguna posición
    le falta el precio o lo tiene viejo. Sí se muestra, marcado como estimado,
    cuando la antigüedad es inferida desde el horario de rueda.

    El motivo de la distinción: un total con una posición vieja adentro se lee
    como completo, y el color de una fila no viaja hasta la suma. Un total
    estimado, en cambio, es un número real de fuente conocida cuya limitación
    se puede escribir al lado.
    """

    total: Money | None
    posiciones_totales: int
    posiciones_sin_precio: int
    posiciones_con_precio_viejo: int
    posiciones_sin_fecha: int
    posiciones_estimadas: int
    currency: str

    @property
    def es_completo(self) -> bool:
        """Todas las posiciones con precio fresco y fecha del proveedor."""
        return (
            self.posiciones_sin_precio == 0
            and self.posiciones_con_precio_viejo == 0
            and self.posiciones_sin_fecha == 0
            and self.posiciones_estimadas == 0
        )

    @property
    def es_estimado(self) -> bool:
        """El total se calculó, pero alguna antigüedad es inferida.

        La interfaz debe mostrarlo distinto de un total completo. No es una
        sutileza: es la diferencia entre "tu cartera vale esto" y "tu cartera
        vale esto según el último cierre conocido".
        """
        return self.total is not None and self.posiciones_estimadas > 0

    @property
    def motivo_incompleto(self) -> str | None:
        """Por qué el total no es confiable, en palabras."""
        if self.es_completo:
            return None
        partes = []
        if self.posiciones_estimadas:
            partes.append(
                f"{self.posiciones_estimadas} con antigüedad estimada"
            )
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
    estimadas = sum(1 for v in valores if v.frescura is Frescura.ESTIMADA)

    # Una antigüedad estimada NO invalida el total (D34-bis): lo marca. Un
    # precio viejo o ausente sí lo invalida, porque ahí no hay número que
    # valga la pena mostrar.
    total: Money | None = None
    if sin_precio == 0 and viejas == 0 and sin_fecha == 0 and valores:
        acumulado = Money.zero(currency)
        for v in valores:
            monto = v.valor
            if monto is None:
                acumulado = None  # type: ignore[assignment]
                break
            acumulado = acumulado + monto
        total = acumulado

    return TotalDeCartera(
        total=total,
        posiciones_totales=len(valores),
        posiciones_sin_precio=sin_precio,
        posiciones_con_precio_viejo=viejas,
        posiciones_sin_fecha=sin_fecha,
        posiciones_estimadas=estimadas,
        currency=currency,
    )
