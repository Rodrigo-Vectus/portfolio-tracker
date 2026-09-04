/**
 * El libro de operaciones.
 *
 * Es la fuente de verdad del sistema: todo lo demás se deriva de acá.
 *
 * Dos cosas que la pantalla hace cumplir y conviene entender:
 *
 * - **La cantidad siempre es positiva.** Comprar o vender se elige en el
 *   selector de tipo. En la planilla anterior una venta era una cantidad
 *   negativa y la columna "Precio Compra" guardaba en realidad el precio de
 *   venta: la columna mentía y nadie podía notarlo mirando una fila.
 * - **Nada se borra.** Una operación mal cargada se anula con un motivo y se
 *   registra la corrección. Anular deja rastro; borrar, no.
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
import { formatearCantidad, formatearFecha, formatearImporte } from "../lib/format";
import {
  anularOperacion,
  crearOperacion,
  fetchAssets,
  fetchPortfolios,
  fetchTransactions,
  type Asset,
  type Portfolio,
  type Transaction,
  type TxType,
} from "../lib/finance";

const TIPOS: { valor: TxType; etiqueta: string }[] = [
  { valor: "BUY", etiqueta: "Compra" },
  { valor: "SELL", etiqueta: "Venta" },
];

function hoyLocal(): string {
  // Formato que espera <input type="datetime-local">. Se manda sin zona y el
  // backend lo interpreta en la zona configurada, no en UTC: una compra de las
  // 22:30 tiene que quedar en la rueda de hoy, no en la de mañana.
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

export function Operaciones() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activos, setActivos] = useState<Asset[]>([]);
  const [elegido, setElegido] = useState("");
  const [operaciones, setOperaciones] = useState<Transaction[] | null>(null);
  const [verAnuladas, setVerAnuladas] = useState(false);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [tipo, setTipo] = useState<TxType>("BUY");
  const [assetId, setAssetId] = useState("");
  const [cantidad, setCantidad] = useState("");
  const [precio, setPrecio] = useState("");
  const [comision, setComision] = useState("0");
  const [cuando, setCuando] = useState(hoyLocal);

  useEffect(() => {
    void (async () => {
      const [p, a] = await Promise.all([fetchPortfolios(), fetchAssets()]);
      if (p.ok) {
        setPortfolios(p.data);
        if (p.data.length > 0) setElegido(p.data[0].id);
      }
      if (a.ok) {
        setActivos(a.data);
        if (a.data.length > 0) setAssetId(a.data[0].id);
      }
    })();
  }, []);

  async function cargar(portfolioId: string, anuladas: boolean) {
    setOperaciones(null);
    const r = await fetchTransactions(portfolioId, anuladas);
    if (r.ok) {
      setOperaciones(r.data);
      setError("");
    } else {
      setError(r.error);
      setOperaciones([]);
    }
  }

  useEffect(() => {
    if (elegido) void cargar(elegido, verAnuladas);
  }, [elegido, verAnuladas]);

  const activo = activos.find((a) => a.id === assetId);

  async function registrar() {
    setGuardando(true);
    setError("");
    const r = await crearOperacion({
      portfolio_id: elegido,
      asset_id: assetId,
      tx_type: tipo,
      quantity: cantidad,
      unit_price: precio,
      price_currency: activo?.currency ?? "ARS",
      commission: comision || "0",
      executed_at: cuando,
    });
    setGuardando(false);

    if (!r.ok) {
      // Un 422 acá no es un error del sistema: es el motor rechazando una
      // operación que no cierra contra la tenencia. El mensaje dice cuál es el
      // problema, porque "operación inválida" no sirve para corregir la carga.
      setError(r.error);
      return;
    }
    setCantidad("");
    setPrecio("");
    setAbierto(false);
    void cargar(elegido, verAnuladas);
  }

  async function anular(id: string) {
    const motivo = window.prompt(
      "¿Por qué se anula? Queda registrado junto con la operación.",
    );
    if (motivo === null) return;
    if (motivo.trim().length < 3) {
      setError("El motivo es obligatorio y tiene que explicar algo.");
      return;
    }
    const r = await anularOperacion(id, motivo.trim());
    if (!r.ok) {
      setError(r.error);
      return;
    }
    setError("");
    void cargar(elegido, verAnuladas);
  }

  if (portfolios.length === 0) {
    return (
      <>
        <PageHeading title="Operaciones" />
        <EmptyState
          title="Necesitás un portfolio antes de cargar operaciones."
          detail="Creá uno en la sección Portfolio."
        />
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="Operaciones"
        subtitle="El registro de compras y ventas. Todo lo demás se calcula a partir de acá."
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
        <Button onClick={() => setAbierto((v) => !v)} disabled={activos.length === 0}>
          {abierto ? "Cancelar" : "Registrar operación"}
        </Button>
        <label className="flex items-center gap-2 pb-2 text-sm text-text-muted">
          <input
            type="checkbox"
            checked={verAnuladas}
            onChange={(e) => setVerAnuladas(e.target.checked)}
          />
          Mostrar anuladas
        </label>
      </div>

      {activos.length === 0 && (
        <div className="mb-6">
          <Nota>
            Para registrar una operación primero tenés que dar de alta el activo en
            la sección Activos.
          </Nota>
        </div>
      )}

      {abierto && (
        <div className="mb-8 max-w-3xl rounded border border-ink-600 bg-ink-800 p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <Select
              label="Tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as TxType)}
            >
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Select
              label="Activo"
              value={assetId}
              onChange={(e) => setAssetId(e.target.value)}
            >
              {activos.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.symbol} — {a.name}
                </option>
              ))}
            </Select>
            <Field
              label="Cuándo"
              type="datetime-local"
              value={cuando}
              onChange={(e) => setCuando(e.target.value)}
            />
            <Field
              label="Cantidad"
              inputMode="decimal"
              value={cantidad}
              onChange={(e) => setCantidad(e.target.value)}
              placeholder="10"
              hint="Siempre positiva. Comprar o vender se elige arriba."
            />
            <Field
              label={`Precio unitario${activo ? ` (${activo.currency})` : ""}`}
              inputMode="decimal"
              value={precio}
              onChange={(e) => setPrecio(e.target.value)}
              placeholder="20960"
            />
            <Field
              label="Comisión"
              inputMode="decimal"
              value={comision}
              onChange={(e) => setComision(e.target.value)}
              hint={
                tipo === "BUY"
                  ? "Suma al costo de la compra."
                  : "Resta de lo que recibís."
              }
            />
          </div>
          <div className="mt-5">
            <Button
              onClick={() => void registrar()}
              disabled={guardando || !cantidad || !precio || !assetId}
            >
              {guardando ? "Registrando…" : "Registrar operación"}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      {operaciones === null ? (
        <p className="text-text-muted">Cargando…</p>
      ) : operaciones.length === 0 ? (
        <EmptyState
          title="No hay operaciones registradas."
          detail="Registrá tu primera compra. La posición se calcula sola a partir del libro."
        />
      ) : (
        <Tabla
          columnas={[
            { titulo: "Fecha" },
            { titulo: "Tipo" },
            { titulo: "Activo" },
            { titulo: "Cantidad", alineacion: "derecha" },
            { titulo: "Precio", alineacion: "derecha" },
            { titulo: "Comisión", alineacion: "derecha" },
            { titulo: "", alineacion: "derecha" },
          ]}
        >
          {operaciones.map((op) => {
            const anulada = op.status === "VOIDED";
            const simbolo =
              activos.find((a) => a.id === op.asset_id)?.symbol ?? "—";
            return (
              <tr
                key={op.id}
                className={`border-b border-ink-700 ${anulada ? "text-text-faint" : ""}`}
              >
                <td className="px-3 py-2.5 first:pl-0 last:pr-0">{formatearFecha(op.trade_date)}</td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0">
                  {op.tx_type === "BUY" ? "Compra" : "Venta"}
                  {anulada && (
                    <span
                      className="ml-2 text-micro text-stale"
                      title={op.voided_reason ?? ""}
                    >
                      anulada
                    </span>
                  )}
                </td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 font-medium">{simbolo}</td>
                <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                  <Num>{formatearCantidad(op.quantity)}</Num>
                </td>
                <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                  <Num>{formatearImporte(op.unit_price)}</Num>
                </td>
                <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                  <Num tono="tenue">{formatearImporte(op.commission)}</Num>
                </td>
                <td className="px-3 py-2.5 text-right first:pl-0 last:pr-0">
                  {!anulada && (
                    <Button variant="ghost" onClick={() => void anular(op.id)}>
                      Anular
                    </Button>
                  )}
                </td>
              </tr>
            );
          })}
        </Tabla>
      )}

      {operaciones !== null && operaciones.length > 0 && (
        <div className="mt-8">
          <Nota>
            Una operación no se edita ni se borra: se anula con un motivo y se
            registra la corrección. Al anular se recalculan los lotes y la
            posición. Si anular dejara una venta sin respaldo, el sistema no lo
            permite y explica por qué.
          </Nota>
        </div>
      )}
    </>
  );
}
