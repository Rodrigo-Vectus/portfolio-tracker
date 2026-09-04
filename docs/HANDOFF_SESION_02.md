# HANDOFF — SESIÓN 02

> Cierre de la segunda sesión. 2026-09-04.
> Fases cerradas al abrir: 0 y 1. **Al cerrar: 0, 1, 1.5 y 2.**

Este documento registra **qué pasó en esta sesión**. El estado del proyecto
está en los otros documentos; acá va el recorrido y el punto donde retomar.

---

## 1. Qué se hizo, en orden

### Verificación del estado documentado

Se corrieron los comandos de `CONTROL_DE_CONSISTENCIA.md` §10.2 y apareció la
primera discrepancia: los documentos decían "27 pruebas, todas pasan" y la
realidad era **21 pasando, 6 fallando**. Ver §2, problema 1.

También se leyó el ADR `0001-decisiones-fase-0.md`, que resolvió el hueco de
**D11** (autenticación) y **D12** (frecuencias de refresco), ausentes del
handoff anterior. Ninguna de las dos afecta al modelo financiero.

Se auditó el repositorio público: **ningún `.env` real entró nunca al
historial**, y los dos blobs del tarball que quedaron en commits antiguos
contienen solo `.env.example`. Lo único expuesto es
`INITIAL_ADMIN_EMAIL` en la plantilla.

### Fase 2 — modelo financiero

Cuatro entregas sucesivas:

1. **Motor de dominio** (`money`, `ledger`, `cost_basis`, `positions`) con 17
   casos verificados a mano.
2. **Modelo de datos**: migración `0003_finance`, 10 tablas, 6 enums.
3. **Servicios**: alta validada, anulación con motivo, reconstrucción de
   posiciones, comando `rebuild-positions`, migración `0004_audit_tx`.
4. **Endpoints**: 8 rutas, con pruebas de aislamiento entre usuarios.

### Fase 1.5 — aislamiento de las pruebas

No estaba en el plan. Se insertó cuando quedó claro que la suite no podía
seguir corriendo contra la base real. Ver §2, problema 1.

### Validación contra el historial real

El usuario compartió el `.xlsx` original. Se corrieron las 73 operaciones
reales contra el motor y se compararon **doce valores** contra los documentados
en `FINANCIAL_ENGINE.md` §1.5. **Los doce coincidieron.**

AAPL lanzó `InsufficientHoldings` (venta de 25 con tenencia de 13): el motor
detectó solo, sobre datos reales, el error que en la planilla pasó seis meses
sin ser notado.

**El archivo no entró al repositorio** y no debe entrar: es historial
financiero real y el repositorio es público.

---

## 2. Problemas encontrados

| # | Problema | Causa raíz | Lección |
|---|---|---|---|
| 1 | La suite daba resultados distintos entre corridas | Las pruebas de API usaban el admin sembrado y su contraseña del `.env`. El usuario la cambió, como el sistema le exigía. Además cada corrida sumaba 8 `LOGIN_FAILED` y agotaba el límite, convirtiendo 401 en 429 | **Una suite acoplada a datos de producción deja de ser una señal.** Y el acoplamiento se rompió justamente porque el producto funcionó bien |
| 2 | El enum `audit_action` no tenía las acciones de operaciones | Insertar la bitácora de una operación abortaba la transacción completa | Mismo patrón que el bug de `INET`: el fallo aparece lejos de su causa |
| 3 | `can't compare offset-naive and offset-aware datetimes` | Historial de `TIMESTAMPTZ` mezclado con una operación recién llegada del JSON | **Pasó 23 pruebas de dominio sin ser detectado**, porque ahí todas las fechas eran naive. Solo apareció en la segunda operación |
| 4 | `trade_date` derivado de `.date()` sobre UTC | 22:30 en Buenos Aires es 01:30 UTC del día siguiente | Segundo bug de la misma familia, que las pruebas no alcanzaban a ver |
| 5 | Dominio `.test` rechazado por `email-validator` | Es un TLD de uso especial | Error mío al elegir el dominio. **No se aflojó la validación del login para que los tests pasaran** |
| 6 | El `conftest.py` importaba FastAPI a nivel de módulo | Las pruebas de dominio no podían correr sin infraestructura | Contradecía la decisión de arquitectura de aislar el dominio |

**Tres de los seis aparecieron lejos de su causa.** Es el mismo patrón que en
la sesión anterior, y el argumento permanente para probar contra una base real.

---

## 3. Decisiones tomadas

Ocho decisiones nuevas, D18 a D25. Están en `PROJECT_STATE.md` con su motivo.
Las tres que más pesan:

- **D18** — `lot_consumption` sin `realized_pnl`. Cambia el diseño aprobado en
  `DATA_MODEL.md` §B.6. El argumento se volvió empírico durante la sesión: el
  mismo consumo de lotes produjo 477.475 ARS por WAC y 575.975 por FIFO sobre
  las operaciones reales.
- **D23** — recálculo sincrónico. Consistencia por sobre latencia, con la
  salida documentada si el volumen crece.
- **D24** — fecha sin zona = zona local, no UTC.

### Quedaron abiertas

- La definición de "capital invertido" para el **rendimiento** (Fase 4).
  `open_cost_basis` resolvió solo el caso de `position_cache`.
- Todo lo listado en `PROJECT_STATE.md` §Definiciones que siguen abiertas.

---

## 4. Estado al cerrar

```
Fase 0    ✔    Fase 1  ✔    Fase 1.5  ✔    Fase 2  ✔
Fase 2.5  ✗ bloqueada por D14
Fase 3    ← no comenzada

72 tests pasando, 0 fallando
16 tablas · 4 migraciones (0004_audit_tx)
17 endpoints
Base de pruebas dedicada: portfolio_tracker_test · Redis DB 1
```

Verificado en el servidor del usuario, no solo declarado.

---

## 5. Pendientes del lado del usuario

| # | Qué | Por qué corre prisa |
|---|---|---|
| 1 | **Extractos de IOL** | D14 sigue bloqueando la Fase 2.5. Se pidió en la sesión 01 y sigue pendiente. El motor ya rechaza el historial de AAPL, así que el bloqueo es ahora efectivo, no teórico |
| 2 | Confirmar si esos extractos traen **comisiones** | Sin ellas todo el rendimiento importado queda sobreestimado |
| 3 | **Decidir la próxima fase** entre 2.5, 3 o el frontend de la 2 | Ver `PROJECT_STATE.md` §Próxima tarea |
| 4 | Limpiar el bloque duplicado de `*.xlsx` en `.gitignore` | Cosmético |
| 5 | Volumen huérfano `portfolio-tracker_pgdata` | Sigue sin inspeccionar desde la sesión 01 |
| 6 | Qué criptomonedas opera y en qué exchange | Fase 3 |
| 7 | Cambiar las contraseñas genéricas | Acordado para el cierre |

---

## 6. Método de trabajo

El ciclo por fase de la sesión 01 se mantuvo y funcionó. Dos observaciones:

**El tarball siguió siendo el método de entrega.** Se propuso `git pull` y el
usuario no lo descartó, pero nunca se ejecutó el cambio. La fricción se redujo
igual: **los paquetes de esta sesión no incluyeron `.gitignore` ni los
entrypoints**, así que no volvieron a pisarse. Conviene mantener esa regla.

**Se entregó código sin ejecutar en dos ocasiones** (servicios y endpoints),
siempre declarándolo explícitamente. Las dos veces falló algo en el primer
despliegue. Es el costo real de no tener PostgreSQL en el entorno de trabajo, y
conviene seguir declarándolo en vez de disimularlo.

---

## 7. Punto exacto donde retomar

La Fase 2 está cerrada y validada. **No hay una próxima tarea confirmada.**

Antes de escribir código, el próximo Claude debería:

1. Correr los comandos de verificación (`git log`, `docker compose ps`,
   `alembic current`, `bash scripts/test.sh`, `health/ready`) y confirmar que
   el estado documentado sigue vigente. **Usar `scripts/test.sh`, nunca
   `pytest` a secas.**
2. Preguntar cuál de los tres caminos de `PROJECT_STATE.md` §Próxima tarea se
   toma.
3. Si es la Fase 3, pedir la lista de criptomonedas reales y confirmar si hay
   credenciales de API disponibles.

**No avanzar de fase automáticamente.** Regla 15.
