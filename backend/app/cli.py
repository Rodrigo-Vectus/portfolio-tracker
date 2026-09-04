"""Comandos de mantenimiento.

    python -m app.cli seed-admin           crea o repara el administrador inicial
    python -m app.cli rebuild-positions    recalcula posiciones desde el libro

Es idempotente: si el administrador ya existe no lo pisa, solo informa. La
contrasena sale de INITIAL_ADMIN_PASSWORD y nunca queda en el codigo ni en
la base en texto plano.
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import AuditAction, AuditLog, Portfolio, User, UserRole
from app.services.positions import rebuild_portfolio

settings = get_settings()
configure_logging()
log = get_logger("cli")


async def seed_admin() -> int:
    email = settings.initial_admin_email.strip().lower()
    password = settings.initial_admin_password

    if not email or not password:
        log.warning(
            "seed_admin.skipped",
            reason="faltan INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD",
        )
        return 0  # no es un error fatal: la app puede levantar igual

    if len(password) < 10:
        log.error("seed_admin.failed", reason="la contrasena inicial es demasiado corta")
        return 1

    async with SessionLocal() as session:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            log.info("seed_admin.exists", email=email)
            return 0

        # Si ya hay algun admin, no se crea otro en silencio.
        any_admin = await session.execute(select(User).where(User.role == UserRole.ADMIN))
        if any_admin.scalars().first() is not None:
            log.warning("seed_admin.skipped", reason="ya existe un administrador")
            return 0

        user = User(
            email=email,
            name=settings.initial_admin_name,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
            # Clave del .env: sirve para entrar una vez, no para quedarse.
            must_change_password=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            AuditLog(
                user_id=user.id,
                action=AuditAction.USER_CREATED,
                entity_type="user",
                entity_id=str(user.id),
                details={"role": "ADMIN", "origin": "seed inicial"},
            )
        )
        await session.commit()
        log.info("seed_admin.created", email=email)
        return 0


async def rebuild_positions(portfolio_id: str | None = None) -> int:
    """Reconstruye el cache de posiciones desde el libro de operaciones.

    Existe porque la arquitectura lo exige: todo dato derivado tiene que
    poder rehacerse desde cero. Si el cache y el libro discrepan alguna vez,
    esto los reconcilia tomando el libro como verdad.

    Es seguro de correr en cualquier momento: no toca ninguna operacion, solo
    lo derivado.
    """
    async with SessionLocal() as session:
        query = select(Portfolio)
        if portfolio_id:
            query = query.where(Portfolio.id == portfolio_id)
        portfolios = (await session.execute(query)).scalars().all()

        if not portfolios:
            log.warning("rebuild_positions.sin_portfolios")
            return 0

        for portfolio in portfolios:
            activos = await rebuild_portfolio(
                session, user_id=portfolio.user_id, portfolio_id=portfolio.id
            )
            session.add(
                AuditLog(
                    user_id=portfolio.user_id,
                    action=AuditAction.POSITIONS_REBUILT,
                    entity_type="portfolio",
                    entity_id=str(portfolio.id),
                    details={"activos": activos, "origen": "cli"},
                )
            )
            log.info(
                "rebuild_positions.done",
                portfolio=portfolio.name,
                activos=activos,
            )
        await session.commit()
        return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: python -m app.cli [seed-admin|rebuild-positions]")
        raise SystemExit(2)

    command = sys.argv[1]
    if command == "seed-admin":
        raise SystemExit(asyncio.run(seed_admin()))
    if command == "rebuild-positions":
        arg = sys.argv[2] if len(sys.argv) > 2 else None
        raise SystemExit(asyncio.run(rebuild_positions(arg)))

    print(f"comando desconocido: {command}")
    raise SystemExit(2)


if __name__ == "__main__":
    main()
