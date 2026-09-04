# Adenda — frontend de la Fase 2

> Complementa `PROJECT_STATE.md` y `HANDOFF_SESION_02.md`, escritos antes de
> esta entrega. Commit `5d14267`.

---

## Estado que cambia

En `PROJECT_STATE.md`, la fila de **Frontend** decía "sin consumir todavía los
endpoints financieros" y la matriz de `ARCHITECTURE.md` listaba
"Frontend de operaciones y posiciones — `PENDIENTE`, hay API sin interfaz".

**Las dos quedan `IMPLEMENTADO`.** Con eso desaparece la opción C de la
sección "Próxima tarea": el frontend de la Fase 2 ya está hecho.

### Lo que se agregó

```
frontend/src/lib/format.ts      formateo de cifras y fechas
frontend/src/lib/finance.ts     llamadas a la API financiera
frontend/src/pages/Activos.tsx      catálogo, con alta
frontend/src/pages/Operaciones.tsx  libro, con alta y anulación
frontend/src/pages/Portfolio.tsx    posiciones y gestión de portfolios
frontend/src/components/ui.tsx      + Num, Select, Tabla, Nota
```

Verificado en el navegador del usuario, con datos reales: alta de activo, alta
de portfolio, compra de 10 a 20.960, venta de 4 a 25.000 (posición 6, costo
abierto 125.760, realizado 16.160), rechazo de una venta de 25 sobre una
tenencia de 10, y rechazo de la anulación de una compra que dejaría la venta
sin respaldo.

---

## Decisiones nuevas

| # | Decisión | Motivo |
|---|---|---|
| D26 | **El frontend nunca convierte un importe a `number`.** El formateo se hace sobre el texto: agrupado de miles y redondeo con acarreo dígito por dígito | `Number("477475.1351871143733252380232")` pierde dígitos **al leerse**, antes de que nadie formatee. De nada sirve `Decimal` en la base y en el dominio si el último tramo lo degrada |
| D27 | **Los tipos de la API tipan los importes como `string`, no `number`** | Tiparlos `number` invitaría a hacer una cuenta en el navegador y obtener otro resultado que el servidor. Si hace falta calcular del lado del cliente, se le pide el cálculo al backend |
| D28 | **Los `Decimal` salen del backend en notación posicional** (`format(v, "f")`, no `str(v)`) | `str(Decimal("0.000000000000000000"))` devuelve `"0E-18"` |
| D29 | **Una fecha de rueda no pasa por `Date` en el frontend** | Una fecha sin hora se interpreta como medianoche UTC. Es un día calendario, no un instante |
| D30 | **La pantalla de posiciones dice por qué no muestra valor de mercado** | Una columna vacía se confunde con un cero |

---

## Bugs encontrados y resueltos (continúa la numeración de §2 del handoff)

| # | Problema | Causa raíz | Detectado por |
|---|---|---|---|
| 7 | `0E-18` en pantalla, en comisión y resultado realizado | `str()` de un `Decimal` en cero con escala 18 usa notación exponencial. El formateador no la reconocía y devolvía la cadena cruda | Captura del usuario |
| 8 | `se intenta vender 25 y hay 10.000000000000000000 disponibles` | El mensaje del motor usaba el `Decimal` crudo. Correcto pero ilegible | Captura del usuario |
| 9 | **Todas las fechas de rueda se mostraban un día antes** | `new Date("2026-09-04")` se interpreta como medianoche UTC; en Buenos Aires cae el día anterior. Una compra del 1 de enero figuraba como del 31 de diciembre | Comparación entre el formulario y la tabla, en una captura |
| 10 | Los encabezados "Resultado realizado" y "Método" se tocaban | El relleno estaba del lado equivocado: se agregó a la izquierda de una columna alineada a la derecha | Captura del usuario |
| 11 | En Portfolio no había forma de crear un segundo portfolio | El formulario sólo aparecía cuando no existía ninguno. Al crear el primero desaparecía y la pantalla quedaba sin ninguna acción | Reporte del usuario |

**El bug 9 es el más grave de los cinco**, y el único que corrompía un dato a
la vista: los otros cuatro eran feos o incómodos, ese mostraba una fecha
equivocada. También es el cuarto de la sesión que aparece lejos de su causa —
el backend guardaba bien y la pantalla corría el día.

**Los cinco los encontró el usuario mirando la interfaz.** Ninguna prueba los
detectó, y no por descuido: las 74 verifican el backend, y el frontend no
tiene ni una sola prueba automatizada. Es la deuda técnica que este episodio
vuelve concreta.

---

## Pendientes que esto agrega

1. **El frontend sigue sin pruebas automatizadas.** Cinco bugs en una entrega,
   todos visibles en pantalla, ninguno detectado por la suite. `format.ts` es
   lógica pura y sería lo primero que conviene cubrir.
2. **Falta confirmar en el navegador** que la fecha muestra el día correcto
   después del arreglo. Se probó contra tres casos fuera del navegador; la
   verificación visual quedó pendiente. `REQUIERE VERIFICACIÓN`.
3. **No hay pantalla para `DEPOSIT`, `WITHDRAWAL`, `FEE`, `DIVIDEND` ni
   `TRANSFER`.** Los cinco tipos existen en el modelo y en la API; el
   formulario sólo ofrece compra y venta. Sin depósitos no hay caja, y sin
   caja no hay XIRR (D15).
4. **No hay alta de cuentas** (`account`) en la interfaz, aunque el endpoint
   existe. Hoy toda operación se registra sin cuenta asociada, así que no se
   puede distinguir qué está en IOL y qué en un exchange (D17).
5. **No se puede elegir el método de costo** desde la interfaz: siempre WAC.
   FIFO se calcula sobre los mismos lotes y daría otro número.

Los puntos 3 y 4 no son bugs: son alcance que nunca se definió para esta fase.
Conviene decidirlos antes de la importación, porque el importador va a
necesitar cuentas para saber dónde ocurrió cada operación.

---

## Próxima tarea (reemplaza la de `PROJECT_STATE.md`)

Con el frontend hecho, quedan dos caminos y un pendiente transversal:

**A. Fase 2.5 — importador.** Sigue **bloqueada por D14**.

**B. Fase 3 — market data.** No depende de nada pendiente. Requiere validar
proveedores en vivo (D10) y saber qué criptomonedas opera el usuario.

**Transversal: completar la Fase 2 en la interfaz** (puntos 3 y 4 de arriba) y
cubrir `format.ts` con pruebas.

**Recomendación:** cerrar el punto 4 (cuentas) antes de la importación, y
después ir a la Fase 3. La caja y los depósitos pueden esperar a que exista la
pantalla de rendimiento, que es donde el XIRR los va a necesitar.
