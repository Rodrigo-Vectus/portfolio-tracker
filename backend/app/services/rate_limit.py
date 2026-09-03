"""Freno de intentos de login.

Cuenta fallos en Redis por email y por IP. Las dos claves importan: por email
para que nadie martille una cuenta concreta, por IP para que nadie recorra
muchas cuentas desde el mismo lugar.

El contador se borra al primer login exitoso. Si Redis no esta disponible el
freno se desactiva en lugar de bloquear el ingreso: perder el limite es
menos grave que dejar a la persona afuera de su propia plataforma. La falla
queda logueada.
"""

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
log = get_logger("rate_limit")


def _keys(email: str, ip: str | None) -> list[str]:
    keys = [f"login:fail:email:{email.lower()}"]
    if ip:
        keys.append(f"login:fail:ip:{ip}")
    return keys


async def is_locked(redis: Redis, email: str, ip: str | None) -> bool:
    try:
        for key in _keys(email, ip):
            value = await redis.get(key)
            if value and int(value) >= settings.login_max_attempts:
                return True
        return False
    except Exception as exc:  # noqa: BLE001
        log.error("rate_limit.unavailable", error=str(exc))
        return False


async def register_failure(redis: Redis, email: str, ip: str | None) -> None:
    try:
        ttl = settings.login_lockout_minutes * 60
        for key in _keys(email, ip):
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, ttl)
    except Exception as exc:  # noqa: BLE001
        log.error("rate_limit.unavailable", error=str(exc))


async def clear(redis: Redis, email: str, ip: str | None) -> None:
    try:
        await redis.delete(*_keys(email, ip))
    except Exception as exc:  # noqa: BLE001
        log.error("rate_limit.unavailable", error=str(exc))
