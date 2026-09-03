/**
 * Estado de los servicios.
 *
 * Era la pantalla de inicio en la fase 0. Ahora vive detrás del login, como
 * herramienta de diagnóstico: sigue siendo el lugar donde mirar cuando algo
 * no responde.
 */

import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { PageHeading } from "../components/ui";

interface Ready {
  status: "ok" | "degraded";
  checks: Record<string, { status: "ok" | "error"; detail: string }>;
}

const ETIQUETAS: Record<string, string> = {
  postgres: "Base de datos",
  redis: "Caché y cola de tareas",
  migrations: "Esquema de la base",
};

export function Estado() {
  const [ready, setReady] = useState<Ready | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    const r = await api.get<Ready>("/health/ready");
    if (r.ok) {
      setReady(r.data);
      setFailure(null);
    } else {
      setFailure(r.error);
    }
    setCheckedAt(new Date());
  }, []);

  useEffect(() => {
    void refresh();
    const id = setInterval(() => void refresh(), 15_000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <>
      <PageHeading
        title="Estado del sistema"
        subtitle="Si algo no responde, acá se ve cuál de las piezas falló."
      />

      <ul className="divide-y divide-ink-600">
        <Fila
          label="API"
          state={failure ? "error" : ready ? "ok" : "unknown"}
          detail={failure ?? "Responde"}
        />
        {(ready ? Object.entries(ready.checks) : []).map(([key, check]) => (
          <Fila
            key={key}
            label={ETIQUETAS[key] ?? key}
            state={check.status}
            detail={check.detail}
          />
        ))}
      </ul>

      <p className="mt-8 text-sm text-text-faint">
        {checkedAt
          ? `Verificado a las ${checkedAt.toLocaleTimeString("es-AR")} · se actualiza cada 15 s`
          : "Verificando..."}
      </p>
    </>
  );
}

function Fila({
  label,
  state,
  detail,
}: {
  label: string;
  state: "ok" | "error" | "unknown";
  detail: string;
}) {
  const bar = state === "ok" ? "bg-gain" : state === "error" ? "bg-loss" : "bg-stale";
  const word = state === "ok" ? "En línea" : state === "error" ? "Sin respuesta" : "Consultando";

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
