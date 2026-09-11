/**
 * Cartera: una sola pantalla con el estado completo de las posiciones.
 *
 * Funde lo que antes estaba repartido entre Dashboard y Portfolio, que
 * mostraban los mismos números con distinto formato.
 *
 * **Las pestañas filtran en el servidor.** El total que baja ya es el del tipo
 * elegido, así que la suma de arriba siempre corresponde con la tabla de
 * abajo. Recortar la lista en el navegador y volver a sumarla dejaría dos
 * números que se contradicen, y sumar plata del lado del cliente es
 * exactamente lo que este proyecto no hace.
 *
 * **Esta pantalla no calcula nada.** El ROI de cada posición viene de
 * `/performance`, donde lo produce el dominio. Recalcularlo acá sería una
 * segunda copia de una fórmula financiera, y cuando dos copias divergen los
 * números siguen pareciendo razonables.
 */

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Distribucion } from "../components/Distribucion";
import { FormularioDeOperacion } from "../components/FormularioDeOperacion";
import { GraficoDeEvolucion } from "../components/GraficoDeEvolucion";
import { Sparkline } from "../components/Sparkline";
import {
  Button,
  ErrorNote,
  Modal,
  Nota,
  Num,
  PageHeading,
  Pill,
  Select,
  Tabla,
} from "../components/ui";
import {
  fetchPortfolios,
  fetchHistorial,
  fetchPositions,
  fetchSeriesDeCierres,
  fetchPreferencias,
  fetchRendimiento,
  guardarPreferencias,
  type AssetType,
  type Historial as HistorialT,
  type Portfolio,
  type Position,
  type Rendimiento,
  type Total,
  type TxType,
} from "../lib/finance";
import {
  compararDecimal,
  formatearCantidad,
  formatearImporte,
  formatearPorcentaje,
  haceCuanto,
  signo,
} from "../lib/format";

/** Nombres de los tipos tal como los llama el mercado local. */
const NOMBRE_DE_TIPO: Record<AssetType, string> = {
  CEDEAR: "CEDEARs",
  BOND: "Bonos",
  CRYPTO: "Cripto",
  CASH: "Efectivo",
};

const ORDEN_DE_TIPOS: AssetType[] = ["CEDEAR", "BOND", "CRYPTO", "CASH"];

function tono(valor: string | null) {
  const s = signo(valor);
  return s === "positivo" ? "positivo" : s === "negativo" ? "negativo" : "tenue";
}

/** Una cifra de la cabecera. Nunca muestra cero cuando el dato falta. */
function Cifra({
  etiqueta,
  valor,
  moneda,
  tono: t = "neutro",
  detalle,
  grande = false,
  porcentaje,
}: {
  etiqueta: string;
  valor: string | null;
  moneda?: string;
  tono?: "neutro" | "positivo" | "negativo" | "tenue";
  detalle?: string;
  grande?: boolean;
  /** Fracción, no porcentaje: "0.25" es 25%. */
  porcentaje?: string | null;
}) {
  return (
    // `min-w-0` es lo que evita que la celda se desborde: sin eso una columna
    // de grid no baja del ancho de su contenido, y un importe largo se sale
    // por encima de la cifra de al lado en vez de acomodarse.
    <div className="min-w-0">
      <p className="text-sm text-text-muted">{etiqueta}</p>
      <p className={grande ? "mt-1 text-2xl leading-tight" : "mt-1 text-xl leading-tight"}>
        {valor !== null ? (
          <Num tono={t}>{formatearImporte(valor)}</Num>
        ) : (
          <Num tono="tenue">—</Num>
        )}
      </p>
      {/* La moneda va debajo y no al lado: en línea ensancha la celda y es
          lo que empujaba una cifra sobre la otra. */}
      {moneda && valor !== null && (
        <p className="mt-0.5 text-micro text-text-faint">
          {moneda}
          {porcentaje != null && (
            <>
              {" · "}
              <Num tono={t}>{formatearPorcentaje(porcentaje)}</Num>
            </>
          )}
        </p>
      )}
      {detalle && (
        <p className="mt-1 text-micro text-text-faint">{detalle}</p>
      )}
    </div>
  );
}

/** Columnas por las que se puede ordenar. */
type Columna = "symbol" | "precio" | "variacion" | "valor" | "resultado" | "roi";

/**
 * Ordena las posiciones **sin pasar los importes por `number`**.
 *
 * Reutiliza `compararDecimal`, que ya está probado. Un orden que redondee
 * antes de comparar pone dos filas al revés cuando se parecen, y eso es
 * justamente cuando alguien mira el orden.
 *
 * Lo que no se puede calcular va siempre al final, sin importar la dirección:
 * una fila sin precio no es la peor ni la mejor, es una que no se sabe.
 */
function ordenar(
  posiciones: Position[],
  roiDe: (p: Position) => string | null,
  por: Columna,
  desc: boolean,
): Position[] {
  const valorDe = (p: Position): string | null => {
    switch (por) {
      case "symbol":
        return null;
      case "precio":
        return p.current_price;
      case "variacion":
        return p.variacion_diaria;
      case "valor":
        return p.current_value;
      case "resultado":
        return p.unrealized_pnl;
      case "roi":
        return roiDe(p);
    }
  };

  return [...posiciones].sort((a, b) => {
    if (por === "symbol") {
      const cmp = a.symbol.localeCompare(b.symbol);
      return desc ? -cmp : cmp;
    }
    const va = valorDe(a);
    const vb = valorDe(b);
    if (va === null && vb === null) return a.symbol.localeCompare(b.symbol);
    if (va === null) return 1;
    if (vb === null) return -1;
    const cmp = compararDecimal(va, vb);
    return desc ? -cmp : cmp;
  });
}

/** Encabezado que ordena al hacer clic. */
function Encabezado({
  columna,
  orden,
  onOrdenar,
  children,
}: {
  columna: Columna;
  orden: { por: Columna; desc: boolean };
  onOrdenar: (c: Columna) => void;
  children: React.ReactNode;
}) {
  const activa = orden.por === columna;
  return (
    <button
      onClick={() => onOrdenar(columna)}
      className={`inline-flex items-center gap-1 transition-colors hover:text-text ${
        activa ? "text-text" : ""
      }`}
    >
      {children}
      <span aria-hidden className={activa ? "" : "opacity-0"}>
        {orden.desc ? "\u2193" : "\u2191"}
      </span>
    </button>
  );
}

export function Cartera() {
  const [portfolios, setPortfolios] = useState<Portfolio[] | null>(null);
  const [elegido, setElegido] = useState("");
  const [posiciones, setPosiciones] = useState<Position[] | null>(null);
  const [rendimiento, setRendimiento] = useState<Rendimiento | null>(null);
  // Total de la cartera entera. Las pestañas filtran la tabla, no la
  // cabecera: el resumen de arriba responde "cuánto tengo", y esa pregunta no
  // cambia porque abajo se esté mirando un tipo de activo.
  const [totalGeneral, setTotalGeneral] = useState<Total | null>(null);
  const [tipo, setTipo] = useState<AssetType | "">("");
  // Los tipos que la cartera realmente tiene. Se calculan con la lista sin
  // filtrar: si se tomaran de la lista ya filtrada, elegir una pestaña haría
  // desaparecer a todas las demas.
  const [tipos, setTipos] = useState<AssetType[]>([]);
  // `null` mientras no se sabe la preferencia guardada. Distinto de `""`, que
  // ya es una eleccion.
  const [verEn, setVerEn] = useState<string | null>(null);
  const [error, setError] = useState("");
  // Qué operación está por cargarse. `null` = panel cerrado. Guarda el tipo y
  // el activo para que «Vender» desde una fila llegue con todo puesto.
  const [cargando, setCargando] = useState<
    { tipo: TxType; assetId?: string } | null
  >(null);
  // Cambia cuando se registra algo: obliga a volver a pedir posiciones y
  // rendimiento. Es explícito y no un efecto colgado de otra cosa.
  const [revision, setRevision] = useState(0);
  const [historial, setHistorial] = useState<HistorialT | null>(null);
  const [series, setSeries] = useState<Map<string, number[]>>(new Map());
  const [orden, setOrden] = useState<{ por: Columna; desc: boolean }>({
    por: "valor",
    desc: true,
  });

  useEffect(() => {
    void fetchPortfolios().then((r) => {
      if (!r.ok) {
        setError(r.error);
        setPortfolios([]);
        return;
      }
      setPortfolios(r.data);
      if (r.data.length > 0) setElegido(r.data[0].id);
    });
    void fetchPreferencias().then((r) => {
      setVerEn(r.ok ? (r.data.display_currency ?? "") : "");
    });
  }, []);

  // Lista completa: alimenta las pestañas y nada más.
  useEffect(() => {
    if (!elegido) return;
    void fetchPositions(elegido).then((r) => {
      if (!r.ok) return;
      setTotalGeneral(r.data.total);
      const presentes = new Set(r.data.positions.map((p) => p.asset_type));
      setTipos(ORDEN_DE_TIPOS.filter((t) => presentes.has(t)));
    });
  }, [elegido, revision]);

  useEffect(() => {
    if (!elegido || verEn === null) return;
    void (async () => {
      setPosiciones(null);
      const [pos, rend, hist, ser] = await Promise.all([
        fetchPositions(elegido, verEn || undefined, tipo || undefined),
        fetchRendimiento(elegido),
        fetchHistorial(elegido),
        fetchSeriesDeCierres(elegido),
      ]);
      if (pos.ok) {
        setPosiciones(pos.data.positions);
        setError("");
      } else {
        setError(pos.error);
        setPosiciones([]);
      }
      if (rend.ok) setRendimiento(rend.data);
      if (hist.ok) setHistorial(hist.data);
      if (ser.ok) {
        // El sparkline dibuja una forma, no un importe: acá sí se convierte a
        // `number`, porque un píxel de más no es un error contable. Los
        // importes que se muestran como texto siguen sin pasar por `number`.
        setSeries(
          new Map(
            ser.data.series.map((x) => [
              x.asset_id,
              x.puntos.map((pt) => Number(pt.close)),
            ]),
          ),
        );
      }
    })();
  }, [elegido, verEn, tipo, revision]);

  const roiPorSimbolo = useMemo(() => {
    const m = new Map<string, string | null>();
    for (const r of rendimiento?.posiciones ?? []) m.set(r.symbol, r.roi);
    return m;
  }, [rendimiento]);

  const filas = posiciones
    ? ordenar(
        posiciones,
        (p) => roiPorSimbolo.get(p.symbol) ?? null,
        orden.por,
        orden.desc,
      )
    : null;

  function alOrdenar(c: Columna) {
    // Segundo clic en la misma columna invierte. Cambiar de columna arranca
    // descendente, que es como se mira una cartera: lo más grande primero.
    setOrden((o) => (o.por === c ? { por: c, desc: !o.desc } : { por: c, desc: true }));
  }

  function cambiarMoneda(valor: string) {
    setVerEn(valor);
    void guardarPreferencias(valor === "" ? null : valor);
  }

  if (portfolios === null) {
    return (
      <>
        <PageHeading title="Cartera" />
        <p className="text-text-muted">Cargando…</p>
      </>
    );
  }

  const moneda = totalGeneral?.currency ?? "ARS";

  return (
    <>
      <PageHeading
        title="Cartera"
        subtitle="Tus posiciones, derivadas del libro de operaciones."
      />

      {error && <ErrorNote>{error}</ErrorNote>}

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
        <div className="w-44">
          <Select
            label="Ver en"
            value={verEn ?? ""}
            disabled={verEn === null}
            onChange={(e) => cambiarMoneda(e.target.value)}
          >
            <option value="">Moneda original</option>
            <option value="USD">Dólares</option>
          </Select>
        </div>
        {/* Un <a> adentro de un <button> es HTML invalido y el navegador lo
            reacomoda a su gusto. El enlace lleva los estilos directamente. */}
        <Button onClick={() => setCargando({ tipo: "BUY" })}>Comprar</Button>
        <Button
          variant="secondary"
          onClick={() => setCargando({ tipo: "SELL" })}
          disabled={!posiciones || posiciones.length === 0}
        >
          Vender
        </Button>
        <Link
          to="/operaciones"
          className="inline-flex items-center justify-center rounded-full border
                     border-ink-600 px-4 py-2 text-sm font-medium text-text-muted
                     transition-colors hover:text-text"
        >
          Ver operaciones
        </Link>
      </div>

      {/* Cabecera: el estado de la cartera en cuatro números, cada uno con su
          nombre propio. No hay un "beneficio" único que mezcle lo realizado
          con lo que todavía no se vendió: son dos cosas distintas y juntarlas
          en un solo número era uno de los errores de la planilla. */}
      <div className="mb-8 grid gap-6 rounded-xl border border-ink-600 bg-ink-800 p-6 sm:grid-cols-2 lg:grid-cols-4">
        <Cifra
          etiqueta="Valor de la cartera"
          valor={totalGeneral?.total ?? null}
          moneda={moneda}
          grande
          detalle={totalGeneral?.motivo ?? undefined}
        />
        <Cifra
          etiqueta="Beneficio histórico"
          valor={rendimiento?.resultado_total ?? null}
          moneda={moneda}
          tono={tono(rendimiento?.resultado_total ?? null)}
          detalle="Lo realizado más lo no realizado."
        />
        <Cifra
          etiqueta="Resultado no realizado"
          valor={rendimiento?.no_realizado ?? null}
          moneda={moneda}
          tono={tono(rendimiento?.no_realizado ?? null)}
          porcentaje={rendimiento?.roi ?? null}
          detalle="Si vendieras hoy, sobre el costo de lo abierto."
        />
        <Cifra
          etiqueta="Resultado realizado"
          valor={rendimiento?.realizado ?? null}
          moneda={moneda}
          tono={tono(rendimiento?.realizado ?? null)}
          detalle="Lo que ya se cerró con una venta."
        />
      </div>

      {/* Evolución y composición, uno al lado del otro: cómo llegó la cartera
          hasta acá y de qué está hecha hoy. */}
      <div className="mb-8 grid gap-6 xl:grid-cols-2">
        <div className="rounded-xl border border-ink-600 bg-ink-800 p-5">
          <h2 className="mb-4 text-sm font-medium text-text-muted">
            Evolución
          </h2>
          {historial === null ? (
            <p className="text-sm text-text-faint">Cargando…</p>
          ) : historial.puntos.length < 2 ? (
            // Un punto solo no es una línea. Se dice por qué en vez de dibujar
            // algo que parezca una serie.
            <p className="max-w-prose text-sm text-text-faint">
              {historial.nota ??
                "Todavía no hay suficientes días para dibujar una línea."}
            </p>
          ) : (
            <GraficoDeEvolucion puntos={historial.puntos} />
          )}
        </div>

        {posiciones && posiciones.length > 0 && (
          <Distribucion posiciones={posiciones} moneda={moneda} />
        )}
      </div>

      {/* Pestañas por tipo de activo. Sólo aparecen los tipos que la cartera
          tiene: una pestaña de Cripto vacía prometería algo que no está. */}
      {tipos.length > 1 && (
        <div className="mb-4 flex flex-wrap gap-2 border-b border-ink-600 pb-3">
          <Solapa activa={tipo === ""} onClick={() => setTipo("")}>
            Todo
          </Solapa>
          {tipos.map((t) => (
            <Solapa key={t} activa={tipo === t} onClick={() => setTipo(t)}>
              {NOMBRE_DE_TIPO[t]}
            </Solapa>
          ))}
        </div>
      )}

      {posiciones === null ? (
        <p className="text-text-muted">Cargando posiciones…</p>
      ) : posiciones.length === 0 ? (
        <p className="text-text-muted">
          {tipo
            ? "No hay posiciones abiertas de ese tipo."
            : "No hay posiciones abiertas. Las posiciones se calculan a partir de tus operaciones."}
        </p>
      ) : (
        <Tabla
          columnas={[
            { titulo: "Activo" },
            { titulo: "Precio", alineacion: "derecha" },
            { titulo: "Var.", alineacion: "derecha" },
            { titulo: "30 días", alineacion: "derecha" },
            { titulo: "Cantidad", alineacion: "derecha" },
            { titulo: "Monto actual", alineacion: "derecha" },
            { titulo: "PPC", alineacion: "derecha" },
            { titulo: "+/−", alineacion: "derecha" },
            { titulo: "%", alineacion: "derecha" },
            { titulo: "", alineacion: "derecha" },
          ]}
          encabezados={[
            <Encabezado columna="symbol" orden={orden} onOrdenar={alOrdenar}>
              Activo
            </Encabezado>,
            <Encabezado columna="precio" orden={orden} onOrdenar={alOrdenar}>
              Precio
            </Encabezado>,
            <Encabezado columna="variacion" orden={orden} onOrdenar={alOrdenar}>
              Var.
            </Encabezado>,
            null,
            null,
            <Encabezado columna="valor" orden={orden} onOrdenar={alOrdenar}>
              Monto actual
            </Encabezado>,
            null,
            <Encabezado columna="resultado" orden={orden} onOrdenar={alOrdenar}>
              +/−
            </Encabezado>,
            <Encabezado columna="roi" orden={orden} onOrdenar={alOrdenar}>
              %
            </Encabezado>,
            null,
          ]}
        >
          {(filas ?? []).map((p) => {
            const roi = roiPorSimbolo.get(p.symbol) ?? null;
            return (
              <tr key={p.asset_id} className="border-b border-ink-600/60">
                <td className="px-4 py-3">
                  <span className="font-medium">{p.symbol}</span>
                  <span className="ml-2 text-micro text-text-faint">
                    {NOMBRE_DE_TIPO[p.asset_type]}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {p.current_price !== null ? (
                    <>
                      <Num>{formatearImporte(p.current_price)}</Num>
                      <span className="code mt-0.5 block text-micro text-text-faint">
                        {p.price_as_of ? haceCuanto(p.price_as_of) : "sin fecha"}
                        {p.price_is_estimated && " · estimada"}
                      </span>
                    </>
                  ) : (
                    <Num tono="tenue">—</Num>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {p.variacion_diaria !== null ? (
                    <>
                      <Num tono={tono(p.variacion_diaria)}>
                        {formatearPorcentaje(p.variacion_diaria)}
                      </Num>
                      {/* La fecha del cierre usado, porque sin feriados un
                          lunes compara contra el viernes. */}
                      <span className="code mt-0.5 block text-micro text-text-faint">
                        vs {p.variacion_desde}
                      </span>
                    </>
                  ) : (
                    <Num tono="tenue" title="Todavía no hay un cierre anterior">
                      —
                    </Num>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <Sparkline valores={series.get(p.asset_id) ?? []} />
                </td>
                <td className="px-4 py-3 text-right">
                  <Num>{formatearCantidad(p.quantity)}</Num>
                </td>
                <td className="px-4 py-3 text-right">
                  {p.current_value !== null ? (
                    <Num>{formatearImporte(p.current_value)}</Num>
                  ) : (
                    <Num tono="tenue" title="Sin cotización">
                      —
                    </Num>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {p.average_cost !== null ? (
                    <Num>{formatearImporte(p.average_cost)}</Num>
                  ) : (
                    <Num tono="tenue">—</Num>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {p.unrealized_pnl !== null ? (
                    <Num tono={tono(p.unrealized_pnl)}>
                      {formatearImporte(p.unrealized_pnl)}
                    </Num>
                  ) : (
                    <Num tono="tenue">—</Num>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {roi !== null ? (
                    <Num tono={tono(roi)}>{formatearPorcentaje(roi)}</Num>
                  ) : (
                    <Num tono="tenue">—</Num>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  {/* Llega con el activo ya elegido: vender desde la fila no
                      debería obligar a buscarlo otra vez en una lista. */}
                  <span className="inline-flex gap-2">
                    <button
                      onClick={() =>
                        setCargando({ tipo: "BUY", assetId: p.asset_id })
                      }
                      className="rounded-full border border-ink-600 px-3 py-1
                                 text-micro uppercase tracking-wider text-text-muted
                                 transition-colors hover:text-text"
                    >
                      Comprar
                    </button>
                    <button
                      onClick={() =>
                        setCargando({ tipo: "SELL", assetId: p.asset_id })
                      }
                      className="rounded-full border border-ink-600 px-3 py-1
                                 text-micro uppercase tracking-wider text-text-muted
                                 transition-colors hover:text-text"
                    >
                      Vender
                    </button>
                  </span>
                </td>
              </tr>
            );
          })}
        </Tabla>
      )}

      {totalGeneral?.es_estimado && (
        <div className="mt-4">
          <Pill tono="aviso">Antigüedad estimada</Pill>
        </div>
      )}

      {cargando && elegido && (
        <Modal
          titulo={cargando.tipo === "BUY" ? "Registrar compra" : "Registrar venta"}
          onCerrar={() => setCargando(null)}
        >
          <FormularioDeOperacion
            portfolioId={elegido}
            tipoInicial={cargando.tipo}
            activoInicial={cargando.assetId}
            onRegistrada={() => {
              setCargando(null);
              // Las posiciones son función del libro: si el libro cambió, lo
              // que está en pantalla dejó de ser cierto.
              setRevision((n) => n + 1);
            }}
          />
        </Modal>
      )}

      <div className="mt-8 space-y-3">
        <Nota>
          El «%» es el ROI de cada posición: resultado no realizado sobre el
          costo de lo que sigue abierto. No se calcula sobre compras menos
          ventas, porque ese denominador se achica en cada venta y el
          porcentaje se infla solo.
        </Nota>
        <Nota>
          La columna «Var.» compara el precio actual contra el último cierre
          guardado y dice de qué fecha es ese cierre. No se llama «24h» porque
          no siempre lo es: un lunes compara contra el viernes, y sin
          calendario de feriados un lunes feriado compara contra el jueves.
          Mientras no haya un cierre anterior muestra un guion, no un cero.
        </Nota>      </div>
    </>
  );
}

function Solapa({
  activa,
  onClick,
  children,
}: {
  activa: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-4 py-1.5 text-sm font-medium transition-colors ${
        activa
          ? "bg-brand text-ink-950"
          : "border border-ink-600 text-text-muted hover:text-text"
      }`}
    >
      {children}
    </button>
  );
}
