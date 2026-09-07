"""ROI y XIRR.

Los casos del XIRR están elegidos para que la respuesta se conozca **antes**
de correr el código: duplicar la plata en un año es 100%, recuperar lo mismo
que pusiste es 0%. Un test que sólo comprueba que el número no cambió no
detecta que estuvo mal desde el principio.

Python puro: sin base de datos.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.domain.performance import (
    Flujo,
    XirrNoConverge,
    roi_de_posicion,
    xirr,
)


def f(anio: int, mes: int, dia: int, monto: str) -> Flujo:
    return Flujo(date(anio, mes, dia), Decimal(monto))


# ------------------------------------------------------------------- XIRR


def test_duplicar_en_un_anio_es_cien_por_ciento() -> None:
    """Pongo 1.000, saco 2.000 un año después. La tasa anual es 100%."""
    tasa = xirr([f(2025, 1, 1, "-1000"), f(2026, 1, 1, "2000")])
    assert abs(tasa - Decimal(1)) < Decimal("0.001")


def test_recuperar_lo_mismo_es_cero_por_ciento() -> None:
    """Sin ganancia no hay tasa: ni positiva ni negativa."""
    tasa = xirr([f(2025, 1, 1, "-1000"), f(2026, 1, 1, "1000")])
    assert abs(tasa) < Decimal("0.001")


def test_perder_la_mitad_en_un_anio_es_menos_cincuenta() -> None:
    tasa = xirr([f(2025, 1, 1, "-1000"), f(2026, 1, 1, "500")])
    assert abs(tasa - Decimal("-0.5")) < Decimal("0.001")


def test_el_tiempo_importa() -> None:
    """La misma ganancia en menos tiempo es una tasa mayor.

    Es exactamente lo que un porcentaje simple no distingue: ganar 10% en un
    mes y 10% en tres años se verían iguales.
    """
    en_un_anio = xirr([f(2025, 1, 1, "-1000"), f(2026, 1, 1, "1100")])
    en_seis_meses = xirr([f(2025, 1, 1, "-1000"), f(2025, 7, 1, "1100")])
    assert en_seis_meses > en_un_anio * Decimal("1.8")


def test_aportes_en_distintas_fechas() -> None:
    """Dos depósitos y un valor final.

    Es el caso que el ROI simple no puede medir: el segundo aporte estuvo
    invertido la mitad del tiempo que el primero, y eso cambia el rendimiento.
    """
    tasa = xirr([
        f(2025, 1, 1, "-1000"),
        f(2025, 7, 1, "-1000"),
        f(2026, 1, 1, "2300"),
    ])
    # Ganancia de 300 sobre aportes escalonados: bastante más que el 15% que
    # daría dividir 300 por 2.000 sin mirar las fechas.
    assert tasa > Decimal("0.15")
    assert tasa < Decimal("0.35")


def test_un_retiro_intermedio_se_considera() -> None:
    tasa = xirr([
        f(2025, 1, 1, "-10000"),
        f(2025, 6, 1, "3000"),
        f(2026, 1, 1, "8000"),
    ])
    assert tasa > Decimal("0.05")


def test_todos_los_flujos_del_mismo_signo_no_tienen_tasa() -> None:
    """Comprar sin haber registrado el depósito deja sólo salidas.

    Se avisa con un mensaje que dice qué falta, en vez de devolver un número.
    """
    with pytest.raises(XirrNoConverge, match="mismo signo"):
        xirr([f(2025, 1, 1, "-1000"), f(2025, 6, 1, "-500")])


def test_flujos_del_mismo_dia_no_tienen_tasa_anual() -> None:
    """Sin tiempo transcurrido no hay tasa anual que calcular."""
    with pytest.raises(XirrNoConverge, match="mismo día"):
        xirr([f(2025, 1, 1, "-1000"), f(2025, 1, 1, "1100")])


def test_un_solo_flujo_no_alcanza() -> None:
    with pytest.raises(XirrNoConverge):
        xirr([f(2025, 1, 1, "-1000")])


def test_el_resultado_es_decimal_exacto() -> None:
    """Nunca float, tampoco acá.

    Un porcentaje que pasa por doble precisión se ve bien y arrastra un error
    que aparece al multiplicarlo por un patrimonio.
    """
    tasa = xirr([f(2025, 1, 1, "-1000"), f(2026, 1, 1, "1500")])
    assert isinstance(tasa, Decimal)


# -------------------------------------------------------------------- ROI


def test_roi_sobre_el_costo_de_lo_abierto() -> None:
    """Costo 1.000, vale 1.250. ROI 25%."""
    r = roi_de_posicion("AAPL", Decimal(1000), Decimal(1250))
    assert r.roi == Decimal("0.25")
    assert r.no_realizado == Decimal(250)
    assert r.calculable


def test_roi_negativo() -> None:
    r = roi_de_posicion("AAPL", Decimal(1000), Decimal(800))
    assert r.roi == Decimal("-0.2")


def test_sin_cotizacion_no_hay_roi() -> None:
    """`None` y no cero: no saber cuánto vale no es no haber ganado nada."""
    r = roi_de_posicion("AAPL", Decimal(1000), None)
    assert r.roi is None
    assert r.no_realizado is None
    assert not r.calculable


def test_costo_cero_no_da_roi() -> None:
    """Un ROI sobre denominador cero no es infinito: no existe."""
    assert roi_de_posicion("AAPL", Decimal(0), Decimal(500)).roi is None


def test_el_roi_no_se_infla_al_vender() -> None:
    """El defecto central de la fórmula de la planilla.

    Su denominador era compras menos ventas, que se achica en cada venta. Acá
    el denominador es el costo de lo que queda abierto: vender parte de la
    posición no cambia el ROI de lo que sigue en cartera.

    Posición de 10 a 100. Se venden 6: quedan 4 con costo 400. Si el precio no
    se movió, el ROI sigue siendo 0%, no un número inflado.
    """
    antes = roi_de_posicion("AAPL", Decimal(1000), Decimal(1000))
    despues = roi_de_posicion("AAPL", Decimal(400), Decimal(400))
    assert antes.roi == despues.roi == Decimal(0)
