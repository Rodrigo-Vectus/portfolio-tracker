"""Tareas del worker.

Ademas del latido, en F3 se agrega el refresco de cotizaciones y de tipo de
cambio.

Dos criterios que gobiernan estas tareas:

- **Una tarea que falla no rompe a las demas.** Cada refresco abre su propia
  sesion y captura sus errores. Un proveedor caido deja precios sin actualizar,
  no un worker muerto.
- **La falla se registra, no se esconde.** El servicio escribe en
  `provider_log` incluso cuando el proveedor no responde. Sin eso, un
  proveedor caido se veria como una cartera que dejo de moverse.
"""

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.db.redis import redis_client
from app.db.session import SessionLocal
from app.services import market_data

log = get_logger("worker.tasks")


async def heartbeat(ctx: dict) -> str:
    now = datetime.now(UTC).isoformat()
    await redis_client.set("worker:last_heartbeat", now)
    log.info("worker.heartbeat", timestamp=now)
    return now


async def refrescar_fx(ctx: dict) -> int:
    """Actualiza las series de tipo de cambio (D12: cada 30 minutos)."""
    async with SessionLocal() as session:
        try:
            guardadas = await market_data.refrescar_fx(session)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            # Se loguea y se sigue. El proximo ciclo vuelve a intentar, y el
            # precio anterior queda disponible con su antiguedad marcada.
            await session.rollback()
            log.error("worker.refrescar_fx.error", error=str(exc))
            return 0
    log.info("worker.refrescar_fx", guardadas=guardadas)
    return guardadas


async def refrescar_cedears(ctx: dict) -> int:
    """Actualiza el precio local de los CEDEARs del catalogo.

    D12 dice cada 15 minutos **en rueda y nada fuera de horario**. El cron la
    dispara igual y la tarea decide: consultar un mercado cerrado gasta cuota
    del proveedor para traer el mismo precio de cierre una y otra vez.
    """
    from app.domain.rueda import EstadoRueda, estado

    if estado(datetime.now(UTC)) is EstadoRueda.CERRADA:
        log.info("worker.refrescar_cedears.rueda_cerrada")
        return 0

    async with SessionLocal() as session:
        try:
            guardadas = await market_data.refrescar_cedears(session)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            log.error("worker.refrescar_cedears.error", error=str(exc))
            return 0
    log.info("worker.refrescar_cedears", guardadas=guardadas)
    return guardadas


async def refrescar_cripto(ctx: dict) -> int:
    """Actualiza las criptomonedas (D12: cada 5 minutos, 24/7)."""
    async with SessionLocal() as session:
        try:
            guardadas = await market_data.refrescar_cripto(session)
            await session.commit()
        except Exception as exc:  # noqa: BLE001
            await session.rollback()
            log.error("worker.refrescar_cripto.error", error=str(exc))
            return 0
    log.info("worker.refrescar_cripto", guardadas=guardadas)
    return guardadas
