# PROJECT_STATE.md

> Fotografía documental del proyecto **Portfolio Tracker**.
> Fecha de corte: **2026-09-04**.
> Último commit conocido: **`0f1bcd2`+** en `main` (ver §Historial).
> Fases cerradas: **0, 1, 1.5 y 2**. Próxima: **Fase 2.5 o 3**.

---

## Nombre del proyecto

**Portfolio Tracker** — plataforma web personal de seguimiento y gestión de
inversiones (CEDEARs y criptomonedas), desarrollada para reemplazar una
planilla de Excel.

Repositorio: `github.com/Rodrigo-Vectus/portfolio-tracker` (público)
Servidor: `automation-server`, IP local `192.168.11.125`, Ubuntu Server 22.04
Directorio: `/root/portfolio-tracker`

---

## Propósito

Reemplazar el archivo `FINANZAS - POSTA CON USD.xlsx` por un sistema donde el
valor de la cartera se derive de un historial de operaciones y de cotizaciones
obtenidas automáticamente, en lugar de depender de precios escritos a mano.

El problema concreto que motiva el proyecto: **el número que mostraba el Excel
no coincidía con el broker**. Tres causas identificadas: precio actual manual y
desactualizado, un error de datos en la posición de AAPL, y ausencia total de
comisiones e impuestos.

---

## Principio rector

```
OPERACIONES → POSICIONES → COTIZACIONES → VALUACIÓN → RENDIMIENTO → DASHBOARD
```

- **Operaciones**: hecho histórico inmutable, ingresado por el usuario.
- **Posiciones**: función pura del historial. Nunca se editan a mano.
- **Cotizaciones**: hecho externo con fuente y timestamp.
- **Valuación / rendimiento**: siempre derivados, siempre con fecha de corte.

Ningún paso escribe hacia atrás. Todo dato derivado es caché reconstruible.

Contrato de la API para valores monetarios
(`{ value, currency, origin, as_of, source, stale }`): **DEFINIDO — PENDIENTE**.
Hoy los importes ya viajan como **string** (ver Fase 2), pero el sobre completo
con `as_of` y `stale` llega en la Fase 4, cuando existan cotizaciones.

---

## Estado general

**Infraestructura, acceso y modelo financiero: terminados y validados.
Cotizaciones y valuación: no comenzadas.**

La aplicación ya registra operaciones, valida contra la tenencia, materializa
lotes y devuelve posiciones derivadas. **No hay ningún precio de mercado**, y
las posiciones se exponen sin valor actual a propósito.

---

## Estado de cada componente

| Componente | Estado | Detalle |
|---|---|---|
| **Frontend** | IMPLEMENTADO Y VALIDADO (esqueleto) | React 18 + TS + Vite + Tailwind. 9 rutas. **Sin consumir todavía los endpoints financieros.** |
| **Backend** | IMPLEMENTADO Y VALIDADO | FastAPI + Python 3.12. **17 endpoints**. |
| **Database** | IMPLEMENTADO Y VALIDADO | PostgreSQL 16. **16 tablas**, 4 migraciones. |
| **Worker** | IMPLEMENTADO (mínimo) | ARQ. Solo latido. Sin tareas reales. |
| **Redis** | IMPLEMENTADO Y VALIDADO | DB 0 para la app, **DB 1 para las pruebas**. |
| **Market data** | PENDIENTE | Nada implementado. Fase 3. |
| **Portfolio engine** | **IMPLEMENTADO Y VALIDADO** | `app/domain/`: money, ledger, cost_basis, positions. Python puro. |
| **Autenticación** | IMPLEMENTADO Y VALIDADO | Sin cambios respecto de la Fase 1. |
| **Autorización** | **IMPLEMENTADO Y VALIDADO** | Aislamiento por `user_id` con pruebas reales. |
| **Dashboard** | PENDIENTE | Fase 6. |
| **Operaciones** | **IMPLEMENTADO Y VALIDADO** | Alta validada, anulación con motivo, listado. |
| **Posiciones** | **IMPLEMENTADO Y VALIDADO** | Derivadas, sin precio de mercado. |
| **Históricos de precio** | PENDIENTE | Fase 3. |
| **Snapshots** | PENDIENTE | Fase 5. |
| **Auditoría** | IMPLEMENTADO Y VALIDADO | Sesión + operaciones. Sin pantalla (Fase 7). |
| **Testing** | **IMPLEMENTADO Y VALIDADO** | 72 pruebas. Base y Redis dedicados. |
| **Docker** | IMPLEMENTADO Y VALIDADO | Compose, proyecto `pt`. |
| **Deployment** | IMPLEMENTADO (desarrollo) | Sin TLS, sin reverse proxy, sin backups automáticos. |
| **Git** | IMPLEMENTADO Y VALIDADO | `main`, SSH. |

---

## Lo que se implementó en la Fase 2

### Modelo de datos (migración `0003_finance`)

Diez tablas: `asset`, `asset_identifier`, `cedear_detail`, `cedear_ratio`,
`corporate_action`, `account`, `portfolio`, `transaction`, `cost_lot`,
`lot_consumption`, más `position_cache`. Seis enums nativos.

Verificado en la base: **ninguna columna `double precision` ni `real`**. Todo
importe en `NUMERIC(38,18)`, precios en `NUMERIC(28,10)`.

Chequeos en la base, no solo en la aplicación:

```sql
CHECK (quantity >= 0)
CHECK (status <> 'VOIDED' OR voided_reason IS NOT NULL)
UNIQUE (cost_lot.source_tx_id)      -- una compra abre exactamente un lote
```

### Motor de dominio (`app/domain/`)

Python puro, sin FastAPI ni SQLAlchemy ni Redis.

- `money.py` — `Money` = `Decimal` + moneda. **Rechaza `float` en el
  constructor** y se niega a sumar monedas distintas.
- `ledger.py` — `Transaction` inmutable, cantidad siempre positiva, el signo
  lo lleva el tipo. `InsufficientHoldings`.
- `cost_basis.py` — ledger de lotes, consumo FIFO físico, realizado por método.
- `positions.py` — operaciones → posición derivada.

### Servicios

- `services/mappers.py` — traducción ORM ↔ dominio.
- `services/transactions.py` — alta validada **antes** de escribir; anulación
  con motivo que verifica que el historial posterior siga siendo válido.
- `services/positions.py` — borra lo derivado y lo rehace entero, nunca parchea.
- `app/cli.py rebuild-positions` — reconstrucción total.

### Endpoints (8 nuevos)

`GET/POST /api/assets` · `GET/POST /api/accounts` · `GET/POST /api/portfolios`
`GET/POST /api/transactions` · `POST /api/transactions/{id}/void`
`GET /api/positions`

### Migración `0004_audit_tx`

Agrega `TRANSACTION_CREATED`, `TRANSACTION_VOIDED` y `POSITIONS_REBUILT` al
enum `audit_action`. `downgrade()` funcional que **aborta** si hay filas que
usen los valores nuevos: borrarlas sería destruir auditoría.

---

## Lo que se implementó en la Fase 1.5

Aislamiento de las pruebas. Ver §Problemas conocidos, punto 8.

- `scripts/test.sh` — crea `portfolio_tracker_test`, migra, corre pytest con
  `REDIS_DB=1`.
- `tests/conftest.py` — **se niega a correr** si la base no termina en `_test`
  o si `REDIS_DB` es 0.
- Cada prueba crea su propio usuario con contraseña generada. Ninguna depende
  del admin sembrado ni del `.env`.
- El `conftest.py` ya no importa FastAPI a nivel de módulo.

---

## Validación registrada

Ejecutado en el servidor del usuario:

- `alembic current` → `0004_audit_tx (head)`.
- `alembic downgrade -1` y `upgrade head` en ambas migraciones nuevas: reversibles.
- `bash scripts/test.sh` → **72 pruebas, todas pasan**.
- `pytest` a secas → **se detiene** con el mensaje de la guarda, sin escribir nada.
- Base real tras correr la suite: 1 usuario, 0 operaciones, 0 activos,
  0 portfolios, sin entradas nuevas de auditoría, sin contadores en Redis DB 0.
- `health/ready` → los tres chequeos en `ok`, migración `0004_audit_tx`.

Verificado en el entorno de trabajo (sin PostgreSQL): 28 pruebas de dominio,
mapeo y zona horaria; DDL de `0003` compilado contra el dialecto PostgreSQL.

---

## Decisiones nuevas de esta sesión

| # | Decisión | Motivo |
|---|---|---|
| D18 | **`lot_consumption` no guarda `realized_pnl`** | Sobre el historial real el mismo consumo da 477.475 ARS por WAC y 575.975 por FIFO. Una columna no puede guardar los dos, y sin etiqueta de método el dato es ambiguo. Cada método se calcula en el dominio sobre la misma secuencia. **Cambia `DATA_MODEL.md` §B.6 original.** |
| D19 | **`position_cache.open_cost_basis`** en vez de `invested_amount` | Hay tres definiciones incompatibles de "capital invertido". El nombre explícito evita que se confundan. Las otras dos se definen en la Fase 4. |
| D20 | **Importes en `NUMERIC(38,18)`, sin redondeo en base ni dominio** | El redondeo es decisión de presentación. El realizado WAC exacto es un decimal periódico: redondear antes del final corrompe el total. |
| D21 | **Venta que excede la tenencia: el motor siempre rechaza** | Nunca produce cantidad negativa. Qué hace el importador con esa excepción es decisión de la Fase 2.5. |
| D22 | **Los importes se serializan como string en JSON** | JSON usa doble precisión: un `NUMERIC(38,18)` como número llega distinto al navegador sin que nada avise. |
| D23 | **Recálculo de posiciones sincrónico** | La operación, sus lotes y su auditoría entran en la misma transacción o no entra ninguna. Si el volumen crece, se mueve al worker **con `as_of` marcado**, no en silencio. |
| D24 | **Fecha sin zona = zona configurada del sistema**, no UTC | Asumir UTC mandaría una compra de las 22:30 a la rueda del día siguiente. Si el cliente manda offset, se respeta. |
| D25 | **Las pruebas no corren contra la base real** | Guarda en el código, no en la memoria de quien ejecuta. |

D1–D17 siguen vigentes sin cambios.

---

## Problemas conocidos (resueltos en esta sesión)

| # | Problema | Causa raíz | Solución |
|---|---|---|---|
| 8 | **La suite daba resultados distintos entre corridas** | Las pruebas de API usaban el admin sembrado. El usuario había cambiado su contraseña (como el sistema le exigía), así que fallaban; y cada corrida sumaba 8 `LOGIN_FAILED`, agotando el límite y convirtiendo 401 en 429 | Fase 1.5: base y Redis dedicados, usuario propio por prueba |
| 9 | **El enum `audit_action` no tenía las acciones de operaciones** | Insertar una entrada de bitácora por una operación hacía que PostgreSQL rechazara el `INSERT` y **abortara la transacción completa** | Migración `0004_audit_tx` |
| 10 | **`TypeError: can't compare offset-naive and offset-aware datetimes`** | El historial sale de `TIMESTAMPTZ` con zona; la operación nueva venía del JSON sin zona. Ordenarlas juntas reventaba **en el motor de lotes**, lejos de la causa, y solo en la segunda operación | `app/core/timezones.py`, normalización en el borde de la API y en el mapeo |
| 11 | **`trade_date` derivado de `.date()` sobre UTC** | Una operación de las 22:30 en Buenos Aires quedaba en la rueda del día siguiente | `fecha_de_rueda()` |
| 12 | **Dominio de prueba `.test` rechazado por `email-validator`** | Es un TLD de uso especial. Todos los logins de prueba devolvían 422 | `example.com`, reservado por IANA y no entregable |
| 13 | **El `conftest.py` importaba FastAPI a nivel de módulo** | Las pruebas de dominio, que son Python puro, no podían importarse sin infraestructura | Imports dentro de las fixtures |

Los problemas 1 a 7 de la Fase 0/1 siguen resueltos y documentados igual.

**Patrón que se repite:** los problemas 9, 10 y 11 aparecieron **lejos de su
causa**, igual que el bug de `INET` en la Fase 1. Ninguno fue detectado por
pruebas unitarias; los tres aparecieron al integrar contra una base real.

---

## Pendientes críticos

1. **Reconciliar la posición de AAPL contra los extractos de IOL** (D14).
   **Bloquea la Fase 2.5.** El motor hoy **rechaza** el historial de AAPL con
   `InsufficientHoldings` (venta de 25 con tenencia de 13), que es el
   comportamiento correcto, pero significa que ese activo no se puede importar.
2. **Seguridad de producción**: `COOKIE_SECURE=false`, sin TLS,
   `BIND_ADDR=0.0.0.0` sin reverse proxy. Fase 9.
3. **Sin backups automatizados.** Existe `pg_dump` manual, y ya se usó dos
   veces con éxito en esta sesión (6,2 K y 11 K, no vacíos). Fase 8.

---

## Pendientes menores

1. Volumen huérfano `portfolio-tracker_pgdata` (47 MB). Sin inspeccionar.
2. Contraseñas genéricas de PostgreSQL y del seed, a cambiar al cierre.
3. **El `.gitignore` tiene el bloque de `*.xlsx` duplicado.** Inofensivo, pero
   ensucia un archivo que se lee para entender qué se protege.
4. Advertencias de deprecación: `httpx` en `starlette.testclient`, y
   `HTTP_422_UNPROCESSABLE_ENTITY` → `HTTP_422_UNPROCESSABLE_CONTENT`.
   Cosméticas.
5. El bit de ejecución de los entrypoints se pierde en cada entrega por tar.
6. **El frontend no consume ninguno de los endpoints financieros nuevos.** Hay
   API sin interfaz.

---

## Próxima tarea

### REQUIERE DECISIÓN DEL USUARIO

No hay una única próxima tarea obvia. Tres caminos, con criterio:

**A. Fase 2.5 — importador del Excel.** Sigue **bloqueada por D14**. Se puede
construir el parser y el dry-run sin resolver AAPL, pero no se puede importar.

**B. Fase 3 — market data.** Es el siguiente paso natural del principio rector
y no depende de nada pendiente. Requiere validar proveedores en vivo (D10) y
definir qué criptomonedas opera realmente el usuario.

**C. Frontend de la Fase 2.** Hoy hay ocho endpoints sin ninguna pantalla que
los use. No estaba en el plan de fases original como paso separado, pero sin
esto el usuario no puede cargar una sola operación por la interfaz.

**Recomendación:** C antes que B. La Fase 2 no es verificable de punta a punta
por el usuario hasta que exista una pantalla; hoy solo se puede comprobar por
`curl` o por los tests. Y cargar operaciones a mano es lo que destraba poder
usar el sistema aunque la importación siga bloqueada.

### Definiciones que siguen abiertas

- Definición exacta de "capital invertido" para el **rendimiento** (Fase 4).
  `open_cost_basis` resolvió solo el caso de `position_cache`.
- Cómo se presenta un total de cartera que mezcla MEP y USDT.
- Convención de arrastre de precios en días sin cotización.
- Qué hacer con una venta que excede la tenencia **durante la importación**.
- Impuestos de renta financiera: nunca se discutió si el sistema los calcula.
- Tratamiento de dividendos en el rendimiento.
