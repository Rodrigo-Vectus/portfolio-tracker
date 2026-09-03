#!/usr/bin/env bash
# Arranque del backend: espera la base, aplica migraciones y levanta la API.
set -euo pipefail

echo "[entrypoint] esperando a PostgreSQL en ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
for i in $(seq 1 30); do
  if python - <<'PY'
import asyncio, os, sys
import asyncpg
async def main():
    try:
        c = await asyncpg.connect(
            user=os.environ["POSTGRES_USER"], password=os.environ["POSTGRES_PASSWORD"],
            database=os.environ["POSTGRES_DB"], host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]), timeout=3)
        await c.close()
    except Exception:
        sys.exit(1)
asyncio.run(main())
PY
  then
    echo "[entrypoint] PostgreSQL disponible."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "[entrypoint] ERROR: PostgreSQL no respondio tras 30 intentos." >&2
    exit 1
  fi
  sleep 2
done

echo "[entrypoint] aplicando migraciones (alembic upgrade head) ..."
alembic upgrade head

echo "[entrypoint] verificando administrador inicial ..."
python -m app.cli seed-admin

RELOAD_FLAG=""
if [ "${APP_ENV:-development}" = "development" ]; then
  RELOAD_FLAG="--reload"
  echo "[entrypoint] modo desarrollo: hot-reload activado."
fi

echo "[entrypoint] iniciando uvicorn ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 ${RELOAD_FLAG}
