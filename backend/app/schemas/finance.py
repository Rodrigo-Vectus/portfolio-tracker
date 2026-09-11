"""Contratos de la API financiera.

**Todo importe y cantidad se serializa como string.** No es una rareza: en
JSON los numeros son de doble precision, asi que un `NUMERIC(38,18)` que sale
como numero pierde exactitud en el camino y el navegador recibe algo distinto
de lo que hay en la base. Un string cruza intacto y el frontend decide como
mostrarlo.

Es la misma regla que rige en la base y en el dominio, aplicada al ultimo
tramo. De nada sirve `Decimal` de punta a punta si el JSON lo degrada al
salir.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.core.timezones import a_utc

from app.models.enums_finance import (
    AccountType,
    AssetType,
    TransactionStatus,
    TransactionType,
)


class DecimalOut(BaseModel):
    """Base para respuestas: los Decimal salen como string."""

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*", when_used="json")
    def _decimales_como_string(self, value):  # noqa: ANN001, ANN202
        """Decimal a texto en notacion posicional, nunca cientifica.

        `str(Decimal("0.000000000000000000"))` devuelve `"0E-18"`: Python usa
        notacion exponencial cuando el coeficiente es cero. Es un numero
        valido, pero ningun cliente espera leerlo asi, y un formateador que no
        lo reconozca lo muestra crudo en pantalla.

        `format(value, "f")` fuerza la forma posicional sin perder un digito.
        """
        return format(value, "f") if isinstance(value, Decimal) else value


# --------------------------------------------------------------------- activos


class AssetIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    asset_type: AssetType
    currency: str = Field(min_length=2, max_length=8)
    market: str | None = Field(default=None, max_length=16)
    sector: str | None = Field(default=None, max_length=80)
    display_precision: int = Field(default=2, ge=0, le=18)
    #: Cuántas unidades representa el precio informado. 100 para bonos, que
    #: cotizan por lámina de 100 nominales. 1 para todo lo demás.
    price_factor: Decimal = Field(default=Decimal(1), gt=0)


class AssetOut(DecimalOut):
    id: UUID
    symbol: str
    name: str
    asset_type: AssetType
    currency: str
    market: str | None
    sector: str | None
    display_precision: int
    price_factor: Decimal
    is_active: bool


# -------------------------------------------------------- cuentas y portfolios


class AssetPatch(BaseModel):
    """Edición de un activo.

    **El símbolo, el mercado y el tipo no se pueden cambiar**: son la clave
    natural del activo, y cambiarlos convertiría en otra cosa un instrumento
    que ya tiene operaciones asociadas. Si te equivocaste con eso, lo correcto
    es desactivarlo y crear el que corresponde.
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    sector: str | None = Field(default=None, max_length=80)
    display_precision: int | None = Field(default=None, ge=0, le=18)
    price_factor: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    account_type: AccountType
    country: str | None = Field(default=None, max_length=2)
    default_currency: str = Field(default="ARS", max_length=8)


class AccountOut(DecimalOut):
    id: UUID
    name: str
    account_type: AccountType
    country: str | None
    default_currency: str
    is_active: bool


class PortfolioIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    base_currency: str = Field(default="USD", max_length=8)
    is_default: bool = False


class PortfolioOut(DecimalOut):
    id: UUID
    name: str
    base_currency: str
    is_default: bool


# ----------------------------------------------------------------- operaciones


class TransactionIn(BaseModel):
    """Alta de una operacion.

    La cantidad entra como string y siempre positiva. El signo lo lleva
    `tx_type`: aceptar un numero negativo reintroduciria la convencion de la
    planilla anterior, donde una venta era una cantidad negativa y la columna
    de precio de compra guardaba en realidad el precio de venta.
    """

    portfolio_id: UUID
    asset_id: UUID | None = None
    account_id: UUID | None = None
    tx_type: TransactionType
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    price_currency: str = Field(min_length=2, max_length=8)
    settlement_currency: str | None = Field(default=None, max_length=8)
    commission: Decimal = Field(default=Decimal(0), ge=0)
    taxes: Decimal = Field(default=Decimal(0), ge=0)
    fx_rate_used: Decimal | None = Field(default=None, gt=0)
    fx_source: str | None = Field(default=None, max_length=40)
    executed_at: datetime
    trade_date: date | None = None
    notes: str | None = None
    external_id: str | None = Field(default=None, max_length=64)

    @field_validator("executed_at")
    @classmethod
    def _normalizar_zona(cls, value: datetime) -> datetime:
        """Una fecha sin zona se interpreta en la zona configurada del sistema.

        Es la convencion de la API y esta documentada tambien en el endpoint.
        No se asume UTC: una compra de las 22:30 en Buenos Aires quedaria
        fechada al dia siguiente y su `trade_date` saldria en otra rueda.

        Si el cliente manda offset explicito, se respeta.
        """
        return a_utc(value)


class TransactionVoidIn(BaseModel):
    """Anular exige motivo. Sin motivo es un borrado con otro nombre."""

    motivo: str = Field(min_length=3, max_length=255)


class TransactionOut(DecimalOut):
    id: UUID
    portfolio_id: UUID
    asset_id: UUID | None
    account_id: UUID | None
    tx_type: TransactionType
    quantity: Decimal
    unit_price: Decimal
    price_currency: str
    settlement_currency: str
    commission: Decimal
    taxes: Decimal
    gross_amount: Decimal | None
    net_amount: Decimal | None
    fx_rate_used: Decimal | None
    fx_source: str | None
    executed_at: datetime
    trade_date: date
    status: TransactionStatus
    voided_reason: str | None
    notes: str | None


# ------------------------------------------------------------------ posiciones


class PositionOut(DecimalOut):
    """Posición derivada del libro, con su valuación cuando existe.

    **Todo lo de mercado puede venir en `None`, y eso es información.** Un
    `current_value` nulo dice "no sé cuánto vale"; un cero diría "no vale
    nada". No son lo mismo y el frontend los muestra distinto.

    `price_as_of` y `price_is_estimated` viajan siempre con el precio: un
    número de mercado sin su antigüedad es el problema que originó este
    proyecto.
    """

    asset_id: UUID
    symbol: str
    asset_type: AssetType
    quantity: Decimal
    average_cost: Decimal | None
    open_cost_basis: Decimal
    realized_pnl: Decimal
    cost_method: str
    currency: str
    last_transaction_at: datetime | None
    computed_at: datetime | None

    # --- valuación (todo opcional: puede no haber cotización) ---
    current_price: Decimal | None = None
    current_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    price_source: str | None = None
    #: Cuándo se cotizó. Si es una estimación, `price_is_estimated` lo dice.
    price_as_of: datetime | None = None
    price_is_estimated: bool = False
    #: FRESCA | ESTIMADA | VIEJA | SIN_FECHA | AUSENTE
    price_status: str = "AUSENTE"

    # --- variación contra el último cierre ---
    #
    # No se llama "24h" y ese es el punto. Sin calendario de feriados, un lunes
    # compara contra el viernes y un lunes feriado contra el jueves. La única
    # forma honesta de mostrarlo es transportar la fecha del cierre que se usó
    # y que la pantalla la diga.
    #
    # `null` cuando no hay cierre previo. Un cero afirmaría que el precio no se
    # movió, y eso es distinto de no tener contra qué compararlo.
    variacion_diaria: Decimal | None = None
    variacion_desde: date | None = None
    cierre_anterior: Decimal | None = None

    # --- moneda dura (D2) ---
    #
    # El costo se convierte lote por lote al tipo de cambio de la fecha en que
    # se compró cada uno; el valor actual, al de hoy. Esa asimetría es lo que
    # hace que el resultado en dólares diga algo distinto del de pesos.
    hard_currency: str | None = None
    hard_cost_basis: Decimal | None = None
    hard_current_value: Decimal | None = None
    hard_unrealized_pnl: Decimal | None = None
    #: Por qué falta la conversión, cuando falta.
    hard_motivo: str | None = None


class TotalOut(BaseModel):
    """Total de la cartera, con su propia declaración de completitud.

    `total` viene en `None` cuando a alguna posición le falta el precio o lo
    tiene viejo. En ese caso `motivo` explica por qué, para que la interfaz
    pueda decirlo en vez de mostrar un espacio vacío.
    """

    model_config = ConfigDict(from_attributes=True)

    total: str | None
    currency: str
    es_completo: bool
    es_estimado: bool
    motivo: str | None
    posiciones_totales: int
    posiciones_sin_precio: int
    posiciones_con_precio_viejo: int
    posiciones_estimadas: int


class PositionsResponse(BaseModel):
    positions: list[PositionOut]
    total: TotalOut


class MovimientoOut(DecimalOut):
    tx_id: str
    tx_type: TransactionType
    fecha: datetime
    monto: Decimal
    saldo_posterior: Decimal
    currency: str
    descripcion: str


class SaldoOut(DecimalOut):
    """Saldo de caja con su desglose.

    El total solo no explica de dónde sale. `aporte_neto` responde "cuánto
    puse de mi bolsillo", que es distinto del costo de las posiciones abiertas
    y del capital neto aportado: son tres números que la planilla anterior
    confundía en uno.
    """

    currency: str
    saldo: Decimal
    depositos: Decimal
    retiros: Decimal
    invertido: Decimal
    recuperado: Decimal
    dividendos: Decimal
    comisiones: Decimal
    aporte_neto: Decimal
    es_negativo: bool
    movimientos: list[MovimientoOut]


class MovimientoIn(BaseModel):
    """Depósito, retiro, dividendo o costo de cuenta.

    No lleva activo ni cantidad: un depósito de pesos no es la compra de un
    activo cuyo precio es 1. El monto va directo.
    """

    portfolio_id: UUID
    account_id: UUID | None = None
    tx_type: TransactionType
    monto: Decimal = Field(gt=0)
    currency: str = Field(min_length=2, max_length=8)
    executed_at: datetime
    notes: str | None = None

    @field_validator("executed_at")
    @classmethod
    def _normalizar_zona(cls, value: datetime) -> datetime:
        return a_utc(value)


class RoiOut(DecimalOut):
    symbol: str
    open_cost_basis: Decimal
    valor_actual: Decimal | None
    no_realizado: Decimal | None
    #: Fracción, no porcentaje: 0.25 es 25%. El formato es del frontend.
    roi: Decimal | None


class TwrOut(DecimalOut):
    """Rendimiento de la cartera aislando el efecto de los aportes.

    Nunca sale un número pelado: `desde`, `hasta` y `subperiodos` dicen sobre
    qué tramo se calculó, y `corte` avisa cuando la serie se partió por un día
    sin valuar.

    `anualizado` viene en `None` mientras la serie sea corta. Elevar unos pocos
    días a 365/n produce tasas de miles por ciento que no describen ningún año.
    """

    #: Fracción, no porcentaje: 0.25 es 25%.
    acumulado: Decimal | None
    anualizado: Decimal | None
    desde: date | None
    hasta: date | None
    dias: int
    subperiodos: int
    motivo: str | None
    corte: str | None
    #: El número es correcto pero se lee mal. No lo invalida: lo enmarca.
    advertencia: str | None


class RendimientoOut(DecimalOut):
    """Rendimiento de la cartera.

    Cada número trae su propio denominador y ninguno se llama "capital
    invertido": ese rótulo tenía tres significados incompatibles, y usar uno
    solo para todo es lo que hacía que el porcentaje de la planilla se inflara
    al vender.

    `xirr_anual` viene en `None` con `xirr_motivo` explicando por qué, en vez
    de un cero que se leería como "no rindió nada".
    """

    currency: str
    posiciones: list[RoiOut]
    realizado: Decimal
    no_realizado: Decimal | None
    resultado_total: Decimal | None
    valor_actual: Decimal | None
    aporte_neto: Decimal
    #: No realizado sobre el costo de lo abierto. Nunca sobre compras menos
    #: ventas: ese denominador se achica en cada venta y el porcentaje se
    #: infla solo, que es lo que hacia la planilla.
    roi: Decimal | None
    xirr_anual: Decimal | None
    xirr_motivo: str | None
    twr: TwrOut


class PuntoOut(DecimalOut):
    """Un punto de la evolución de la cartera.

    `total_value` puede venir en `None`: ese día faltó alguna cotización. El
    gráfico corta ahí en vez de interpolar, porque una línea que cruza un
    hueco afirma que ese día la cartera valía el promedio de sus vecinos.
    """

    snapshot_date: date
    total_value: Decimal | None
    open_cost_basis: Decimal
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    cash_balance: Decimal
    currency: str
    is_estimated: bool
    motivo: str | None


class HistorialOut(BaseModel):
    """Serie de evolución con la advertencia de su alcance."""

    model_config = ConfigDict(from_attributes=True)

    puntos: list[PuntoOut]
    currency: str
    #: Desde cuándo hay serie. Antes de esa fecha no hay datos y no se inventan.
    desde: date | None
    nota: str | None


class PuntoDeCierre(DecimalOut):
    """Un cierre diario. Lo minimo para dibujar una linea.

    Hereda de DecimalOut: el precio sale como string y en notacion posicional,
    igual que todo importe del sistema. Un cierre es dinero aunque solo se use
    para dibujar.
    """

    trade_date: date
    close: Decimal


class SerieDeActivo(DecimalOut):
    asset_id: UUID
    symbol: str
    currency: str
    puntos: list[PuntoDeCierre]


class SeriesDeCierresOut(DecimalOut):
    """Cierres recientes de cada activo de la cartera.

    **Las series no tienen todas el mismo largo y eso es correcto.** Un activo
    que empezo a cotizar despues, o que tuvo un dia sin cierre, tiene menos
    puntos. Rellenarlos para emparejarlas mostraria dias planos que nadie
    midio.
    """

    desde: date
    series: list[SerieDeActivo]
