"""Saldo de caja: la plata que entró, salió y quedó sin invertir.

**El efectivo no se modela como un activo más.** Un depósito de pesos no es la
compra de un activo cuyo precio es 1: eso obligaría a inventar una cantidad
igual al monto y un precio ficticio, y esa ficción después aparece como una
"posición" en la cartera que nadie compró.

Se modela como lo que es: el saldo derivado de los movimientos.

    saldo = depósitos − retiros − compras + ventas − comisiones no atribuibles

Como todo lo derivado, se calcula desde el libro y nunca se edita.

Función pura: no sabe de HTTP, base de datos ni proveedores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.ledger import Transaction, TxType, active_sorted

ZERO = Decimal(0)

#: Tipos que mueven la caja, y con qué signo.
#:
#: `BUY` resta: comprar consume efectivo. `SELL` suma. `DIVIDEND` suma porque
#: el dinero entra a la cuenta. `TRANSFER` no aparece: mover plata entre
#: cuentas propias no cambia cuánto tenés en total, sólo dónde está.
SIGNOS: dict[TxType, int] = {
    TxType.DEPOSIT: +1,
    TxType.WITHDRAWAL: -1,
    TxType.BUY: -1,
    TxType.SELL: +1,
    TxType.DIVIDEND: +1,
    TxType.FEE: -1,
}


@dataclass(frozen=True, slots=True)
class MovimientoDeCaja:
    """Un movimiento con su efecto sobre el saldo."""

    tx_id: str
    tx_type: TxType
    fecha: datetime
    monto: Decimal
    saldo_posterior: Decimal
    currency: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class SaldoDeCaja:
    """Saldo con su desglose. El total solo no explica de dónde sale."""

    currency: str
    saldo: Decimal
    depositos: Decimal
    retiros: Decimal
    invertido: Decimal
    recuperado: Decimal
    dividendos: Decimal
    comisiones: Decimal
    movimientos: list[MovimientoDeCaja]

    @property
    def aporte_neto(self) -> Decimal:
        """Depósitos menos retiros: la plata que realmente pusiste.

        Es la candidata (3) de "capital invertido" de FINANCIAL_ENGINE.md, y
        la única de las tres que responde "cuánto puse de mi bolsillo". No se
        llama "capital invertido" porque ese nombre tiene tres significados
        incompatibles.

        Es también el flujo que va a necesitar el XIRR de la Fase 4.
        """
        return self.depositos - self.retiros

    @property
    def es_negativo(self) -> bool:
        """Un saldo negativo significa que falta registrar un depósito.

        No se impide: el libro registra lo que pasó, y forzar el orden de
        carga haría que el usuario invente un depósito para poder anotar una
        compra que sí ocurrió. Se muestra y se avisa.
        """
        return self.saldo < ZERO


def _monto_efectivo(tx: Transaction) -> Decimal:
    """Cuánto efectivo mueve una operación, en valor absoluto.

    En una compra la comisión **suma** a lo que sale de la cuenta; en una
    venta **resta** de lo que entra (D6). Por eso el neto no es simplemente
    cantidad × precio.
    """
    bruto = tx.quantity * tx.unit_price
    costos = tx.commission + tx.taxes

    if tx.tx_type is TxType.BUY:
        return bruto + costos
    if tx.tx_type is TxType.SELL:
        return bruto - costos
    # Depósitos, retiros, comisiones sueltas y dividendos se cargan con
    # cantidad 1 y el monto en el precio unitario.
    return bruto + costos if tx.tx_type is TxType.FEE else bruto


def calcular_saldo(
    transacciones: list[Transaction], currency: str = "ARS"
) -> SaldoDeCaja:
    """Reconstruye el saldo de caja desde el libro.

    Sólo considera operaciones de la moneda pedida: mezclar pesos y dólares en
    un mismo saldo requeriría convertir, y esa conversión necesita un tipo de
    cambio con su fecha (D2). Acá no se hace implícitamente.
    """
    ordenadas = [
        t
        for t in active_sorted(transacciones)
        if t.tx_type in SIGNOS and t.currency == currency.upper()
    ]

    saldo = ZERO
    depositos = retiros = invertido = recuperado = dividendos = comisiones = ZERO
    movimientos: list[MovimientoDeCaja] = []

    for tx in ordenadas:
        monto = _monto_efectivo(tx)
        signo = SIGNOS[tx.tx_type]
        saldo += signo * monto

        if tx.tx_type is TxType.DEPOSIT:
            depositos += monto
            descripcion = "Depósito"
        elif tx.tx_type is TxType.WITHDRAWAL:
            retiros += monto
            descripcion = "Retiro"
        elif tx.tx_type is TxType.BUY:
            invertido += monto
            descripcion = f"Compra de {tx.symbol}"
        elif tx.tx_type is TxType.SELL:
            recuperado += monto
            descripcion = f"Venta de {tx.symbol}"
        elif tx.tx_type is TxType.DIVIDEND:
            dividendos += monto
            descripcion = f"Dividendo de {tx.symbol}"
        else:
            comisiones += monto
            descripcion = "Costo de cuenta"

        movimientos.append(
            MovimientoDeCaja(
                tx_id=tx.tx_id,
                tx_type=tx.tx_type,
                fecha=tx.executed_at,
                monto=signo * monto,
                saldo_posterior=saldo,
                currency=currency.upper(),
                descripcion=descripcion,
            )
        )

    return SaldoDeCaja(
        currency=currency.upper(),
        saldo=saldo,
        depositos=depositos,
        retiros=retiros,
        invertido=invertido,
        recuperado=recuperado,
        dividendos=dividendos,
        comisiones=comisiones,
        movimientos=movimientos,
    )


def monedas_con_movimientos(transacciones: list[Transaction]) -> list[str]:
    """Monedas que tienen al menos un movimiento de caja."""
    return sorted(
        {t.currency for t in active_sorted(transacciones) if t.tx_type in SIGNOS}
    )
