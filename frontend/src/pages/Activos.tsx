/**
 * Catálogo de activos.
 *
 * El catálogo vive separado del libro de operaciones a propósito. En la
 * planilla anterior vivía adentro, y el resultado fue que MELI figuraba con
 * dos sectores distintos según la fila y Microsoft estaba escrito "MICROSFT"
 * en las doce filas. Cuando el catálogo es una columna repetida, cada fila es
 * una oportunidad de contradecir a las demás.
 */

import { useEffect, useState } from "react";
import {
  Button,
  ErrorNote,
  EmptyState,
  Field,
  Nota,
  PageHeading,
  Select,
  Tabla,
} from "../components/ui";
import { crearAsset, fetchAssets, type Asset, type AssetType } from "../lib/finance";

const TIPOS: { valor: AssetType; etiqueta: string }[] = [
  { valor: "CEDEAR", etiqueta: "CEDEAR" },
  { valor: "CRYPTO", etiqueta: "Criptomoneda" },
  { valor: "CASH", etiqueta: "Efectivo" },
];

export function Activos() {
  const [activos, setActivos] = useState<Asset[] | null>(null);
  const [error, setError] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [guardando, setGuardando] = useState(false);

  const [symbol, setSymbol] = useState("");
  const [name, setName] = useState("");
  const [tipo, setTipo] = useState<AssetType>("CEDEAR");
  const [moneda, setMoneda] = useState("ARS");
  const [mercado, setMercado] = useState("BYMA");
  const [sector, setSector] = useState("");

  async function cargar() {
    const r = await fetchAssets();
    if (r.ok) {
      setActivos(r.data);
      setError("");
    } else {
      setError(r.error);
    }
  }

  useEffect(() => {
    void cargar();
  }, []);

  async function guardar() {
    setGuardando(true);
    setError("");
    const r = await crearAsset({
      symbol,
      name,
      asset_type: tipo,
      currency: moneda,
      market: mercado || null,
      sector: sector || null,
    });
    setGuardando(false);

    if (!r.ok) {
      setError(r.error);
      return;
    }
    setSymbol("");
    setName("");
    setSector("");
    setAbierto(false);
    void cargar();
  }

  return (
    <>
      <PageHeading
        title="Activos"
        subtitle="Los instrumentos con los que operás. Un mismo símbolo puede existir en más de un mercado."
      />

      <div className="mb-6 flex items-center gap-3">
        <Button onClick={() => setAbierto((v) => !v)}>
          {abierto ? "Cancelar" : "Agregar activo"}
        </Button>
      </div>

      {abierto && (
        <div className="mb-8 max-w-2xl rounded border border-ink-600 bg-ink-800 p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field
              label="Símbolo"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
              placeholder="AAPL"
              hint="Como cotiza en su mercado."
            />
            <Field
              label="Nombre"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="CEDEAR de Apple"
            />
            <Select
              label="Tipo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value as AssetType)}
            >
              {TIPOS.map((t) => (
                <option key={t.valor} value={t.valor}>
                  {t.etiqueta}
                </option>
              ))}
            </Select>
            <Field
              label="Moneda de cotización"
              value={moneda}
              onChange={(e) => setMoneda(e.target.value.toUpperCase())}
              hint="Un CEDEAR cotiza en ARS aunque lo pienses en dólares."
            />
            <Field
              label="Mercado"
              value={mercado}
              onChange={(e) => setMercado(e.target.value.toUpperCase())}
              placeholder="BYMA"
            />
            <Field
              label="Sector"
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              placeholder="Tecnología"
            />
          </div>
          <div className="mt-5">
            <Button onClick={() => void guardar()} disabled={guardando || !symbol || !name}>
              {guardando ? "Guardando…" : "Guardar activo"}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-6">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      {activos === null ? (
        <p className="text-text-muted">Cargando…</p>
      ) : activos.length === 0 ? (
        <EmptyState
          title="El catálogo está vacío."
          detail="Agregá los activos con los que operás. Después vas a poder registrar compras y ventas sobre ellos."
        />
      ) : (
        <>
          <Tabla
            columnas={[
              { titulo: "Símbolo" },
              { titulo: "Nombre" },
              { titulo: "Tipo" },
              { titulo: "Mercado" },
              { titulo: "Moneda" },
              { titulo: "Sector" },
            ]}
          >
            {activos.map((a) => (
              <tr key={a.id} className="border-b border-ink-700">
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 font-medium">{a.symbol}</td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 text-text-muted">{a.name}</td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 text-text-muted">{a.asset_type}</td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 text-text-muted">{a.market ?? "—"}</td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 text-text-muted">{a.currency}</td>
                <td className="px-3 py-2.5 first:pl-0 last:pr-0 text-text-muted">{a.sector ?? "—"}</td>
              </tr>
            ))}
          </Tabla>

          <div className="mt-6">
            <Nota>
              El catálogo todavía no tiene cotizaciones ni ratios de CEDEAR. Las
              cotizaciones llegan en la fase 3.
            </Nota>
          </div>
        </>
      )}
    </>
  );
}
