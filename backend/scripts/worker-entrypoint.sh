#!/usr/bin/env bash
# Arranque del worker de tareas en segundo plano (ARQ).
# No corre migraciones: de eso se encarga el backend.
set -euo pipefail
echo "[worker] iniciando ARQ ..."
exec arq app.worker.settings.WorkerSettings
