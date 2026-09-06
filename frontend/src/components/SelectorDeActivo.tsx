/**
 * Selector de activo con búsqueda y alta en el momento.
 *
 * Reemplaza un `<select>` que sólo listaba lo ya cargado. El problema con eso
 * no era estético: obligaba a abandonar la carga de una operación, ir a otra
 * pantalla, dar de alta el activo y volver a empezar. Con un boleto en la
 * mano, ese viaje es exactamente donde se pierde el hilo.
 *
 * Acá se escribe el símbolo. Si existe, se filtra; si no, se ofrece crearlo
 * sin salir de la pantalla.
 *
 * El alta rápida completa el resto con valores razonables para el caso más
 * común (un CEDEAR en pesos de BYMA) y deja editarlos. No los adivina en
 * silencio: quedan a la vista antes de guardar.
 */

import { useEffect, useRef, useState } from "react";
import { Button, ErrorNote, Field, Select } from "./ui";
import { crearAsset, type Asset, type AssetType } from "../lib/finance";

const TIPOS: { valor: AssetType; etiqueta: string }[] = [
  { valor: "CEDEAR", etiqueta: "CEDEAR" },
  { valor: "BOND", etiqueta: "Bono" },
  { valor: "CRYPTO", etiqueta: "Criptomoneda" },
  { valor: "CASH", etiqueta: "Efectivo" },
];

/** Valores por defecto del caso más común. Visibles y editables. */
const SUGERENCIA: Record<AssetType, { moneda: string; mercado: string }> = {
  CEDEAR: { moneda: "ARS", mercado: "BYMA" },
  BOND: { moneda: "ARS", mercado: "BYMA" },
  CRYPTO: { moneda: "USDT", mercado: "" },
  CASH: { moneda: "ARS", mercado: "" },
};

export function SelectorDeActivo({
  activos,
  valor,
  onElegir,
  onCreado,
}: {
  activos: Asset[];
  valor: string;
  onElegir: (id: string) => void;
  onCreado: (a: Asset) => void;
}) {
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [creando, setCreando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");
  const contenedor = useRef<HTMLDivElement>(null);

  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState<AssetType>("CEDEAR");
  const [moneda, setMoneda] = useState("ARS");
  const [mercado, setMercado] = useState("BYMA");

  const elegido = activos.find((a) => a.id === valor);

  // Cerrar al hacer clic afuera: sin esto la lista queda flotando sobre el
  // resto del formulario y tapa los campos siguientes.
  useEffect(() => {
    function afuera(e: MouseEvent) {
      if (!contenedor.current?.contains(e.target as Node)) setAbierto(false);
    }
    document.addEventListener("mousedown", afuera);
    return () => document.removeEventListener("mousedown", afuera);
  }, []);

  const consulta = texto.trim().toUpperCase();
  const coincidencias = consulta
    ? activos.filter(
        (a) =>
          a.symbol.includes(consulta) ||
          a.name.toUpperCase().includes(consulta),
      )
    : activos;

  const exacto = activos.some((a) => a.symbol === consulta);
  const puedeCrear = consulta.length >= 1 && !exacto;

  function abrirAlta() {
    setNombre("");
    setTipo("CEDEAR");
    setMoneda(SUGERENCIA.CEDEAR.moneda);
    setMercado(SUGERENCIA.CEDEAR.mercado);
    setCreando(true);
    setAbierto(false);
  }

  function cambiarTipo(t: AssetType) {
    setTipo(t);
    setMoneda(SUGERENCIA[t].moneda);
    setMercado(SUGERENCIA[t].mercado);
  }

  async function guardar() {
    setGuardando(true);
    setError("");
    const r = await crearAsset({
      symbol: consulta,
      name: nombre || consulta,
      asset_type: tipo,
      currency: moneda,
      market: mercado || null,
    });
    setGuardando(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    onCreado(r.data);
    onElegir(r.data.id);
    setTexto("");
    setCreando(false);
  }

  if (creando) {
    return (
      <div className="rounded border border-brand/40 bg-ink-800 p-4">
        <p className="mb-3 text-sm text-text-muted">
          Nuevo activo <span className="font-medium text-text">{consulta}</span>
        </p>
        <div className="grid gap-3">
          <Field
            label="Nombre"
            value={nombre}
            onChange={(e) => setNombre(e.target.value)}
            placeholder={`Descripción de ${consulta}`}
          />
          <Select
            label="Tipo"
            value={tipo}
            onChange={(e) => cambiarTipo(e.target.value as AssetType)}
          >
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.etiqueta}
              </option>
            ))}
          </Select>
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Moneda"
              value={moneda}
              onChange={(e) => setMoneda(e.target.value.toUpperCase())}
            />
            <Field
              label="Mercado"
              value={mercado}
              onChange={(e) => setMercado(e.target.value.toUpperCase())}
            />
          </div>
        </div>
        {error && (
          <div className="mt-3">
            <ErrorNote>{error}</ErrorNote>
          </div>
        )}
        <div className="mt-4 flex gap-2">
          <Button onClick={() => void guardar()} disabled={guardando}>
            {guardando ? "Creando…" : "Crear y usar"}
          </Button>
          <Button variant="ghost" onClick={() => setCreando(false)}>
            Cancelar
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div ref={contenedor} className="relative">
      <label className="block">
        <span className="mb-1.5 block text-sm text-text-muted">Activo</span>
        <input
          type="text"
          value={abierto ? texto : (elegido ? `${elegido.symbol} — ${elegido.name}` : texto)}
          onChange={(e) => {
            setTexto(e.target.value);
            setAbierto(true);
          }}
          onFocus={() => {
            setTexto("");
            setAbierto(true);
          }}
          placeholder="Escribí el símbolo: AAPL, AL30…"
          className="w-full rounded border border-ink-600 bg-ink-800 px-3 py-2 text-base
                     placeholder:text-text-faint focus:border-brand"
        />
      </label>

      {abierto && (
        <div
          className="absolute z-10 mt-1 max-h-64 w-full overflow-y-auto rounded border
                     border-ink-600 bg-ink-800 shadow-lg"
        >
          {coincidencias.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => {
                onElegir(a.id);
                setAbierto(false);
                setTexto("");
              }}
              className="flex w-full items-baseline gap-2 px-3 py-2 text-left
                         hover:bg-ink-700"
            >
              <span className="font-medium">{a.symbol}</span>
              <span className="truncate text-sm text-text-muted">{a.name}</span>
              <span className="ml-auto text-micro text-text-faint">
                {a.currency}
              </span>
            </button>
          ))}

          {coincidencias.length === 0 && !puedeCrear && (
            <p className="px-3 py-2 text-sm text-text-muted">
              No hay activos cargados todavía.
            </p>
          )}

          {puedeCrear && (
            <button
              type="button"
              onClick={abrirAlta}
              className="w-full border-t border-ink-600 px-3 py-2 text-left text-sm
                         text-brand hover:bg-ink-700"
            >
              Crear <span className="font-medium">{consulta}</span> como activo
              nuevo
            </button>
          )}
        </div>
      )}
    </div>
  );
}
