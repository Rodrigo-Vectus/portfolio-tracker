"""Interpretación de las respuestas de los proveedores.

Los payloads son **reales**: se capturaron corriendo `validar-proveedores.sh`
en el servidor del usuario el 2026-09-04. No son inventados ni idealizados, y
por eso incluyen las rarezas que trae el dato de verdad.

Se prueba `parse()`, que es una función pura, sin red y sin base. Un proveedor
que sólo se puede probar con red es un proveedor que en la práctica no se
prueba, y el punto donde el dato externo entra al sistema es justamente donde
más importa tener red de seguridad.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.market import Frescura
from app.services.providers import (
    BinanceProvider,
    Data912Provider,
    DolarApiProvider,
    cargar_json,
)

AHORA = datetime(2026, 9, 4, 20, 44, tzinfo=UTC)

# --- Respuestas reales, tal como llegaron ---

DOLARAPI_MEP = """
{"moneda":"USD","casa":"bolsa","nombre":"Bolsa","compra":1516.9,"venta":1525.3,
 "fechaActualizacion":"2026-09-04T19:56:00.000Z"}
"""

DATA912 = """
[{"symbol":"AAL","q_bid":33.0,"px_bid":10360.0,"px_ask":10700.0,"q_ask":8030.0,
  "v":9088.0,"q_op":292.0,"c":10360.0,"pct_change":0.48},
 {"symbol":"AALC","q_bid":1000.0,"px_bid":6.54,"px_ask":6.77,"q_ask":100.0,
  "v":0.0,"q_op":1.0,"c":6.53,"pct_change":0.0},
 {"symbol":"AAPL","q_bid":10.0,"px_bid":20900.0,"px_ask":21000.0,"q_ask":15.0,
  "v":15000.0,"q_op":120.0,"c":20960.0,"pct_change":1.2}]
"""

BINANCE_UNO = '{"symbol":"BTCUSDT","price":"79700.01000000"}'
BINANCE_VARIOS = """
[{"symbol":"BTCUSDT","price":"79700.01000000"},
 {"symbol":"ETHUSDT","price":"2410.55000000"}]
"""


# --------------------------------------------------------------- parseo base


def test_los_decimales_no_pasan_por_float() -> None:
    """`json.loads` normal degradaría el dato en el primer paso del pipeline.

    Y ningún `Decimal` posterior podría recuperarlo: la precisión se pierde al
    leer, no al calcular.
    """
    datos = cargar_json('{"venta": 1516.9}')
    assert isinstance(datos["venta"], Decimal)
    assert datos["venta"] == Decimal("1516.9")
    assert datos["venta"] != Decimal(1516.9)  # así se vería si pasara por float


# ------------------------------------------------------------------ dolarapi


def test_dolarapi_usa_el_precio_de_venta() -> None:
    """Es lo que costaría comprar el dólar, que es la referencia para valuar."""
    c = DolarApiProvider("bolsa").parse(DOLARAPI_MEP, fetched_at=AHORA)[0]
    assert c.price == Decimal("1525.3")
    assert c.currency == "ARS"
    assert c.symbol == "USD/ARS:MEP"


def test_dolarapi_conserva_la_fecha_del_proveedor() -> None:
    """Es el único proveedor validado que dice cuándo se cotizó."""
    c = DolarApiProvider("bolsa").parse(DOLARAPI_MEP, fetched_at=AHORA)[0]
    assert c.quoted_at == datetime(2026, 9, 4, 19, 56, tzinfo=UTC)
    assert c.es_confiable
    assert c.frescura(AHORA) is Frescura.FRESCA


def test_dolarapi_con_fecha_ilegible_no_inventa_una() -> None:
    """Rellenar con `fetched_at` sería inventar el dato que falta (D33)."""
    roto = '{"venta":1525.3,"fechaActualizacion":"no-es-una-fecha"}'
    c = DolarApiProvider("bolsa").parse(roto, fetched_at=AHORA)[0]
    assert c.quoted_at is None
    assert c.frescura(AHORA) is Frescura.SIN_FECHA


def test_una_casa_desconocida_se_rechaza_al_construir() -> None:
    with pytest.raises(ValueError, match="Casa desconocida"):
        DolarApiProvider("dolar-imaginario")


# ------------------------------------------------------------------- data912


def test_data912_no_inventa_la_fecha_de_cotizacion() -> None:
    """El proveedor no la informa, así que `quoted_at` queda en None (D33).

    La antigüedad se infiere aparte, en `momento_estimado`, desde el horario
    de rueda (D34-bis). Son campos distintos: copiar la estimación al primero
    convertiría una inferencia en un dato del proveedor.
    """
    cotizaciones = Data912Provider().parse(DATA912, fetched_at=AHORA)
    assert all(c.quoted_at is None for c in cotizaciones)
    assert all(not c.es_confiable for c in cotizaciones)
    assert all(c.momento_estimado is not None for c in cotizaciones)
    assert all(c.frescura(AHORA) is Frescura.ESTIMADA for c in cotizaciones)


def test_data912_filtra_por_simbolo() -> None:
    """El endpoint devuelve el panel entero; no acepta filtro del lado servidor."""
    cotizaciones = Data912Provider(["AAPL"]).parse(DATA912, fetched_at=AHORA)
    assert [c.symbol for c in cotizaciones] == ["AAPL"]
    assert cotizaciones[0].price == Decimal("20960.0")


def test_data912_descarta_precios_no_positivos() -> None:
    """Un cero o un nulo no es un precio: es la ausencia de uno."""
    payload = """
    [{"symbol":"NADA","c":0.0},{"symbol":"NULO","c":null},
     {"symbol":"OK","c":100.5}]
    """
    cotizaciones = Data912Provider().parse(payload, fetched_at=AHORA)
    assert [c.symbol for c in cotizaciones] == ["OK"]


def test_data912_ignora_filas_con_forma_inesperada() -> None:
    """Una respuesta 200 con el cuerpo cambiado es peor que un error de red."""
    payload = '[{"sin_symbol":1}, "texto suelto", {"symbol":"OK","c":50}]'
    cotizaciones = Data912Provider().parse(payload, fetched_at=AHORA)
    assert [c.symbol for c in cotizaciones] == ["OK"]


# ------------------------------------------------------------------- binance


def test_binance_conserva_la_precision_del_string() -> None:
    """Binance devuelve el precio como string y por eso llega intacto.

    CoinGecko lo devuelve como número JSON, ya degradado por doble precisión
    antes de que lo veamos. Ese fue el criterio para elegir.
    """
    c = BinanceProvider(["BTCUSDT"]).parse(BINANCE_UNO, fetched_at=AHORA)[0]
    assert c.price == Decimal("79700.01000000")
    assert c.currency == "USDT"


def test_binance_acepta_objeto_y_lista() -> None:
    """Con un par devuelve un objeto; con varios, una lista."""
    p = BinanceProvider(["BTCUSDT", "ETHUSDT"])
    assert len(p.parse(BINANCE_UNO, fetched_at=AHORA)) == 1
    varios = p.parse(BINANCE_VARIOS, fetched_at=AHORA)
    assert [c.symbol for c in varios] == ["BTCUSDT", "ETHUSDT"]


def test_binance_sin_pares_se_rechaza() -> None:
    with pytest.raises(ValueError):
        BinanceProvider([])


# ------------------------------------------------------------------ frescura


def test_el_umbral_de_cripto_es_mas_estricto_que_el_de_cedears() -> None:
    """Las criptomonedas cotizan 24/7; los CEDEARs no operan de noche.

    Marcar como viejo el precio del viernes un sábado sería ruido, no aviso.
    """
    from app.domain.market import Cotizacion

    hace_dos_horas = AHORA - timedelta(hours=2)
    cripto = Cotizacion(
        symbol="BTCUSDT", price=Decimal(1), currency="USDT", source="x",
        fetched_at=AHORA, quoted_at=hace_dos_horas, asset_type="CRYPTO",
    )
    cedear = Cotizacion(
        symbol="AAPL", price=Decimal(1), currency="ARS", source="x",
        fetched_at=AHORA, quoted_at=hace_dos_horas, asset_type="CEDEAR",
    )
    assert cripto.frescura(AHORA) is Frescura.VIEJA
    assert cedear.frescura(AHORA) is Frescura.FRESCA
