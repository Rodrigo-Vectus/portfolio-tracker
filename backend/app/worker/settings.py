"""Configuracion del worker de tareas en segundo plano.

Se usa ARQ en lugar de Celery: es async nativo (mismo modelo de concurrencia
que FastAPI), pesa mucho menos y no necesita un broker aparte de Redis, que
igual hace falta para cache de cotizaciones.

Ademas del latido, en F3 corren los refrescos de cotizaciones y tipo de cambio
con las frecuencias de D12. Los snapshots llegan en F5.
"""

from arq.connections import RedisSettings
from arq.cron import cron

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.worker.tasks import (
    heartbeat,
    refrescar_cedears,
    refrescar_cripto,
    refrescar_fx,
)

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
    functions = [heartbeat, refrescar_fx, refrescar_cedears, refrescar_cripto]
    cron_jobs = [
        # Cada 5 minutos: deja rastro de que el worker esta vivo.
        cron(heartbeat, minute={0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}),
        # Frecuencias de D12. Los minutos estan corridos entre si a proposito:
        # arrancar las tres tareas en el mismo instante concentra la carga y
        # hace mas dificil leer los logs cuando algo falla.
        cron(refrescar_cripto, minute={1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56}),
        cron(refrescar_cedears, minute={2, 17, 32, 47}),
        cron(refrescar_fx, minute={3, 33}),
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    job_timeout = 300
