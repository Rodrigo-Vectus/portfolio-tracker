"""Configuracion del worker de tareas en segundo plano.

Se usa ARQ en lugar de Celery: es async nativo (mismo modelo de concurrencia
que FastAPI), pesa mucho menos y no necesita un broker aparte de Redis, que
igual hace falta para cache de cotizaciones.

En F0 solo corre un latido que prueba que la cadena worker -> Redis funciona.
Las tareas reales (refresco de precios, FX, snapshots) llegan en F3 y F5.
"""

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.worker.tasks import heartbeat

settings = get_settings()
configure_logging()
log = get_logger("worker")


async def startup(ctx: dict) -> None:
    log.info("worker.startup", environment=settings.app_env)


async def shutdown(ctx: dict) -> None:
    log.info("worker.shutdown")


class WorkerSettings:
    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        database=settings.redis_db,
    )
    functions = [heartbeat]
    cron_jobs = [
        # Cada 5 minutos: deja rastro de que el worker esta vivo.
        cron(heartbeat, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
