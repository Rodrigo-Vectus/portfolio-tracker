# Estado tras las entregas de usabilidad

> Actualiza `PROJECT_STATE.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`,
> `FINANCIAL_ENGINE.md` y `PRODUCT_SPEC.md`.
> 2026-09-06. Commit `689f344`. Continúa `ESTADO_FASE3.md`.

---

## 1. Cambio de rumbo del proyecto

**La Fase 2.5 (importación del Excel) queda cancelada.** El usuario decidió
arrancar con la cartera en cero: la planilla y los boletos son contexto
histórico, no datos a migrar.

Consecuencias directas:

- **D14 deja de ser un pendiente crítico.** Bloqueó tres sesiones. La
  reconciliación de AAPL ya no hace falta porque no se importa nada.
- **El asunto de SPY deja de ser urgente.** La caída del 61% sigue sin
  explicación confirmada, pero sólo afectaba a la valuación de cantidades
  históricas.
- **Los números de referencia de `FINANCIAL_ENGINE.md` §1.5 pasan a ser sólo
  casos de prueba del motor.** Ya no son un objetivo de migración.

Objetivo vigente, en palabras del usuario: **tener un tracker de inversiones
propio, con seguimiento de activos, ganancias y transacciones**, cargando a
mano y quizás en el futuro leyendo comprobantes.

---

## 2. Lo que se agregó

| Área | Estado |
|---|---|
| **Caja** | **IMPLEMENTADA** — saldo derivado, 4 tipos de movimiento, pantalla propia |
| **Dashboard** | **IMPLEMENTADO** — dejó de estar vacío |
| **Catálogo** | Alta en línea desde Operaciones, edición y desactivación |
| **Bonos** | Tipo `BOND` y factor de precio por lámina |
| **Cuentas** | Pantalla propia, y cuenta por operación |

```
128 tests · 18 tablas · 7 migraciones · 21 endpoints · 8 pantallas
```

### Migraciones nuevas

| Revisión | Contenido |
|---|---|
| `0006_bond` | Agrega `BOND` al enum `asset_type` |
| `0007_price_factor` | Agrega `asset.price_factor`, con `CHECK > 0`. Pone 100 en los bonos existentes |

Las dos son reversibles y se probaron de ida y vuelta. `0006` aborta el
downgrade si hay activos de tipo `BOND`, por el mismo criterio que `0004`.

---

## 3. Decisiones nuevas

| # | Decisión | Motivo |
|---|---|---|
| D38 | **El efectivo no es un activo.** El saldo se deriva del libro y no se guarda | Un depósito de pesos no es la compra de algo cuyo precio es 1. Esa ficción aparecería como una posición que nadie compró |
| D39 | **El saldo puede quedar negativo y se muestra en vez de impedirse** | Bloquearlo obligaría a inventar un depósito para poder anotar una compra que sí ocurrió. El libro registra lo que pasó |
| D40 | **`aporte_neto` = depósitos − retiros** | Es la candidata (3) de "capital invertido" y la única que responde "cuánto puse de mi bolsillo". Es el flujo que va a necesitar el XIRR |
| D41 | **Cada moneda lleva su propio saldo de caja** | Sumar pesos y dólares requiere convertir, y esa conversión necesita FX con fecha (D2). No se hace implícitamente |
| D42 | **El dashboard no calcula nada propio**: compone `/positions` y `/cash` | Calcular por su cuenta daría dos fuentes para el mismo número |
| D43 | **La distribución no se dibuja si falta alguna cotización** | Un reparto porcentual incompleto exagera el peso de los que sí tienen precio: el 100% deja de ser el total |
| D44 | **`BOND` como tipo de activo** | Apareció al mirar boletos reales. AL30 cotiza en pesos y AL30D en dólares |
| D45 | **`price_factor` en el activo**: `costo = cantidad × precio / factor` | Los bonos cotizan por lámina de 100 nominales. Ver §4 |
| D46 | **Símbolo, mercado y tipo no son editables** | Forman la clave natural y puede haber operaciones que los referencien. Desactivar no borra |
| D47 | **El alta de activo se puede hacer desde Operaciones** | Obligar a cambiar de pantalla rompe el flujo justo con el comprobante en la mano |

---

## 4. El factor de precio, en detalle

Es el hallazgo más importante de estas entregas y no estaba en ninguna parte
de la especificación original.

**Los bonos cotizan por lámina de 100 nominales.** Un boleto real de AL30
informa precio 10.392 y bruto 10.392 sobre 100 nominales. Calcular
`cantidad × precio` da 1.039.200: **cien veces de más**.

El error no se habría notado. El número queda grande pero plausible, que es
exactamente cómo se propaga en silencio un error de cálculo (riesgo financiero
3 de `CONTROL_DE_CONSISTENCIA.md`).

**Cómo apareció:** una validación cruzada que compara el bruto informado por
el comprobante contra `cantidad × precio`. Estaba puesta como control de
sanidad y encontró una regla de mercado que nadie había modelado.

**Dónde se aplica:**

```
Transaction.precio_efectivo = unit_price / price_factor
```

Propagado a las cuatro funciones que calculan costo: `build_lots`,
`realized_fifo`, `realized_wac` y el saldo de caja. **Si una sola hubiera
quedado con el precio crudo, el costo y el saldo discreparían entre sí.**

`price_factor` vive en el activo y no en la operación porque es una propiedad
del instrumento. Vale 1 para todo lo demás, así que el cálculo de CEDEARs y
cripto no cambió: los 24 casos del motor que ya existían siguen pasando sin
modificación.

**Relación con los CEDEARs:** el ratio de CEDEAR es un problema de la misma
familia (una unidad negociada no equivale a una unidad del subyacente), pero
**no se resuelve con `price_factor`**. El ratio es una serie temporal con
vigencia y afecta la valuación teórica, no el costo de la operación. Siguen
siendo dos mecanismos distintos.

---

## 5. Modelo de datos

### `asset` (agrega)

```
price_factor  NUMERIC(28,10) NOT NULL DEFAULT 1   CHECK (price_factor > 0)
```

### Caja: no hay tabla

El saldo **no se persiste**. Se calcula al consultar desde `transaction`,
igual que las posiciones. Guardarlo obligaría a sincronizarlo en cada alta,
anulación y corrección; basta que falle un camino para que discrepe del libro
sin que nadie lo note.

Un movimiento de efectivo se guarda como una operación con `quantity = 1`,
el monto en `unit_price` y `asset_id` nulo.

---

## 6. Arquitectura: qué se agregó

```
app/domain/cash.py          saldo derivado, función pura
app/services/cash.py        puente entre el libro y el dominio
app/api/routes/             + GET/POST /api/cash, PATCH /api/assets/{id}
frontend/src/pages/
  Caja.tsx                  saldo, desglose y movimientos
  Dashboard.tsx             composición de /positions y /cash
  Cuentas.tsx               alta de brokers y exchanges
frontend/src/components/
  SelectorDeActivo.tsx      búsqueda con alta en línea
```

---

## 7. `PRODUCT_SPEC.md`: qué cambia de estado

| Funcionalidad | Antes | Ahora |
|---|---|---|
| Posiciones abiertas con costo | `PLANNED` F2 | `CURRENT` |
| Valuación con cotización actual | `PLANNED` F4 | `CURRENT` |
| Resultado no realizado | `PLANNED` F4 | `CURRENT` |
| Caja | `PLANNED` F2 | `CURRENT` |
| Dashboard con KPIs | `PLANNED` F6 | `CURRENT` (parcial: sin evolución temporal) |
| Distribución por activo | `PLANNED` F6 | `CURRENT` (barras, no torta) |
| Importación del Excel | `PLANNED` F2.5 | **CANCELADA** |
| Carga desde comprobante | — | `FUTURE` — pospuesta por el usuario |
| ROI / TWR / XIRR | `PLANNED` F4 | `PLANNED` — sigue pendiente |
| Evolución temporal | `PLANNED` F5 | `PLANNED` — requiere snapshots |

---

## 8. Pendientes

### Técnicos

1. **`PATCH /api/assets/{id}` no tiene pruebas de API.** Es lo más flojo de
   estas entregas.
2. **El frontend sigue sin una sola prueba automatizada.** Ya son seis bugs
   encontrados a ojo, contando la regresión de `BOND` (ver §9).
3. **Sin calendario de feriados**, sin segunda fuente de CEDEARs, sin
   histórico de precios.
4. **Sin pantalla para `TRANSFER`.** Los otros seis tipos ya tienen dónde
   cargarse.
5. **El lector de comprobantes está escrito y probado contra 113 boletos
   reales, pero no se entregó.** El usuario prefirió cargar a mano. Si se
   retoma, requiere agregar `pypdf` a las dependencias y reconstruir la
   imagen.

### Del usuario

1. Decidir si el rendimiento (Fase 4) es lo próximo.
2. Contraseñas genéricas y volumen huérfano: siguen pendientes desde la
   sesión 01.

---

## 9. Una regresión propia, registrada

`BOND` desapareció de `AssetType` en el frontend. La causa fue el método de
entrega: se preparó una entrega sobre un clon del repositorio hecho **antes**
de que la anterior estuviera commiteada, y el paquete pisó el cambio.

El backend nunca se vio afectado, pero `npm run build` fallaba. No se notó en
desarrollo porque Vite usa esbuild, que borra los tipos sin verificarlos.

**Mitigación aplicada:** commitear antes de preparar la entrega siguiente.
**Mitigación de fondo, sin decidir:** pasar la entrega a `git pull`, que es la
recomendación abierta desde la sesión 01.

---

## 10. Corrección sobre la lentitud de la suite

En `HANDOFF_SESION_03.md` §5 quedó registrado que la suite tardaba 64 s y que
la causa no estaba confirmada. Con más mediciones: **la misma suite tarda entre
22 y 69 segundos sin que cambie el código**.

Es variación del entorno —contenedor recién reiniciado, caché frío, o carga de
los otros ocho stacks del servidor— y no de las pruebas. Las dos hipótesis
anteriores (Argon2 y setup de conexiones) quedan descartadas.
