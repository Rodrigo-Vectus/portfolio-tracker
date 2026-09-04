# ARCHITECTURE.md — cambios de la Fase 2

> Reemplaza §3 (endpoints y estructura del backend), §8 (portfolio engine),
> §12 (matriz) y agrega §13 (testing). El resto sigue vigente.

---

## 3. Backend (actualiza)

### Estructura nueva

```
backend/app/
├── core/
│   └── timezones.py          NUEVO — normalización de fechas
├── domain/                   IMPLEMENTADO (era solo un README)
│   ├── money.py              Money = Decimal + moneda. Rechaza float
│   ├── ledger.py             Transaction inmutable, validaciones
│   ├── cost_basis.py         lotes, consumo FIFO, realizado WAC/FIFO
│   └── positions.py          operaciones → posición derivada
├── models/
│   ├── enums_finance.py      NUEVO — 6 enums del dominio financiero
│   ├── asset.py              NUEVO — asset, identifier, cedear_*, corporate_action
│   ├── account.py            NUEVO — account, portfolio
│   ├── transaction.py        NUEVO — el libro
│   └── lots.py               NUEVO — cost_lot, lot_consumption, position_cache
├── schemas/
│   └── finance.py            NUEVO — contratos; Decimal serializado como string
├── services/
│   ├── mappers.py            NUEVO — traducción ORM ↔ dominio
│   ├── transactions.py       NUEVO — alta validada, anulación
│   └── positions.py          NUEVO — materialización de lotes y posiciones
└── api/routes/
    ├── portfolio.py          NUEVO — assets, accounts, portfolios
    └── transactions.py       NUEVO — operaciones y posiciones

backend/scripts/test.sh       NUEVO — corre la suite aislada
```

`app/domain/` **no importa FastAPI, SQLAlchemy ni Redis.** Es verificable:
sus pruebas corren sin esas librerías instaladas. Todo el tráfico entre capas
pasa por `services/mappers.py`.

### Endpoints (17 en total)

Los 9 de la Fase 1 siguen igual. Los 8 nuevos:

| Método | Ruta | Auth | CSRF | Nota |
|---|---|---|---|---|
| GET | `/api/assets` | bearer | no | Catálogo compartido |
| POST | `/api/assets` | bearer | **sí** | 409 si repite (symbol, market, type) |
| GET | `/api/accounts` | bearer | no | Filtra por usuario |
| POST | `/api/accounts` | bearer | **sí** | |
| GET | `/api/portfolios` | bearer | no | Filtra por usuario |
| POST | `/api/portfolios` | bearer | **sí** | |
| GET | `/api/transactions?portfolio_id=` | bearer | no | 404 si el portfolio es ajeno |
| POST | `/api/transactions` | bearer | **sí** | 422 si la regla de negocio no cierra |
| POST | `/api/transactions/{id}/void` | bearer | **sí** | Motivo obligatorio |
| GET | `/api/positions?portfolio_id=` | bearer | no | **Sin valor de mercado** |

**El catálogo de activos es compartido a propósito.** Que AAPL exista como
CEDEAR en BYMA no es información privada de nadie. Lo privado son cuentas,
portfolios y operaciones.

**Códigos de error, con criterio:**

- **404** para recursos ajenos, nunca 403. Un 403 confirmaría que el recurso
  existe y solo no es tuyo, con lo que se pueden enumerar carteras probando
  identificadores.
- **422** para reglas de negocio que no cierran (vender más de lo que hay,
  anular dejando una venta descubierta). La petición está bien formada; lo que
  falla es el dominio. El mensaje dice cuál, porque "venta inválida" no le
  sirve a nadie para corregir la carga.
- **409** para colisiones de clave natural.

### Convención de fechas de la API

`executed_at` sin zona horaria se interpreta en `DEFAULT_TIMEZONE`
(`America/Argentina/Buenos_Aires`), **no en UTC**. Con offset explícito, se
respeta.

Asumir UTC mandaría una compra de las 22:30 a la rueda del día siguiente.
`trade_date` se deriva del día local por el mismo motivo.

---

## 8. Portfolio engine (reemplaza)

**Estado: IMPLEMENTADO Y VALIDADO.**

Python puro en `app/domain/`. Validado de dos formas:

1. **17 casos verificados a mano**, con la aritmética escrita en cada
   docstring. Incluyen la divergencia FIFO/WAC sobre el mismo historial: si ese
   test alguna vez da cero, uno de los dos métodos dejó de calcularse.
2. **Contra las 73 operaciones reales** del Excel: doce comparaciones, doce
   coincidencias. AAPL rechazado con `InsufficientHoldings`, que es el
   comportamiento correcto.

La separación del dominio **es una decisión de arquitectura vigente y no debe
eliminarse.** Es lo que permite validar los cálculos sin levantar una base.

---

## 13. Testing (nuevo)

**La suite no corre contra la base de la aplicación**, y la protección está en
el código:

```
POSTGRES_DB debe terminar en _test    → si no, pytest.exit()
REDIS_DB no puede ser 0                → si no, pytest.exit()
```

Forma correcta de correrla:

```bash
docker compose exec backend bash scripts/test.sh
```

El script crea `portfolio_tracker_test` si falta, aplica las migraciones y
recién entonces invoca pytest con `REDIS_DB=1`.

**Por qué un script y no una fixture:** el engine de SQLAlchemy es un objeto de
módulo construido desde `Settings`, que está cacheado con `lru_cache`. No se
puede repuntar desde una fixture; la inyección tiene que ocurrir **antes** de
que arranque el proceso de pytest.

Cada prueba crea su propio usuario con contraseña generada. Ninguna depende del
admin sembrado ni del `.env`.

| Archivo | Cantidad | Requiere |
|---|---:|---|
| `test_security.py` | 15 | nada |
| `test_domain_cost_basis.py` | 17 | nada |
| `test_mappers.py` | 6 | solo configuración |
| `test_timezones.py` | 5 | solo configuración |
| `test_health.py` | 3 | Postgres, Redis |
| `test_auth_api.py` | 14 | Postgres, Redis |
| `test_finance_api.py` | 12 | Postgres, Redis |
| **Total** | **72** | |

Cuatro de `test_finance_api.py` verifican el aislamiento entre usuarios, con un
**ADMIN** como segundo usuario: administrar la plataforma no da acceso
funcional a carteras ajenas.

**Sigue sin cubrirse:** frontend (cero pruebas), rendimiento y carga, worker más
allá del latido.

---

## 12. Matriz de estado (reemplaza)

| Componente | Estado | Fase |
|---|---|---|
| Docker, Postgres, Redis, migraciones, healthchecks | `COMPLETADO` | 0 |
| Autenticación, roles, layout, rutas protegidas | `COMPLETADO` | 1 |
| Aislamiento de las pruebas | `COMPLETADO` | 1.5 |
| Modelo financiero, ledger, lotes, posiciones | `COMPLETADO` | 2 |
| Endpoints de operaciones y posiciones | `COMPLETADO` | 2 |
| **Frontend de operaciones y posiciones** | `PENDIENTE` — hay API sin interfaz | 2 |
| Importador del Excel | `BLOQUEADO` por D14 | 2.5 |
| Market data, FX, caché | `PENDIENTE` | 3 |
| Valuación y rendimiento (ROI, TWR, XIRR) | `PENDIENTE` | 4 |
| Snapshots y backfill | `PENDIENTE` | 5 |
| Dashboard | `PENDIENTE` | 6 |
| Administración y consulta de auditoría | `PENDIENTE` | 7 |
| Robustez, backups, observabilidad | `PENDIENTE` | 8 |
| Producción, TLS, responsive | `PENDIENTE` | 9 |

### REQUIERE DECISIÓN DEL USUARIO

1. **Extractos de IOL** (D14). Bloquea la Fase 2.5.
2. **Cuál es la próxima fase**: 2.5, 3, o el frontend de la 2.
3. Librería de gráficos para la Fase 6: Recharts o ECharts.
4. Momento de introducir el reverse proxy con TLS.
5. Qué hacer con el volumen huérfano `portfolio-tracker_pgdata`.
