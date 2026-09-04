"""Horario de rueda y antigüedad inferida.

Existe porque la única fuente gratuita de CEDEARs no dice cuándo se cotizó
cada papel. Sin esto, un precio traído un domingo y uno traído un martes al
mediodía serían indistinguibles.

Es una inferencia y las pruebas la tratan como tal: verifican que sea
razonable, no que sea exacta.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.rueda import (
    EstadoRueda,
    descripcion,
    es_dia_habil,
    estado,
    momento_inferido,
    ultimo_cierre,
)

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def ba(a: int, m: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(a, m, d, h, mi, tzinfo=ZONA)


# 2026-09-04 es viernes; 05 sábado; 06 domingo; 07 lunes.


def test_la_rueda_esta_abierta_en_horario_habil() -> None:
    assert estado(ba(2026, 9, 4, 13)) is EstadoRueda.ABIERTA


def test_la_rueda_esta_cerrada_antes_y_despues() -> None:
    assert estado(ba(2026, 9, 4, 9)) is EstadoRueda.CERRADA
    assert estado(ba(2026, 9, 4, 20)) is EstadoRueda.CERRADA


def test_el_fin_de_semana_la_rueda_esta_cerrada() -> None:
    assert not es_dia_habil(ba(2026, 9, 5, 13).date())
    assert estado(ba(2026, 9, 5, 13)) is EstadoRueda.CERRADA
    assert estado(ba(2026, 9, 6, 13)) is EstadoRueda.CERRADA


def test_con_la_rueda_abierta_el_precio_es_de_ahora() -> None:
    momento = ba(2026, 9, 4, 13)
    assert momento_inferido(momento) == momento


def test_con_la_rueda_cerrada_el_precio_es_del_ultimo_cierre() -> None:
    """A las 20:00 del viernes, el último precio operado es el del cierre."""
    assert momento_inferido(ba(2026, 9, 4, 20)) == ba(2026, 9, 4, 17)


def test_el_domingo_el_precio_es_del_viernes() -> None:
    """Sin esto, un precio traído el domingo figuraría como de hoy.

    Es la diferencia entre "obtenido recién" y "el mercado lo dijo hace dos
    días", que es justamente lo que hay que poder distinguir.
    """
    assert momento_inferido(ba(2026, 9, 6, 13)) == ba(2026, 9, 4, 17)


def test_antes_de_la_apertura_el_precio_es_del_dia_anterior() -> None:
    """El lunes a las 9 todavía rige el cierre del viernes."""
    assert momento_inferido(ba(2026, 9, 7, 9)) == ba(2026, 9, 4, 17)


def test_la_descripcion_es_entendible() -> None:
    """El usuario lee "cierre del viernes", no una marca de tiempo ISO."""
    assert descripcion(ba(2026, 9, 4, 13)) == "rueda abierta"
    assert descripcion(ba(2026, 9, 4, 20)) == "cierre de hoy"
    assert descripcion(ba(2026, 9, 5, 13)) == "cierre de ayer"
    assert "04/09/2026" in descripcion(ba(2026, 9, 6, 13))


def test_ultimo_cierre_con_la_rueda_abierta_es_el_dia_anterior() -> None:
    """La sesión de hoy todavía no cerró."""
    assert ultimo_cierre(ba(2026, 9, 4, 13)) == ba(2026, 9, 3, 17)
