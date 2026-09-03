"""Punto de entrada de la API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.redis import redis_client
from app.db.session import engine

settings = get_settings()
configure_logging()
log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(
        "app.startup",
        environment=settings.app_env,
        version=settings.app_version,
    )
    yield
    await engine.dispose()
    await redis_client.aclose()
    log.info("app.shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Plataforma de seguimiento de inversiones. "
        "Fuente de verdad: operaciones + cotizaciones. Nunca precios manuales."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
