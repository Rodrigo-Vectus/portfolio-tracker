/**
 * Caja: la plata que entró, salió y quedó sin invertir.
 *
 * Sin esta pantalla el sistema sabía qué comprabas pero no de dónde salía el
 * dinero ni cuánto quedaba disponible.
 *
 * El saldo no se guarda en ningún lado: se calcula desde el libro, igual que
 * las posiciones. Por eso el desglose siempre cierra con el total.
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
import { formatearFecha, formatearImporte, signo } from "../lib/format";
import {
  crearMovimiento,
  fetchPortfolios,
  fetchSaldo,
  type Portfolio,
  type Saldo,
  type TxType,
} from "../lib/finance";

const TIPOS: { valor: TxType; etiqueta: string; ayuda: string }[] = [
  { valor: "DEPOSIT", etiqueta: "Depósito", ayuda: "Plata que entra a la cuenta." },
  { valor: "WITHDRAWAL", etiqueta: "Retiro", ayuda: "Plata que sacás." },
  { valor: "DIVIDEND", etiqueta: "Dividendo", ayuda: "Cobro por tenencia." },
  {
    valor: "FEE",
    etiqueta: "Costo de cuenta",
    ayuda: "Mantenimiento u otros costos no atribuibles a un activo.",
  },
];

function ahoraLocal(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function Dato({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <p className="text-sm text-text-muted">{etiqueta}</p>
      <p className="mt-0.5">
        <Num>{formatearImporte(valor)}</Num>
      </p>
    </div>
  );
}

export function Caja() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [elegido, setElegido] = useState("");
  const [moneda, setMoneda] = useState("ARS");
  const [saldo, setSaldo] = useState<Saldo | null>(null);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [tipo, setTipo] = useState<TxType>("DEPOSIT");
  const [monto, setMonto] = useState("");
  const [cuando, setCuando] = useState(ahoraLocal);

  useEffect(() => {
    void (async () => {
      const r = await fetchPortfolios();
      if (r.ok) {
        setPortfolios(r.data);
        if (r.data.length > 0) setElegido(r.data[0].id);
      }
    })();
  }, []);

  async function cargar() {
    if (!elegido) return;
    setSaldo(null);
    const r = await fetchSaldo(elegido, moneda);
    if (r.ok) {
      setSaldo(r.data);
      setError("");
    } else {
      setError(r.error);
    }
  }

  useEffect(() => {
    void cargar();
  }, [elegido, moneda]);

  async function registrar() {
    setGuardando(true);
    setError("");
    const r = await crearMovimiento({
      portfolio_id: elegido,
      tx_type: tipo,
      monto,
      currency: moneda,
      executed_at: cuando,
    });
    setGuardando(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    setMonto("");
    setAbierto(false);
    void cargar();
  }

  if (portfolios.length === 0) {
    return (
      <>
        <PageHeading title="Caja" />
        <EmptyState
          title="Necesitás un portfolio."
          detail="Creá uno en la sección Portfolio para empezar a registrar movimientos."
        />
      </>
    );
  }

  const ayuda = TIPOS.find((t) => t.valor === tipo)?.ayuda;

  return (
    <>
      <PageHeading
        title="Caja"
        subtitle="La plata que entró, salió y quedó sin invertir. Se calcula desde el libro."
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
        <div className="w-32">
          <Select
            label="Moneda"
            value={moneda}
            onChange={(e) => setMoneda(e.target.value)}
          >
            <option value="ARS">ARS</option>
            <option value="USD">USD</option>
            <option value="USDT">USDT</option>
          </Select>
        </div>
        <Button onClick={() => setAbierto((v) => !v)}>
          {abierto ? "Cancelar" : "Registrar movimiento"}
        </Button>
      </div>

      {abierto && (
        <div className="mb-8 max-w-2xl rounded border border-ink-600 bg-ink-800 p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Select
              label="Tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TxType)}
              hint={ayuda}
            >
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Field
              label={`Monto (${moneda})`}
              inputMode="decimal"
              value={monto}
              onChange={(e) => setMonto(e.target.value)}
              placeholder="100000"
            />
            <Field
              label="Cuándo"
              type="datetime-local"
              value={cuando}
              onChange={(e) => setCuando(e.target.value)}
            />
          </div>
          <div className="mt-5">
            <Button onClick={() => void registrar()} disabled={guardando || !monto}>
              {guardando ? "Registrando…" : "Registrar"}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      {saldo === null ? (
        <p className="text-text-muted">Cargando…</p>
      ) : (
        <>
          <div className="mb-8 rounded border border-ink-600 bg-ink-800 p-5">
            <p className="text-sm text-text-muted">Disponible en {saldo.currency}</p>
            <p className="mt-1 text-2xl">
              <Num
                tono={
                  saldo.es_negativo
                    ? "negativo"
                    : signo(saldo.saldo) === "cero"
                      ? "tenue"
                      : "neutro"
                }
              >
                {formatearImporte(saldo.saldo)}
              </Num>
            </p>
            {saldo.es_negativo && (
              <p className="mt-2 max-w-prose text-sm text-stale">
                El saldo es negativo: hay compras registradas sin el depósito que
                las financió. No es un error del sistema, es una operación que
                falta cargar. Se muestra en vez de impedirse, porque el libro
                registra lo que pasó.
              </p>
            )}
          </div>

          <div className="mb-8 grid gap-5 sm:grid-cols-3 lg:grid-cols-6">
            <Dato etiqueta="Depósitos" valor={saldo.depositos} />
            <Dato etiqueta="Retiros" valor={saldo.retiros} />
            <Dato etiqueta="Invertido" valor={saldo.invertido} />
            <Dato etiqueta="Recuperado" valor={saldo.recuperado} />
            <Dato etiqueta="Dividendos" valor={saldo.dividendos} />
            <Dato etiqueta="Aporte neto" valor={saldo.aporte_neto} />
          </div>

          {saldo.movimientos.length === 0 ? (
            <EmptyState
              title="No hay movimientos de efectivo."
              detail="Registrá tu primer depósito para empezar a llevar el saldo."
            />
          ) : (
            <Tabla
              columnas={[
                { titulo: "Fecha" },
                { titulo: "Movimiento" },
                { titulo: "Monto", alineacion: "derecha" },
                { titulo: "Saldo", alineacion: "derecha" },
              ]}
            >
              {saldo.movimientos
                .slice()
                .reverse()
                .map((m) => (
                  <tr key={m.tx_id} className="border-b border-ink-700">
                    <td className="px-3 py-2.5 first:pl-0 last:pr-0">
                      {formatearFecha(m.fecha.slice(0, 10))}
                    </td>
                    <td className="px-3 py-2.5 text-text-muted first:pl-0 last:pr-0">
                      {m.descripcion}
                    </td>
                    <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                      <Num
                        tono={
                          signo(m.monto) === "positivo"
                            ? "positivo"
                            : signo(m.monto) === "negativo"
                              ? "negativo"
                              : "tenue"
                        }
                      >
                        {formatearImporte(m.monto)}
                      </Num>
                    </td>
                    <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                      <Num tono="tenue">{formatearImporte(m.saldo_posterior)}</Num>
                    </td>
                  </tr>
                ))}
            </Tabla>
          )}

          <div className="mt-8">
            <Nota>
              Cada moneda lleva su propio saldo. Sumar pesos y dólares
              requeriría convertir, y esa conversión necesita un tipo de cambio
              con su fecha: se hace explícita cuando exista la pantalla de
              rendimiento, no acá por atrás.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
