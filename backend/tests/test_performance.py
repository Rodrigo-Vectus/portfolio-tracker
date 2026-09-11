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
    ZERO,
    Flujo,
    PuntoDeTwr,
    XirrNoConverge,
    roi_de_posicion,
    twr,
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


# -------------------------------------------------------------------- TWR


def pt(dia: int, patrimonio: str | None, flujo: str = "0") -> PuntoDeTwr:
    """Un punto de la serie en enero de 2026, para no repetir la fecha."""
    return PuntoDeTwr(
        fecha=date(2026, 1, dia),
        patrimonio=None if patrimonio is None else Decimal(patrimonio),
        flujo=Decimal(flujo),
    )


def test_un_deposito_no_es_rendimiento() -> None:
    """La cartera vale 100, entran 100, vale 200. No rindió nada: 0%.

    Es la prueba que justifica que el TWR exista. El XIRR sobre estos mismos
    datos tampoco daría 0, y está bien: mide otra cosa.
    """
    r = twr([pt(1, "100"), pt(2, "200", flujo="100")])
    assert r.acumulado is not None
    assert abs(r.acumulado) < Decimal("0.000001")


def test_un_retiro_no_es_perdida() -> None:
    """Vale 200, se retiran 100, queda 100. Tampoco pasó nada: 0%."""
    r = twr([pt(1, "200"), pt(2, "100", flujo="-100")])
    assert r.acumulado is not None
    assert abs(r.acumulado) < Decimal("0.000001")


def test_los_tramos_se_multiplican_no_se_suman() -> None:
    """100 → 110 → 121 es 21%, no 20%. El interés compuesto no es opcional."""
    r = twr([pt(1, "100"), pt(2, "110"), pt(3, "121")])
    assert r.acumulado is not None
    assert abs(r.acumulado - Decimal("0.21")) < Decimal("0.000001")
    assert r.subperiodos == 2


def test_el_flujo_va_al_denominador() -> None:
    """100, entran 100, cierra en 220: rindió 10% sobre los 200, no 120%.

    Si el depósito no entrara al denominador el tramo daría 220/100−1 = 120%:
    plata que entró leída como plata que se ganó.
    """
    r = twr([pt(1, "100"), pt(2, "220", flujo="100")])
    assert r.acumulado is not None
    assert abs(r.acumulado - Decimal("0.10")) < Decimal("0.000001")


def test_el_aporte_bien_timeado_no_mejora_el_twr() -> None:
    """Dos carteras con el mismo rendimiento y aportes distintos empatan.

    Es exactamente lo que el TWR promete: no premia haber acertado el momento
    de poner la plata. El XIRR sí, y por eso conviven.
    """
    sin_aporte = twr([pt(1, "100"), pt(2, "110"), pt(3, "121")])
    con_aporte = twr([pt(1, "100"), pt(2, "1210", flujo="1000"), pt(3, "1331")])
    assert sin_aporte.acumulado is not None and con_aporte.acumulado is not None
    assert abs(sin_aporte.acumulado - con_aporte.acumulado) < Decimal("0.000001")


def test_un_hueco_corta_la_serie_y_lo_dice() -> None:
    """Un día sin valuar no se saltea: se calcula desde el hueco en adelante."""
    r = twr([pt(1, "100"), pt(2, None), pt(3, "100"), pt(4, "110")])
    assert r.desde == date(2026, 1, 3)
    assert r.subperiodos == 1
    assert r.corte is not None
    assert abs((r.acumulado or ZERO) - Decimal("0.10")) < Decimal("0.000001")


def test_sin_hueco_no_se_avisa_de_un_corte() -> None:
    r = twr([pt(1, "100"), pt(2, "110")])
    assert r.corte is None


def test_se_usa_el_tramo_mas_reciente_no_el_mas_largo() -> None:
    """Un bloque viejo y extenso describe una cartera que ya no existe."""
    r = twr(
        [pt(1, "100"), pt(2, "110"), pt(3, "120"), pt(4, None), pt(5, "50"), pt(6, "55")]
    )
    assert r.desde == date(2026, 1, 5)
    assert r.subperiodos == 1


def test_un_solo_dia_valuado_no_alcanza() -> None:
    """Con un punto no hay tramo que encadenar. Se dice, no se devuelve cero."""
    r = twr([pt(1, "100")])
    assert r.acumulado is None
    assert r.motivo is not None


def test_serie_vacia_no_explota() -> None:
    r = twr([])
    assert r.acumulado is None
    assert r.desde is None


def test_capital_negativo_no_produce_un_porcentaje() -> None:
    """Con patrimonio negativo el porcentaje no significa nada. Se declara.

    Pasa cuando hay compras sin el depósito que las financió: la caja queda en
    rojo y el patrimonio puede dar negativo.
    """
    r = twr([pt(1, "-500"), pt(2, "-400")])
    assert r.acumulado is None
    assert r.motivo is not None and "caja" in r.motivo


def test_no_se_anualiza_una_serie_corta() -> None:
    """Un 2% en dos días anualizado daría más de 1.000%. No se muestra."""
    r = twr([pt(1, "100"), pt(3, "102")])
    assert r.acumulado is not None
    assert r.anualizado is None
    assert r.motivo is not None


def test_se_anualiza_con_serie_suficiente() -> None:
    """10% en 365 días es 10% anual. Sin sorpresas."""
    r = twr(
        [
            PuntoDeTwr(date(2025, 1, 1), Decimal("100")),
            PuntoDeTwr(date(2026, 1, 1), Decimal("110")),
        ]
    )
    assert r.anualizado is not None
    assert abs(r.anualizado - Decimal("0.10")) < Decimal("0.001")
    assert r.dias == 365


def test_medio_anio_al_diez_por_ciento_anualiza_a_veintiuno() -> None:
    """Ganar 10% en medio año y repetirlo da 21%, no 20%."""
    r = twr(
        [
            PuntoDeTwr(date(2025, 1, 1), Decimal("100")),
            PuntoDeTwr(date(2025, 7, 2), Decimal("110")),
        ]
    )
    assert r.anualizado is not None
    assert abs(r.anualizado - Decimal("0.21")) < Decimal("0.01")


def test_una_perdida_total_no_rompe_el_calculo() -> None:
    """Si la cartera cae a cero el TWR es −100%, no un error."""
    r = twr([pt(1, "100"), pt(2, "0")])
    assert r.acumulado is not None
    assert abs(r.acumulado - Decimal("-1")) < Decimal("0.000001")
    assert r.anualizado is None


def test_la_caja_en_rojo_se_declara_sin_invalidar_el_numero() -> None:
    """Una caja negativa achica el denominador: el número sale amplificado.

    No se oculta ni se corrige la fórmula. Se muestra con la advertencia al
    lado, que es la misma distinción que sostiene D34-bis: un dato con
    advertencia no es un dato con mentira.
    """
    r = twr(
        [
            PuntoDeTwr(date(2026, 9, 8), Decimal("15260"), caja=Decimal("-338900")),
            PuntoDeTwr(date(2026, 9, 9), Decimal("12480"), caja=Decimal("-338900")),
        ]
    )
    assert r.acumulado is not None
    assert r.advertencia is not None and "depósito" in r.advertencia


def test_sin_caja_negativa_no_hay_advertencia() -> None:
    r = twr(
        [
            PuntoDeTwr(date(2026, 1, 1), Decimal("100"), caja=Decimal("10")),
            PuntoDeTwr(date(2026, 1, 2), Decimal("110"), caja=Decimal("10")),
        ]
    )
    assert r.advertencia is None


def test_la_caja_no_entra_al_calculo() -> None:
    """`caja` sólo se transporta para avisar: no cambia ni un dígito.

    El patrimonio ya la tiene adentro. Si además se restara o sumara acá,
    estaría contada dos veces.
    """
    con = twr([pt(1, "100"), pt(2, "110")])
    sin = twr(
        [
            PuntoDeTwr(date(2026, 1, 1), Decimal("100"), caja=Decimal("-9999")),
            PuntoDeTwr(date(2026, 1, 2), Decimal("110"), caja=Decimal("-9999")),
        ]
    )
    assert con.acumulado == sin.acumulado
