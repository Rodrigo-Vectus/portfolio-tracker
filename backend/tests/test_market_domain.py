"""Frescura de las cotizaciones y totalización de la cartera.

Acá vive la regla que originó el proyecto: **nunca presentar un precio viejo
como actual**. Estas pruebas existen para que esa regla sea verificable y no
una intención escrita en un documento.

Python puro. Sin red, sin base.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.domain.market import (
    Cotizacion,
    Frescura,
    ValorDePosicion,
    totalizar,
    variacion_diaria,
)

AHORA = datetime(2026, 9, 4, 20, 0, tzinfo=UTC)


def cotiz(
    precio: str,
    *,
    hace: timedelta | None = None,
    tipo: str = "CEDEAR",
    estimado_hace: timedelta | None = None,
):
    return Cotizacion(
        symbol="AAPL",
        price=Decimal(precio),
        currency="ARS",
        source="prueba",
        fetched_at=AHORA,
        quoted_at=None if hace is None else AHORA - hace,
        asset_type=tipo,
        momento_estimado=None if estimado_hace is None else AHORA - estimado_hace,
    )


def pos(cantidad: str, cotizacion, frescura: Frescura) -> ValorDePosicion:
    return ValorDePosicion(
        symbol="AAPL",
        quantity=Decimal(cantidad),
        cotizacion=cotizacion,
        frescura=frescura,
    )


# ------------------------------------------------------------------ frescura


def test_una_estimacion_no_se_confunde_con_un_hecho() -> None:
    """`quoted_at` sigue en None aunque haya estimación.

    Son campos distintos a propósito. Copiar la estimación a `quoted_at`
    convertiría una inferencia en un dato del proveedor, y después nadie
    podría distinguirlos.
    """
    c = cotiz("20960", estimado_hace=timedelta(hours=3))
    assert c.quoted_at is None
    assert not c.es_confiable
    assert c.frescura(AHORA) is Frescura.ESTIMADA


def test_una_estimacion_vieja_sigue_siendo_vieja() -> None:
    """Saber de qué cierre es un precio no lo vuelve actual.

    Un precio del cierre de hace cinco días es viejo aunque sepamos
    exactamente de cuándo es.
    """
    c = cotiz("20960", estimado_hace=timedelta(days=5))
    assert c.frescura(AHORA) is Frescura.VIEJA


def test_sin_fecha_del_proveedor_no_se_puede_saber_la_antiguedad() -> None:
    """`antiguedad()` devuelve None, no la antigüedad del pedido.

    Responder con `ahora - fetched_at` contestaría otra pregunta: cuánto hace
    que preguntamos, no cuánto hace que el mercado lo dijo. Entre las dos
    puede haber un fin de semana.
    """
    c = cotiz("20960")
    assert c.antiguedad(AHORA) is None
    assert c.frescura(AHORA) is Frescura.SIN_FECHA
    assert not c.es_confiable


def test_una_cotizacion_dentro_del_umbral_es_fresca() -> None:
    c = cotiz("20960", hace=timedelta(hours=2))
    assert c.frescura(AHORA) is Frescura.FRESCA
    assert c.antiguedad(AHORA) == timedelta(hours=2)


def test_una_cotizacion_pasado_el_umbral_es_vieja() -> None:
    assert cotiz("20960", hace=timedelta(days=2)).frescura(AHORA) is Frescura.VIEJA


# ------------------------------------------------- total de cartera (D34)


def test_el_total_se_calcula_cuando_todo_esta_fresco() -> None:
    valores = [
        pos("10", cotiz("20960", hace=timedelta(hours=1)), Frescura.FRESCA),
        pos("5", cotiz("25000", hace=timedelta(hours=1)), Frescura.FRESCA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert t.es_completo
    assert t.total is not None
    assert t.total.amount == Decimal(10) * Decimal(20960) + Decimal(5) * Decimal(25000)
    assert t.motivo_incompleto is None


def test_una_sola_posicion_vieja_invalida_el_total() -> None:
    """El color de una fila no viaja hasta la suma.

    Una posición vieja marcada en pantalla se lee como vieja. Un total con una
    posición vieja adentro se lee como completo, y ahí está el engaño. Por eso
    el total no se entrega como número.
    """
    valores = [
        pos("10", cotiz("20960", hace=timedelta(hours=1)), Frescura.FRESCA),
        pos("5", cotiz("25000", hace=timedelta(days=3)), Frescura.VIEJA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert not t.es_completo
    assert t.total is None
    assert "1 con precio viejo" in t.motivo_incompleto


def test_una_antiguedad_estimada_no_invalida_el_total_pero_lo_marca() -> None:
    """D34-bis. Es el caso real de los CEDEARs.

    `data912` no informa cuándo se cotizó, pero la antigüedad se infiere desde
    el horario de rueda. Ocultar el total dejaría al usuario sin lo que más le
    importa; mostrarlo sin marcar sería presentar una estimación como un
    hecho. Se muestra y se marca.
    """
    valores = [
        pos("10", cotiz("20960", estimado_hace=timedelta(hours=3)), Frescura.ESTIMADA),
        pos("5", cotiz("25000", hace=timedelta(hours=1)), Frescura.FRESCA),
    ]
    t = totalizar(valores, "ARS", AHORA)

    assert t.total is not None
    assert t.total.amount == Decimal(10) * Decimal(20960) + Decimal(5) * Decimal(25000)
    # Se calculó, pero no es lo mismo que un total completo.
    assert not t.es_completo
    assert t.es_estimado
    assert "1 con antigüedad estimada" in t.motivo_incompleto


def test_una_posicion_sin_ninguna_fecha_si_invalida_el_total() -> None:
    """Sin fecha del proveedor y sin forma de inferirla, no hay número.""" 
    valores = [
        pos("10", cotiz("20960"), Frescura.SIN_FECHA),
        pos("5", cotiz("25000", hace=timedelta(hours=1)), Frescura.FRESCA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert t.total is None
    assert "1 sin fecha de cotización" in t.motivo_incompleto


def test_una_posicion_sin_cotizacion_invalida_el_total() -> None:
    valores = [
        pos("10", cotiz("20960", hace=timedelta(hours=1)), Frescura.FRESCA),
        pos("5", None, Frescura.AUSENTE),
    ]
    t = totalizar(valores, "ARS", AHORA)
    assert t.total is None
    assert "1 sin cotización" in t.motivo_incompleto
    assert t.posiciones_sin_precio == 1


def test_el_motivo_acumula_todos_los_problemas() -> None:
    """Decir sólo el primero obligaría a arreglar de a uno para enterarse."""
    valores = [
        pos("1", None, Frescura.AUSENTE),
        pos("1", cotiz("100", hace=timedelta(days=5)), Frescura.VIEJA),
        pos("1", cotiz("100"), Frescura.SIN_FECHA),
        pos("1", cotiz("100", estimado_hace=timedelta(hours=2)), Frescura.ESTIMADA),
    ]
    t = totalizar(valores, "ARS", AHORA)
    motivo = t.motivo_incompleto
    assert "1 sin cotización" in motivo
    assert "1 con precio viejo" in motivo
    assert "1 sin fecha de cotización" in motivo
    assert "1 con antigüedad estimada" in motivo


def test_una_cartera_vacia_no_finge_un_total_en_cero() -> None:
    """Cero pesos y "no hay nada" no son lo mismo."""
    t = totalizar([], "ARS", AHORA)
    assert t.total is None
    assert t.posiciones_totales == 0


# ------------------------------------------------------ variacion diaria (F10)


def test_la_variacion_se_calcula_contra_el_cierre_informado() -> None:
    v = variacion_diaria(Decimal("110"), Decimal("100"), date(2026, 9, 10))
    assert v is not None
    assert v.fraccion == Decimal("0.1")
    assert v.desde == date(2026, 9, 10)


def test_una_baja_da_negativo() -> None:
    v = variacion_diaria(Decimal("90"), Decimal("100"), date(2026, 9, 10))
    assert v is not None
    assert v.fraccion == Decimal("-0.1")


def test_sin_cierre_anterior_no_hay_variacion_y_tampoco_cero() -> None:
    """Cero afirmaria que el precio no se movio.

    "No se movio" y "no se contra que compararlo" son afirmaciones distintas, y
    un cero en una columna de variacion se lee como la primera.
    """
    assert variacion_diaria(Decimal("110"), None, date(2026, 9, 10)) is None
    assert variacion_diaria(None, Decimal("100"), date(2026, 9, 10)) is None
    assert variacion_diaria(Decimal("110"), Decimal("100"), None) is None


def test_un_cierre_en_cero_no_produce_un_porcentaje() -> None:
    """La division no existe, y un numero inventado es peor que la ausencia."""
    assert variacion_diaria(Decimal("110"), Decimal("0"), date(2026, 9, 10)) is None


def test_la_fecha_del_cierre_viaja_con_el_numero() -> None:
    """Sin calendario de feriados, un lunes feriado compara contra el jueves.

    Llamar a eso "24 horas" seria mentir, asi que se transporta la fecha del
    cierre que se uso y la pantalla la muestra.
    """
    v = variacion_diaria(Decimal("110"), Decimal("100"), date(2026, 9, 4))
    assert v is not None
    assert v.desde == date(2026, 9, 4)
    assert v.cierre_anterior == Decimal("100")
