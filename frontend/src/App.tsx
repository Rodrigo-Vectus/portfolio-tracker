/**
 * Pantalla de estado del sistema (Fase 0).
 *
 * No es el dashboard: es la verificacion de que la infraestructura responde.
 * Muestra datos reales del backend, nunca valores simulados. Si un servicio
 * no contesta, se dice; no se rellena con un "ok" optimista.
 */

import { useCallback, useEffect, useState } from "react";
import { apiGet, type MetaResponse, type ReadyResponse } from "./lib/api";

const SERVICE_LABELS: Record<string, string> = {
  postgres: "Base de datos",
  redis: "Cache y cola de tareas",
  migrations: "Esquema de la base",
};

function StatusRow({
  label,
  state,
  detail,
}: {
  label: string;
  state: "ok" | "error" | "unknown";
  detail: string;
}) {
  const bar =
    state === "ok" ? "bg-gain" : state === "error" ? "bg-loss" : "bg-stale";
  const word =
    state === "ok" ? "En linea" : state === "error" ? "Sin respuesta" : "Consultando";

  return (
    <li className="flex gap-4 py-4">
      <span className={`w-[3px] shrink-0 rounded-full ${bar}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-4">
          <span className="font-medium">{label}</span>
          <span className="text-sm text-text-muted">{word}</span>
        </div>
        <p className="mt-1 truncate text-sm text-text-faint" title={detail}>
          {detail}
        </p>
      </div>
    </li>
  );
}

export default function App() {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    const [r, m] = await Promise.all([
      apiGet<ReadyResponse>("/health/ready"),
      apiGet<MetaResponse>("/meta"),
    ]);
    if (r.ok) setReady(r.data);
    if (m.ok) setMeta(m.data);
    setFailure(r.ok ? null : r.error);
    setCheckedAt(new Date());
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 10_000);
    return () => clearInterval(id);
  }, [refresh]);

  const services = ready
    ? Object.entries(ready.checks)
    : Object.keys(SERVICE_LABELS).map((k) => [k, null] as const);

  return (
    <main className="mx-auto flex min-h-full max-w-2xl flex-col justify-center px-6 py-16">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio Tracker</h1>
        <p className="mt-2 max-w-prose text-text-muted">
          La infraestructura esta levantada. Todavia no hay operaciones cargadas
          ni cotizaciones: eso llega en las fases 2 y 3.
        </p>
      </header>

      <section className="mt-10" aria-labelledby="servicios">
        <h2 id="servicios" className="text-sm font-medium text-text-muted">
          Servicios
        </h2>
        <ul className="mt-2 divide-y divide-ink-600">
          <StatusRow
            label="API"
            state={failure ? "error" : ready ? "ok" : "unknown"}
            detail={failure ?? `${meta?.name ?? "—"} v${meta?.version ?? "—"}`}
          />
          {services.map(([key, check]) => (
            <StatusRow
              key={key}
              label={SERVICE_LABELS[key] ?? key}
              state={check ? check.status : "unknown"}
              detail={check ? check.detail : "Sin datos todavia"}
            />
          ))}
        </ul>
      </section>

      {meta && (
        <section className="mt-10" aria-labelledby="config">
          <h2 id="config" className="text-sm font-medium text-text-muted">
            Configuracion de dominio
          </h2>
          <dl className="mt-3 grid grid-cols-1 gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            <Pair k="Moneda de visualizacion" v={meta.defaults.display_currency} />
            <Pair k="Dolar para CEDEARs" v={meta.defaults.fx_source_equity} />
            <Pair k="Dolar para cripto" v={meta.defaults.fx_source_crypto} />
            <Pair k="Metodo de costo" v={meta.defaults.cost_basis_method} />
            <Pair k="Zona horaria" v={meta.defaults.timezone} />
            <Pair k="Fase" v={meta.phase} />
          </dl>
        </section>
      )}

      <footer className="mt-12 text-sm text-text-faint">
        {checkedAt
          ? `Verificado a las ${checkedAt.toLocaleTimeString("es-AR")} · se actualiza cada 10 s`
          : "Verificando..."}
      </footer>
    </main>
  );
}

function Pair({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-ink-600/60 py-1.5">
      <dt className="text-text-muted">{k}</dt>
      <dd className="num text-text">{v}</dd>
    </div>
  );
}
