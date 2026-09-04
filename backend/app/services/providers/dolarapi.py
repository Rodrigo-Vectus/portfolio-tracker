"""Tipo de cambio desde dolarapi.com.

Verificado en vivo desde el servidor (D10): responde 200 en menos de 500 ms y
**trae fecha propia** en `fechaActualizacion`, que es lo que permite saber si
un precio es de hoy.

Es el único de los proveedores validados que informa la fecha de cotización,
así que es el que menos depende de inferencias.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.market import Cotizacion
from app.services.providers.base import MarketDataProvider, cargar_json

#: Casa de cambio -> `rate_type` del modelo. MEP para acciones y USDT para
#: cripto es D1; el resto se guarda igual porque cambiar de fuente altera todo
#: el histórico en dólares y conviene tener las series disponibles (D16).
CASAS = {
    "bolsa": "MEP",
    "contadoconliqui": "CCL",
    "cripto": "CRYPTO",
    "oficial": "OFICIAL",
    "blue": "BLUE",
}


class DolarApiProvider(MarketDataProvider):
    nombre = "dolarapi"

    def __init__(self, casa: str = "bolsa") -> None:
        if casa not in CASAS:
            raise ValueError(f"Casa desconocida: {casa}. Opciones: {sorted(CASAS)}")
        self.casa = casa

    @property
    def url(self) -> str:
        return f"https://dolarapi.com/v1/dolares/{self.casa}"

    @property
    def rate_type(self) -> str:
        return CASAS[self.casa]

    def parse(self, cuerpo: str | bytes, fetched_at: datetime) -> list[Cotizacion]:
        datos = cargar_json(cuerpo)
        if not isinstance(datos, dict):
            raise TypeError("se esperaba un objeto")

        venta = datos["venta"]
        if not isinstance(venta, Decimal):
            raise TypeError(f"'venta' no es numérico: {venta!r}")

        return [
            Cotizacion(
                symbol=f"USD/ARS:{self.rate_type}",
                # Se usa el precio de VENTA: es lo que costaría comprar el
                # dólar, que es la referencia para valuar en moneda dura.
                price=venta,
                currency="ARS",
                source=f"dolarapi:{self.casa}",
                fetched_at=fetched_at,
                quoted_at=_parsear_fecha(datos.get("fechaActualizacion")),
                asset_type="FX",
            )
        ]


def _parsear_fecha(valor: object) -> datetime | None:
    """Convierte la fecha del proveedor. Ante la duda, `None`.

    Devolver `fetched_at` cuando la fecha no se entiende sería inventar el dato
    que justamente hace falta (D33).
    """
    if not isinstance(valor, str) or not valor:
        return None
    try:
        momento = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)
