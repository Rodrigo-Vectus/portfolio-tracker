# FINANCIAL_ENGINE.md — cambios de la Fase 2

> Reemplaza el **ESTADO GLOBAL** de la cabecera, corrige §1.5 y actualiza la
> Parte 3. La Parte 1 (análisis del Excel) sigue vigente salvo lo indicado.

---

## ESTADO GLOBAL (reemplaza)

> **El motor está implementado y validado contra el historial real.**
>
> `backend/app/domain/` contiene `money.py`, `ledger.py`, `cost_basis.py` y
> `positions.py`, en Python puro: sin FastAPI, sin SQLAlchemy, sin Redis.
>
> **Lo que sigue sin existir: cotizaciones, tipo de cambio, valuación y
> rendimiento.** Las posiciones se calculan y se exponen **sin valor de
> mercado**, a propósito.

---

## 1.5 Números de referencia — CORRECCIÓN IMPORTANTE

Los números documentados originalmente se validaron corriendo las 73
operaciones reales contra el motor. **Doce comparaciones, doce coincidencias.**

| Ticker | Posición | Realizado WAC | Realizado FIFO | No realizado |
|---|---:|---:|---:|---:|
| MELI | 60 ✔ | 11.978 ✔ | 17.740 ✔ | −39.568 ✔ |
| MSFT | 17 ✔ | 208.545 ✔ | 208.545 ✔ | −7.640 ✔ |
| QQQ | 49 ✔ | 97.348 ✔ | 133.240 ✔ | 522.297 ✔ |
| SPY | 88 ✔ | 159.604 ✔ | 216.450 ✔ | 957.021 ✔ |

### Corrección 1 — los totales son exactos, los valores por ticker están redondeados

Al sumar los valores por ticker daba un peso menos que el total documentado.
La causa no era un error: **los valores por ticker están redondeados y los
totales son exactos.**

```
FIFO   575.975 (cuatro tickers) + 402.164 (AAPL) = 978.139   exacto
WAC    477.475,1352...          + AAPL           = 690.572   exacto
```

Al escribir pruebas sobre estos números hay que **comparar a una precisión
declarada**, no al valor completo. El realizado WAC exacto es
`477475.1351871143733252380232...`: el precio promedio móvil es una división
que no cierra y el motor no redondea nunca.

### Corrección 2 — los valores de AAPL NO son una referencia válida

`AAPL: realizado WAC 213.096 · FIFO 402.164 · no realizado −54.102`

Estos números **fueron calculados tolerando una posición negativa**. El motor
actual rechaza ese historial con `InsufficientHoldings`: venta de 25 unidades
con una tenencia de 13, exactamente la fila 44 del Excel.

**No deben usarse como caso de prueba** hasta que se resuelva D14. Están
contaminados por el mismo error de datos que motivó el proyecto.

Que el motor los rechace no es una limitación: es la prueba de que la
validación funciona sobre datos reales.

---

## Parte 2 — decisiones nuevas

D1–D17 siguen vigentes. Se agregan **D18 a D25**, registradas en
`PROJECT_STATE.md`. Las que afectan directamente al cálculo:

| # | Decisión |
|---|---|
| D18 | `lot_consumption` guarda consumo de cantidad, no resultado realizado |
| D19 | `open_cost_basis` en vez de "capital invertido" en `position_cache` |
| D20 | Sin redondeo en base ni dominio; solo en presentación |
| D21 | Venta que excede la tenencia: el motor **siempre** rechaza |
| D24 | Fecha sin zona = zona configurada, no UTC |

---

## Parte 3 — definiciones de cálculo (estado actualizado)

### 3.1 Operaciones — **IMPLEMENTADO**

Los siete tipos existen en el enum. La cantidad es **siempre positiva** y el
signo lo lleva el tipo: la convención de la planilla (venta = cantidad
negativa, con la columna de precio de compra guardando el de venta) no se puede
escribir, ni siquiera saltándose la aplicación.

Ledger inmutable con anulación: se anula con motivo obligatorio y se crea la
corrección. Anular verifica que el historial posterior siga siendo válido; si
anular una compra dejaría una venta descubierta, **falla entera y explica por
qué**, en vez de dejar una posición imposible.

### 3.2 Posiciones — **IMPLEMENTADO**

Derivadas del historial, nunca editables. `position_cache` es caché
reconstruible y existe `python -m app.cli rebuild-positions`.

La estrategia de recálculo es **borrar lo derivado y rehacerlo entero**, nunca
parchear. Es deliberado: un recálculo incremental tiene que acertar en cada
camino posible (alta, anulación, corrección retroactiva, importación), y basta
que falle en uno para que el caché discrepe del libro con números que siguen
pareciendo razonables.

El recálculo es **sincrónico** (D23): la operación, sus lotes y su auditoría
entran en la misma transacción de base o no entra ninguna.

### 3.3 Precio promedio — **IMPLEMENTADO**

WAC como vista por defecto, FIFO disponible sobre los mismos lotes. Ambos
verificados contra el historial real.

### 3.4 Capital invertido — **PARCIALMENTE RESUELTO**

`position_cache.open_cost_basis` implementa la candidata (1): costo base de los
lotes abiertos.

**Las otras dos siguen sin definir**, y hacen falta para el rendimiento de la
Fase 4:

- Compras menos ventas (capital neto aportado) — no debe llamarse "capital
  invertido".
- Depósitos menos retiros — no disponible por D15.

`REQUIERE DEFINICIÓN ANTES DE IMPLEMENTAR LA FASE 4.`

### 3.5 Valor actual — **PENDIENTE**

Sin cambios: no hay cotizaciones. `GET /api/positions` **no devuelve valor de
mercado** y eso es intencional, no un olvido.

### 3.6 P&L — **PARCIALMENTE IMPLEMENTADO**

Realizado: implementado y verificado, por WAC y por FIFO.
No realizado: **PENDIENTE**, requiere cotizaciones (Fase 4).

### 3.7 Rendimiento porcentual — **PENDIENTE**

ROI, TWR y XIRR: nada implementado. Fase 4.

### 3.8 Comisiones — **IMPLEMENTADO**

Compras: suman al costo base del lote, prorrateadas en `unit_cost`.
Ventas: restan del producido, **una sola vez por venta y no por cada lote
consumido**. Hay una prueba específica para eso.

### 3.9 Monedas — **PARCIALMENTE IMPLEMENTADO**

`transaction` separa `price_currency` de `settlement_currency`. El dominio se
niega a sumar monedas distintas: pide un tipo de cambio explícito con su fecha.

`portfolio.base_currency` existe. `display_currency` (preferencia del usuario)
sigue pendiente, Fase 3.

### 3.10 Tipo de cambio — **PENDIENTE**

`transaction.fx_rate_used`, `fx_source` y `fx_origin` existen como columnas. La
tabla `fx_rate` y toda la serie histórica: Fase 3.

### 3.11 CEDEARs — **MODELO IMPLEMENTADO, VALUACIÓN PENDIENTE**

`asset`, `cedear_detail`, `cedear_ratio` (serie con vigencia) y
`corporate_action` existen como tablas. **Ningún ratio fue cargado ni
verificado.** La valuación teórica (D5) sigue sin implementarse.

Ratios de AAPL, MSFT, MELI, SPY y QQQ: `REQUIERE VERIFICACIÓN`.

### 3.12 Criptomonedas — **MODELO IMPLEMENTADO, TODO LO DEMÁS PENDIENTE**

`asset_type = CRYPTO` existe. Qué monedas opera el usuario:
`REQUIERE VERIFICACIÓN`.

### 3.13 Snapshots — **PENDIENTE**, Fase 5.

---

## Parte 4 — problemas pendientes (actualizado)

Resueltos en la Fase 2: el punto 4 (venta que excede la tenencia **en el
motor**, D21) y el punto 5 (redondeo, D20).

Siguen abiertos:

1. Definición de "capital invertido" para el rendimiento (ver 3.4).
2. Agregación de cartera con dos tipos de cambio distintos (MEP y USDT).
3. Convención de arrastre de precios en días sin cotización.
4. Qué hacer con una venta que excede la tenencia **durante la importación**.
   El motor rechaza; falta decidir si el importador salta la fila, rechaza el
   lote o importa marcando.
5. Impuestos de renta financiera: nunca se discutió si el sistema los calcula.
6. Tratamiento de dividendos en el rendimiento.

### Riesgos financieros (actualizado)

El riesgo 4 del documento original — **un error en el motor de lotes se
propaga en silencio** — está mitigado, no eliminado: hay 17 casos verificados a
mano más la validación contra las 73 operaciones reales. Cualquier cambio al
motor debe correr esa suite.

El riesgo 1 (importar una posición incorrecta de AAPL) **cambió de naturaleza**:
el motor ahora rechaza ese historial en vez de aceptarlo. El riesgo ya no es
importar datos malos en silencio, sino que la importación de AAPL sea imposible
hasta resolver D14.

Los riesgos 2, 3, 5 y 6 siguen intactos.
