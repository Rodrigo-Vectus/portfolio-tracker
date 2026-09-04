"""Normalizacion de fechas.

Regresion de un bug que **paso 23 pruebas de dominio sin ser detectado**: en
esas pruebas todas las fechas las construia yo y todas eran naive, asi que
nunca se mezclaron con las que salen de PostgreSQL con zona.

Solo aparecio al registrar una segunda operacion contra un historial ya
persistido, y el error salto en el motor de lotes, lejos de su causa. Es el
mismo patron que el bug de la columna INET.

No requieren base de datos.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.timezones import a_utc, con_zona, fecha_de_rueda

TZ = "America/Argentina/Buenos_Aires"


def test_una_fecha_sin_zona_se_interpreta_como_local() -> None:
    """22:30 en Buenos Aires son las 01:30 UTC del dia siguiente."""
    resultado = a_utc(datetime(2025, 6, 2, 22, 30), tz=TZ)
    assert resultado.hour == 1
    assert resultado.day == 3
    assert resultado.tzinfo is timezone.utc


def test_no_se_asume_utc() -> None:
    """Asumir UTC correria la operacion tres horas sin avisar.

    Es la diferencia entre registrar un hecho y inventarlo.
    """
    naive = datetime(2025, 6, 2, 22, 30)
    assert a_utc(naive, tz=TZ) != naive.replace(tzinfo=timezone.utc)


def test_un_offset_explicito_se_respeta() -> None:
    """Si el cliente fue explicito, no corresponde reinterpretarlo."""
    aware = datetime(2025, 6, 2, 22, 30, tzinfo=timezone(timedelta(hours=9)))
    assert a_utc(aware, tz=TZ) == aware.astimezone(timezone.utc)
    assert con_zona(aware, tz=TZ) is aware


def test_la_rueda_es_el_dia_local_y_no_el_utc() -> None:
    """Una compra de las 22:30 pertenece a la rueda de ese dia, no del siguiente.

    Tomar la fecha sobre el instante en UTC la mandaria a otra rueda, y con
    eso todo el agrupamiento por dia queda corrido.
    """
    momento = datetime(2025, 6, 2, 22, 30)
    assert fecha_de_rueda(momento, tz=TZ) == date(2025, 6, 2)
    assert a_utc(momento, tz=TZ).date() == date(2025, 6, 3)


def test_se_pueden_ordenar_fechas_de_ambos_origenes() -> None:
    """El bug exacto: historial con zona mas operacion nueva sin zona."""
    de_la_base = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    del_json = datetime(2025, 6, 2, 12, 0)

    with pytest.raises(TypeError):
        sorted([de_la_base, del_json])

    ordenadas = sorted([de_la_base, con_zona(del_json, tz=TZ)])
    assert ordenadas[0] == de_la_base
