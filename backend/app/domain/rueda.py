"""Horario de rueda de BYMA.

Existe por una limitación concreta: la única fuente gratuita de precios de
CEDEARs (`data912`) no informa cuándo se cotizó cada papel. Sin esto, un precio
obtenido un domingo a la mañana y uno obtenido un martes al mediodía serían
indistinguibles, y los dos figurarían simplemente como "sin fecha".

Lo que se hace acá es **inferir** la antigüedad: si la rueda está abierta, el
último precio operado es de hoy; si está cerrada, es del último cierre.

Es una inferencia y se declara como tal. No reemplaza un timestamp del
proveedor: lo aproxima cuando no hay otro.

**Limitación conocida y no resuelta:** no contempla feriados. Un lunes feriado
se trata como día hábil, así que la antigüedad inferida va a quedar corta y el
precio se va a mostrar más fresco de lo que es. Cargar el calendario bursátil
resolvería esto; hoy no está hecho, y por eso el dato viaja siempre marcado
como estimado y nunca como confiable.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

#: Rueda de BYMA para renta variable, en horario de Buenos Aires.
#: `REQUIERE VERIFICACIÓN`: tomado del horario habitual, no confirmado contra
#: el calendario oficial. Si cambia, cambia sólo esta constante.
APERTURA = time(11, 0)
CIERRE = time(17, 0)

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


class EstadoRueda(str, Enum):
    ABIERTA = "ABIERTA"
    CERRADA = "CERRADA"


def _local(momento: datetime) -> datetime:
    if momento.tzinfo is None:
        raise ValueError("El instante tiene que traer zona horaria.")
    return momento.astimezone(ZONA)


def es_dia_habil(dia: date) -> bool:
    """Lunes a viernes. **No contempla feriados** (ver docstring del módulo)."""
    return dia.weekday() < 5


def estado(momento: datetime) -> EstadoRueda:
    local = _local(momento)
    if not es_dia_habil(local.date()):
        return EstadoRueda.CERRADA
    return (
        EstadoRueda.ABIERTA
        if APERTURA <= local.time() <= CIERRE
        else EstadoRueda.CERRADA
    )


def ultimo_cierre(momento: datetime) -> datetime:
    """Instante del cierre de rueda más reciente antes de `momento`.

    Con la rueda abierta devuelve el cierre del día hábil anterior: la sesión
    de hoy todavía no cerró.
    """
    local = _local(momento)
    dia = local.date()

    # Si hoy es hábil y ya pasó el cierre, el último cierre es el de hoy.
    if es_dia_habil(dia) and local.time() > CIERRE:
        return datetime.combine(dia, CIERRE, tzinfo=ZONA)

    # Si no, se retrocede hasta el día hábil anterior.
    dia -= timedelta(days=1)
    while not es_dia_habil(dia):
        dia -= timedelta(days=1)
    return datetime.combine(dia, CIERRE, tzinfo=ZONA)


def momento_inferido(fetched_at: datetime) -> datetime:
    """Cuándo se cotizó, probablemente, un precio obtenido en `fetched_at`.

    Con la rueda abierta, el último precio operado es de hace instantes: se
    usa el momento del pedido. Con la rueda cerrada, es el precio de cierre:
    se usa el último cierre.

    Sigue siendo una inferencia. Un papel que no operó en toda la rueda
    conserva un precio anterior, y esto lo va a datar más fresco de lo que es.
    """
    return (
        fetched_at
        if estado(fetched_at) is EstadoRueda.ABIERTA
        else ultimo_cierre(fetched_at)
    )


def descripcion(momento: datetime) -> str:
    """Cómo explicárselo a una persona, sin fingir precisión."""
    local = _local(momento)
    if estado(momento) is EstadoRueda.ABIERTA:
        return "rueda abierta"
    cierre = _local(ultimo_cierre(momento))
    if cierre.date() == local.date():
        return "cierre de hoy"
    if (local.date() - cierre.date()).days == 1:
        return "cierre de ayer"
    return f"cierre del {cierre.strftime('%d/%m/%Y')}"
