/**
 * Cuentas: dónde está depositado cada activo.
 *
 * Reemplaza el campo `broker` de texto libre de la especificación original.
 * Texto libre garantiza "IOL", "iol" e "InvertirOnline" como tres brokers
 * distintos, que es la misma suciedad que traía la planilla en la columna de
 * sector.
 *
 * Importa más de lo que parece: sin cuentas no se puede distinguir qué está en
 * el broker y qué en un exchange, y el importador del historial va a necesitar
 * saber dónde ocurrió cada operación.
 */

import { useEffect, useState } from "react";
import {
  Button,
  EmptyState,
  ErrorNote,
  Field,
  Nota,
  PageHeading,
  Select,
  Tabla,
} from "../components/ui";
import {
  crearAccount,
  fetchAccounts,
  type Account,
  type AccountType,
} from "../lib/finance";

const TIPOS: { valor: AccountType; etiqueta: string; ayuda: string }[] = [
  { valor: "BROKER", etiqueta: "Broker", ayuda: "IOL, por ejemplo." },
  { valor: "EXCHANGE", etiqueta: "Exchange", ayuda: "Binance, BingX." },
  { valor: "WALLET", etiqueta: "Billetera", ayuda: "Una wallet propia." },
];

export function Cuentas() {
  const [cuentas, setCuentas] = useState<Account[] | null>(null);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<AccountType>("BROKER");
  const [moneda, setMoneda] = useState("ARS");

  async function cargar() {
    const r = await fetchAccounts();
    if (r.ok) {
      setCuentas(r.data);
      setError("");
    } else {
      setError(r.error);
      setCuentas([]);
    }
  }

  useEffect(() => {
    void cargar();
  }, []);

  async function guardar() {
    setGuardando(true);
    setError("");
    const r = await crearAccount({
      name: nombre,
      account_type: tipo,
      default_currency: moneda,
    });
    setGuardando(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    setNombre("");
    setAbierto(false);
    void cargar();
  }

  const ayuda = TIPOS.find((t) => t.valor === tipo)?.ayuda;

  return (
    <>
      <PageHeading
        title="Cuentas"
        subtitle="Dónde está depositado cada activo. Cada operación se registra contra una cuenta."
      />

      <div className="mb-6">
        <Button onClick={() => setAbierto((v) => !v)}>
          {abierto ? "Cancelar" : "Agregar cuenta"}
        </Button>
      </div>

      {abierto && (
        <div className="mb-8 max-w-2xl rounded border border-ink-600 bg-ink-800 p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Field
              label="Nombre"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              placeholder="IOL"
              hint="Como lo llamás vos. Se usa siempre igual."
            />
            <Select
              label="Tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as AccountType)}
              hint={ayuda}
            >
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Field
              label="Moneda habitual"
              value={moneda}
              onChange={(e) => setMoneda(e.target.value.toUpperCase())}
            />
          </div>
          <div className="mt-5">
            <Button onClick={() => void guardar()} disabled={guardando || !nombre}>
              {guardando ? "Guardando…" : "Guardar cuenta"}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      {cuentas === null ? (
        <p className="text-text-muted">Cargando…</p>
      ) : cuentas.length === 0 ? (
        <EmptyState
          title="No tenés cuentas cargadas."
          detail="Agregá el broker o el exchange donde operás. Después vas a poder indicar en cada operación dónde ocurrió."
        />
      ) : (
        <>
          <Tabla
            columnas={[
              { titulo: "Nombre" },
              { titulo: "Tipo" },
              { titulo: "Moneda" },
              { titulo: "Estado" },
            ]}
          >
            {cuentas.map((c) => (
              <tr key={c.id} className="border-b border-ink-700">
                <td className="px-3 py-2.5 font-medium first:pl-0 last:pr-0">
                  {c.name}
                </td>
                <td className="px-3 py-2.5 text-text-muted first:pl-0 last:pr-0">
                  {TIPOS.find((t) => t.valor === c.account_type)?.etiqueta ??
                    c.account_type}
                </td>
                <td className="px-3 py-2.5 text-text-muted first:pl-0 last:pr-0">
                  {c.default_currency}
                </td>
                <td className="px-3 py-2.5 text-text-muted first:pl-0 last:pr-0">
                  {c.is_active ? "Activa" : "Inactiva"}
                </td>
              </tr>
            ))}
          </Tabla>

          <div className="mt-8">
            <Nota>
              Las cuentas no se borran: se desactivan, porque hay operaciones
              históricas que las referencian. La desactivación todavía no está
              en la interfaz.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
