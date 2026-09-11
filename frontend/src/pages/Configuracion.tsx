import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { api } from "../lib/api";
import { Button, ErrorNote, Nota, PageHeading, Select } from "../components/ui";
import {
  fetchPreferencias,
  guardarPreferencias,
  type Preferencias,
} from "../lib/finance";

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
        <h2 className="mb-3 text-sm font-medium text-text-muted">Catálogo</h2>
        <p className="mb-3 max-w-prose text-sm text-text-muted">
          Los activos y las cuentas se crean solos cuando cargás una operación.
          Estas pantallas son para corregir lo que ya existe: el sector, el
          factor de precio de un bono o desactivar algo que dejaste de operar.
        </p>
        <div className="flex flex-wrap gap-4">
          <Link
            to="/activos"
            className="text-sm text-brand underline-offset-4 hover:underline"
          >
            Activos
          </Link>
          <Link
            to="/cuentas"
            className="text-sm text-brand underline-offset-4 hover:underline"
          >
            Cuentas
          </Link>
        </div>
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
        <h2 className="mb-3 text-sm font-medium text-text-muted">
          Preferencias personales
        </h2>
        <MonedaDeVisualizacion />
      </section>
    </>
  );
}

/**
 * Elección de la moneda en la que se muestra la cartera.
 *
 * Dos opciones y no tres: dólares, o la moneda original de cada activo. No
 * hay "pesos" porque la conversión que el sistema sabe hacer produce dólares
 * y sólo dólares —la serie de tipo de cambio es USD/ARS—, y ofrecer una
 * moneda que después no se puede cumplir es prometer un número que no existe.
 */
function MonedaDeVisualizacion() {
  const [prefs, setPrefs] = useState<Preferencias | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const [guardado, setGuardado] = useState(false);

  useEffect(() => {
    void fetchPreferencias().then((r) => {
      if (r.ok) setPrefs(r.data);
      else setError(r.error);
    });
  }, []);

  async function cambiar(valor: string) {
    setGuardando(true);
    setError("");
    setGuardado(false);
    const r = await guardarPreferencias(valor === "" ? null : valor);
    if (r.ok) {
      setPrefs(r.data);
      setGuardado(true);
    } else {
      setError(r.error);
    }
    setGuardando(false);
  }

  if (prefs === null) {
    return <p className="text-sm text-text-faint">Consultando...</p>;
  }

  return (
    <div className="max-w-md">
      <div className="w-64">
        <Select
          label="Moneda de visualización"
          value={prefs.display_currency ?? ""}
          disabled={guardando}
          onChange={(e) => void cambiar(e.target.value)}
        >
          <option value="">Moneda original de cada activo</option>
          <option value="USD">Dólares</option>
        </Select>
      </div>

      {error && (
        <div className="mt-3">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}
      {guardado && !error && (
        <p className="mt-3 text-micro text-text-faint">Preferencia guardada.</p>
      )}

      <Nota>
        En dólares, el costo de cada compra se convierte con el tipo de cambio
        de su propia fecha y el valor actual con el de hoy. Esa asimetría es a
        propósito: un costo histórico no cambia porque se movió el dólar esta
        mañana. Convertir las dos puntas con el mismo tipo de cambio daría un
        resultado idéntico al de pesos, que era uno de los errores de la
        planilla.
      </Nota>

      {prefs.display_currency !== null && (
        <Button
          variant="ghost"
          className="mt-3"
          disabled={guardando}
          onClick={() => void cambiar("")}
        >
          Ver cada activo en su moneda
        </Button>
      )}
    </div>
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
