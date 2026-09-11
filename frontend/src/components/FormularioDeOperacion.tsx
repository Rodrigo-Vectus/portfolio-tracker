/**
 * Alta de una operación.
 *
 * Vive en un componente propio porque se usa desde dos lugares: la pantalla de
 * Operaciones y el panel de Cartera. Copiarlo daría dos formularios que
 * validan distinto y mandan campos distintos, y el día que uno cambie el otro
 * va a seguir andando mal en silencio.
 *
 * Se trae sus propios activos y cuentas: quien lo usa no tiene que saber qué
 * necesita adentro. Al registrar avisa con `onRegistrada` y el llamador decide
 * qué recargar.
 */

import { useEffect, useState } from "react";
import { SelectorDeActivo } from "./SelectorDeActivo";
import { Button, ErrorNote, Field, Select } from "./ui";
import {
  crearOperacion,
  fetchAccounts,
  fetchAssets,
  type Account,
  type Asset,
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

export function FormularioDeOperacion({
  portfolioId,
  tipoInicial = "BUY",
  activoInicial,
  onRegistrada,
}: {
  portfolioId: string;
  tipoInicial?: TxType;
  /** Preselecciona un activo: sirve para «vender» desde una fila de la tabla. */
  activoInicial?: string;
  onRegistrada: () => void;
}) {
  const [activos, setActivos] = useState<Asset[]>([]);
  const [cuentas, setCuentas] = useState<Account[]>([]);
  const [tipo, setTipo] = useState<TxType>(tipoInicial);
  const [assetId, setAssetId] = useState(activoInicial ?? "");
  const [accountId, setAccountId] = useState("");
  const [cantidad, setCantidad] = useState("");
  const [precio, setPrecio] = useState("");
  const [comision, setComision] = useState("");
  const [cuando, setCuando] = useState(hoyLocal);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    void fetchAssets().then((r) => {
      if (!r.ok) return;
      setActivos(r.data);
      if (!activoInicial && r.data.length > 0) setAssetId((a) => a || r.data[0].id);
    });
    void fetchAccounts().then((r) => {
      if (r.ok) setCuentas(r.data);
    });
  }, [activoInicial]);

  const activo = activos.find((a) => a.id === assetId);

  async function registrar() {
    setGuardando(true);
    setError("");
    const r = await crearOperacion({
      portfolio_id: portfolioId,
      asset_id: assetId,
      // Sin cuenta la operación se registra igual: la columna es opcional. Lo
      // que se pierde es poder distinguir después qué está en el broker y qué
      // en un exchange, y eso no se puede reconstruir.
      account_id: accountId || null,
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
    setComision("");
    onRegistrada();
  }

  return (
    <div>
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
        <SelectorDeActivo
          activos={activos}
          valor={assetId}
          onElegir={setAssetId}
          onCreado={(a) => setActivos((prev) => [...prev, a])}
        />
        <Field
          label="Cuándo"
          type="datetime-local"
          value={cuando}
          onChange={(e) => setCuando(e.target.value)}
        />
        <Select
          label="Cuenta"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
        >
          <option value="">Sin especificar</option>
          {cuentas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <Field
          label="Cantidad"
          inputMode="decimal"
          value={cantidad}
          onChange={(e) => setCantidad(e.target.value)}
          placeholder="10"
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

      {error && (
        <div className="mt-4">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      <div className="mt-5">
        <Button
          onClick={() => void registrar()}
          disabled={guardando || !cantidad || !precio || !assetId}
        >
          {guardando ? "Registrando…" : "Registrar operación"}
        </Button>
      </div>
    </div>
  );
}
