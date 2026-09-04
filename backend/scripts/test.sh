#!/usr/bin/env bash
# Corre la suite contra una base de datos y una base de Redis dedicadas.
#
# Existe porque el engine de SQLAlchemy es un objeto de modulo construido a
# partir de Settings, y Settings esta cacheado con lru_cache: no se puede
# repuntar desde una fixture. La inyeccion tiene que ocurrir **antes** de que
# arranque el proceso de pytest, y eso es lo que hace este script.
#
# Las variables de entorno tienen prioridad sobre el .env en pydantic-settings,
# asi que no se toca ningun archivo de configuracion.
#
#   docker compose exec backend bash scripts/test.sh
#   docker compose exec backend bash scripts/test.sh tests/test_mappers.py -v
#
# Se invoca con bash a proposito: el bind mount tapa el chmod de la imagen, asi
# que el bit de ejecucion no es confiable.

set -euo pipefail

export POSTGRES_DB="${POSTGRES_DB_TEST:-portfolio_tracker_test}"
export REDIS_DB="${REDIS_DB_TEST:-1}"

echo "[test] base    : ${POSTGRES_DB}"
echo "[test] redis db: ${REDIS_DB}"

# La base de pruebas se crea si falta. CREATE DATABASE no corre dentro de una
# transaccion, por eso va por una conexion suelta y no por Alembic.
python - <<'PY'
import asyncio, os, asyncpg

async def main() -> None:
    destino = os.environ["POSTGRES_DB"]
    conn = await asyncpg.connect(
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", 5432)),
        database="postgres",
    )
    existe = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = $1", destino
    )
    if existe:
        print(f"[test] la base {destino} ya existe")
    else:
        await conn.execute(f'CREATE DATABASE "{destino}"')
        print(f"[test] base {destino} creada")
    await conn.close()

asyncio.run(main())
PY

echo "[test] aplicando migraciones ..."
alembic upgrade head

echo "[test] corriendo pytest ..."
if [ "$#" -gt 0 ]; then
  exec pytest "$@"
else
  exec pytest -q
fi
