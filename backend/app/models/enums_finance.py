"""Enumeraciones del dominio financiero (Fase 2).

Se declaran como enums nativos de PostgreSQL, igual que `user_role`: la base
valida el valor y agregar uno exige una migracion explicita. En un sistema
donde el tipo de operacion define el signo del dinero, no alcanza con que lo
valide la aplicacion.

Estos enums son el espejo de los del dominio (`app/domain/ledger.py`). El
dominio no importa este modulo a proposito: es Python puro y no debe conocer
SQLAlchemy. La duplicacion es el precio de esa separacion, y es barata: son
listas de constantes que cambian con una migracion de por medio.
"""

from enum import StrEnum


class AssetType(StrEnum):
    """Que clase de activo es.

    `CASH` incluye tanto pesos y dolares como USDT y USDC (D8): son efectivo
    en su moneda, pero tienen precio de mercado propio en ARS. En Argentina el
    USDT no vale exactamente un dolar, y modelarlo como si valiera 1 seria
    inventar un dato.
    """

    CEDEAR = "CEDEAR"
    CRYPTO = "CRYPTO"
    CASH = "CASH"


class AccountType(StrEnum):
    BROKER = "BROKER"
    EXCHANGE = "EXCHANGE"
    WALLET = "WALLET"


class TransactionType(StrEnum):
    """Tipos de operacion (D6, D7, D9).

    `FEE` es solo para costos **no atribuibles a un activo**, como el
    mantenimiento de cuenta. La comision de una compra o una venta no es un
    `FEE`: es un campo de esa misma operacion, porque afecta su costo base.
    """

    BUY = "BUY"
    SELL = "SELL"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    FEE = "FEE"
    DIVIDEND = "DIVIDEND"
    TRANSFER = "TRANSFER"


class TransactionStatus(StrEnum):
    """D13: el libro es inmutable.

    Una operacion no se borra ni se edita: se anula y se crea la correccion.
    Sin esto no hay forma de reconstruir que se sabia en cada momento, ni de
    auditar quien cambio que.
    """

    ACTIVE = "ACTIVE"
    VOIDED = "VOIDED"


class CorporateActionType(StrEnum):
    SPLIT = "SPLIT"
    RATIO_CHANGE = "RATIO_CHANGE"
    DIVIDEND = "DIVIDEND"


class DataOrigin(StrEnum):
    """De donde salio un numero.

    Formaliza la convencion `(MOD)` que el propio usuario habia inventado en
    su planilla para marcar las cuatro columnas que cargaba a mano. Distinguir
    dato ingresado, dato de mercado y dato calculado es requisito de producto:
    la interfaz tiene que poder explicar cada numero que muestra.
    """

    INPUT = "INPUT"
    MARKET = "MARKET"
    COMPUTED = "COMPUTED"
