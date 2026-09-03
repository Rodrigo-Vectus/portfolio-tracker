"""Configuracion compartida de las pruebas.

Por que el cliente es de alcance `session`:

`TestClient` levanta su propio bucle de eventos. El engine de SQLAlchemy es un
objeto de modulo y mantiene un pool de conexiones asyncpg; cada conexion queda
atada al bucle donde nacio. Si cada prueba crea su propio `TestClient`, la
segunda toma del pool una conexion del bucle anterior y asyncpg falla con
"attached to a different loop".

Un unico cliente para toda la corrida mantiene un solo bucle, que es lo que
espera el pool. El engine se libera al terminar.
"""

import asyncio
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.db.redis import redis_client
from app.db.session import engine
from app.main import app


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
    asyncio.run(_dispose())


async def _dispose() -> None:
    await engine.dispose()
    await redis_client.aclose()
