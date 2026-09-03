"""Escritura de la bitacora."""

import ipaddress
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditAction, AuditLog


def _valid_ip(value: str | None) -> str | None:
    """Devuelve el valor solo si es una IP real; None en cualquier otro caso.

    Es imprescindible: `ip_address` es una columna INET y PostgreSQL rechaza
    todo lo que no sea una direccion valida, abortando la transaccion que la
    incluya. Como `X-Forwarded-For` lo controla quien hace el pedido, sin esta
    validacion bastaria enviar un encabezado con basura para tumbar el login
    con un error 500.

    Ante la duda se guarda NULL. Perder la IP de una entrada de auditoria es
    infinitamente menos grave que perder la operacion completa.
    """
    if not value:
        return None
    try:
        ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    return value.strip()


def client_user_agent(request: Request | None) -> str | None:
    """User agent recortado, o None.

    El encabezado es opcional: un cliente HTTP crudo puede no enviarlo, y
    recortar None revienta. La columna admite 255 caracteres, asi que tambien
    hay que truncar antes de insertar.
    """
    if request is None:
        return None
    value = request.headers.get("user-agent")
    return value[:255] if value else None


def client_ip(request: Request | None) -> str | None:
    """IP del cliente, mirando X-Forwarded-For si hay un proxy adelante.

    Se toma el primer valor de la cadena, que es el cliente original. El
    encabezado es falsificable mientras no haya un reverse proxy que lo
    reescriba (llega en F9), por eso todo lo que salga de aca pasa por
    `_valid_ip` antes de tocar la base.
    """
    if request is None:
        return None

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        candidate = _valid_ip(forwarded.split(",")[0])
        if candidate:
            return candidate

    return _valid_ip(request.client.host if request.client else None)


async def record(
    session: AsyncSession,
    action: AuditAction,
    *,
    user_id: UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Agrega una entrada. No hace commit: se suma a la transaccion en curso."""
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=client_ip(request),
            user_agent=client_user_agent(request),
        )
    )
