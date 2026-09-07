/**
 * Rendimiento de la cartera.
 *
 * Dos cosas que esta pantalla hace distinto de la planilla que reemplaza:
 *
 * - **Cada porcentaje dice sobre qué se calcula.** El ROI de una posición usa
 *   el costo de lo que sigue abierta; el de la planilla usaba compras menos
 *   ventas, que se achica al vender e infla el número solo.
 * - **Cuando algo no se puede calcular, aparece el motivo.** Un cero se leería
 *   como "no rindió nada", que es una afirmación distinta de "no se sabe".
 */

import { useEffect, useState } from "react";
import {
  EmptyState,
  Nota,
  Num,
  PageHeading,
  Select,
  Tabla,
} from "../components/ui";
import {
  formatearImporte,
  formatearPorcentaje,
  signo,
} from "../lib/format";
import {
  fetchPortfolios,
  fetchRendimiento,
  type Portfolio,
  type Rendimiento as RendimientoT,
} from "../lib/finance";

function tono(valor: string | null) {
  const s = signo(valor);
  return s === "positivo" ? "positivo" : s === "negativo" ? "negativo" : "tenue";
}

function Cifra({
  etiqueta,
  valor,
  detalle,
  porcentaje = false,
}: {
  etiqueta: string;
  valor: string | null;
  detalle: string;
  porcentaje?: boolean;
}) {
  return (
    <div className="rounded border border-ink-600 bg-ink-800 p-5">
      <p className="text-sm text-text-muted">{etiqueta}</p>
      <p className="mt-1 text-xl">
        {valor === null ? (
          <Num tono="tenue">—</Num>
        ) : (
          <Num tono={tono(valor)}>
            {porcentaje ? formatearPorcentaje(valor) : formatearImporte(valor)}
          </Num>
        )}
      </p>
      <p className="mt-2 max-w-prose text-micro text-text-faint">{detalle}</p>
    </div>
  );
}

export function Rendimiento() {
  const [portfolios, setPortfolios] = useState<Portfolio[] | null>(null);
  const [elegido, setElegido] = useState("");
  const [datos, setDatos] = useState<RendimientoT | null>(null);

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
      const r = await fetchRendimiento(elegido);
      if (r.ok) setDatos(r.data);
    })();
  }, [elegido]);

  if (portfolios === null) {
    return (
      <>
        <PageHeading title="Rendimiento" />
        <p className="text-text-muted">Cargando…</p>
      </>
    );
  }

  if (portfolios.length === 0) {
    return (
      <>
        <PageHeading title="Rendimiento" />
        <EmptyState
          title="Todavía no hay nada que medir."
          detail="Creá un portfolio, registrá un depósito y cargá tu primera operación."
        />
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="Rendimiento"
        subtitle="Cuánto rindió la cartera, y sobre qué se calcula cada número."
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
        <p className="text-text-muted">Calculando…</p>
      ) : (
        <>
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Cifra
              etiqueta="Tasa anual (XIRR)"
              valor={datos.xirr_anual}
              porcentaje
              detalle={
                datos.xirr_anual !== null
                  ? "Tasa que iguala lo que pusiste con lo que tenés hoy, considerando las fechas."
                  : (datos.xirr_motivo ?? "")
              }
            />
            <Cifra
              etiqueta="Resultado total"
              valor={datos.resultado_total}
              detalle="Realizado más no realizado, en la moneda de las operaciones."
            />
            <Cifra
              etiqueta="Realizado"
              valor={datos.realizado}
              detalle="Ganancia ya materializada en ventas, por costo promedio."
            />
            <Cifra
              etiqueta="No realizado"
              valor={datos.no_realizado}
              detalle="Todavía no se cobró: cambia con cada cotización."
            />
          </div>

          <h2 className="mb-4 text-sm font-medium text-text-muted">
            Rendimiento por posición
          </h2>

          {datos.posiciones.length === 0 ? (
            <p className="text-sm text-text-muted">No hay posiciones abiertas.</p>
          ) : (
            <Tabla
              columnas={[
                { titulo: "Activo" },
                { titulo: "Costo de lo abierto", alineacion: "derecha" },
                { titulo: "Valor actual", alineacion: "derecha" },
                { titulo: "No realizado", alineacion: "derecha" },
                { titulo: "ROI", alineacion: "derecha" },
              ]}
            >
              {datos.posiciones.map((p) => (
                <tr key={p.symbol} className="border-b border-ink-700">
                  <td className="px-3 py-2.5 font-medium first:pl-0 last:pr-0">
                    {p.symbol}
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num>{formatearImporte(p.open_cost_basis)}</Num>
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num tono={p.valor_actual === null ? "tenue" : "neutro"}>
                      {p.valor_actual === null
                        ? "—"
                        : formatearImporte(p.valor_actual)}
                    </Num>
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num tono={p.no_realizado === null ? "tenue" : tono(p.no_realizado)}>
                      {p.no_realizado === null
                        ? "—"
                        : formatearImporte(p.no_realizado)}
                    </Num>
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num tono={p.roi === null ? "tenue" : tono(p.roi)}>
                      {p.roi === null ? "—" : formatearPorcentaje(p.roi)}
                    </Num>
                  </td>
                </tr>
              ))}
            </Tabla>
          )}

          <div className="mt-10 space-y-3">
            <Nota>
              El ROI de cada posición se calcula sobre el costo de lo que sigue
              abierto. La planilla anterior usaba compras menos ventas como
              denominador, y ese número se achica cada vez que vendés: el
              porcentaje se inflaba solo, y si cerrabas todo tendía a infinito.
            </Nota>
            <Nota>
              El XIRR mide el rendimiento de la plata que pusiste, considerando
              cuándo la pusiste. Ganar 10% en un mes y 10% en tres años son
              cosas distintas, y un porcentaje simple las muestra iguales.
            </Nota>
            <Nota>
              Falta el TWR, que mide el rendimiento aislando el efecto de tus
              aportes. Necesita el valor de la cartera en cada fecha de
              movimiento, y por ahora sólo se guarda la última cotización de
              cada activo. Llega con los snapshots diarios.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
