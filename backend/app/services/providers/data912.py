"""Precio local de CEDEARs desde data912.com.

Verificado en vivo desde el servidor (D10): responde 200 con el listado
completo del panel.

**No informa cuándo se cotizó cada papel**, y hoy es la única fuente de
CEDEARs que funcionó: Yahoo devolvió 429 desde el servidor. Es el punto más
débil de toda la Fase 3 y conviene tenerlo presente.

Consecuencia directa: `quoted_at` queda en `None` (D33). Se sabe cuándo se
pidió el dato, no cuándo lo dijo el mercado, y entre una cosa y la otra puede
haber un fin de semana largo. La interfaz debe decir "obtenido hace X", nunca
"cotizado hace X".

Señal concreta del riesgo: en la muestra real, el papel `AALC` traía
`"v": 0.0` y `"q_op": 1.0` — una sola operación en toda la rueda. Su precio de
cierre puede ser de hace días y la respuesta no lo dice.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.domain.market import Cotizacion
from app.domain.rueda import momento_inferido
from app.services.providers.base import MarketDataProvider, cargar_json


class Data912Provider(MarketDataProvider):
    nombre = "data912"
    timeout = 25.0  # medido en 1816 ms; el margen es por si el panel crece

    def __init__(self, simbolos: list[str] | None = None) -> None:
        #: Si se pasan símbolos, se filtra. El endpoint devuelve el panel
        #: entero y no acepta filtro del lado del servidor.
        self.simbolos = {s.upper() for s in simbolos} if simbolos else None

    @property
    def url(self) -> str:
        return "https://data912.com/live/arg_cedears"

    def parse(self, cuerpo: str | bytes, fetched_at: datetime) -> list[Cotizacion]:
        datos = cargar_json(cuerpo)
        if not isinstance(datos, list):
            raise TypeError("se esperaba una lista")

        cotizaciones: list[Cotizacion] = []
        for fila in datos:
            if not isinstance(fila, dict):
                continue
            symbol = fila.get("symbol")
            if not isinstance(symbol, str):
                continue
            symbol = symbol.upper()
            if self.simbolos is not None and symbol not in self.simbolos:
                continue

            # `c` es el último precio operado. Se prefiere sobre el punto medio
            # entre puntas: es un precio al que alguien efectivamente operó, no
            # una interpolación.
            precio = fila.get("c")
            if not isinstance(precio, Decimal) or precio <= 0:
                continue

            cotizaciones.append(
                Cotizacion(
                    symbol=symbol,
                    price=precio,
                    currency="ARS",
                    source="data912",
                    fetched_at=fetched_at,
                    # El proveedor no lo informa y no se rellena (D33).
                    quoted_at=None,
                    # Se infiere desde el horario de rueda (D34-bis), en un
                    # campo aparte. Copiarlo a `quoted_at` convertiría una
                    # estimación en un hecho, que es exactamente el error que
                    # este proyecto existe para no repetir.
                    momento_estimado=momento_inferido(fetched_at),
                    asset_type="CEDEAR",
                )
            )
        return cotizaciones
