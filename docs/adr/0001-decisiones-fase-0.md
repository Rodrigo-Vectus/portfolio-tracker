# ADR 0001 — Decisiones tomadas antes de escribir codigo

Fecha: 2026-09-02 · Estado: aceptado

Registro de las decisiones que quedaron cerradas tras analizar la
especificacion y el Excel anterior (`FINANZAS - POSTA CON USD.xlsx`).

## Decisiones de dominio

| # | Decision | Resolucion |
|---|---|---|
| D1 | Que es "USD" | Dolar **MEP** para CEDEARs, **USDT** para cripto. El total de cartera mezcla dos tipos de cambio a proposito: cada activo se valua al dolar por el que efectivamente se liquidaria. La interfaz debe mostrarlo, no esconderlo. |
| D2 | Moneda de contabilidad | Se calcula en la moneda de la operacion. Se valua en USD por defecto. El costo se convierte al FX **de la fecha de cada operacion** (metodo de moneda dura). ARS queda como vista alternativa. |
| D3 | Rendimiento | ROI simple por posicion; **XIRR** y **TWR** a nivel cartera. |
| D4 | Costo | **Ledger de lotes** desde F2, con promedio ponderado (WAC) como vista por defecto y FIFO disponible sin migrar. Justificacion: sobre el historial real, FIFO y WAC difieren 287.567 ARS (41,6%) en el resultado realizado. |
| D5 | Valuacion de CEDEARs | Precio local de BYMA como valor oficial. El teorico (subyacente x ratio x FX) se calcula como dato secundario. |
| D6 | Comisiones | Suman al costo base en compras, restan del producido en ventas. Campo aparte para derechos de mercado e IVA. Tipo `FEE` solo para costos no atribuibles a un activo. |
| D7 | Caja | Se modela desde F2. Sin caja no hay XIRR ni "cuanto tengo sin invertir". |
| D8 | USDT / USDC | Activo de tipo `CASH` en USD, pero con precio de mercado propio en ARS. |
| D9 | Dividendos | El tipo `DIVIDEND` existe en el modelo desde F2. La carga automatica llega despues. |
| D10 | Proveedores de cotizacion | A validar en vivo durante F3. La interfaz `MarketDataProvider` existe justamente para que no sea una decision irreversible. |
| D11 | Autenticacion | JWT de vida corta + refresh token en cookie httpOnly + proteccion CSRF. Sin auto-registro: los usuarios los crea el administrador. |
| D12 | Actualizacion de precios | Cripto cada 5 min; CEDEARs cada 15 min en rueda; FX cada 30 min. Umbral de dato viejo configurable por tipo de activo. |
| D13 | Edicion de operaciones | Ledger inmutable: se anula (`VOIDED`) y se recrea, con auditoria. Recalcula lotes, posiciones y snapshots posteriores. |
| D14 | Posicion de AAPL | Reconciliar las filas 41 y 44 del Excel contra los extractos de IOL **antes** de importar. Bloquea F2.5, no F0. |
| D15 | Historial de caja | Se arranca en cero. La TIR se calcula hacia adelante. |
| D16 | Historico en dolares | Se guardan ambos: el TC que el usuario registro como dato `INPUT`, y la serie MEP oficial como dato `MARKET`. El usuario elige la vista. |
| D17 | Cuentas | IOL (broker), Binance y BingX (exchanges). Modelo extensible: las cuentas son filas, no un enum. |

## Decisiones tecnicas de la Fase 0

**Worker: ARQ en lugar de Celery.** Celery esta pensado para cargas
distribuidas grandes y arrastra bastante configuracion. ARQ es async nativo
(mismo modelo de concurrencia que FastAPI), pesa mucho menos, y usa el Redis
que de todos modos hace falta para cachear cotizaciones.

**Migraciones con Alembic sobre engine async.** Un unico driver (asyncpg) en
todo el sistema, en lugar de mantener asyncpg para la app y psycopg para las
migraciones.

**Convencion de nombres explicita en SQLAlchemy.** Sin ella, Alembic genera
nombres de constraint distintos segun el contexto y las migraciones dejan de
ser reproducibles.

**`liveness` y `readiness` separados.** Si el chequeo de vida consultara la
base, una caida momentanea de Postgres haria que Docker reinicie un backend
que estaba perfectamente sano.

**Postgres y Redis sin puertos publicados.** Solo son accesibles desde la red
interna de Docker. Para conectarse a la base se usa `docker compose exec` o un
tunel SSH.

**El dominio no conoce la infraestructura.** `app/domain/` es Python puro. Los
calculos financieros se testean sin levantar una base de datos.

**Decimal, nunca float.** Los importes iran en `NUMERIC`; las cantidades en
`NUMERIC(38,18)` por los 18 decimales de las criptomonedas. Se define en F2,
pero la decision ya esta tomada.

**`portfolio_id` desde el primer modelo.** Multiples portfolios por usuario
figura como "futuro" en la especificacion, pero agregar esa columna despues
obliga a migrar toda la tabla de operaciones. Cuesta casi nada ahora.
