"""Conversión entre monedas con tipo de cambio fechado.

**Este módulo existe por el error que originó el proyecto.**

La planilla convertía el precio de hoy usando el dólar del día de la compra.
Una compra de junio valuaba su precio de diciembre a $1198, cuando el dólar
estaba a $1550. El resultado fue una cartera sobrevaluada un 24%.

La regla correcta (D2) es asimétrica y esa asimetría es todo el punto:

    el COSTO de una operación se convierte al FX de SU PROPIA fecha
    el VALOR ACTUAL se convierte al FX de HOY

Convertir las dos puntas con el mismo tipo de cambio hace que el resultado en
dólares sea idéntico al resultado en pesos, que es precisamente lo que pasaba:
seis columnas en dólares que no decían nada nuevo porque numerador y
denominador se dividían por el mismo número.

Python puro: sin base de datos, sin red.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class SinTipoDeCambio(Exception):
    """No hay cotización aplicable para la fecha pedida."""


@dataclass(frozen=True, slots=True)
class CotizacionFx:
    fecha: date
    rate: Decimal
    rate_type: str
    source: str


@dataclass(frozen=True, slots=True)
class MontoConvertido:
    """Un importe convertido, con la cotización que se usó.

    La cotización viaja con el resultado a propósito: un número en dólares sin
    decir a qué dólar es medio número. Y con MEP, CCL y cripto conviviendo, la
    diferencia entre uno y otro llega al 4%.
    """

    monto: Decimal
    currency: str
    rate: Decimal
    rate_date: date
    rate_type: str
    #: La cotización es de una fecha anterior a la pedida. Pasa siempre en
    #: fines de semana y feriados, y hay que poder decirlo.
    arrastrada: bool


class SerieFx:
    """Serie histórica de un tipo de cambio, consultable por fecha.

    Devuelve la cotización **de la fecha pedida o la anterior más cercana**.
    Nunca una posterior: usar el dólar del martes para valuar una operación
    del lunes sería usar información que en ese momento no existía.
    """

    def __init__(self, cotizaciones: list[CotizacionFx], quote_currency: str = "ARS"):
        self._orden = sorted(cotizaciones, key=lambda c: c.fecha)
        self._fechas = [c.fecha for c in self._orden]
        self.quote_currency = quote_currency.upper()

    def __len__(self) -> int:
        return len(self._orden)

    @property
    def vacia(self) -> bool:
        return not self._orden

    @property
    def desde(self) -> date | None:
        return self._fechas[0] if self._orden else None

    def cotizacion_en(self, fecha: date) -> CotizacionFx:
        """Cotización vigente en esa fecha."""
        if self.vacia:
            raise SinTipoDeCambio(
                "No hay ninguna cotización de tipo de cambio guardada."
            )

        i = bisect_right(self._fechas, fecha)
        if i == 0:
            raise SinTipoDeCambio(
                f"No hay tipo de cambio para el {fecha:%d/%m/%Y}. La serie "
                f"arranca el {self._fechas[0]:%d/%m/%Y}, y usar una cotización "
                "posterior sería valuar con información que en ese momento no "
                "existía."
            )
        return self._orden[i - 1]

    def convertir(self, monto: Decimal, fecha: date, *, a: str = "USD") -> MontoConvertido:
        """Convierte un importe usando la cotización vigente en `fecha`.

        La serie está expresada como cuántas unidades de `quote_currency`
        vale una de `a`, así que se divide.
        """
        c = self.cotizacion_en(fecha)
        if c.rate <= 0:
            raise SinTipoDeCambio(f"Cotización inválida para el {c.fecha}: {c.rate}")

        return MontoConvertido(
            monto=monto / c.rate,
            currency=a.upper(),
            rate=c.rate,
            rate_date=c.fecha,
            rate_type=c.rate_type,
            arrastrada=c.fecha != fecha,
        )


@dataclass(frozen=True, slots=True)
class LoteConFecha:
    """Costo de un lote con la fecha en que se adquirió."""

    costo: Decimal
    fecha: date


def costo_en_moneda_dura(lotes: list[LoteConFecha], serie: SerieFx) -> Decimal:
    """Costo total convertido, cada lote al tipo de cambio de **su** fecha.

    Es la corrección concreta del error del Excel. Convertir el costo total al
    tipo de cambio de hoy daría un número que cambia cada vez que se mueve el
    dólar, aunque no hayas comprado ni vendido nada: el costo histórico es un
    hecho pasado y no puede depender de la cotización de esta mañana.
    """
    return sum(
        (serie.convertir(l.costo, l.fecha).monto for l in lotes), Decimal(0)
    )
