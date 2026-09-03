import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import { EmptyState, PageHeading } from "../components/ui";

interface Meta {
  version: string;
  environment: string;
  phase: string;
  defaults: Record<string, string>;
}

const ETIQUETAS: Record<string, string> = {
  display_currency: "Moneda de visualización",
  fx_source_equity: "Dólar para CEDEARs",
  fx_source_crypto: "Dólar para cripto",
  cost_basis_method: "Método de costo",
  timezone: "Zona horaria",
};

export function Configuracion() {
  const { user } = useAuth();
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    void api.get<Meta>("/meta").then((r) => {
      if (r.ok) setMeta(r.data);
    });
  }, []);

  return (
    <>
      <PageHeading title="Configuración" subtitle="Tu cuenta y las preferencias del sistema." />

      <section className="mb-10">
        <h2 className="mb-3 text-sm font-medium text-text-muted">Cuenta</h2>
        <dl className="max-w-md space-y-2 text-sm">
          <Par k="Nombre" v={user?.name ?? "—"} />
          <Par k="Email" v={user?.email ?? "—"} />
          <Par k="Rol" v={user?.role === "ADMIN" ? "Administrador" : "Usuario"} />
        </dl>
        <Link
          to="/cambiar-contrasena"
          className="mt-4 inline-block text-sm text-brand underline-offset-4 hover:underline"
        >
          Cambiar contraseña
        </Link>
      </section>

      <section className="mb-10">
        <h2 className="mb-3 text-sm font-medium text-text-muted">Valores del sistema</h2>
        {meta ? (
          <dl className="max-w-md space-y-2 text-sm">
            {Object.entries(meta.defaults).map(([k, v]) => (
              <Par key={k} k={ETIQUETAS[k] ?? k} v={v} />
            ))}
            <Par k="Versión" v={meta.version} />
            <Par k="Fase" v={meta.phase} />
          </dl>
        ) : (
          <p className="text-sm text-text-faint">Consultando...</p>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-muted">Preferencias personales</h2>
        <EmptyState
          title="Todavía no son editables."
          detail="Elegir tu propia moneda de visualización y fuente de precios requiere que el motor de cotizaciones exista. Se habilita en la fase 3."
        />
      </section>
    </>
  );
}

function Par({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-6 border-b border-ink-600/60 py-1.5">
      <dt className="text-text-muted">{k}</dt>
      <dd className="num">{v}</dd>
    </div>
  );
}
