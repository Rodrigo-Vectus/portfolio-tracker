"""Normalizacion de fechas.

Existe por un bug concreto: el historial sale de PostgreSQL con zona horaria
(`TIMESTAMPTZ`) y una operacion recien llegada del JSON puede no tenerla.
Ordenarlas juntas revienta con "can't compare offset-naive and offset-aware
datetimes", y ese error aparece **en el motor de lotes**, lejos de donde se
origina.

La decision de fondo no es tecnica. Una fecha sin zona es un dato ambiguo, y
hay que elegir que significa:

- Asumir UTC seria inventar un dato. Una compra cargada a las 22:30 en Buenos
  Aires quedaria fechada al dia siguiente y su `trade_date` saldria mal, que
  en una cartera argentina significa mover operaciones a otra rueda.
- Rechazarla con un 422 es defendible, pero obliga a cada cliente a construir
  el offset a mano, y un `<input type="datetime-local">` de HTML no lo manda.

Se elige interpretarla en la zona configurada del sistema
(`DEFAULT_TIMEZONE`), que es coherente con `trade_date` ya definido como dia
de rueda porteno. La convencion queda documentada aca y en el endpoint, en vez
de vivir escondida en una conversion.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings


@lru_cache(maxsize=8)
def zona_local(nombre: str | None = None) -> ZoneInfo:
    """Zona horaria configurada del sistema.

    Falla de forma explicita si la base de datos de zonas no esta disponible
    en la imagen. Caer a UTC en silencio seria mover las operaciones tres
    horas sin que nadie se entere, que es peor que no arrancar.
    """
    tz = nombre or get_settings().default_timezone
    try:
        return ZoneInfo(tz)
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(
            f"No se encontro la zona horaria '{tz}'. Falta tzdata en la imagen. "
            "No se asume UTC a proposito: correria las fechas sin aviso."
        ) from exc


def con_zona(momento: datetime, *, tz: str | None = None) -> datetime:
    """Devuelve el instante con zona, interpretando lo ambiguo como local.

    Si ya trae zona, se respeta tal cual: el cliente fue explicito y no
    corresponde reinterpretarlo.
    """
    if momento.tzinfo is not None:
        return momento
    return momento.replace(tzinfo=zona_local(tz))


def a_utc(momento: datetime, *, tz: str | None = None) -> datetime:
    """Normaliza a UTC para persistir y comparar."""
    return con_zona(momento, tz=tz).astimezone(UTC)


def fecha_de_rueda(momento: datetime, *, tz: str | None = None):
    """Dia de rueda del instante, en la zona local.

    No es `momento.date()`: una operacion de las 22:30 en Buenos Aires es
    01:30 UTC del dia siguiente, y tomar la fecha en UTC la mandaria a otra
    rueda. Los CEDEARs cotizan en horario local; las criptomonedas 24/7, pero
    el corte del dia sigue siendo local para poder agrupar.
    """
    return con_zona(momento, tz=tz).astimezone(zona_local(tz)).date()
