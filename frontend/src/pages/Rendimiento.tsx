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
  Pill,
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
  type Twr as TwrT,
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
    <div className="rounded-xl border border-ink-600 bg-ink-800 p-card">
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

/**
 * Tarjeta del TWR.
 *
 * No alcanza con el porcentaje: el TWR de una serie corta es un número
 * técnicamente correcto y prácticamente vacío. Por eso la tarjeta muestra
 * siempre sobre qué tramo se calculó, y cuando la serie se cortó o la caja
 * está en rojo, lo dice en ámbar. Verde y rojo quedan para el signo.
 */
function TarjetaTwr({ twr }: { twr: TwrT }) {
  const hay = twr.acumulado !== null;

  return (
    <div className="rounded-xl border border-ink-600 bg-ink-800 p-card">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-text-muted">Rendimiento de la cartera (TWR)</p>
        {(twr.corte || twr.advertencia) && <Pill tono="aviso">Leer la nota</Pill>}
      </div>

      <p className="mt-1 text-xl">
        {hay ? (
          <Num tono={tono(twr.acumulado)}>
            {formatearPorcentaje(twr.acumulado as string)}
          </Num>
        ) : (
          <Num tono="tenue">—</Num>
        )}
      </p>

      {hay && (
        <p className="mt-1 text-sm text-text-muted">
          {twr.anualizado !== null ? (
            <>
              <Num tono={tono(twr.anualizado)}>
                {formatearPorcentaje(twr.anualizado)}
              </Num>{" "}
              anualizado
            </>
          ) : (
            "Acumulado del período. Todavía no se anualiza."
          )}
        </p>
      )}

      <p className="mt-2 max-w-prose text-micro text-text-faint">
        {hay
          ? `Del ${twr.desde} al ${twr.hasta}: ${twr.dias} día(s), ` +
            `${twr.subperiodos} tramo(s) encadenados. Neutraliza tus aportes, ` +
            `así que mide la cartera y no el momento en que pusiste la plata.`
          : (twr.motivo ?? "")}
      </p>

      {hay && twr.motivo && (
        <p className="mt-2 max-w-prose text-micro text-text-faint">{twr.motivo}</p>
      )}

      {twr.advertencia && (
        <p className="mt-3 max-w-prose border-l-2 border-stale/50 pl-3 text-micro text-stale">
          {twr.advertencia}
        </p>
      )}

      {twr.corte && (
        <p className="mt-3 max-w-prose border-l-2 border-stale/50 pl-3 text-micro text-stale">
          {twr.corte}
        </p>
      )}
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
          {/* Las dos tasas van juntas y arriba porque responden preguntas
              distintas sobre lo mismo: el TWR mide la cartera, el XIRR mide tu
              plata. Separarlas invitaría a leer una como corrección de la
              otra. */}
          <div className="mb-4 grid gap-4 lg:grid-cols-2">
            <TarjetaTwr twr={datos.twr} />
            <Cifra
              etiqueta="Rendimiento de tu plata (XIRR)"
              valor={datos.xirr_anual}
              porcentaje
              detalle={
                datos.xirr_anual !== null
                  ? "Tasa anual que iguala lo que pusiste con lo que tenés hoy, considerando las fechas. A diferencia del TWR, acertar el momento del aporte la mejora."
                  : (datos.xirr_motivo ?? "")
              }
            />
          </div>

          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
                <tr key={p.symbol} className="border-b border-ink-600/60">
                  <td className="px-4 py-3 font-medium">
                    {p.symbol}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Num>{formatearImporte(p.open_cost_basis)}</Num>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Num tono={p.valor_actual === null ? "tenue" : "neutro"}>
                      {p.valor_actual === null
                        ? "—"
                        : formatearImporte(p.valor_actual)}
                    </Num>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Num tono={p.no_realizado === null ? "tenue" : tono(p.no_realizado)}>
                      {p.no_realizado === null
                        ? "—"
                        : formatearImporte(p.no_realizado)}
                    </Num>
                  </td>
                  <td className="px-4 py-3 text-right">
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
              El TWR mide lo contrario: cuánto rindió la cartera, sin importar
              cuándo pusiste la plata. Encadena el rendimiento de cada día y en
              cada tramo descuenta lo que entró o salió, así que un depósito no
              se lee como ganancia. Es la métrica con la que se comparan los
              fondos entre sí.
            </Nota>
            <Nota>
              El TWR se calcula sobre los snapshots diarios, que arrancan el día
              del primer cierre y no se pueden reconstruir hacia atrás. Un día
              sin valuar corta la serie en vez de saltearse: encadenar por
              encima de un hueco afirmaría que entre sus puntas no pasó nada.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
