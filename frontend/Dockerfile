FROM node:20-alpine

WORKDIR /app

# Capa de dependencias separada para aprovechar la cache de Docker.
# Se copia tambien el lock: sin el, dos builds de la misma imagen pueden
# resolver versiones distintas.
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

COPY . .

# El entrypoint verifica que node_modules coincida con package.json antes de
# arrancar. Ver el comentario del script: el volumen anonimo del compose
# sobrevive a los rebuilds y puede quedar desactualizado.
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 5173
ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
