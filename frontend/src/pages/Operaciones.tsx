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
import { FormularioDeOperacion } from "../components/FormularioDeOperacion";
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
  fetchAccounts,
  fetchAssets,
  fetchPortfolios,
  fetchTransactions,
  type FiltroOperaciones,
  type Account,
  type Asset,
  type Portfolio,
  type Transaction,
} from "../lib/finance";

export function Operaciones() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activos, setActivos] = useState<Asset[]>([]);
  const [cuentas, setCuentas] = useState<Account[]>([]);
  const [elegido, setElegido] = useState("");
  const [operaciones, setOperaciones] = useState<Transaction[] | null>(null);
  const [verAnuladas, setVerAnuladas] = useState(false);
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [txType, setTxType] = useState("");
  const [accountFiltro, setAccountFiltro] = useState("");
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(false);

  useEffect(() => {
    void (async () => {
      // El formulario se trae los suyos. Estos son para la tabla: traducen el
      // `asset_id` de cada operación a su símbolo, y para el filtro de cuenta.
      const [p, a, c] = await Promise.all([
        fetchPortfolios(),
        fetchAssets(),
        fetchAccounts(),
      ]);
      if (p.ok) {
        setPortfolios(p.data);
        if (p.data.length > 0) setElegido(p.data[0].id);
      }
      if (a.ok) setActivos(a.data);
      if (c.ok) setCuentas(c.data);
    })();
  }, []);

  async function cargar(portfolioId: string, filtro: FiltroOperaciones) {
    setOperaciones(null);
    const r = await fetchTransactions(portfolioId, filtro);
    if (r.ok) {
      setOperaciones(r.data);
      setError("");
    } else {
      setError(r.error);
      setOperaciones([]);
    }
  }

  const hayFiltro = Boolean(desde || hasta || txType || accountFiltro);

  const filtro: FiltroOperaciones = {
    incluirAnuladas: verAnuladas,
    desde: desde || undefined,
    hasta: hasta || undefined,
    txType: txType || undefined,
    accountId: accountFiltro || undefined,
  };

  useEffect(() => {
    if (elegido) void cargar(elegido, filtro);
    // El filtro se arma en cada render, así que se depende de sus campos y no
    // del objeto: comparar el objeto dispararía la carga en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elegido, verAnuladas, desde, hasta, txType, accountFiltro]);


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
    void cargar(elegido, filtro);
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
        <Button onClick={() => setAbierto((v) => !v)}>
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

      {/* Los filtros se resuelven en el servidor. El período se compara contra
          el día de rueda, no contra el instante: una compra de las 22:30
          pertenece al día en que la hiciste, no al siguiente en UTC. */}
      <div className="mb-6 flex flex-wrap items-end gap-4 border-t border-ink-600 pt-5">
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
        <div className="w-44">
          <Select
            label="Tipo"
            value={txType}
            onChange={(e) => setTxType(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="BUY">Compras</option>
            <option value="SELL">Ventas</option>
            <option value="DEPOSIT">Depósitos</option>
            <option value="WITHDRAWAL">Retiros</option>
            <option value="DIVIDEND">Dividendos</option>
            <option value="FEE">Costos</option>
            <option value="TRANSFER">Transferencias</option>
          </Select>
        </div>
        <div className="w-48">
          <Select
            label="Cuenta"
            value={accountFiltro}
            onChange={(e) => setAccountFiltro(e.target.value)}
            hint="Las posiciones no se filtran por cuenta: son del portfolio."
          >
            <option value="">Todas</option>
            {cuentas.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>
        {hayFiltro && (
          <Button
            variant="ghost"
            onClick={() => {
              setDesde("");
              setHasta("");
              setTxType("");
              setAccountFiltro("");
            }}
          >
            Limpiar filtros
          </Button>
        )}
      </div>

      {abierto && elegido && (
        <div className="mb-8 max-w-3xl rounded-xl border border-ink-600 bg-ink-800 p-card">
          {/* El mismo formulario que usa Cartera. Copiarlo daria dos que
              validan distinto, y el dia que uno cambie el otro seguiria
              andando mal en silencio. */}
          <FormularioDeOperacion
            portfolioId={elegido}
            onRegistrada={() => {
              setAbierto(false);
              void cargar(elegido, filtro);
            }}
          />
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
          title={
            hayFiltro
              ? "No hay operaciones que cumplan el filtro."
              : "No hay operaciones registradas."
          }
          detail={
            hayFiltro
              ? "Ampliá el período o limpiá los filtros."
              : "Registrá tu primera compra. La posición se calcula sola a partir del libro."
          }
        />
      ) : (
        <Tabla
          columnas={[
            { titulo: "Fecha" },
            { titulo: "Tipo" },
            { titulo: "Activo" },
            { titulo: "Cuenta" },
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
                className={`border-b border-ink-600/60 ${anulada ? "text-text-faint" : ""}`}
              >
                <td className="px-4 py-3">{formatearFecha(op.trade_date)}</td>
                <td className="px-4 py-3">
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
                <td className="px-4 py-3 font-medium">{simbolo}</td>
                <td className="px-4 py-3 text-right">
                  <Num>{formatearCantidad(op.quantity)}</Num>
                </td>
                <td className="px-4 py-3 text-right">
                  <Num>{formatearImporte(op.unit_price)}</Num>
                </td>
                <td className="px-4 py-3 text-right">
                  <Num tono="tenue">{formatearImporte(op.commission)}</Num>
                </td>
                <td className="px-4 py-3 text-right">
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
