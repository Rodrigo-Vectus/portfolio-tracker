"""Conversión de moneda con tipo de cambio fechado.

Estas pruebas son la red del error que originó el proyecto: la planilla
convertía el precio de hoy con el dólar del día de la compra, y eso
sobrevaluaba la cartera un 24%.

Python puro: sin base de datos.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.fx import (
    CotizacionFx,
    LoteConFecha,
    SerieFx,
    SinTipoDeCambio,
    costo_en_moneda_dura,
)


def c(anio: int, mes: int, dia: int, rate: str) -> CotizacionFx:
    return CotizacionFx(date(anio, mes, dia), Decimal(rate), "MEP", "dolarapi")


#: Serie real que el usuario registró en su planilla, mes a mes.
SERIE = SerieFx([
    c(2025, 6, 23, "1198"),
    c(2025, 7, 15, "1276"),
    c(2025, 8, 15, "1329"),
    c(2025, 9, 15, "1380"),
    c(2025, 10, 15, "1530"),
    c(2025, 11, 15, "1501"),
    c(2025, 12, 23, "1550"),
])


def test_usa_la_cotizacion_de_la_fecha_exacta() -> None:
    assert SERIE.cotizacion_en(date(2025, 6, 23)).rate == Decimal(1198)


def test_arrastra_la_cotizacion_anterior() -> None:
    """Fines de semana y feriados no tienen cotización propia."""
    r = SERIE.convertir(Decimal(1000), date(2025, 6, 30))
    assert r.rate == Decimal(1198)
    assert r.rate_date == date(2025, 6, 23)
    assert r.arrastrada


def test_nunca_usa_una_cotizacion_posterior() -> None:
    """Valuar el lunes con el dólar del martes es usar información futura.

    En vez de estirar hacia atrás la primera cotización disponible, se avisa.
    """
    with pytest.raises(SinTipoDeCambio, match="no existía"):
        SERIE.convertir(Decimal(1000), date(2025, 1, 1))


def test_una_serie_vacia_lo_dice() -> None:
    with pytest.raises(SinTipoDeCambio, match="ninguna cotización"):
        SerieFx([]).convertir(Decimal(1000), date(2025, 6, 23))


def test_la_cotizacion_viaja_con_el_resultado() -> None:
    """Un número en dólares sin decir a qué dólar es medio número.

    Con MEP, CCL y cripto conviviendo, la diferencia llega al 4%.
    """
    r = SERIE.convertir(Decimal("11980"), date(2025, 6, 23))
    assert r.monto == Decimal(10)
    assert r.rate_type == "MEP"
    assert r.rate == Decimal(1198)
    assert not r.arrastrada


# --------------------------------------------------------- el error del Excel


def test_cada_lote_se_convierte_al_dolar_de_su_fecha() -> None:
    """La corrección concreta del error E1.

    Dos compras de 1.198.000 pesos: una en junio a 1198, otra en diciembre a
    1550. En dólares son 1.000 y 772,90, no 1.000 y 1.000.
    """
    lotes = [
        LoteConFecha(Decimal("1198000"), date(2025, 6, 23)),
        LoteConFecha(Decimal("1198000"), date(2025, 12, 23)),
    ]
    total = costo_en_moneda_dura(lotes, SERIE)

    assert total == Decimal("1198000") / Decimal(1198) + Decimal("1198000") / Decimal(1550)
    assert total < Decimal(2000)


def test_convertir_todo_al_dolar_de_hoy_da_otro_numero() -> None:
    """Muestra el tamaño del error que se está evitando.

    Convertir el costo total al dólar de hoy no sólo da distinto: da un costo
    que **cambia cada mañana** aunque no hayas comprado ni vendido nada. Un
    hecho pasado no puede depender de la cotización de esta mañana.
    """
    lotes = [
        LoteConFecha(Decimal("1198000"), date(2025, 6, 23)),
        LoteConFecha(Decimal("1198000"), date(2025, 12, 23)),
    ]
    correcto = costo_en_moneda_dura(lotes, SERIE)
    al_dolar_de_hoy = Decimal("2396000") / Decimal(1550)

    assert correcto != al_dolar_de_hoy
    # El método correcto reconoce que la compra vieja costó más dólares.
    assert correcto > al_dolar_de_hoy


def test_el_resultado_en_dolares_no_es_el_mismo_que_en_pesos() -> None:
    """Error E2: las seis columnas en dólares de la planilla no decían nada.

    Numerador y denominador se dividían por el mismo TC, así que el porcentaje
    en dólares era idéntico al de pesos. Con la conversión correcta dejan de
    coincidir, que es todo el sentido de mirar en moneda dura.
    """
    costo_ars = Decimal("1198000")
    valor_ars = Decimal("1550000")

    var_pesos = (valor_ars - costo_ars) / costo_ars

    # Costo al dólar de su fecha; valor actual al dólar de hoy.
    costo_usd = SERIE.convertir(costo_ars, date(2025, 6, 23)).monto
    valor_usd = SERIE.convertir(valor_ars, date(2025, 12, 23)).monto
    var_dolares = (valor_usd - costo_usd) / costo_usd

    # En pesos parece una ganancia del 29%; en dólares no ganaste nada. Los
    # 1.198.000 de junio eran 1.000 dólares y los 1.550.000 de diciembre
    # también: lo único que se movió fue el dólar.
    #
    # Ese 29,38% está a un pelo del 29,07% que mostraba la planilla como
    # rendimiento de la cartera.
    assert var_pesos > Decimal("0.29")
    assert var_dolares == 0
    assert var_pesos != var_dolares
