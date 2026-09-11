"""Operaciones y posiciones.

El recalculo de posiciones es **sincronico**: la operacion, sus lotes y su
entrada de auditoria entran en la misma transaccion de base o no entra
ninguna. Delegar el recalculo al worker haria mas rapida el alta, pero
`GET /positions` podria devolver un numero viejo durante unos segundos sin
decirlo, y presentar un dato desactualizado como actual es exactamente el
error que origino este proyecto.

Con el volumen real (73 operaciones) el costo es imperceptible. Si algun dia
deja de serlo, la salida es mover el recalculo al worker **y marcar el dato
con su `as_of`**, no dejarlo en silencio.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ActiveUser, require_csrf
from app.core.timezones import fecha_de_rueda
from app.db.session import get_session
from app.models import (
    AssetType,
    Portfolio,
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.schemas.finance import (
    MovimientoIn,
    PositionOut,
    PositionsResponse,
    TotalOut,
    TransactionIn,
    TransactionOut,
    TransactionVoidIn,
    SaldoOut,
    RendimientoOut,
    TwrOut,
    RoiOut,
    HistorialOut,
    PuntoOut,
)
from app.services import transactions as tx_service
from app.services.valuation import resultado_no_realizado, valuar_portfolio
from app.services.cash import saldo_de_portfolio
from app.services.fx import cargar_serie
from app.services.valuation import valuar_en_moneda_dura
from app.services.performance import rendimiento_de_portfolio
from app.services.snapshots import serie as serie_de_snapshots
from app.services.transactions import TransactionServiceError

router = APIRouter(tags=["operaciones"])

Session = Annotated[AsyncSession, Depends(get_session)]

NO_ENCONTRADO = HTTPException(status.HTTP_404_NOT_FOUND, detail="No encontrado.")


def _rango_valido(desde: date | None, hasta: date | None) -> None:
    """Rechaza un período dado vuelta.

    Sin esto la consulta devuelve una lista vacia, que se lee como "no hay
    operaciones en ese período" cuando lo que pasa es que el período no
    existe. Un vacio silencioso es peor que un error: parece un dato.
    """
    if desde is not None and hasta is not None and desde > hasta:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El período está al revés: 'desde' ({desde.isoformat()}) es "
                f"posterior a 'hasta' ({hasta.isoformat()})."
            ),
        )


async def _en_moneda_dura(
    session, portfolio_id, pos, asset, monto, serie, hoy, currency: str
) -> dict:
    """Campos de moneda dura para una posición, o el motivo de su ausencia."""
    r = await valuar_en_moneda_dura(
        session,
        portfolio_id=portfolio_id,
        asset_id=pos.asset_id,
        symbol=asset.symbol,
        valor_actual_local=monto.amount if monto else None,
        serie=serie,
        hoy=hoy,
        currency=currency.upper(),
    )
    return {
        "hard_currency": r.currency,
        "hard_cost_basis": r.costo,
        "hard_current_value": r.valor_actual,
        "hard_unrealized_pnl": r.no_realizado,
        "hard_motivo": r.motivo,
    }


async def _portfolio_propio(
    session: AsyncSession, user_id: UUID, portfolio_id: UUID
) -> Portfolio:
    """Devuelve el portfolio solo si es del usuario autenticado.

    El 404 en lugar del 403 es deliberado: un 403 confirmaria que el portfolio
    existe y solo no es tuyo, y eso permite enumerar recursos ajenos probando
    identificadores.
    """
    result = await session.execute(
        select(Portfolio).where(
            Portfolio.id == portfolio_id, Portfolio.user_id == user_id
        )
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise NO_ENCONTRADO
    return portfolio


@router.get(
    "/transactions",
    response_model=list[TransactionOut],
    summary="Listar operaciones de un portfolio",
)
async def list_transactions(
    portfolio_id: UUID,
    user: ActiveUser,
    session: Session,
    incluir_anuladas: bool = False,
    desde: date | None = None,
    hasta: date | None = None,
    tx_type: str | None = None,
    account_id: UUID | None = None,
) -> list[Transaction]:
    """Operaciones del portfolio, filtrables.

    **El período se filtra por `trade_date`, no por `executed_at`.** Una compra
    de las 22:30 en Buenos Aires es 01:30 UTC del día siguiente, y filtrar por
    el instante la mandaría a otra rueda. `trade_date` ya guarda el día local
    que corresponde, que es el que la persona tiene en la cabeza cuando pide
    "las de septiembre".

    `desde` y `hasta` son **inclusivos**.

    `account_id` no necesita comprobarse: la consulta ya filtra por el usuario
    autenticado, así que una cuenta ajena devuelve la lista vacía igual que una
    inexistente y no permite distinguir entre las dos.
    """
    await _portfolio_propio(session, user.id, portfolio_id)

    _rango_valido(desde, hasta)

    # El enum es nativo: un valor cualquiera no filtra de menos, aborta la
    # transaccion. Se valida antes de llegar a la base.
    tipo: TransactionType | None = None
    if tx_type is not None:
        try:
            tipo = TransactionType(tx_type.upper())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"'{tx_type}' no es un tipo de operacion. "
                    f"Los validos son: {', '.join(t.value for t in TransactionType)}."
                ),
            ) from None

    query = select(Transaction).where(
        Transaction.portfolio_id == portfolio_id,
        # Redundante con el filtro del portfolio, y esta a proposito: si
        # alguna vez alguien cambia el filtro de arriba, este sigue de pie.
        Transaction.user_id == user.id,
    )
    if not incluir_anuladas:
        query = query.where(Transaction.status == TransactionStatus.ACTIVE)
    if desde:
        query = query.where(Transaction.trade_date >= desde)
    if hasta:
        query = query.where(Transaction.trade_date <= hasta)
    if tipo is not None:
        query = query.where(Transaction.tx_type == tipo)
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)

    result = await session.execute(query.order_by(Transaction.executed_at))
    return list(result.scalars().all())


@router.post(
    "/transactions",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Registrar una operacion",
)
async def create_transaction(
    payload: TransactionIn,
    user: ActiveUser,
    session: Session,
    request: Request,
) -> Transaction:
    """Registra una operacion y recalcula la posicion en la misma transaccion.

    **Convencion de fechas.** Si `executed_at` no trae zona horaria se
    interpreta en la zona configurada del sistema (por defecto
    `America/Argentina/Buenos_Aires`), no en UTC. Asumir UTC correria una
    compra de las 22:30 al dia siguiente y su rueda saldria mal. Si el cliente
    manda un offset explicito, se respeta tal cual.

    `trade_date` se deriva del dia local, salvo que venga informado.
    """
    await _portfolio_propio(session, user.id, payload.portfolio_id)

    try:
        fila = await tx_service.registrar(
            session,
            user_id=user.id,
            portfolio_id=payload.portfolio_id,
            asset_id=payload.asset_id,
            account_id=payload.account_id,
            tx_type=payload.tx_type,
            quantity=payload.quantity,
            unit_price=payload.unit_price,
            price_currency=payload.price_currency,
            settlement_currency=payload.settlement_currency or payload.price_currency,
            commission=payload.commission,
            taxes=payload.taxes,
            fx_rate_used=payload.fx_rate_used,
            fx_source=payload.fx_source,
            executed_at=payload.executed_at,
            # fecha_de_rueda y no .date(): executed_at ya viene normalizado a
            # UTC, y una operacion de las 22:30 de Buenos Aires es 01:30 UTC
            # del dia siguiente. Tomar la fecha en UTC la mandaria a otra
            # rueda y correria todo el agrupamiento por dia.
            trade_date=payload.trade_date or fecha_de_rueda(payload.executed_at),
            notes=payload.notes,
            external_id=payload.external_id,
            request=request,
        )
    except TransactionServiceError as exc:
        # 422 y no 400: la peticion esta bien formada, lo que no cierra es la
        # regla de negocio. El mensaje explica cual, porque "venta invalida" no
        # le sirve a nadie para corregir la carga.
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    await session.commit()
    await session.refresh(fila)
    return fila


@router.post(
    "/transactions/{transaction_id}/void",
    response_model=TransactionOut,
    dependencies=[Depends(require_csrf)],
    summary="Anular una operacion",
)
async def void_transaction(
    transaction_id: UUID,
    payload: TransactionVoidIn,
    user: ActiveUser,
    session: Session,
    request: Request,
) -> Transaction:
    """Anula, nunca borra (D13).

    Puede fallar legitimamente: anular una compra sobre la que despues se
    vendio dejaria una venta descubierta. En ese caso no se anula nada y se
    explica por que, en vez de dejar el libro con una posicion imposible.
    """
    try:
        fila = await tx_service.anular(
            session,
            user_id=user.id,
            transaction_id=transaction_id,
            motivo=payload.motivo,
            request=request,
        )
    except TransactionServiceError as exc:
        await session.rollback()
        mensaje = str(exc)
        if mensaje == "La operacion no existe.":
            raise NO_ENCONTRADO from None
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=mensaje
        ) from None

    await session.commit()
    await session.refresh(fila)
    return fila


@router.get(
    "/positions",
    response_model=PositionsResponse,
    summary="Posiciones de un portfolio, valuadas",
)
async def list_positions(
    portfolio_id: UUID,
    user: ActiveUser,
    session: Session,
    hard_currency: str | None = None,
    asset_type: str | None = None,
) -> PositionsResponse:
    """Posiciones derivadas del libro, valuadas contra la última cotización.

    **Todo dato de mercado puede venir nulo.** Si no hay cotización para un
    activo, su valor es `null`, no cero: "no sé cuánto vale" y "no vale nada"
    son afirmaciones distintas.

    El precio siempre viaja con su antigüedad y su fuente. Cuando el proveedor
    no informa cuándo se cotizó, la antigüedad es una estimación desde el
    horario de rueda y `price_is_estimated` lo dice.

    El total se entrega en `null` si a alguna posición le falta el precio o lo
    tiene viejo, con el motivo explicado: un total incompleto se lee como
    completo, y el color de una fila no viaja hasta la suma.

    Con `hard_currency=USD` cada posición trae además su costo y su valor en
    moneda dura. **El costo se convierte lote por lote al tipo de cambio de la
    fecha de cada compra**, no al de hoy: un costo histórico no puede cambiar
    porque se movió el dólar esta mañana. El valor actual sí usa el de hoy, y
    esa asimetría es lo que hace que el número en dólares diga algo distinto
    del de pesos.

    Con `asset_type=CEDEAR` se devuelven sólo las posiciones de ese tipo, **y
    el total es el de lo filtrado**. El filtro se aplica en la consulta y no
    sobre el resultado: si se recortara después, el total habría sumado lo que
    la pantalla no muestra.
    """
    await _portfolio_propio(session, user.id, portfolio_id)

    # Se valida antes de tocar la base y no se delega en PostgreSQL. El enum
    # es nativo, así que un valor cualquiera no da un filtro vacío: aborta la
    # transacción entera. Es el mismo patrón que convirtió un
    # `X-Forwarded-For` con basura en un 500 sobre una columna INET.
    tipo: AssetType | None = None
    if asset_type is not None:
        try:
            tipo = AssetType(asset_type.upper())
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"'{asset_type}' no es un tipo de activo. "
                    f"Los válidos son: {', '.join(t.value for t in AssetType)}."
                ),
            ) from None

    valuadas, total = await valuar_portfolio(
        session, user_id=user.id, portfolio_id=portfolio_id, asset_type=tipo
    )

    # La conversión es opcional y se pide explícitamente: si el usuario no
    # eligió moneda dura, no se hacen consultas de FX ni se devuelven campos
    # que nadie va a mirar.
    serie = None
    if hard_currency:
        serie = await cargar_serie(session)

    hoy = datetime.now(UTC).date()
    posiciones = []
    for pos, asset, valor in valuadas:
        cotizacion = valor.cotizacion
        monto = valor.valor
        es_estimada = cotizacion is not None and cotizacion.quoted_at is None

        posiciones.append(
            PositionOut(
                asset_id=pos.asset_id,
                symbol=asset.symbol,
                asset_type=asset.asset_type,
                quantity=pos.quantity,
                average_cost=pos.average_cost,
                open_cost_basis=pos.open_cost_basis,
                realized_pnl=pos.realized_pnl,
                cost_method=pos.cost_method,
                currency=pos.currency,
                last_transaction_at=pos.last_transaction_at,
                computed_at=pos.computed_at,
                current_price=cotizacion.price if cotizacion else None,
                current_value=monto.amount if monto else None,
                unrealized_pnl=resultado_no_realizado(pos, valor),
                price_source=cotizacion.source if cotizacion else None,
                price_as_of=(
                    (cotizacion.quoted_at or cotizacion.momento_estimado)
                    if cotizacion
                    else None
                ),
                price_is_estimated=es_estimada,
                price_status=valor.frescura.value,
                **(
                    await _en_moneda_dura(
                        session, portfolio_id, pos, asset, monto, serie, hoy,
                        hard_currency,
                    )
                    if serie is not None and hard_currency
                    else {}
                ),
            )
        )

    return PositionsResponse(
        positions=posiciones,
        total=TotalOut(
            # String por lo mismo que el resto de los importes: un
            # NUMERIC(38,18) serializado como número JSON pierde dígitos.
            total=str(total.total.amount) if total.total else None,
            currency=total.currency,
            es_completo=total.es_completo,
            es_estimado=total.es_estimado,
            motivo=total.motivo_incompleto,
            posiciones_totales=total.posiciones_totales,
            posiciones_sin_precio=total.posiciones_sin_precio,
            posiciones_con_precio_viejo=total.posiciones_con_precio_viejo,
            posiciones_estimadas=total.posiciones_estimadas,
        ),
    )


# ---------------------------------------------------------------------- caja


@router.get("/cash", response_model=SaldoOut, summary="Saldo de caja")
async def get_saldo(
    portfolio_id: UUID,
    user: ActiveUser,
    session: Session,
    currency: str = "ARS",
) -> SaldoOut:
    """Cuánta plata hay sin invertir, y de dónde salió.

    El saldo se deriva del libro como todo lo demás: depósitos menos retiros,
    menos lo que costaron las compras, más lo que dejaron las ventas.

    Cada moneda tiene su saldo. Sumar pesos y dólares requeriría convertir, y
    esa conversión necesita un tipo de cambio con su fecha (D2).
    """
    await _portfolio_propio(session, user.id, portfolio_id)
    saldo = await saldo_de_portfolio(
        session, user_id=user.id, portfolio_id=portfolio_id, currency=currency
    )
    return SaldoOut(
        currency=saldo.currency,
        saldo=saldo.saldo,
        depositos=saldo.depositos,
        retiros=saldo.retiros,
        invertido=saldo.invertido,
        recuperado=saldo.recuperado,
        dividendos=saldo.dividendos,
        comisiones=saldo.comisiones,
        aporte_neto=saldo.aporte_neto,
        es_negativo=saldo.es_negativo,
        movimientos=saldo.movimientos,
    )


@router.post(
    "/cash",
    response_model=TransactionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Registrar un movimiento de efectivo",
)
async def crear_movimiento(
    payload: MovimientoIn,
    user: ActiveUser,
    session: Session,
    request: Request,
) -> Transaction:
    """Registra un depósito, retiro, dividendo o costo de cuenta.

    Va al mismo libro que las compras y las ventas: es la misma clase de hecho
    histórico y se anula igual. Un movimiento de efectivo se guarda con
    cantidad 1 y el monto en el precio unitario, sin activo asociado.
    """
    await _portfolio_propio(session, user.id, payload.portfolio_id)

    try:
        fila = await tx_service.registrar(
            session,
            user_id=user.id,
            portfolio_id=payload.portfolio_id,
            asset_id=None,
            account_id=payload.account_id,
            tx_type=payload.tx_type,
            quantity=Decimal(1),
            unit_price=payload.monto,
            price_currency=payload.currency,
            settlement_currency=payload.currency,
            executed_at=payload.executed_at,
            trade_date=fecha_de_rueda(payload.executed_at),
            notes=payload.notes,
            request=request,
        )
    except TransactionServiceError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from None

    await session.commit()
    await session.refresh(fila)
    return fila


# --------------------------------------------------------------- rendimiento


@router.get(
    "/performance", response_model=RendimientoOut, summary="Rendimiento de la cartera"
)
async def get_rendimiento(
    portfolio_id: UUID,
    user: ActiveUser,
    session: Session,
    currency: str = "ARS",
) -> RendimientoOut:
    """ROI por posición, XIRR y TWR de la cartera.

    **El XIRR y el TWR no miden lo mismo y por eso están los dos.** El XIRR
    responde cuánto rindió tu plata, así que le importa cuándo la pusiste. El
    TWR responde cuánto rindió la cartera, neutralizando los aportes: es la
    métrica con la que se comparan los fondos entre sí.

    El ROI de cada posición se calcula sobre el costo de lo que sigue abierto,
    no sobre el capital neto aportado: ese denominador se achica al vender e
    infla el porcentaje solo.
    """
    await _portfolio_propio(session, user.id, portfolio_id)
    r = await rendimiento_de_portfolio(
        session, user_id=user.id, portfolio_id=portfolio_id, currency=currency
    )
    return RendimientoOut(
        currency=r.currency,
        posiciones=[RoiOut.model_validate(p, from_attributes=True) for p in r.posiciones],
        realizado=r.realizado,
        no_realizado=r.no_realizado,
        resultado_total=r.resultado_total,
        valor_actual=r.valor_actual,
        aporte_neto=r.aporte_neto,
        xirr_anual=r.xirr_anual,
        xirr_motivo=r.xirr_motivo,
        twr=TwrOut.model_validate(r.twr, from_attributes=True),
    )


# ----------------------------------------------------------------- historial


@router.get(
    "/history", response_model=HistorialOut, summary="Evolucion de la cartera"
)
async def get_historial(
    portfolio_id: UUID,
    user: ActiveUser,
    session: Session,
    desde: date | None = None,
    hasta: date | None = None,
) -> HistorialOut:
    """Serie diaria del valor de la cartera.

    **La serie arranca el dia que se tomo el primer snapshot y crece hacia
    adelante.** No se puede reconstruir hacia atras: eso exigiria el precio de
    cada activo en cada dia pasado, y el sistema solo guarda la ultima
    cotizacion de cada uno. Rellenar los dias anteriores con el precio de hoy
    daria una linea plana que parece historia sin serlo.

    Los dias sin valuacion vienen con `total_value` en `null` y su motivo. El
    grafico corta ahi en vez de interpolar.

    `desde` y `hasta` acotan el período y son **inclusivos**. Acotar no cambia
    los puntos: cada uno sigue siendo el mismo cierre con su misma marca de
    estimado. Lo unico que cambia es cuantos se devuelven.
    """
    await _portfolio_propio(session, user.id, portfolio_id)

    _rango_valido(desde, hasta)

    puntos = await serie_de_snapshots(
        session, user_id=user.id, portfolio_id=portfolio_id, desde=desde, hasta=hasta
    )

    # Una serie que no existe y un período sin puntos son dos cosas distintas,
    # y el aviso tiene que mandar a la persona al lugar correcto: a esperar el
    # primer cierre en un caso, a cambiar el período en el otro.
    acotado = desde is not None or hasta is not None

    nota = None
    if not puntos:
        nota = (
            "No hay snapshots en el período elegido. Probá con un rango más "
            "amplio."
            if acotado
            else (
                "Todavia no hay historial. La serie arranca con el primer "
                "cierre diario y crece a partir de ahi: no se puede "
                "reconstruir hacia atras porque no existe el precio historico "
                "de cada activo."
            )
        )
    elif len(puntos) < 2:
        nota = (
            "Hay un solo punto en el período elegido. El grafico necesita al "
            "menos dos dias para dibujar una linea."
            if acotado
            else (
                "Hay un solo punto. El grafico necesita al menos dos dias "
                "para dibujar una linea."
            )
        )

    return HistorialOut(
        puntos=[PuntoOut.model_validate(p, from_attributes=True) for p in puntos],
        currency=puntos[0].currency if puntos else "ARS",
        desde=puntos[0].snapshot_date if puntos else None,
        nota=nota,
    )
