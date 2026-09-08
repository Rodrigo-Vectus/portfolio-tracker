/**
 * Evolución de la cartera.
 *
 * Dos decisiones que se ven en el gráfico:
 *
 * - **Los huecos no se interpolan.** Un día sin cotización corta la línea en
 *   vez de unir sus vecinos. Una línea continua sobre un hueco afirma que ese
 *   día la cartera valía el promedio de los días de al lado, y eso no se sabe.
 * - **Los puntos estimados se marcan.** Cuando la antigüedad del precio se
 *   dedujo del horario de rueda en vez de venir del proveedor, el punto se
 *   dibuja distinto. Sin eso, un dato deducido se leería como uno medido.
 */

import { useEffect, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EmptyState, Nota, Num, PageHeading, Select } from "../components/ui";
import { formatearFecha, formatearImporte, signo } from "../lib/format";
import {
  fetchHistorial,
  fetchPortfolios,
  type Historial as HistorialT,
  type Portfolio,
  type Punto,
} from "../lib/finance";

/** Abrevia para el eje: 253.200 → 253 k. Sin decimales, es una referencia. */
function abreviar(valor: number): string {
  const abs = Math.abs(valor);
  if (abs >= 1_000_000) return `${(valor / 1_000_000).toFixed(1)} M`;
  if (abs >= 1_000) return `${Math.round(valor / 1_000)} k`;
  return String(Math.round(valor));
}

interface Fila {
  fecha: string;
  etiqueta: string;
  valor: number | null;
  costo: number;
  estimado: boolean;
  motivo: string | null;
}

function aFilas(puntos: Punto[]): Fila[] {
  return puntos.map((p) => ({
    fecha: p.snapshot_date,
    etiqueta: formatearFecha(p.snapshot_date).slice(0, 5),
    // `null` corta la línea. Recharts no une los puntos alrededor de un nulo,
    // que es exactamente el comportamiento que se quiere.
    valor: p.total_value === null ? null : Number(p.total_value),
    costo: Number(p.open_cost_basis),
    estimado: p.is_estimated,
    motivo: p.motivo,
  }));
}

function Globo({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const f: Fila = payload[0].payload;

  return (
    <div className="rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 shadow-2xl shadow-black/60">
      <p className="code text-micro text-text-faint">{formatearFecha(f.fecha)}</p>
      <p className="mt-1 text-sm">
        {f.valor === null ? (
          <span className="text-stale">Sin valuación</span>
        ) : (
          <Num>{formatearImporte(String(f.valor))}</Num>
        )}
      </p>
      <p className="mt-0.5 text-micro text-text-faint">
        Costo <Num tono="tenue">{formatearImporte(String(f.costo))}</Num>
      </p>
      {f.motivo && <p className="mt-1 text-micro text-stale">{f.motivo}</p>}
    </div>
  );
}

/** Punto marcado cuando la antigüedad del precio es deducida. */
function Marca({ cx, cy, payload }: any) {
  if (cx === undefined || cy === undefined || payload?.valor === null) return null;
  if (!payload?.estimado) {
    return <circle cx={cx} cy={cy} r={2.5} fill="#2D9CF0" />;
  }
  return (
    <circle
      cx={cx}
      cy={cy}
      r={3.5}
      fill="#08090B"
      stroke="#E0A93B"
      strokeWidth={1.5}
    />
  );
}

export function Historial() {
  const [portfolios, setPortfolios] = useState<Portfolio[] | null>(null);
  const [elegido, setElegido] = useState("");
  const [datos, setDatos] = useState<HistorialT | null>(null);

  useEffect(() => {
    void (async () => {
      const r = await fetchPortfolios();
      if (!r.ok) {
        setPortfolios([]);
        return;
      }
      setPortfolios(r.data);
      if (r.data.length > 0) setElegido(r.data[0].id);
    })();
  }, []);

  useEffect(() => {
    if (!elegido) return;
    void (async () => {
      setDatos(null);
      const r = await fetchHistorial(elegido);
      if (r.ok) setDatos(r.data);
    })();
  }, [elegido]);

  if (portfolios === null) {
    return (
      <>
        <PageHeading title="Historial" />
        <p className="text-text-muted">Cargando…</p>
      </>
    );
  }

  if (portfolios.length === 0) {
    return (
      <>
        <PageHeading title="Historial" />
        <EmptyState
          title="Todavía no hay nada que graficar."
          detail="Creá un portfolio y cargá tu primera operación."
        />
      </>
    );
  }

  const filas = datos ? aFilas(datos.puntos) : [];
  const conValor = filas.filter((f) => f.valor !== null);
  const estimados = filas.filter((f) => f.estimado).length;
  const ultimo = conValor.at(-1);
  const primero = conValor[0];
  const variacion =
    ultimo && primero && primero.valor && ultimo.valor
      ? ultimo.valor - primero.valor
      : null;

  return (
    <>
      <PageHeading
        title="Historial"
        subtitle="Cómo evolucionó el valor de tu cartera, día a día."
      />

      {portfolios.length > 1 && (
        <div className="mb-6 w-56">
          <Select
            label="Portfolio"
            value={elegido}
            onChange={(e) => setElegido(e.target.value)}
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </div>
      )}

      {datos === null ? (
        <p className="text-text-muted">Cargando…</p>
      ) : filas.length < 2 ? (
        <>
          <EmptyState
            title={
              filas.length === 0
                ? "Todavía no hay historial."
                : "Hay un solo día registrado."
            }
            detail={datos.nota ?? undefined}
          />
          <div className="mt-6">
            <Nota>
              El historial se construye hacia adelante: cada día a las 18:10 se
              guarda una foto del valor de la cartera. No se puede reconstruir
              hacia atrás porque no existe el precio histórico de cada activo, y
              rellenar los días anteriores con el precio de hoy daría una línea
              plana que parece historia sin serlo.
            </Nota>
          </div>
        </>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-baseline gap-x-8 gap-y-2">
            <div>
              <p className="text-sm text-text-muted">Último valor</p>
              <p className="mt-1 text-xl">
                <Num>{formatearImporte(String(ultimo?.valor ?? 0))}</Num>{" "}
                <span className="text-base text-text-muted">{datos.currency}</span>
              </p>
            </div>
            {variacion !== null && (
              <div>
                <p className="text-sm text-text-muted">
                  Desde el {formatearFecha(primero.fecha)}
                </p>
                <p className="mt-1 text-lg">
                  <Num
                    tono={
                      signo(String(variacion)) === "positivo"
                        ? "positivo"
                        : signo(String(variacion)) === "negativo"
                          ? "negativo"
                          : "tenue"
                    }
                  >
                    {formatearImporte(String(variacion))}
                  </Num>
                </p>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-ink-600 bg-ink-800 p-5">
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={filas}
                  margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
                >
                  <defs>
                    <linearGradient id="areaValor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2D9CF0" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#2D9CF0" stopOpacity={0} />
                    </linearGradient>
                  </defs>

                  <CartesianGrid stroke="#242830" vertical={false} />
                  <XAxis
                    dataKey="etiqueta"
                    stroke="#667085"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: "#242830" }}
                  />
                  <YAxis
                    stroke="#667085"
                    tick={{ fontSize: 11 }}
                    tickLine={false}
                    axisLine={false}
                    width={56}
                    tickFormatter={abreviar}
                  />
                  <Tooltip content={<Globo />} cursor={{ stroke: "#333944" }} />

                  {/* El costo va detrás y en gris: es la referencia contra la
                      que se lee el valor, no un protagonista. */}
                  <Line
                    type="monotone"
                    dataKey="costo"
                    stroke="#667085"
                    strokeWidth={1}
                    strokeDasharray="4 4"
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="valor"
                    stroke="#2D9CF0"
                    strokeWidth={2}
                    fill="url(#areaValor)"
                    // `false` es lo que hace que la línea corte en los huecos
                    // en vez de saltarlos como si no existieran.
                    connectNulls={false}
                    dot={<Marca />}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 text-micro text-text-faint">
              <span className="flex items-center gap-2">
                <span className="h-0.5 w-5 rounded bg-brand" />
                Valor de la cartera
              </span>
              <span className="flex items-center gap-2">
                <span className="h-px w-5 border-t border-dashed border-text-faint" />
                Costo de lo abierto
              </span>
              {estimados > 0 && (
                <span className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full border border-stale bg-ink-900" />
                  Antigüedad estimada
                </span>
              )}
            </div>
          </div>

          <div className="mt-8 space-y-3">
            <Nota>
              Los días sin cotización cortan la línea en vez de unirse con sus
              vecinos. Una línea continua sobre un hueco afirmaría que ese día
              la cartera valía el promedio de los días de al lado, y eso no se
              sabe.
            </Nota>
            {estimados > 0 && (
              <Nota>
                {estimados === 1
                  ? "Un punto tiene"
                  : `${estimados} puntos tienen`}{" "}
                la antigüedad deducida del horario de rueda, porque la fuente de
                precios de CEDEARs no informa la hora de cotización. Se marcan
                distinto para no confundirlos con un dato medido.
              </Nota>
            )}
            <Nota>
              La serie arranca el {formatearFecha(datos.desde ?? "")} y crece
              hacia adelante. No se puede reconstruir hacia atrás: haría falta el
              precio de cada activo en cada día pasado.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
