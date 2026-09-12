/**
 * Gráfico de evolución de la cartera.
 *
 * Vive acá y no adentro de una pantalla porque lo usan dos: Cartera lo muestra
 * como parte del resumen e Historial con su tabla de días. Copiarlo daría dos
 * gráficos que con el tiempo dibujarían los huecos de manera distinta, y
 * justamente el tratamiento de los huecos es lo que este gráfico tiene que
 * hacer bien.
 *
 * Dos decisiones que se ven dibujadas:
 *
 * - **Los huecos no se interpolan.** Un día sin cotización corta la línea en
 *   vez de unir sus vecinos. Una línea continua sobre un hueco afirma que ese
 *   día la cartera valía el promedio de los días de al lado, y eso no se sabe.
 * - **Los puntos estimados se marcan.** Cuando la antigüedad del precio se
 *   dedujo del horario de rueda en vez de venir del proveedor, el punto se
 *   dibuja distinto. Sin eso, un dato deducido se leería como uno medido.
 */

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
import { Num } from "./ui";
import { formatearFecha, formatearImporte } from "../lib/format";
import type { Punto } from "../lib/finance";

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
    <div className="rounded border border-ink-500 bg-ink-900 px-3 py-2">
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

/**
 * Rango del eje vertical.
 *
 * **No arranca en cero y eso necesita justificarse.** Una cartera de 365.000
 * que se movió 11.000 en cuatro días, dibujada desde cero, da una línea recta:
 * el gráfico ocupa lugar y no dice nada. Un eje que arranca cerca de los datos
 * muestra el movimiento que existe.
 *
 * El riesgo conocido de recortar el eje es exagerar: una variación mínima
 * parece un derrumbe. Se acota de dos maneras. Primero, el eje **siempre
 * muestra sus números**, así que la magnitud real está a la vista y no hay que
 * deducirla de la pendiente. Segundo, se agrega un margen del 15% del rango
 * arriba y abajo, para que la línea no toque los bordes y la pendiente no se
 * vea más empinada de lo que es.
 *
 * El costo de lo abierto entra en el cálculo: es la referencia contra la que
 * se lee el valor, y dejarlo fuera del rango lo sacaría del dibujo.
 */
function calcularDominio(filas: Fila[]): [number, number] | undefined {
  const valores = filas
    .flatMap((f) => [f.valor, f.costo])
    .filter((v): v is number => v !== null);

  if (valores.length === 0) return undefined;

  const min = Math.min(...valores);
  const max = Math.max(...valores);

  // Una serie plana no tiene rango del que sacar un margen: se abre a mano
  // para que la línea quede en el medio y no pegada a un borde.
  if (min === max) {
    const margen = Math.abs(min) * 0.05 || 1;
    return [min - margen, max + margen];
  }

  const margen = (max - min) * 0.15;
  // El piso no baja de cero: una cartera con valor negativo no existe, y un
  // eje que lo insinúa afirma algo imposible.
  return [Math.max(0, min - margen), max + margen];
}

export function GraficoDeEvolucion({ puntos }: { puntos: Punto[] }) {
  const filas = aFilas(puntos);
  const estimados = filas.filter((f) => f.estimado).length;
  const dominio = calcularDominio(filas);

  return (
    <div>
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
                    domain={dominio}
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
              {/* Decirlo es lo que hace honesto al recorte. La pendiente de un
                  eje acotado se ve más empinada de lo que es, y quien mira
                  tiene derecho a saber que el eje no arranca en cero. */}
              <span>El eje arranca cerca de los datos, no en cero.</span>
        </div>
    </div>
  );
}

export { aFilas };
export type { Fila };
