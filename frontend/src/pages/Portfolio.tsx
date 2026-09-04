/**
 * Posiciones abiertas.
 *
 * Lo que esta pantalla **no** muestra es tan importante como lo que muestra:
 * no hay precio actual, ni valor de mercado, ni resultado no realizado. No es
 * una omisión ni una pantalla a medio hacer. El sistema todavía no tiene
 * cotizaciones, y mostrar un valor de mercado inventado sería exactamente el
 * error que originó el proyecto.
 *
 * La pantalla lo dice explícitamente en vez de dejar una columna vacía que se
 * pueda confundir con un cero.
 */

import { useEffect, useState } from "react";
import {
  Button,
  EmptyState,
  ErrorNote,
  Field,
  Nota,
  Num,
  PageHeading,
  Select,
  Tabla,
} from "../components/ui";
import { formatearCantidad, formatearImporte, signo } from "../lib/format";
import {
  crearPortfolio,
  fetchPortfolios,
  fetchPositions,
  type Portfolio as PortfolioT,
  type Position,
} from "../lib/finance";

export function Portfolio() {
  const [portfolios, setPortfolios] = useState<PortfolioT[] | null>(null);
  const [elegido, setElegido] = useState("");
  const [posiciones, setPosiciones] = useState<Position[] | null>(null);
  const [error, setError] = useState("");
  const [nombre, setNombre] = useState("Principal");
  const [moneda, setMoneda] = useState("USD");
  const [creando, setCreando] = useState(false);
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    void (async () => {
      const r = await fetchPortfolios();
      if (!r.ok) {
        setError(r.error);
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
      setPosiciones(null);
      const r = await fetchPositions(elegido);
      if (r.ok) {
        setPosiciones(r.data);
        setError("");
      } else {
        setError(r.error);
        setPosiciones([]);
      }
    })();
  }, [elegido]);

  async function crear() {
    setCreando(true);
    setError("");
    const r = await crearPortfolio({ name: nombre, base_currency: moneda });
    setCreando(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    setPortfolios((prev) => [...(prev ?? []), r.data]);
    setElegido(r.data.id);
    setAbierto(false);
    setNombre("");
  }

  if (portfolios === null) {
    return (
      <>
        <PageHeading title="Portfolio" />
        <p className="text-text-muted">Cargando…</p>
      </>
    );
  }

  const sinPortfolios = portfolios.length === 0;

  // El formulario no es exclusivo del estado vacío. En la primera versión sólo
  // aparecía cuando no había ninguno, así que al crear el primero desaparecía
  // para siempre y la pantalla quedaba sin ninguna acción posible.
  const formulario = (
    <div className="mb-8 max-w-md rounded border border-ink-600 bg-ink-800 p-5">
      <div className="grid gap-4">
            <Field
              label="Nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
            />
        <Field
          label="Moneda de contabilidad"
          value={moneda}
          onChange={(e) => setMoneda(e.target.value.toUpperCase())}
          hint="En la que se van a medir los resultados. Podés verlos en otra moneda más adelante."
        />
      </div>
      <div className="mt-5">
        <Button onClick={() => void crear()} disabled={creando || !nombre}>
          {creando ? "Creando…" : "Crear portfolio"}
        </Button>
      </div>
    </div>
  );

  if (sinPortfolios) {
    return (
      <>
        <PageHeading
          title="Portfolio"
          subtitle="Un portfolio agrupa tus operaciones. Las posiciones se calculan a partir de ellas."
        />
        <p className="mb-5 max-w-prose text-text-muted">
          Todavía no tenés ningún portfolio. Creá uno para empezar a registrar
          operaciones.
        </p>
        {formulario}
        {error && <ErrorNote>{error}</ErrorNote>}
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="Portfolio"
        subtitle="Tus posiciones abiertas, derivadas del libro de operaciones."
      />

      <div className="mb-6 flex flex-wrap items-end gap-4">
        {/* El selector se muestra siempre, incluso con uno solo: saber en qué
            portfolio estás parado es parte de leer los números. */}
        <div className="w-56">
          <Select
            label="Portfolio"
            value={elegido}
            onChange={(e) => setElegido(e.target.value)}
          >
            {portfolios.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.base_currency}
              </option>
            ))}
          </Select>
        </div>
        <Button variant="ghost" onClick={() => setAbierto((v) => !v)}>
          {abierto ? "Cancelar" : "Nuevo portfolio"}
        </Button>
      </div>

      {abierto && formulario}

      {error && (
        <div className="mb-6">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      {posiciones === null ? (
        <p className="text-text-muted">Cargando posiciones…</p>
      ) : posiciones.length === 0 ? (
        <EmptyState
          title="No hay posiciones abiertas."
          detail="Las posiciones se calculan a partir de tus operaciones. Registrá una compra en la sección Operaciones."
        />
      ) : (
        <>
          <Tabla
            columnas={[
              { titulo: "Activo" },
              { titulo: "Cantidad", alineacion: "derecha" },
              { titulo: "Costo promedio", alineacion: "derecha" },
              { titulo: "Costo de lo abierto", alineacion: "derecha" },
              { titulo: "Resultado realizado", alineacion: "derecha" },
              { titulo: "Método" },
            ]}
          >
            {posiciones.map((p) => {
              const s = signo(p.realized_pnl);
              return (
                <tr key={p.asset_id} className="border-b border-ink-700">
                  <td className="px-3 py-2.5 first:pl-0 last:pr-0 font-medium">{p.symbol}</td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num>{formatearCantidad(p.quantity)}</Num>
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num tono={p.average_cost === null ? "tenue" : "neutro"}>
                      {p.average_cost === null
                        ? "—"
                        : formatearImporte(p.average_cost)}
                    </Num>
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num>{formatearImporte(p.open_cost_basis)}</Num>
                  </td>
                  <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                    <Num
                      tono={
                        s === "positivo"
                          ? "positivo"
                          : s === "negativo"
                            ? "negativo"
                            : "tenue"
                      }
                    >
                      {formatearImporte(p.realized_pnl)}
                    </Num>
                  </td>
                  <td className="px-3 py-2.5 first:pl-0 last:pr-0 text-text-muted">{p.cost_method}</td>
                </tr>
              );
            })}
          </Tabla>

          <div className="mt-8 space-y-3">
            <Nota>
              No figura el valor actual de la cartera porque el sistema todavía no
              obtiene cotizaciones. Preferimos no mostrar un número antes que
              mostrar uno viejo o estimado sin decirlo: ese fue el problema que
              dio origen a este proyecto. La valuación llega en la fase 4.
            </Nota>
            <Nota>
              Los importes están en la moneda de cada operación y no incluyen
              conversión a dólares. El resultado realizado se calcula por costo
              promedio ponderado; con FIFO daría otro número, y esa diferencia
              vas a poder elegirla cuando exista la pantalla de rendimiento.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
