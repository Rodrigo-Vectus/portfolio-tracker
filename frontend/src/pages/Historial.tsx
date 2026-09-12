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
  aFilas,
  GraficoDeEvolucion,
} from "../components/GraficoDeEvolucion";
import {
  Button,
  EmptyState,
  Field,
  Nota,
  Num,
  PageHeading,
  Select,
} from "../components/ui";
import { formatearFecha, formatearImporte, signo } from "../lib/format";
import {
  fetchHistorial,
  fetchPortfolios,
  type Historial as HistorialT,
  type Portfolio,
} from "../lib/finance";

export function Historial() {
  const [portfolios, setPortfolios] = useState<Portfolio[] | null>(null);
  const [elegido, setElegido] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
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
      const r = await fetchHistorial(
        elegido,
        desde || undefined,
        hasta || undefined,
      );
      if (r.ok) setDatos(r.data);
    })();
  }, [elegido, desde, hasta]);

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

      <div className="mb-6 flex flex-wrap items-end gap-4">
        {portfolios.length > 1 && (
          <div className="w-56">
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
        {/* Acotar el período no cambia los puntos: cada uno sigue siendo el
            mismo cierre con su misma marca de estimado. Sólo cambia cuántos
            se piden. */}
        <div className="w-40">
          <Field
            label="Desde"
            type="date"
            value={desde}
            onChange={(e) => setDesde(e.target.value)}
          />
        </div>
        <div className="w-40">
          <Field
            label="Hasta"
            type="date"
            value={hasta}
            onChange={(e) => setHasta(e.target.value)}
          />
        </div>
        {(desde || hasta) && (
          <Button
            variant="ghost"
            onClick={() => {
              setDesde("");
              setHasta("");
            }}
          >
            Ver todo
          </Button>
        )}
      </div>

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

          <div className="rounded-xl border border-ink-600 bg-ink-800 p-card">
            <GraficoDeEvolucion puntos={datos.puntos} />
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
