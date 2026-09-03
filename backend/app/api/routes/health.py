"""Health checks.

Dos endpoints distintos, a proposito:

  /api/health/live   ¿el proceso esta vivo? No toca dependencias.
                     Lo usa Docker para decidir si reiniciar el contenedor.

  /api/health/ready  ¿puede el sistema atender pedidos reales?
                     Verifica PostgreSQL y Redis. Devuelve 503 si algo falla.

Mezclar los dos es un error clasico: si `live` consultara la base, una caida
momentanea de Postgres haria que Docker mate un backend que estaba sano.
"""

from typing import Any

from fastapi import APIRouter, Depends, Response, status
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.redis import get_redis
from app.db.session import get_session

router = APIRouter(prefix="/health", tags=["health"])
log = get_logger("health")
settings = get_settings()


@router.get("/live", summary="Liveness: el proceso responde")
async def live() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }


@router.get("/ready", summary="Readiness: dependencias disponibles")
async def ready(
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}

    # --- PostgreSQL ---
    try:
        result = await session.execute(text("SELECT version()"))
        version = result.scalar_one()
        checks["postgres"] = {"status": "ok", "detail": version.split(",")[0]}
    except Exception as exc:  # noqa: BLE001
        log.error("readiness.postgres_failed", error=str(exc))
        checks["postgres"] = {"status": "error", "detail": str(exc)}

    # --- Redis ---
    try:
        pong = await redis.ping()
        checks["redis"] = {"status": "ok" if pong else "error", "detail": "PONG"}
    except Exception as exc:  # noqa: BLE001
        log.error("readiness.redis_failed", error=str(exc))
        checks["redis"] = {"status": "error", "detail": str(exc)}

    # --- Estado de las migraciones ---
    try:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        revision = result.scalar_one_or_none()
        checks["migrations"] = {
            "status": "ok" if revision else "error",
            "detail": revision or "sin revision aplicada",
        }
    except Exception as exc:  # noqa: BLE001
        checks["migrations"] = {"status": "error", "detail": str(exc)}

    all_ok = all(c["status"] == "ok" for c in checks.values())
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ok" if all_ok else "degraded", "checks": checks}
