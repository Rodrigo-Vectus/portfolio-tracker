/**
 * Pantalla de inicio.
 *
 * **No calcula nada propio.** Compone lo que ya devuelven `/positions` y
 * `/cash`. Si calculara por su cuenta habría dos fuentes para el mismo número
 * y tarde o temprano discreparían, que es el problema de la planilla con otra
 * forma.
 *
 * Requisito de producto que gobierna esta pantalla: **todo número debe poder
 * explicarse**. Por eso cada tarjeta dice de dónde sale su valor, y cuando un
 * número no se puede calcular aparece el motivo en lugar de un cero.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, Nota, Num, PageHeading } from "../components/ui";
import { formatearImporte, signo } from "../lib/format";
import {
  fetchPortfolios,
  fetchPositions,
  fetchSaldo,
  type Portfolio,
  type Position,
  type Saldo,
  type Total,
} from "../lib/finance";

function Tarjeta({
  etiqueta,
  valor,
  origen,
  tono = "neutro",
  aviso,
}: {
  etiqueta: string;
  valor: string;
  origen: string;
  tono?: "neutro" | "positivo" | "negativo" | "tenue";
  aviso?: string;
}) {
  return (
    <div className="rounded border border-ink-600 bg-ink-800 p-5">
      <p className="text-sm text-text-muted">{etiqueta}</p>
      <p className="mt-1 text-xl">
        <Num tono={tono}>{valor}</Num>
      </p>
      <p className="mt-2 text-micro text-text-faint">{origen}</p>
      {aviso && <p className="mt-1.5 text-micro text-stale">{aviso}</p>}
    </div>
  );
}

/**
 * Distribución por activo.
 *
 * Barras y no torta: comparar longitudes es más preciso que comparar ángulos,
 * y acá el punto es ver qué pesa más. Sólo se dibuja si **todas** las
 * posiciones tienen valor: un reparto porcentual al que le falta un activo
 * miente sobre los que sí están, porque el 100% deja de ser el total.
 */
function Distribucion({ posiciones }: { posiciones: Position[] }) {
  const conValor = posiciones.filter((p) => p.current_value !== null);
  if (conValor.length === 0) return null;

  if (conValor.length !== posiciones.length) {
    return (
      <Nota>
        No se muestra la distribución porque {posiciones.length - conValor.length}{" "}
        de {posiciones.length} posiciones no tienen cotización. Un reparto
        porcentual incompleto exagera el peso de los activos que sí tienen
        precio.
      </Nota>
    );
  }

  // El total se recalcula sólo para obtener proporciones dentro de este
  // gráfico. No pretende ser el valor de la cartera: ese lo declara el
  // backend con su propia completitud.
  const valores = conValor.map((p) => ({
    symbol: p.symbol,
    valor: Number(p.current_value),
  }));
  const suma = valores.reduce((a, v) => a + v.valor, 0);
  if (suma <= 0) return null;

  return (
    <div className="space-y-2.5">
      {valores
        .sort((a, b) => b.valor - a.valor)
        .map((v) => {
          const pct = (v.valor / suma) * 100;
          return (
            <div key={v.symbol}>
              <div className="mb-1 flex items-baseline justify-between text-sm">
                <span className="font-medium">{v.symbol}</span>
                <Num tono="tenue">{pct.toFixed(1)}%</Num>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-ink-700">
                <div
                  className="h-full rounded-full bg-brand"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
    </div>
  );
}

export function Dashboard() {
  const [portfolios, setPortfolios] = useState<Portfolio[] | null>(null);
  const [posiciones, setPosiciones] = useState<Position[]>([]);
  const [total, setTotal] = useState<Total | null>(null);
  const [saldo, setSaldo] = useState<Saldo | null>(null);

  useEffect(() => {
    void (async () => {
      const p = await fetchPortfolios();
      if (!p.ok) {
        setPortfolios([]);
        return;
      }
      setPortfolios(p.data);
      if (p.data.length === 0) return;

      const id = p.data[0].id;
      const [pos, sal] = await Promise.all([fetchPositions(id), fetchSaldo(id)]);
      if (pos.ok) {
        setPosiciones(pos.data.positions);
        setTotal(pos.data.total);
      }
      if (sal.ok) setSaldo(sal.data);
    })();
  }, []);

  if (portfolios === null) {
    return (
      <>
        <PageHeading title="Dashboard" />
        <p className="text-text-muted">Cargando…</p>
      </>
    );
  }

  if (portfolios.length === 0) {
    return (
      <>
        <PageHeading title="Dashboard" />
        <EmptyState
          title="Todavía no hay nada que mostrar."
          detail="Creá un portfolio y registrá tu primer depósito para empezar."
        />
        <div className="mt-6 flex gap-4 text-sm">
          <Link to="/portfolio" className="text-brand hover:underline">
            Crear portfolio
          </Link>
          <Link to="/activos" className="text-brand hover:underline">
            Cargar activos
          </Link>
        </div>
      </>
    );
  }

  const realizado = posiciones.reduce(
    (a, p) => a + Number(p.realized_pnl ?? 0),
    0,
  );
  const noRealizadoDisponible = posiciones.every((p) => p.unrealized_pnl !== null);
  const noRealizado = posiciones.reduce(
    (a, p) => a + Number(p.unrealized_pnl ?? 0),
    0,
  );

  return (
    <>
      <PageHeading
        title="Dashboard"
        subtitle={`${portfolios[0].name} · todos los números salen del libro de operaciones`}
      />

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Tarjeta
          etiqueta="Valor de la cartera"
          valor={total?.total ? formatearImporte(total.total) : "—"}
          origen={
            total?.total
              ? `${total.currency} · posiciones × última cotización`
              : "No se puede calcular"
          }
          tono={total?.total ? "neutro" : "tenue"}
          aviso={
            total?.es_estimado
              ? "Antigüedad estimada"
              : (total?.motivo ?? undefined)
          }
        />
        <Tarjeta
          etiqueta="Disponible"
          valor={saldo ? formatearImporte(saldo.saldo) : "—"}
          origen={saldo ? `${saldo.currency} · sin invertir` : "Sin datos"}
          tono={saldo?.es_negativo ? "negativo" : "neutro"}
          aviso={saldo?.es_negativo ? "Falta registrar un depósito" : undefined}
        />
        <Tarjeta
          etiqueta="Aporte neto"
          valor={saldo ? formatearImporte(saldo.aporte_neto) : "—"}
          origen="Depósitos menos retiros"
        />
        <Tarjeta
          etiqueta="Resultado realizado"
          valor={formatearImporte(String(realizado))}
          origen="Ventas cerradas, por costo promedio"
          tono={
            signo(String(realizado)) === "positivo"
              ? "positivo"
              : signo(String(realizado)) === "negativo"
                ? "negativo"
                : "tenue"
          }
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <h2 className="mb-4 text-sm font-medium text-text-muted">
            Distribución por activo
          </h2>
          {posiciones.length === 0 ? (
            <p className="text-sm text-text-muted">No hay posiciones abiertas.</p>
          ) : (
            <Distribucion posiciones={posiciones} />
          )}
        </div>

        <div>
          <h2 className="mb-4 text-sm font-medium text-text-muted">
            Resultado no realizado
          </h2>
          {posiciones.length === 0 ? (
            <p className="text-sm text-text-muted">No hay posiciones abiertas.</p>
          ) : noRealizadoDisponible ? (
            <>
              <p className="text-xl">
                <Num
                  tono={
                    signo(String(noRealizado)) === "positivo"
                      ? "positivo"
                      : signo(String(noRealizado)) === "negativo"
                        ? "negativo"
                        : "tenue"
                  }
                >
                  {formatearImporte(String(noRealizado))}
                </Num>
              </p>
              <p className="mt-2 text-micro text-text-faint">
                Valor actual menos costo de lo abierto. Todavía no se cobró:
                cambia con cada cotización.
              </p>
            </>
          ) : (
            <p className="max-w-prose text-sm text-text-muted">
              No se puede calcular: falta la cotización de al menos una
              posición. Se muestra vacío en vez de sumar sólo las que tienen
              precio, porque ese número parecería el resultado completo.
            </p>
          )}
        </div>
      </div>

      <div className="mt-10 space-y-3">
        <Nota>
          El rendimiento porcentual todavía no está: ROI, TWR y XIRR llegan en la
          próxima fase. El porcentaje sobre "compras menos ventas" que usaba la
          planilla se infla solo al vender, así que no se muestra ninguno hasta
          tener las fórmulas correctas.
        </Nota>
        <Nota>
          Tampoco hay evolución temporal: el sistema guarda la última cotización
          de cada activo, no la serie histórica. Requiere los snapshots diarios
          de una fase posterior.
        </Nota>
      </div>
    </>
  );
}
