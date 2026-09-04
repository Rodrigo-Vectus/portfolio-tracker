# DATA_MODEL.md — cambios de la Fase 2

> Este archivo **reemplaza** las secciones A.1, A.2, A.7 y B.6 de
> `DATA_MODEL.md`, y agrega A.8. El resto del documento sigue vigente.

---

## A.1 Migraciones (reemplaza)

| Revisión | Predecesora | Contenido |
|---|---|---|
| `0001_baseline` | — | `app_metadata` |
| `0002_auth` | `0001_baseline` | enums `user_role` y `audit_action`; tablas `user_account`, `refresh_token`, `audit_log` |
| `0003_finance` | `0002_auth` | 6 enums financieros; 11 tablas del modelo financiero; actualiza `app_metadata` a fase 2 |
| `0004_audit_tx` | `0003_finance` | agrega `TRANSACTION_CREATED`, `TRANSACTION_VOIDED`, `POSITIONS_REBUILT` a `audit_action` |

Las cuatro son reversibles y se probó `downgrade` + `upgrade` de las dos nuevas.

**Nota sobre `0004`.** `ALTER TYPE ... ADD VALUE` no corre dentro de un bloque
transaccional en PostgreSQL anterior a la 12, por eso va precedido de un
`COMMIT` explícito. Su `downgrade()` recrea el tipo y reapunta la columna, y
**aborta con un mensaje claro** si existen filas que usen los valores nuevos:
borrarlas sería destruir auditoría, y la bitácora no se borra desde la
aplicación.

---

## A.2 Enums nativos (agrega)

A `user_role` y `audit_action` se suman seis:

```
asset_type              CEDEAR · CRYPTO · CASH
account_type            BROKER · EXCHANGE · WALLET
transaction_type        BUY · SELL · DEPOSIT · WITHDRAWAL · FEE · DIVIDEND · TRANSFER
transaction_status      ACTIVE · VOIDED
corporate_action_type   SPLIT · RATIO_CHANGE · DIVIDEND
data_origin             INPUT · MARKET · COMPUTED
```

`audit_action` suma `TRANSACTION_CREATED`, `TRANSACTION_VOIDED` y
`POSITIONS_REBUILT`.

`data_origin` formaliza la convención `(MOD)` que el usuario había inventado en
su planilla para marcar las columnas que cargaba a mano.

---

## A.7 Entidades que NO existen (reemplaza)

**Ya existen** (migración `0003_finance`):

```
Asset · AssetIdentifier · CedearDetail · CedearRatio · CorporateAction
Account · Portfolio · Transaction · CostLot · LotConsumption · PositionCache
```

**Siguen sin existir:**

```
PriceQuote · PriceBarDaily · FxRate · ProviderLog     ← Fase 3
PortfolioSnapshot                                      ← Fase 5
ImportBatch                                            ← Fase 2.5
UserSettings                                           ← Fase 3
Role (tabla) · Permission                              ← REEMPLAZADAS por el enum
```

`transaction.import_batch_id` **existe como columna** desde `0003`, pero la
tabla `import_batch` no. Es deliberado: la columna da idempotencia al
importador y agregarla después obligaría a migrar el libro entero.

---

## A.8 Reglas transversales aplicadas (nuevo)

**Tipos numéricos.** Verificado contra la base:

```
cantidades   NUMERIC(38,18)
precios      NUMERIC(28,10)
importes     NUMERIC(38,18)
```

**Ninguna columna `DOUBLE PRECISION` ni `REAL`.** Cualquier tabla nueva debe
respetarlo.

**Serialización.** Los importes salen de la API como **string**. JSON usa doble
precisión: un `NUMERIC(38,18)` serializado como número llega distinto al
navegador sin que nada avise. De nada sirve `Decimal` de punta a punta si el
último tramo lo degrada.

**Redondeo.** No se redondea en la base ni en el dominio. El realizado por
costo promedio es una división que no cierra: sobre el historial real da
`477475.1351871143733252380232...`. Redondear antes del final corrompe el
total. El redondeo es decisión de presentación.

**Zona horaria.** `executed_at` se guarda en `TIMESTAMPTZ` normalizado a UTC.
Una fecha que llegue sin zona se interpreta en `DEFAULT_TIMEZONE`, **no en
UTC** (D24). `trade_date` se deriva del día **local**: una operación de las
22:30 en Buenos Aires es 01:30 UTC del día siguiente, y tomar la fecha en UTC
la mandaría a otra rueda.

**Chequeos en la base.** No alcanza con validar en la aplicación:

```sql
transaction:      CHECK (quantity >= 0)
                  CHECK (commission >= 0), CHECK (taxes >= 0)
                  CHECK (status <> 'VOIDED' OR voided_reason IS NOT NULL)
cost_lot:         CHECK (quantity_open >= 0)
                  CHECK (quantity_open <= quantity_original)
                  UNIQUE (source_tx_id)
lot_consumption:  CHECK (quantity > 0)
```

`UNIQUE(cost_lot.source_tx_id)` merece una nota: una compra abre exactamente un
lote. Si aparece un segundo, la reconstrucción corrió dos veces sin limpiar, y
eso se detecta al insertar en vez de descubrirse meses después con los números
ya torcidos.

**Aislamiento.** `transaction`, `cost_lot` y `position_cache` llevan `user_id`
aunque sea derivable del portfolio. Es redundancia deliberada: toda consulta
financiera filtra por el usuario autenticado, y ese filtro no debería depender
de un join que alguien olvide escribir.

**Claves foráneas del libro.** `transaction.account_id` y `transaction.asset_id`
usan `ON DELETE RESTRICT`, no `CASCADE`. Borrar una cuenta no puede llevarse
operaciones por delante.

---

## B.6 Derivados (reemplaza)

```
position_cache      user_id, portfolio_id, asset_id, quantity,
                    average_cost, open_cost_basis, realized_pnl,
                    cost_method, currency,
                    last_transaction_at, computed_at, computed_through

cost_lot            id, user_id, portfolio_id, asset_id, source_tx_id,
                    quantity_original, quantity_open, unit_cost,
                    currency, acquired_at, closed_at

lot_consumption     id, sell_tx_id, cost_lot_id, quantity, sequence
```

Tres cambios respecto del diseño original:

**1. `lot_consumption` no guarda `realized_pnl` (D18).** El diseño original lo
incluía. Se quitó porque un resultado a nivel de lote **no dice de qué método
es**, y no puede ser de los dos: sobre el historial real, el mismo consumo
produce 477.475 ARS por costo promedio y 575.975 por FIFO.

Lo que sí es unívoco es **qué lote se agotó y en qué orden**, y eso es lo que se
guarda, junto con `sequence` para poder reproducir la secuencia al auditar. El
resultado de cada método lo calcula `app/domain/cost_basis.py` sobre la misma
secuencia.

Que el consumo físico sea FIFO no es una elección contable: es el orden en que
se agotan los lotes, y es el mismo para todos los métodos.

**2. `invested_amount` pasó a llamarse `open_cost_basis` (D19).** Hay tres
definiciones incompatibles de "capital invertido" y dan tres porcentajes
distintos. Esta columna guarda una sola: el costo base de los lotes abiertos.
El nombre lo dice para que nadie la confunda.

**3. `cost_method` es una columna nueva.** Sin ella, el `realized_pnl` guardado
sería ambiguo por el mismo motivo del punto 1.

**Lo que sigue sin persistirse, y es lo más importante:** `position_cache` no
guarda `current_price`, `current_value` ni `unrealized_pnl`. Esa era la entidad
`Position` de la especificación original, que mezclaba dato ingresado, dato de
mercado y dato calculado en una fila: el mismo problema de la planilla con más
pasos. El valor actual se resolverá en tiempo de consulta, con su `as_of`.

---

## B.9 Aislamiento por usuario (actualiza el estado)

Estado: **IMPLEMENTADO Y VALIDADO**.

Verificado con pruebas reales: dos usuarios, cada uno pide el recurso del otro,
ambos reciben **404**. El segundo usuario de esas pruebas es un **ADMIN** a
propósito: administrar la plataforma no da acceso funcional a carteras ajenas.

El 404 y no 403 es deliberado: un 403 confirmaría que el recurso existe y solo
no es tuyo, con lo que se pueden enumerar carteras probando identificadores.
