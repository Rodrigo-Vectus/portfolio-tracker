# Dominio

Este paquete contiene el **modelo financiero en Python puro**: sin FastAPI,
sin SQLAlchemy, sin Redis. Recibe operaciones y cotizaciones, devuelve
numeros.

La razon es simple: los calculos de cantidad, costo, valuacion y rendimiento
son la parte del sistema donde un error importa de verdad. Aislandolos de la
infraestructura se pueden testear con casos verificados a mano, sin levantar
una base de datos.

Contenido previsto:

    ledger.py        reglas y validaciones de operaciones
    positions.py     operaciones -> lotes -> posicion
    cost_basis.py    estrategias de costo (WAC / FIFO) sobre el ledger de lotes
    valuation.py     posicion x cotizacion x tipo de cambio -> valor
    performance.py   ROI, TWR, XIRR, realizado y no realizado
    money.py         tipo Money (Decimal + moneda). Nunca float.

Vacio en Fase 0 a proposito. Se implementa en Fase 2.
