"""Configuracion compartida de las pruebas.

**Las pruebas no corren contra la base real.** La guarda de este modulo lo
impide: si `POSTGRES_DB` no termina en `_test` o `REDIS_DB` es 0, la suite se
detiene antes de tocar nada.

No es paranoia. Hasta la Fase 2 las pruebas de API corrian contra la base de
produccion, y el costo fue concreto: dejaron entradas basura en la bitacora de
auditoria, que por diseno no se borra, y bloqueaban la cuenta del
administrador en cada corrida. Cuando las pruebas empiecen a registrar
operaciones, el mismo acoplamiento significaria operaciones ficticias en un
libro que es inmutable por decision de dominio (D13).

La forma de correrlas:

    docker compose exec backend bash scripts/test.sh

Ese script crea la base de pruebas si falta, le aplica las migraciones y
recien despues invoca pytest con el entorno correcto.

Sobre el alcance `session` del cliente: `TestClient` levanta su propio bucle
de eventos y el pool de asyncpg ata cada conexion al bucle donde nacio. Un
cliente por prueba hace que la segunda tome una conexion del bucle anterior y
falle con "attached to a different loop".

Los imports de FastAPI y SQLAlchemy viven **dentro** de las fixtures a
proposito. En el nivel del modulo obligarian a las pruebas de dominio, que son
Python puro, a arrastrar toda la infraestructura solo para poder importarse.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Iterator

import pytest

SUFIJO_OBLIGATORIO = "_test"

#: Dominio de los usuarios de prueba.
#:
#: `example.com` esta reservado por IANA para documentacion y nunca es
#: entregable, asi que ningun correo de prueba puede llegar a una persona real.
#:
#: No se usan `.test`, `.local` ni `.invalid`, que parecen la eleccion obvia:
#: son TLD de uso especial y `email-validator` los rechaza con un 422. Ese
#: rechazo es correcto y no debe sortearse aflojando la validacion del login.
DOMINIO_DE_PRUEBA = "example.com"


def _guardar_o_abortar() -> None:
    """Se niega a correr si el entorno apunta a la base real."""
    from app.core.config import get_settings

    settings = get_settings()

    if not settings.postgres_db.endswith(SUFIJO_OBLIGATORIO):
        pytest.exit(
            f"\n\nLas pruebas apuntan a la base '{settings.postgres_db}', que no "
            f"termina en '{SUFIJO_OBLIGATORIO}'.\n"
            "Se detiene para no escribir en la base real.\n"
            "Corre la suite con: docker compose exec backend bash scripts/test.sh\n",
            returncode=3,
        )

    if settings.redis_db == 0:
        pytest.exit(
            "\n\nREDIS_DB es 0, que es la base que usa la aplicacion.\n"
            "Los contadores de intentos de login de las pruebas pisarian los "
            "reales.\n"
            "Corre la suite con: docker compose exec backend bash scripts/test.sh\n",
            returncode=3,
        )


@pytest.fixture(scope="session")
def entorno_de_pruebas() -> None:
    _guardar_o_abortar()


@pytest.fixture(scope="session")
def client(entorno_de_pruebas) -> Iterator:
    from fastapi.testclient import TestClient

    from app.db.redis import redis_client
    from app.db.session import engine
    from app.main import app

    with TestClient(app) as c:
        yield c

    async def _cerrar() -> None:
        await engine.dispose()
        await redis_client.aclose()

    asyncio.run(_cerrar())


def _nueva_password() -> str:
    """Contrasena valida y distinta en cada corrida.

    Tiene letras y numeros y supera los 10 caracteres, que es lo que exige la
    politica. Se genera en el momento: no hay ninguna credencial de prueba
    escrita en el repositorio, y ninguna prueba depende del `.env`.
    """
    return f"Prueba{secrets.token_hex(8)}"


async def _crear_usuario(email: str, password: str, admin: bool) -> str:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings
    from app.core.security import hash_password
    from app.models import User, UserRole

    # Engine propio y descartable: el compartido queda atado al bucle del
    # TestClient, y usarlo desde otro bucle reproduce el error de asyncpg.
    engine = create_async_engine(get_settings().database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        user = User(
            email=email,
            name="Usuario de prueba",
            password_hash=hash_password(password),
            role=UserRole.ADMIN if admin else UserRole.USER,
            is_active=True,
            must_change_password=False,
        )
        session.add(user)
        await session.commit()
        user_id = str(user.id)
    await engine.dispose()
    return user_id


async def _borrar_usuario(email: str) -> None:
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import get_settings
    from app.models import User

    engine = create_async_engine(get_settings().database_url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        # CASCADE se lleva refresh_token; audit_log queda con user_id NULL,
        # que es el comportamiento buscado: borrar un usuario no borra su
        # rastro.
        await session.execute(delete(User).where(User.email == email))
        await session.commit()
    await engine.dispose()


async def _limpiar_contadores(email: str) -> None:
    from redis.asyncio import Redis

    from app.core.config import get_settings

    r = Redis.from_url(get_settings().redis_url, decode_responses=True)
    await r.delete(f"login:fail:email:{email.lower()}")
    await r.aclose()


@pytest.fixture
def usuario(entorno_de_pruebas) -> Iterator[tuple[str, str]]:
    """Un usuario nuevo por prueba, con contrasena generada.

    Se crea y se borra en cada prueba. Ninguna prueba depende del
    administrador sembrado ni de `INITIAL_ADMIN_PASSWORD`: ese acoplamiento es
    lo que rompio la suite cuando el usuario cambio su contrasena, que era
    justamente lo que el sistema le exigia hacer.
    """
    email = f"prueba-{secrets.token_hex(6)}@{DOMINIO_DE_PRUEBA}"
    password = _nueva_password()
    asyncio.run(_crear_usuario(email, password, admin=False))
    try:
        yield email, password
    finally:
        asyncio.run(_limpiar_contadores(email))
        asyncio.run(_borrar_usuario(email))


@pytest.fixture
def admin(entorno_de_pruebas) -> Iterator[tuple[str, str]]:
    email = f"admin-{secrets.token_hex(6)}@{DOMINIO_DE_PRUEBA}"
    password = _nueva_password()
    asyncio.run(_crear_usuario(email, password, admin=True))
    try:
        yield email, password
    finally:
        asyncio.run(_limpiar_contadores(email))
        asyncio.run(_borrar_usuario(email))


@pytest.fixture(autouse=True)
def sesion_limpia(request) -> Iterator[None]:
    """Cookies limpias entre pruebas.

    Sin esto, una prueba que deja una sesion abierta cambia el resultado de la
    siguiente y las fallas aparecen o desaparecen segun el orden. Cada usuario
    es distinto en cada prueba, asi que los contadores de intentos ya no se
    arrastran: ese era el motivo de que dos corridas seguidas dieran numeros
    distintos sin cambiar una linea de codigo.
    """
    if "client" in request.fixturenames:
        request.getfixturevalue("client").cookies.clear()
    yield
    if "client" in request.fixturenames:
        request.getfixturevalue("client").cookies.clear()
