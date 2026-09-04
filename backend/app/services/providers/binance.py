"""Precio de criptomonedas desde la API pública de Binance.

Verificado en vivo desde el servidor (D10): responde 200 en unos 590 ms.

Se eligió sobre CoinGecko por un motivo concreto: **Binance devuelve el precio
como string** (`"79700.01000000"`) y CoinGecko como número JSON (`79720`). El
string llega intacto; el número ya pasó por doble precisión antes de que
nosotros lo veamos, y además CoinGecko redondeaba.

Que Binance sea el exchange donde el usuario tiene fondos hoy es incidental
(D31): se usa como fuente pública de precios, no como cuenta.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.domain.market import Cotizacion
from app.services.providers.base import MarketDataProvider, cargar_json


class BinanceProvider(MarketDataProvider):
    nombre = "binance"

    def __init__(self, pares: list[str]) -> None:
        if not pares:
            raise ValueError("Hay que indicar al menos un par, por ejemplo BTCUSDT.")
        self.pares = [p.upper() for p in pares]

    @property
    def url(self) -> str:
        símbolos = ",".join(f'"{p}"' for p in self.pares)
        return f"https://api.binance.com/api/v3/ticker/price?symbols=[{símbolos}]"

    def parse(self, cuerpo: str | bytes, fetched_at: datetime) -> list[Cotizacion]:
        datos = cargar_json(cuerpo)
        # Con un solo par la API devuelve un objeto; con varios, una lista.
        filas = datos if isinstance(datos, list) else [datos]

        cotizaciones: list[Cotizacion] = []
        for fila in filas:
            if not isinstance(fila, dict):
                continue
            symbol = fila.get("symbol")
            crudo = fila.get("price")
            if not isinstance(symbol, str) or crudo is None:
                continue
            try:
                precio = crudo if isinstance(crudo, Decimal) else Decimal(str(crudo))
            except InvalidOperation:
                continue
            if precio <= 0:
                continue

            cotizaciones.append(
                Cotizacion(
                    symbol=symbol.upper(),
                    price=precio,
                    currency="USDT",
                    source="binance",
                    fetched_at=fetched_at,
                    # El endpoint de ticker/price no trae marca de tiempo.
                    quoted_at=None,
                    asset_type="CRYPTO",
                )
            )
        return cotizaciones
