# Estado tras la Fase 3

> Actualiza `PROJECT_STATE.md`, `ARCHITECTURE.md`, `DATA_MODEL.md`,
> `FINANCIAL_ENGINE.md` y `MARKET_DATA_AND_DEPLOYMENT.md`.
> Fecha: 2026-09-06. Commit `2f68acd`.

---

## 1. Estado general (reemplaza)

**Infraestructura, acceso, modelo financiero y market data: terminados y
validados. Rendimiento e histórico: no comenzados.**

El sistema registra operaciones, deriva posiciones, obtiene cotizaciones
automáticamente y muestra el valor de la cartera con su antigüedad y su
fuente. Es, por primera vez, un tracker utilizable.

Lo que todavía no hace: calcular rendimiento porcentual (ROI, TWR, XIRR),
guardar histórico de precios, y mostrar evolución temporal.

---

## 2. Componentes que cambian de estado

| Componente | Antes | Ahora |
|---|---|---|
| **Market data** | PENDIENTE | **IMPLEMENTADO Y VALIDADO** |
| **Worker** | mínimo (sólo latido) | **IMPLEMENTADO** — 3 tareas de refresco |
| **Frontend** | esqueleto, sin consumir endpoints | **IMPLEMENTADO** — 5 pantallas con datos reales |
| **CEDEARs** | modelo conceptual | **Precio local implementado.** Ratios y valuación teórica siguen PENDIENTES |
| **Crypto** | PENDIENTE | Proveedor implementado. **Sin activos cargados** |

---

## 3. Modelo de datos: migración `0005_market_data`

Tres tablas nuevas. Total: **17**.

```
price_quote      última cotización por activo y fuente
fx_rate          serie histórica de tipo de cambio
provider_log     bitácora de toda llamada a proveedor
```

**Ningún enum nuevo.** `rate_type` y `status` van como texto para que agregar
una serie de FX o un estado de proveedor no requiera migración.

### La decisión que define la fase

```sql
fetched_at    TIMESTAMPTZ NOT NULL   -- cuándo lo pedimos
quoted_at     TIMESTAMPTZ            -- cuándo lo dijo el mercado. NULLABLE
estimated_at  TIMESTAMPTZ            -- antigüedad inferida. Campo aparte
```

`quoted_at` es nullable porque es la única forma honesta de modelar lo que
devuelve el único proveedor gratuito de CEDEARs. Ponerlo `NOT NULL` obligaría
a rellenarlo con `fetched_at`, convirtiendo "cuándo preguntamos" en "cuándo lo
dijo el mercado", que es exactamente el error que originó el proyecto.

`estimated_at` vive aparte para que una estimación nunca se confunda con un
hecho mirando la tabla.

---

## 4. Arquitectura: qué se agregó

```
app/domain/
  market.py       Cotizacion, Frescura, totalización de cartera
  rueda.py        horario de BYMA, inferencia de antigüedad
app/services/
  providers/      base + dolarapi + data912 + binance
  market_data.py  consulta, persiste y registra
  valuation.py    posiciones × cotización
app/models/market.py
app/worker/tasks.py    + refrescar_fx, refrescar_cedears, refrescar_cripto
```

`app/domain/` sigue sin importar FastAPI, SQLAlchemy ni Redis. Verificable:
sus pruebas corren sin esas librerías instaladas.

### Separación en los proveedores

Cada uno separa `parse()` (función pura, probada con payloads reales
capturados del servidor) de `fetch()` (HTTP). Un proveedor que sólo se puede
probar con red es un proveedor que en la práctica no se prueba.

### Contrato de `GET /api/positions` (cambió)

Ya no devuelve un array sino `{ positions, total }`. El total necesita poder
decir por qué no se puede calcular, y eso no cabe en una lista.

Todo dato de mercado puede venir `null`: `current_value` nulo dice "no sé
cuánto vale"; un cero diría "no vale nada".

### Frecuencias del worker (D12)

```
cripto    :01 :06 :11 ...   cada 5 min, 24/7
CEDEARs   :02 :17 :32 :47   cada 15 min, sólo con rueda abierta
FX        :03 :33           cada 30 min
```

Los minutos van corridos entre sí: arrancar las tres en el mismo instante
concentra la carga y hace más difícil leer los logs cuando algo falla.

---

## 5. `FINANCIAL_ENGINE.md` §3.5 — Valor actual (reemplaza)

**IMPLEMENTADO.**

```
valor(posición) = cantidad × última_cotización_válida
```

Acompañado siempre de `price_as_of`, `price_source` y `price_status`
(`FRESCA` | `ESTIMADA` | `VIEJA` | `SIN_FECHA` | `AUSENTE`).

Si no hay cotización, el valor es `null` y la pantalla muestra un guion.

**Umbrales de vejez**, por tipo de activo:

| Tipo | Umbral | Motivo |
|---|---|---|
| CRYPTO | 30 min | Cotiza 24/7: un precio de hace una hora ya es viejo |
| CEDEAR | 24 h | No cotiza de noche ni fines de semana |
| FX | 6 h | |

### §3.10 Tipo de cambio — parcialmente implementado

`fx_rate` existe y el worker la puebla con MEP, CCL y CRYPTO (se guardan las
tres por D16). **Todavía no se usa para convertir**: las posiciones se valúan
en la moneda de la operación. La conversión a moneda dura es Fase 4.

### §3.6 P&L — completo

Realizado (Fase 2) y no realizado (Fase 3), separados. El Excel los mezclaba
en un solo número.

---

## 6. `MARKET_DATA_AND_DEPLOYMENT.md` Parte 1 (reemplaza)

### Estado: IMPLEMENTADO

| Categoría | Contenido |
|---|---|
| Proveedor **utilizado** | dolarapi (FX), data912 (CEDEARs), Binance (cripto) |
| Proveedor **descartado** | Yahoo Finance — 429 desde el servidor |
| Proveedor **evaluado y no elegido** | CoinGecko (redondea y devuelve número), criptoya (precio por exchange), BYMA oficial (paga) |

### BYMA: la alternativa que existe y se descartó

Tiene API oficial con tarifa retail. Requiere contrato firmado y pedido por
mail a `marketdata@byma.com.ar`. BYMA es dueña de la información y restringe
la redistribución.

| Plan | Retail | Contenido |
|---|---|---|
| Snapshot | USD 120/mes | Tiempo real |
| Delay | USD 60/mes | 20 minutos de retraso |
| EOD | USD 30/mes | Cierre del día |

**Decisión del usuario: no pagar.** Queda registrado como la salida disponible
si algún día la antigüedad estimada deja de alcanzar.

### Reglas verificadas en producción

- **No inventar**: `quoted_at` nulo cuando el proveedor no informa.
- **No ocultar errores**: toda llamada deja fila en `provider_log`. Ya capturó
  una falla real de `dolarapi` en `fx:bolsa`.
- **No acoplar**: la lógica de negocio no importa ningún proveedor concreto.
- **Aislamiento**: que falle una casa de FX no impide guardar las otras.
  Comprobado en la primera corrida real.

---

## 7. Riesgos nuevos

| # | Riesgo | Severidad |
|---|---|---|
| 11 | **Una sola fuente de CEDEARs.** Si `data912` desaparece no hay precios ni alternativa gratuita | **Alta** |
| 12 | **Sin calendario de feriados.** Un lunes feriado el precio se ve más fresco de lo que es | Media |
| 13 | **SPY cayó 61% mientras QQQ subía 20%.** Probable cambio de ratio no procesado. Afecta la importación | **Alta** para Fase 2.5 |
| 14 | **El frontend sigue sin pruebas.** Cinco bugs encontrados a ojo | Media |

El riesgo 5 del documento original —presentar un precio viejo como actual—
está **mitigado y verificable**: hay umbrales por tipo de activo, marcas de
frescura que el frontend respeta, y pruebas que fijan el comportamiento.
Deja de ser una intención escrita para ser una regla ejecutada.
