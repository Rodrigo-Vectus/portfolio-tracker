FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# curl para healthchecks manuales; el resto lo trae la imagen slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Capa de dependencias separada para aprovechar la cache de Docker
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

COPY . .
RUN chmod +x /app/scripts/*.sh

EXPOSE 8000
ENTRYPOINT ["bash", "/app/scripts/entrypoint.sh"]
