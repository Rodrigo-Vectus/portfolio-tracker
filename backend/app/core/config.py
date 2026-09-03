"""Configuracion de la aplicacion.

Toda la configuracion entra por variables de entorno. Nada de secretos
hardcodeados: si falta una variable obligatoria, la app no arranca.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Entorno ---
    app_env: Literal["development", "production"] = "development"
    app_name: str = "Portfolio Tracker"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # --- PostgreSQL ---
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    # --- Redis ---
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    # --- Seguridad ---
    secret_key: str = Field(min_length=32)
    cors_origins: str = "http://localhost:8211"

    # Access token corto: si se filtra, la ventana de uso es chica.
    access_token_minutes: int = 15
    # Refresh largo: define cuanto dura la sesion sin volver a ingresar clave.
    refresh_token_days: int = 7
    # Cookie Secure exige HTTPS. En desarrollo va en False; en produccion,
    # detras del reverse proxy con TLS (F9), pasa a True.
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Freno de fuerza bruta en el login.
    login_max_attempts: int = 8
    login_lockout_minutes: int = 15

    # --- Administrador inicial ---
    initial_admin_name: str = "Administrador"
    initial_admin_email: str = ""
    initial_admin_password: str = ""

    # --- Preferencias de dominio (defaults del sistema) ---
    default_display_currency: str = "USD"
    default_fx_source_equity: str = "MEP"
    default_fx_source_crypto: str = "USDT"
    default_cost_basis_method: str = "WAC"
    default_timezone: str = "America/Argentina/Buenos_Aires"

    @computed_field
    @property
    def database_url(self) -> str:
        """DSN async para SQLAlchemy/asyncpg."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
