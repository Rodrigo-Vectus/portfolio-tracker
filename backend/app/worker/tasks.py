"""Tareas del worker.

F0: solo un latido. Deja en Redis la marca `worker:last_heartbeat` para que
el readiness pueda confirmar, mas adelante, que el worker no quedo colgado.
"""

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.db.redis import redis_client

log = get_logger("worker.tasks")


async def heartbeat(ctx: dict) -> str:
    now = datetime.now(UTC).isoformat()
    await redis_client.set("worker:last_heartbeat", now)
    log.info("worker.heartbeat", timestamp=now)
    return now
