"""Rendimiento: ROI por posición y XIRR de cartera.

Dos aclaraciones que gobiernan este módulo.

**No existe "el capital invertido".** La planilla anterior usaba un solo
número como denominador de todo, y ese número era compras menos ventas: se
achica cada vez que vendés, así que el porcentaje se infla solo. Si cerrabas
todo, tendía a infinito. Acá cada métrica usa el denominador que le
corresponde y ninguna se llama así.

**El TWR ya está**, y mide algo distinto del XIRR. El XIRR responde "cuánto
rindió mi plata", así que le importa cuándo la pusiste: acertar el momento
mejora la tasa. El TWR responde "cuánto rindió la cartera", y para eso
neutraliza los aportes: el mismo resultado te da hayas puesto la plata antes o
después. Uno mide al inversor, el otro a la cartera, y por eso conviven.

Python puro: sin base de datos, sin red.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation
from itertools import pairwise

ZERO = Decimal(0)
DIAS_DEL_ANIO = Decimal(365)


@dataclass(frozen=True, slots=True)
class Flujo:
    """Un movimiento de dinero fechado, desde el punto de vista del inversor.

    Negativo cuando sale de tu bolsillo (un depósito en el broker), positivo
    cuando vuelve (un retiro). El valor actual de la cartera entra como un
    flujo positivo final: es lo que recibirías si liquidaras hoy.
    """

    fecha: date
    monto: Decimal


class XirrNoConverge(Exception):
    """No se pudo encontrar una tasa que anule el valor presente.

    Pasa cuando los flujos no describen una inversión: todos del mismo signo,
    o una pérdida tan grande que ninguna tasa real la explica. Se avisa en vez
    de devolver un número cualquiera.
    """


def _van(tasa: Decimal, flujos: list[Flujo], inicio: date) -> Decimal:
    """Valor actual neto de los flujos a una tasa anual dada."""
    total = ZERO
    for f in flujos:
        años = Decimal((f.fecha - inicio).days) / DIAS_DEL_ANIO
        total += f.monto / (Decimal(1) + tasa) ** años
    return total


def xirr(
    flujos: list[Flujo],
    *,
    tolerancia: Decimal = Decimal("0.0000001"),
    max_iteraciones: int = 200,
) -> Decimal:
    """Tasa interna de retorno de flujos con fechas irregulares.

    Es la tasa anual que hace que el valor presente de todo lo que pusiste y
    todo lo que recibiste sea cero.

    Responde una pregunta que el ROI no responde: **cuánto rindió tu plata
    considerando cuándo la pusiste.** Ganar 10% en un mes no es lo mismo que
    ganar 10% en tres años, y un porcentaje simple los muestra igual.

    Se resuelve por bisección y no por Newton-Raphson. Newton converge más
    rápido pero puede irse a cualquier lado cuando la derivada es chica, y en
    una función financiera eso significa devolver una tasa absurda con toda
    confianza. La bisección es más lenta y no puede divergir: si hay una raíz
    en el intervalo, la encuentra.
    """
    if len(flujos) < 2:
        raise XirrNoConverge("Hacen falta al menos dos flujos.")

    ordenados = sorted(flujos, key=lambda f: f.fecha)
    inicio = ordenados[0].fecha

    if all(f.monto >= 0 for f in ordenados) or all(f.monto <= 0 for f in ordenados):
        raise XirrNoConverge(
            "Todos los flujos tienen el mismo signo: no hay una inversión que "
            "medir. Registrá el depósito que financió las compras."
        )

    if ordenados[0].fecha == ordenados[-1].fecha:
        raise XirrNoConverge(
            "Todos los flujos son del mismo día: no hay tiempo transcurrido "
            "sobre el cual calcular una tasa anual."
        )

    # −99,99% a +100.000%. El extremo inferior no llega a −1 porque ahí la
    # fórmula se indefine: sería perder más que todo lo invertido.
    bajo, alto = Decimal("-0.9999"), Decimal(1000)

    try:
        v_bajo, v_alto = _van(bajo, ordenados, inicio), _van(alto, ordenados, inicio)
    except (InvalidOperation, DivisionByZero, OverflowError) as exc:
        raise XirrNoConverge("Los flujos producen un cálculo indefinido.") from exc

    if v_bajo * v_alto > 0:
        raise XirrNoConverge(
            "No hay una tasa entre −99,99% y 100.000% que explique estos "
            "flujos. Puede haber una operación mal cargada."
        )

    for _ in range(max_iteraciones):
        medio = (bajo + alto) / 2
        try:
            valor = _van(medio, ordenados, inicio)
        except (InvalidOperation, DivisionByZero, OverflowError) as exc:
            raise XirrNoConverge("Los flujos producen un cálculo indefinido.") from exc

        if abs(valor) < tolerancia:
            return medio
        if valor * v_bajo < 0:
            alto = medio
        else:
            bajo, v_bajo = medio, valor

    # Se devuelve igual: 200 bisecciones acotan el intervalo a menos de
    # 10⁻⁵⁷ del original. Que no haya bajado de la tolerancia significa que la
    # función es muy plana ahí, no que la respuesta sea mala.
    return (bajo + alto) / 2


@dataclass(frozen=True, slots=True)
class RoiDePosicion:
    """Rendimiento de una posición abierta.

    El denominador es el **costo base de lo que todavía tenés**, no el capital
    neto aportado. Esa diferencia es la que hacía que el porcentaje de la
    planilla se inflara al vender.
    """

    symbol: str
    open_cost_basis: Decimal
    valor_actual: Decimal | None
    no_realizado: Decimal | None
    roi: Decimal | None

    @property
    def calculable(self) -> bool:
        return self.roi is not None


def roi_de_posicion(
    symbol: str, open_cost_basis: Decimal, valor_actual: Decimal | None
) -> RoiDePosicion:
    """(valor actual − costo de lo abierto) / costo de lo abierto.

    Devuelve `None` si no hay cotización o si el costo es cero. Un ROI sobre
    denominador cero no es infinito ni cien por ciento: no existe.
    """
    if valor_actual is None or open_cost_basis == ZERO:
        return RoiDePosicion(symbol, open_cost_basis, valor_actual, None, None)

    no_realizado = valor_actual - open_cost_basis
    return RoiDePosicion(
        symbol=symbol,
        open_cost_basis=open_cost_basis,
        valor_actual=valor_actual,
        no_realizado=no_realizado,
        roi=no_realizado / open_cost_basis,
    )


# ------------------------------------------------------------------------ TWR
#
# El TWR (time-weighted return) encadena el rendimiento de cada subperíodo
# entre dos valuaciones consecutivas, y en cada uno descuenta el dinero que
# entró o salió. Al multiplicar los tramos, los aportes quedan neutralizados:
# lo que queda es cuánto rindió la cartera, no cuánto acertó el inversor
# eligiendo el momento de poner la plata.
#
# Es la métrica con la que se comparan los fondos entre sí, justamente porque
# no premia ni castiga por el calendario de aportes de cada cliente.


#: Debajo de este umbral no se anualiza. Elevar unos pocos días a 365/n
#: produce tasas de miles por ciento con toda seriedad: un 2% en tres días
#: anualizado da 1.000%, y ese número no dice nada sobre el año que viene.
DIAS_MINIMOS_PARA_ANUALIZAR = 90


@dataclass(frozen=True, slots=True)
class PuntoDeTwr:
    """Una valuación fechada de la cartera, con el dinero que entró ese día.

    `patrimonio` es **posiciones más caja**, no sólo posiciones. Los flujos
    del TWR son depósitos y retiros, y esos entran a la caja: si el
    denominador excluyera la caja, un depósito que todavía no se invirtió
    aparecería como flujo sin contrapartida y ensuciaría el tramo.

    Viene en `None` cuando ese día no se pudo valuar. Un `None` corta la
    cadena: multiplicar salteando el hueco afirmaría que entre las dos puntas
    no pasó nada.

    `flujo` es lo que **entró** a la cartera ese día: un depósito es positivo,
    un retiro negativo.

    `caja` es opcional y no participa del cálculo: se transporta sólo para
    poder avisar cuando está en rojo. Una caja negativa achica el patrimonio y
    con él el denominador de cada tramo, así que el porcentaje sale correcto y
    se lee mal.
    """

    fecha: date
    patrimonio: Decimal | None
    flujo: Decimal = ZERO
    caja: Decimal | None = None


@dataclass(frozen=True, slots=True)
class ResultadoTwr:
    """El TWR con su alcance declarado.

    Nunca devuelve un número pelado: siempre dice sobre qué tramo se calculó,
    cuántos subperíodos encadenó y, si no se pudo, por qué.
    """

    acumulado: Decimal | None
    anualizado: Decimal | None
    desde: date | None
    hasta: date | None
    dias: int
    subperiodos: int
    motivo: str | None
    #: Presente cuando la serie se cortó por un hueco anterior.
    corte: str | None = None
    #: Presente cuando el número es correcto pero se lee mal. No lo invalida:
    #: lo enmarca. Misma distinción que D34-bis hace con el total estimado.
    advertencia: str | None = None

    @property
    def calculable(self) -> bool:
        return self.acumulado is not None


def _tramo_continuo_mas_reciente(
    puntos: list[PuntoDeTwr],
) -> tuple[list[PuntoDeTwr], bool]:
    """El último bloque de valuaciones seguidas, y si hubo algo antes.

    Un día sin valor corta la serie. Se usa el tramo más reciente porque es el
    que describe la cartera de hoy; los anteriores quedan afuera y se avisa.
    """
    ultimo: list[PuntoDeTwr] = []
    inicio = 0

    for i, p in enumerate(puntos):
        if p.patrimonio is None:
            ultimo = []
            inicio = i + 1
            continue
        if not ultimo:
            inicio = i
        ultimo.append(p)

    # Se toma el tramo **más reciente**, no el más largo: un bloque viejo y
    # extenso describe una cartera que ya no es la de hoy.
    if not ultimo:
        return [], bool(puntos)

    return ultimo, inicio > 0


def twr(
    puntos: list[PuntoDeTwr],
    *,
    dias_minimos_para_anualizar: int = DIAS_MINIMOS_PARA_ANUALIZAR,
) -> ResultadoTwr:
    """Rendimiento de la cartera aislando el efecto de los aportes.

    Cada subperíodo se calcula así::

        r = patrimonio_final / (patrimonio_inicial + flujo_del_tramo) − 1

    El flujo va **en el denominador** y no restado del numerador porque el
    snapshot se toma a las 18:10, después del cierre de rueda: un depósito del
    día ya está adentro del patrimonio de ese día. Dividir por el patrimonio
    anterior a secas contaría la plata que entró como plata que se ganó, que
    es el error E1 de la planilla con otra cara.

    Los tramos se multiplican, no se suman: ganar 10% y después 10% es 21%, no
    20%.

    **Limitación conocida.** Poner el flujo en el denominador equivale a
    suponer que entró al principio del día, así que estuvo expuesto al
    rendimiento de esa jornada completa. Si el depósito llegó a las 16:00, el
    tramo queda apenas subestimado. Corregirlo requiere la hora del flujo
    ponderada dentro del día (Dietz modificado), y con snapshots diarios el
    error es de una jornada sobre toda la serie. Se elige la aproximación
    simple y se declara, en vez de sugerir una precisión que no hay.
    """
    ordenados = sorted(puntos, key=lambda p: p.fecha)
    tramo, hubo_antes = _tramo_continuo_mas_reciente(ordenados)

    corte = None
    if hubo_antes and tramo:
        corte = (
            f"La serie se cortó: antes del {tramo[0].fecha.isoformat()} hay días "
            "sin valuar. El TWR se calcula sobre el tramo continuo más "
            "reciente, porque encadenar salteando un hueco afirmaría que entre "
            "sus puntas no pasó nada."
        )

    # Una caja negativa no invalida el TWR: lo distorsiona. El patrimonio es
    # posiciones más caja, así que un rojo en la caja achica el denominador y
    # el mismo movimiento de precios sale amplificado. Suele significar que hay
    # compras sin el depósito que las financió, y eso se arregla cargando el
    # depósito, no cambiando la fórmula.
    advertencia = None
    if any(p.caja is not None and p.caja < ZERO for p in tramo):
        advertencia = (
            "La caja está en negativo, así que el patrimonio contra el que se "
            "mide cada tramo queda achicado y el porcentaje sale amplificado. "
            "El número es correcto; lo que falta es el depósito que financió "
            "las compras. Registralo y esta advertencia desaparece."
        )

    if len(tramo) < 2:
        return ResultadoTwr(
            acumulado=None,
            anualizado=None,
            desde=tramo[0].fecha if tramo else None,
            hasta=tramo[-1].fecha if tramo else None,
            dias=0,
            subperiodos=0,
            motivo=(
                "Hacen falta al menos dos días valuados seguidos para encadenar "
                "un rendimiento. La serie de snapshots arranca el día del primer "
                "cierre y no se puede reconstruir hacia atrás."
            ),
            corte=corte,
            advertencia=advertencia,
        )

    acumulado = Decimal(1)

    for anterior, actual in pairwise(tramo):
        previo = anterior.patrimonio or ZERO
        final = actual.patrimonio or ZERO
        base = previo + actual.flujo

        if base <= ZERO:
            return ResultadoTwr(
                acumulado=None,
                anualizado=None,
                desde=tramo[0].fecha,
                hasta=tramo[-1].fecha,
                dias=(tramo[-1].fecha - tramo[0].fecha).days,
                subperiodos=0,
                motivo=(
                    f"El {actual.fecha.isoformat()} el capital sobre el que se "
                    "mide el tramo es cero o negativo, y un porcentaje sobre esa "
                    "base no significa nada. Suele pasar cuando hay compras sin "
                    "el depósito que las financió: revisá el saldo de caja."
                ),
                corte=corte,
                advertencia=advertencia,
            )

        acumulado *= final / base

    resultado = acumulado - Decimal(1)
    dias = (tramo[-1].fecha - tramo[0].fecha).days

    anualizado: Decimal | None = None
    if dias >= dias_minimos_para_anualizar and acumulado > ZERO:
        try:
            anualizado = acumulado ** (DIAS_DEL_ANIO / Decimal(dias)) - Decimal(1)
        except (InvalidOperation, DivisionByZero, OverflowError):
            anualizado = None

    motivo = None
    if anualizado is None:
        motivo = (
            f"Con {dias} día(s) de serie no se anualiza. Elevar un tramo corto a "
            f"365/{dias or 1} produce una tasa enorme que no describe ningún año. "
            f"Hacen falta {dias_minimos_para_anualizar} días."
        )

    return ResultadoTwr(
        acumulado=resultado,
        anualizado=anualizado,
        desde=tramo[0].fecha,
        hasta=tramo[-1].fecha,
        dias=dias,
        subperiodos=len(tramo) - 1,
        motivo=motivo,
        corte=corte,
        advertencia=advertencia,
    )
