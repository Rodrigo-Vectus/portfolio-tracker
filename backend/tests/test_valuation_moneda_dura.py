"""Conversión de una posición a moneda dura.

**Por qué existe este archivo.** La Fase 4.5 quedó documentada como completada
y validada, y sin embargo `valuar_en_moneda_dura` moría en
`NameError: name 'ZERO' is not defined` en su primera línea, antes de leer un
solo lote. Cualquier consulta a `/positions?hard_currency=USD` devolvía 500.

No lo detectó nada porque **ninguna prueba pedía la conversión**: las 30 de
`test_finance_api.py` no usan `hard_currency` en ningún lado. Es el precedente
de la Regla 24 repitiéndose: importar el módulo no alcanza cuando el nombre no
definido vive adentro de una función que nadie llama en las pruebas.

La única dependencia de base es `_lotes_abiertos`, que se sustituye. El resto
del camino —la conversión lote por lote al FX de cada fecha— corre de verdad.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.domain.fx import CotizacionFx, SerieFx
from app.services import valuation


class LoteFalso:
    """Lo mínimo que `valuar_en_moneda_dura` le pide a un lote."""

    def __init__(self, cantidad: str, costo_unitario: str, dia: date) -> None:
        self.quantity_open = Decimal(cantidad)
        self.unit_cost = Decimal(costo_unitario)
        self.acquired_at = datetime(dia.year, dia.month, dia.day, 15, 0, tzinfo=UTC)


def serie(*pares: tuple[date, str]) -> SerieFx:
    return SerieFx(
        [
            CotizacionFx(fecha=f, rate=Decimal(r), rate_type="MEP", source="test")
            for f, r in pares
        ]
    )


@pytest.fixture
def lotes(monkeypatch):
    """Sustituye la única consulta a la base por una lista fija."""

    def poner(valores):
        async def _falso(session, portfolio_id, asset_id):
            return valores

        monkeypatch.setattr(valuation, "_lotes_abiertos", _falso)

    return poner


async def test_una_posicion_sin_lotes_no_explota(lotes) -> None:
    """La regresión exacta: sin lotes, el costo acumulado arranca en cero.

    Antes del arreglo esta línea era un `NameError` y se llevaba puesta toda
    la conversión a dólares.
    """
    lotes([])

    r = await valuation.valuar_en_moneda_dura(
        None,
        portfolio_id=None,
        asset_id=None,
        symbol="AAPL",
        valor_actual_local=Decimal(1000),
        serie=serie((date(2026, 1, 1), "1000")),
        hoy=date(2026, 1, 1),
    )

    assert r.costo == Decimal(0)
    assert r.currency == "USD"


async def test_cada_lote_se_convierte_al_dolar_de_su_fecha(lotes) -> None:
    """Dos lotes iguales en pesos y distintos en dólares.

    Es el error E1 de la planilla mirado desde el otro lado: convertir los dos
    al dólar de hoy los haría iguales, y no lo son.
    """
    lotes(
        [
            LoteFalso("10", "100", date(2026, 1, 10)),  # 1000 a 1000 -> 1 USD
            LoteFalso("10", "100", date(2026, 6, 10)),  # 1000 a 2000 -> 0,5
        ]
    )

    r = await valuation.valuar_en_moneda_dura(
        None,
        portfolio_id=None,
        asset_id=None,
        symbol="AAPL",
        valor_actual_local=Decimal(3000),
        serie=serie((date(2026, 1, 10), "1000"), (date(2026, 6, 10), "2000")),
        hoy=date(2026, 6, 10),
    )

    assert r.costo == Decimal("1.5")


async def test_el_valor_actual_usa_el_dolar_de_hoy(lotes) -> None:
    """La asimetría de D2: el costo a la fecha de cada lote, el valor a hoy."""
    lotes([LoteFalso("10", "100", date(2026, 1, 10))])

    r = await valuation.valuar_en_moneda_dura(
        None,
        portfolio_id=None,
        asset_id=None,
        symbol="AAPL",
        valor_actual_local=Decimal(4000),
        serie=serie((date(2026, 1, 10), "1000"), (date(2026, 6, 10), "2000")),
        hoy=date(2026, 6, 10),
    )

    assert r.costo == Decimal(1)  # 1000 pesos al dólar de enero
    assert r.valor_actual == Decimal(2)  # 4000 pesos al dólar de hoy
    assert r.no_realizado == Decimal(1)


async def test_sin_cotizacion_del_activo_se_dice_el_motivo(lotes) -> None:
    """Un valor ausente no es cero. Viaja el motivo (Regla 29)."""
    lotes([LoteFalso("10", "100", date(2026, 1, 10))])

    r = await valuation.valuar_en_moneda_dura(
        None,
        portfolio_id=None,
        asset_id=None,
        symbol="AAPL",
        valor_actual_local=None,
        serie=serie((date(2026, 1, 10), "1000")),
        hoy=date(2026, 1, 10),
    )

    assert r.valor_actual is None
    assert r.no_realizado is None
    assert r.motivo is not None


async def test_sin_tipo_de_cambio_anterior_no_se_inventa_uno(lotes) -> None:
    """Un lote anterior al inicio de la serie no se valúa con el primer dólar.

    Usar la cotización más vieja disponible para algo que pasó antes sería
    inventar el dato. Se devuelve el motivo y nada más.
    """
    lotes([LoteFalso("10", "100", date(2025, 1, 10))])

    r = await valuation.valuar_en_moneda_dura(
        None,
        portfolio_id=None,
        asset_id=None,
        symbol="AAPL",
        valor_actual_local=Decimal(1000),
        serie=serie((date(2026, 1, 10), "1000")),
        hoy=date(2026, 1, 10),
    )

    assert r.costo is None
    assert r.motivo is not None


# ------------------------------------------- variacion contra el cierre previo


def _valor(precio: str | None):
    """Una posicion valuada, con o sin cotizacion."""
    from app.domain.market import Cotizacion, Frescura, ValorDePosicion

    cotizacion = (
        Cotizacion(
            symbol="AAPL",
            price=Decimal(precio),
            currency="ARS",
            source="test",
            fetched_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
        )
        if precio is not None
        else None
    )
    return ValorDePosicion(
        symbol="AAPL",
        quantity=Decimal(1),
        cotizacion=cotizacion,
        frescura=Frescura.FRESCA if cotizacion else Frescura.AUSENTE,
    )


def test_la_variacion_lee_el_precio_de_la_cotizacion() -> None:
    """La regresion: el atributo se llamaba `price`, no `precio`.

    `cotizacion.precio` compilaba, pasaba el linter y pasaba las pruebas
    —ninguna tenia cotizacion **y** cierre a la vez— y devolvia 500 en la
    primera pantalla real. Esta prueba tiene las dos cosas.
    """
    v = valuation.variacion_de(
        _valor("26600"), (Decimal("25980"), date(2026, 9, 10))
    )
    assert v is not None
    assert v.desde == date(2026, 9, 10)
    assert v.cierre_anterior == Decimal("25980")
    # (26600 - 25980) / 25980
    assert v.fraccion > 0


def test_sin_cierre_previo_no_hay_variacion() -> None:
    assert valuation.variacion_de(_valor("26600"), None) is None


def test_sin_cotizacion_no_hay_variacion_aunque_haya_cierre() -> None:
    """Falta una de las dos puntas: no se inventa la que falta."""
    assert (
        valuation.variacion_de(_valor(None), (Decimal("25980"), date(2026, 9, 10)))
        is None
    )
