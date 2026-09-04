# CONTROL_DE_CONSISTENCIA.md — cambios de la Fase 2

> Actualiza §1, §2, §3, §7 y la matriz final.

---

## 1. Información documentada (actualiza)

Se agrega a lo ya documentado:

- 17 endpoints (9 de auth + 8 financieros), con método, auth y CSRF
- 16 tablas, 8 enums, 4 migraciones
- **72 pruebas** (era 27), con detalle por archivo
- 25 decisiones de dominio (D1–D25)
- Motor de dominio validado contra las 73 operaciones reales

---

## 2. Información que NO pudo determinarse (actualiza)

Sigue sin determinarse: 1 (contenido del `.env` real), 2 (volumen huérfano),
3 (contraseña del admin), 4 (qué era el proyecto anterior), 5 (ratios de
CEDEAR), 6 (qué criptomonedas opera), 7 (si existen extractos de IOL),
8 (depósitos históricos), 9 (responsive en móvil), 10 (rendimiento bajo carga).

**Se resolvió:** el contenido del ADR `0001-decisiones-fase-0.md`, que aportó
D11 (autenticación) y D12 (frecuencias de refresco), ausentes del handoff
anterior.

**Nuevo, sin determinar:**

| # | Qué | Por qué |
|---|---|---|
| 11 | **Si la suite es determinista a lo largo del tiempo** | Se verificó en dos corridas consecutivas. La propiedad se confirma con el uso |
| 12 | **Comportamiento del motor con un historial largo** | Probado con 73 operaciones en memoria y con pocas por la API. El recálculo sincrónico crece con el tamaño del libro y nunca se midió |

---

## 3. Verificación contra el código (agrega)

A la lista existente se suman, para el modelo financiero:

- Que `app/domain/` no importe FastAPI, SQLAlchemy ni Redis
- Que ninguna columna nueva use `DOUBLE PRECISION` o `REAL`
- Que todo endpoint financiero filtre por el usuario autenticado y devuelva
  **404** (no 403) para lo ajeno
- Que los importes salgan de la API como **string**
- Que ninguna fecha entre al dominio sin zona horaria
- Que `lot_consumption` siga sin guardar resultado realizado
- Que la guarda del `conftest.py` siga en pie: **`pytest` a secas debe
  detenerse**, no correr

---

## 7. Decisiones pendientes (actualiza)

**Resueltas en la Fase 2:**

- Mecánica de consumo de lotes en ventas parciales → FIFO físico, resultado por
  método en el dominio (D18)
- Momento y precisión del redondeo → solo en presentación (D20)
- Qué hace el motor con una venta que excede la tenencia → rechaza siempre (D21)
- `invested_amount` en `position_cache` → `open_cost_basis` (D19)

**Siguen abiertas:**

- Definición de "capital invertido" para el **rendimiento** (Fase 4)
- Punto de partida del TWR y del XIRR
- Si los dividendos suman al realizado o van aparte
- Fórmula exacta del realizado con impuestos de ambas puntas
- Ratios reales de los 5 CEDEARs
- Cómo se presenta un total que mezcla MEP y USDT
- Qué hacer con una venta que excede la tenencia **en la importación**
- Proveedores concretos de market data (Fase 3)
- Regla de arrastre en días sin cotización

---

## Matriz final (reemplaza las filas que cambiaron)

| Componente | Implementado | Validado | Estado actual |
|---|---|---|---|
| **Assets** | **Sí** | **Sí** | IMPLEMENTADO — ratios sin cargar |
| **Transactions** | **Sí** | **Sí** | IMPLEMENTADO Y VALIDADO |
| **Positions** | **Sí** | **Sí** | IMPLEMENTADO Y VALIDADO — sin valor de mercado |
| **Portfolio Engine** | **Sí** | **Sí** | IMPLEMENTADO — validado contra las 73 operaciones reales |
| **Authorization** | **Sí** | **Sí** | IMPLEMENTADO Y VALIDADO — aislamiento con pruebas |
| **Testing** | **Sí** | **Sí** | 72 pruebas, base y Redis dedicados |
| **Frontend** | Sí (esqueleto) | Sí (manual) | **NO consume los endpoints financieros** |
| **Market Data** | No | No | PENDIENTE — Fase 3 |
| **CEDEARs** | Modelo sí | No | Tablas creadas; valuación PENDIENTE |
| **Crypto** | Modelo sí | No | PENDIENTE — sin lista de monedas |

El resto de la matriz sigue igual.

---

## Resumen en una línea

**El modelo financiero está implementado y validado contra el historial real:
registra operaciones, valida contra la tenencia y deriva posiciones. Lo que no
existe es cualquier precio de mercado, y las posiciones se exponen sin valor
actual a propósito. Queda por decidir si sigue la importación (bloqueada por
D14), market data, o la interfaz que hoy falta para los ocho endpoints nuevos.**
