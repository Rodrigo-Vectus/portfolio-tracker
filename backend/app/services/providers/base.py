"""Interfaz de proveedor de market data.

La lógica de negocio no importa un proveedor concreto (Regla 6). Cambiar de
proveedor tiene que ser una decisión de configuración, no una reescritura.

Cada proveedor separa dos responsabilidades a propósito:

- `parse()` es una **función pura**: recibe el cuerpo de la respuesta y
  devuelve cotizaciones. Se puede probar con payloads reales guardados, sin
  red y sin base.
- `fetch()` hace la llamada HTTP y delega en `parse()`.

Esa separación es lo que permite tener pruebas de verdad sobre el punto donde
el dato entra al sistema. Un proveedor que sólo se puede probar con red es un
proveedor que en la práctica no se prueba.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.core.logging import get_logger
from app.domain.market import Cotizacion

log = get_logger("market_data")


def cargar_json(cuerpo: str | bytes) -> object:
    """Parsea JSON convirtiendo todo decimal a `Decimal`, no a `float`.

    `json.loads` normal convierte `1516.9` en un flotante de doble precisión
    **antes** de que el código lo toque: el primer paso del pipeline degradaría
    el dato y ningún `Decimal` posterior podría recuperarlo.

    Es una línea, y si se olvida no se nota nunca.
    """
    return json.loads(cuerpo, parse_float=Decimal, parse_int=Decimal)


class ProviderError(Exception):
    """Falla al obtener o interpretar la respuesta de un proveedor."""


class MarketDataProvider(ABC):
    """Un origen de precios."""

    nombre: str
    timeout: float = 15.0

    @property
    @abstractmethod
    def url(self) -> str: ...

    @abstractmethod
    def parse(self, cuerpo: str | bytes, fetched_at: datetime) -> list[Cotizacion]:
        """Convierte la respuesta cruda en cotizaciones. Función pura."""

    async def fetch(self, client: httpx.AsyncClient | None = None) -> list[Cotizacion]:
        """Consulta al proveedor. Registra la falla en vez de esconderla."""
        propio = client is None
        client = client or httpx.AsyncClient(timeout=self.timeout)
        inicio = datetime.now(UTC)
        try:
            respuesta = await client.get(self.url)
            respuesta.raise_for_status()
            cotizaciones = self.parse(respuesta.text, fetched_at=datetime.now(UTC))
            log.info(
                "provider.ok",
                provider=self.nombre,
                cotizaciones=len(cotizaciones),
                duracion_ms=int(
                    (datetime.now(UTC) - inicio).total_seconds() * 1000
                ),
            )
            return cotizaciones
        except httpx.HTTPError as exc:
            log.warning("provider.http_error", provider=self.nombre, error=str(exc))
            raise ProviderError(f"{self.nombre}: {exc}") from exc
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            # Una respuesta 200 con un cuerpo que cambió de forma es peor que
            # un error de red: parece que funcionó.
            log.warning("provider.parse_error", provider=self.nombre, error=str(exc))
            raise ProviderError(f"{self.nombre}: respuesta inesperada ({exc})") from exc
        finally:
            if propio:
                await client.aclose()
