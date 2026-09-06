# HANDOFF — SESIÓN 03

> Cierre de la tercera sesión. 2026-09-04/06.
> Fases cerradas al abrir: 0, 1, 1.5 y 2. **Al cerrar: se suma la 3.**
> Último commit: `2f68acd`.

---

## 1. Qué se hizo, en orden

### Frontend de la Fase 2 (pendiente de la sesión anterior)

Tres pantallas (`Activos`, `Operaciones`, `Portfolio`) más `Cuentas`. La Fase 2
tenía ocho endpoints y ninguna forma de usarlos: cargar una operación requería
`curl`.

### Fase 3 — market data

Cinco entregas:

1. **Validación en vivo de los ocho candidatos de D10**, con un script que
   corre desde el servidor. Es lo que la decisión pedía desde la primera
   sesión y nunca se había hecho.
2. **Interfaz de proveedor** y tres implementaciones, con reglas de frescura
   en el dominio.
3. **Inferencia de antigüedad** desde el horario de rueda, tras descubrir que
   no existe fuente gratuita de CEDEARs con fecha de cotización.
4. **Migración `0005`**, servicio de persistencia y tareas del worker.
5. **Valuación de punta a punta**: endpoint, esquemas y pantalla.

---

## 2. La validación de proveedores decidió el diseño

Corrida desde el servidor del usuario, no desde otro entorno: probarlos desde
otra máquina no demuestra que funcionen desde donde vive el worker.

| Proveedor | HTTP | Latencia | Fecha propia | Formato |
|---|---|---:|---|---|
| dolarapi (MEP/CCL/cripto) | 200 | 240–470 ms | **sí** | número |
| criptoya USDT/ARS | 200 | 298 ms | sí, por exchange | número |
| data912 CEDEARs | 200 | 1816 ms | **NO** | número |
| Yahoo `AAPL.BA` | **429** | — | — | rechazado |
| Binance | 200 | 588 ms | no | **string** |
| CoinGecko | 200 | 235 ms | no | número |

**Lo que cambió por estos números:**

- Binance sobre CoinGecko: devuelve el precio como string y llega intacto.
- Todo el JSON se parsea con `parse_float=Decimal`: `1516.9` como número JSON
  se degrada en el primer paso del pipeline.
- La elección del dólar mueve la valuación casi 4%: MEP 1.525,30 contra CCL
  1.583,20. D1 ya había elegido MEP; estos números muestran por qué importaba.

---

## 3. El problema central de la fase

**No existe fuente gratuita de CEDEARs con fecha de cotización.**

`data912` es la única que funciona y no informa cuándo se cotizó cada papel.
Yahoo rechaza al servidor con 429. BYMA tiene API oficial con tarifa retail
(USD 30–60/mes) pero requiere contrato firmado, y el usuario decidió no pagar.

Eso convirtió un problema técnico en una decisión de producto. Se recorrieron
tres opciones y se eligió la intermedia (ver D34-bis).

La distinción que sostiene la decisión: **el Excel mostraba un número inventado
sin decirlo; esto muestra un número real de fuente conocida con su limitación
escrita al lado.** Un dato con advertencia no es un dato con mentira.

---

## 4. Decisiones tomadas

| # | Decisión |
|---|---|
| D26 | El frontend nunca convierte un importe a `number`: el formateo se hace sobre el texto |
| D27 | Los tipos de la API tipan los importes como `string` |
| D28 | Los `Decimal` salen del backend en notación posicional (`format(v, "f")`) |
| D29 | Una fecha de rueda no pasa por `Date` en el frontend |
| D30 | La pantalla dice por qué no muestra valor de mercado |
| D31 | Exchanges y brokers son referenciales, no parte del diseño: son filas de `account` |
| D32 | D8 se mantiene: el USDT es `CASH` con precio propio y fuente configurable |
| D33 | Si el proveedor no informa la fecha, `quoted_at` queda en `NULL`. La interfaz dice "obtenido hace X", no "cotizado hace X" |
| D34 | *(reemplazada)* El total no se muestra si algún componente está viejo o falta |
| **D34-bis** | Una antigüedad **estimada** no invalida el total: lo marca. Un precio **viejo** o **ausente** sí lo invalida |
| D35 | Todo JSON externo se parsea con `parse_float=Decimal` |
| D36 | El refresco de CEDEARs no consulta con la rueda cerrada (D12) |
| D37 | Si un refresco falla, no se borra el precio anterior: queda viejo y marcado |

D34 fue reemplazada por D34-bis **dentro de la misma sesión**, después de
constatar que ninguna fuente gratuita informa la fecha. La regla original
habría dejado al usuario sin ver nunca el valor de su cartera.

---

## 5. Bugs encontrados

Continúa la numeración de la adenda de la Fase 2.

| # | Problema | Causa raíz |
|---|---|---|
| 12 | `dolarapi` falló en `fx:bolsa` en la primera corrida real | Transitorio. **Quedó registrado en `provider_log` y las otras dos casas se guardaron igual**: el aislamiento por casa funcionó |

Los bugs 7 a 11 (frontend de la Fase 2) están en `ADENDA_FASE2_FRONTEND.md`.

**Un error de diagnóstico mío, que vale registrar:** atribuí la lentitud de la
suite (66 s) a Argon2 y entregué una optimización que cachea el hash. Medida,
bajó a 64 s: 3,6%, ruido. Se revirtió. El costo está en el setup de conexiones
por prueba, no en el hashing. **La causa real no está confirmada** y se deja
declarada como tal en vez de sustituir una explicación equivocada por otra.

---

## 6. Estado al cerrar

```
Fase 0 ✔  Fase 1 ✔  Fase 1.5 ✔  Fase 2 ✔  Fase 3 ✔
Fase 2.5 ✗ bloqueada por D14

111 tests · 17 tablas · 5 migraciones (0005_market_data)
17 endpoints · 5 pantallas con datos reales
```

Verificado en el servidor del usuario: migraciones reversibles, proveedores
consultados contra la red real, cotizaciones persistidas con la distinción
`quoted_at` / `estimated_at` visible en la base, y `provider_log` capturando
una falla real.

---

## 7. Pendientes

### Del lado del usuario

| # | Qué | Por qué |
|---|---|---|
| 1 | **Extractos de IOL** | D14. Tercera sesión pendiente. Bloquea la 2.5 |
| 2 | Cargar MSFT, MELI, SPY y QQQ en el catálogo | Sin eso sólo se cotiza AAPL |
| 3 | Confirmar si los extractos traen comisiones | Sin ellas el rendimiento importado queda sobreestimado |
| 4 | Volumen huérfano `portfolio-tracker_pgdata` | Sigue sin inspeccionar desde la sesión 01 |
| 5 | Contraseñas genéricas | Acordado para el cierre |

### Técnicos

1. **SPY cayó 61% mientras QQQ subía 20%** entre el 23/12/2025 y hoy.
   Casi seguro un cambio de ratio o un split. `REQUIERE VERIFICACIÓN`.
   **Afecta la Fase 2.5**: valuar cantidades históricas con el precio actual
   daría mal. La tabla `corporate_action` existe desde `0003` pero nadie la
   procesa. No es sólo AAPL lo que puede entrar mal en la importación.
2. **Una sola fuente de CEDEARs.** Si `data912` desaparece, no hay precios y
   no hay a qué cambiar. La interfaz de proveedor permite el reemplazo; falta
   un candidato.
3. **No hay calendario de feriados.** Un lunes feriado se trata como hábil y
   el precio queda más fresco de lo que es.
4. **El frontend no tiene una sola prueba automatizada.** Cinco bugs
   encontrados a ojo por el usuario. `format.ts` es lógica pura y sería lo
   primero que conviene cubrir.
5. **La suite tarda 64 s** y no se sabe exactamente por qué.
6. **`price_bar_daily` no existe**: no hay histórico de precios, sólo el
   último. Fase 5.
7. **Sin pantalla para `DEPOSIT`, `WITHDRAWAL`, `FEE`, `DIVIDEND`,
   `TRANSFER`.** Sin depósitos no hay caja, y sin caja no hay XIRR (D15).

---

## 8. Punto donde retomar

La Fase 3 está cerrada. **No hay próxima tarea confirmada.**

Antes de escribir código:

1. Correr `git log --oneline -5`, `docker compose ps`,
   `docker compose exec backend alembic current` (debe decir
   `0005_market_data`), `bash scripts/test.sh` (111) y `health/ready`.
   **Usar `scripts/test.sh`, nunca `pytest` a secas**: la guarda lo impide.
2. Preguntar cuál es la prioridad. Los caminos abiertos:
   - **Fase 4** — rendimiento (ROI, TWR, XIRR). Requiere definir "capital
     invertido", que sigue con tres candidatas incompatibles.
   - **Fase 2.5** — importación. Bloqueada por D14 y ahora también por el
     asunto de SPY.
   - **Fase 5** — snapshots e histórico de precios.
   - **Deuda**: pruebas de frontend, segunda fuente de CEDEARs, feriados.

**Recomendación:** la Fase 4 es el siguiente paso natural del principio rector
y no depende de nada externo. Pero conviene resolver antes la definición de
"capital invertido", porque de eso depende cada porcentaje que muestre el
sistema, y elegir mal ahí reproduce el error del Excel con otra fórmula.

**No avanzar de fase automáticamente.** Regla 15.
