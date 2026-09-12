/**
 * Distribución de la cartera por activo.
 *
 * **No se dibuja si falta una sola cotización.** Un porcentaje es una parte de
 * un total, y si el total está incompleto cada porción afirma una proporción
 * que nadie midió: el activo sin precio desaparecería del gráfico y los demás
 * se repartirían el 100% entre ellos, mostrando una cartera más concentrada de
 * lo que es.
 *
 * Los colores son de la paleta de marca. **Ninguno es verde ni rojo**: esos dos
 * significan el signo de un resultado y nada más, y una porción verde en un
 * gráfico de composición diría "esto ganó" cuando sólo dice "esto pesa tanto".
 */

import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";
import { Nota, Num } from "./ui";
import { formatearImporte, formatearPorcentaje } from "../lib/format";
import type { Position } from "../lib/finance";

/** Celeste de marca en cinco intensidades, más un gris para el resto. */
const COLORES = ["#2D9CF0", "#5CB4F5", "#8ACBF9", "#B0DCFB", "#6E8BA6", "#485466"];

export function Distribucion({
  posiciones,
  moneda,
}: {
  posiciones: Position[];
  moneda: string;
}) {
  const sinPrecio = posiciones.filter((p) => p.current_value === null);

  if (posiciones.length === 0) return null;

  if (sinPrecio.length > 0) {
    return (
      <Nota>
        No se dibuja la distribución porque {sinPrecio.length === 1 ? "falta" : "faltan"}{" "}
        {sinPrecio.length === 1 ? "la cotización de" : "las cotizaciones de"}{" "}
        {sinPrecio.map((p) => p.symbol).join(", ")}. Un porcentaje sobre un total
        incompleto repartiría el 100% entre los demás y mostraría una cartera más
        concentrada de lo que es.
      </Nota>
    );
  }

  // El valor ya viene calculado del servidor. Para dibujar un ángulo hace
  // falta un número, y ahí sí se convierte: un píxel de más o de menos no es
  // un error contable. Los importes que se muestran como texto siguen
  // saliendo del string original, sin pasar por `number`.
  const datos = posiciones
    .map((p) => ({
      symbol: p.symbol,
      valorTexto: p.current_value as string,
      valor: Number(p.current_value),
    }))
    .filter((d) => d.valor > 0)
    .sort((a, b) => b.valor - a.valor);

  if (datos.length === 0) return null;

  const total = datos.reduce((acc, d) => acc + d.valor, 0);

  return (
    <div className="rounded-xl border border-ink-600 bg-ink-800 p-card">
      <h2 className="mb-4 text-sm font-medium text-text-muted">
        Distribución por activo
      </h2>

      <div className="flex flex-col items-center gap-6 sm:flex-row">
        <div className="h-48 w-48 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={datos}
                dataKey="valor"
                nameKey="symbol"
                innerRadius="58%"
                outerRadius="100%"
                paddingAngle={2}
                stroke="none"
                isAnimationActive={false}
              >
                {datos.map((d, i) => (
                  <Cell key={d.symbol} fill={COLORES[i % COLORES.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>

        <ul className="min-w-0 flex-1 space-y-2 text-sm">
          {datos.map((d, i) => (
            <li key={d.symbol} className="flex items-baseline justify-between gap-4">
              <span className="flex min-w-0 items-center gap-2">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: COLORES[i % COLORES.length] }}
                />
                <span className="truncate font-medium">{d.symbol}</span>
              </span>
              <span className="shrink-0 text-right">
                <Num>{formatearPorcentaje(String(d.valor / total))}</Num>
                <span className="code ml-3 text-micro text-text-faint">
                  {formatearImporte(d.valorTexto)} {moneda}
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
