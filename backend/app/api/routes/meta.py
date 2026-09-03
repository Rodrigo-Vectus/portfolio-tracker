"""Metadatos de la plataforma.

Expone la configuracion de dominio no sensible para que el frontend sepa,
por ejemplo, cual es la moneda de visualizacion por defecto sin hardcodearla.
"""

from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/meta", tags=["meta"])
settings = get_settings()


@router.get("", summary="Version y configuracion de dominio")
async def meta() -> dict[str, Any]:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "phase": "0 — scaffolding",
        "defaults": {
            "display_currency": settings.default_display_currency,
            "fx_source_equity": settings.default_fx_source_equity,
            "fx_source_crypto": settings.default_fx_source_crypto,
            "cost_basis_method": settings.default_cost_basis_method,
            "timezone": settings.default_timezone,
        },
    }
