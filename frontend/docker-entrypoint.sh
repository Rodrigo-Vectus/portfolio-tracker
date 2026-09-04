#!/usr/bin/env sh
# Arranque del frontend.
#
# `node_modules` es un volumen anonimo que tapa el de la imagen, y Docker
# Compose lo CONSERVA al recrear el contenedor. Es decir: agregar una
# dependencia, reconstruir la imagen y levantar de nuevo NO alcanza; el
# volumen viejo sigue ahi y la aplicacion falla con "Failed to resolve
# import", apuntando a un archivo que existe perfectamente.
#
# La solucion es no depender de que el volumen este al dia: se guarda el hash
# de package.json dentro de node_modules y, si no coincide, se reinstala.
set -eu

MARKER="/app/node_modules/.pt-deps-hash"
CURRENT="$(md5sum /app/package.json | cut -d' ' -f1)"

if [ ! -f "$MARKER" ] || [ "$(cat "$MARKER")" != "$CURRENT" ]; then
  echo "[frontend] las dependencias no coinciden con package.json, instalando..."
  npm install --no-audit --no-fund
  printf '%s' "$CURRENT" > "$MARKER"
  echo "[frontend] dependencias al dia."
else
  echo "[frontend] dependencias al dia, sin cambios."
fi

exec npm run dev
