"""Traduccion entre la persistencia y el dominio.

El dominio es Python puro y no conoce SQLAlchemy: esa separacion es lo que
permite testear los calculos sin levantar una base. El precio de esa decision
es que alguien tiene que traducir, y ese alguien es este modulo.

Todo el trafico entre las dos capas pasa por aca. Si aparece un
`from app.models import ...` dentro de `app/domain/`, la separacion se rompio.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.cost_basis import CostLot as DomainLot
from app.domain.ledger import Transaction as DomainTx
from app.domain.ledger import TxStatus, TxType
from app.models.enums_finance import TransactionStatus, TransactionType
from app.models.transaction import Transaction as OrmTx


def to_domain(row: OrmTx, *, symbol: str) -> DomainTx:
    """Convierte una fila del libro en una operacion del dominio.

    El simbolo se pasa aparte y no se lee de `row.asset`: cargar la relacion
    dispararia una consulta por operacion, y el motor recorre el historial
    completo de un activo. Quien llama ya tiene el activo cargado.

    Los valores llegan como `Decimal` desde la base y se pasan tal cual. Si en
    algun punto llegara un `float`, el constructor de `Money` lo rechaza: esa
    es la red de seguridad de la Regla 2 y no debe eliminarse por comodidad.
    """
    return DomainTx(
        tx_id=str(row.id),
        symbol=symbol,
        tx_type=TxType(row.tx_type.value),
        quantity=row.quantity,
        unit_price=row.unit_price,
        currency=row.price_currency,
        executed_at=row.executed_at,
        trade_date=row.trade_date,
        commission=row.commission or Decimal(0),
        taxes=row.taxes or Decimal(0),
        status=(
            TxStatus.ACTIVE
            if row.status is TransactionStatus.ACTIVE
            else TxStatus.VOIDED
        ),
    )


def domain_type_to_orm(tx_type: TxType) -> TransactionType:
    return TransactionType(tx_type.value)


def lot_source_tx_id(lot: DomainLot) -> str:
    """Devuelve el id de la operacion que abrio el lote.

    El dominio identifica sus lotes como `lot:<tx_id>` porque no conoce UUID
    ni base de datos. Al persistir hay que recuperar ese id para enlazar con
    `cost_lot.source_tx_id`.
    """
    return lot.source_tx_id
