"""Rendimiento: ROI por posición y XIRR de cartera.

Dos aclaraciones que gobiernan este módulo.

**No existe "el capital invertido".** La planilla anterior usaba un solo
número como denominador de todo, y ese número era compras menos ventas: se
achica cada vez que vendés, así que el porcentaje se infla solo. Si cerrabas
todo, tendía a infinito. Acá cada métrica usa el denominador que le
corresponde y ninguna se llama así.

**El TWR no está, a propósito.** Necesita el valor de la cartera en cada fecha
de flujo, y hoy sólo existe el último precio. Calcularlo con lo que hay daría
un número que parece un rendimiento sin serlo. Llega cuando existan los
snapshots diarios.

Python puro: sin base de datos, sin red.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation

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
