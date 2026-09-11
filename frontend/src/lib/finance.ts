/**
 * Llamadas a la API financiera.
 *
 * **Todos los importes y cantidades son `string`, nunca `number`.** No es un
 * descuido de tipado: la base guarda `NUMERIC(38,18)` y el `number` de
 * JavaScript no puede representarlo. Tiparlos como `number` invitaría a que
 * alguien haga una cuenta en el navegador y obtenga otro resultado que el
 * servidor.
 *
 * Si en algún momento hace falta operar con estos valores del lado del
 * cliente, la respuesta correcta es pedirle el cálculo al backend, no
 * convertir a float.
 */

import { api, type ApiResult } from "./api";

/**
 * Tipos de activo.
 *
 * `BOND` se agregó al mirar boletos reales: el catálogo original no
 * contemplaba bonos. AL30 cotiza en pesos y AL30D en dólares, así que un bono
 * puede tener moneda distinta del resto de la cartera.
 */
export type AssetType = "CEDEAR" | "BOND" | "CRYPTO" | "CASH";
export type AccountType = "BROKER" | "EXCHANGE" | "WALLET";
export type TxType =
  | "BUY"
  | "SELL"
  | "DEPOSIT"
  | "WITHDRAWAL"
  | "FEE"
  | "DIVIDEND"
  | "TRANSFER";

export interface Asset {
  id: string;
  symbol: string;
  name: string;
  asset_type: AssetType;
  currency: string;
  market: string | null;
  sector: string | null;
  display_precision: number;
  /**
   * Cuántas unidades representa el precio informado.
   *
   * 100 para bonos, que cotizan por lámina de 100 nominales; 1 para todo lo
   * demás. Sin esto el costo de un bono sale cien veces mayor, y el error no
   * se nota porque el número queda grande pero plausible.
   */
  price_factor: string;
  is_active: boolean;
}

export interface Account {
  id: string;
  name: string;
  account_type: AccountType;
  country: string | null;
  default_currency: string;
  is_active: boolean;
}

export interface Portfolio {
  id: string;
  name: string;
  base_currency: string;
  is_default: boolean;
}

export interface Transaction {
  id: string;
  portfolio_id: string;
  asset_id: string | null;
  account_id: string | null;
  tx_type: TxType;
  quantity: string;
  unit_price: string;
  price_currency: string;
  settlement_currency: string;
  commission: string;
  taxes: string;
  gross_amount: string | null;
  net_amount: string | null;
  fx_rate_used: string | null;
  fx_source: string | null;
  executed_at: string;
  trade_date: string;
  status: "ACTIVE" | "VOIDED";
  voided_reason: string | null;
  notes: string | null;
}

/** Calidad de la antigüedad de un precio. */
export type PriceStatus =
  | "FRESCA"
  | "ESTIMADA"
  | "VIEJA"
  | "SIN_FECHA"
  | "AUSENTE";

/**
 * Posición derivada del libro, con su valuación cuando existe.
 *
 * **Todo lo de mercado puede venir en `null`, y eso es información.** Un
 * `current_value` nulo dice "no sé cuánto vale"; un cero diría "no vale
 * nada". La pantalla los muestra distinto.
 */
export interface Position {
  asset_id: string;
  symbol: string;
  asset_type: AssetType;
  quantity: string;
  average_cost: string | null;
  open_cost_basis: string;
  realized_pnl: string;
  cost_method: string;
  currency: string;
  last_transaction_at: string | null;
  computed_at: string | null;

  current_price: string | null;
  current_value: string | null;
  unrealized_pnl: string | null;
  price_source: string | null;
  price_as_of: string | null;
  price_is_estimated: boolean;
  price_status: PriceStatus;

  /**
   * Costo y valor en moneda dura, cuando se piden.
   *
   * El costo se convierte lote por lote al tipo de cambio de la fecha de cada
   * compra; el valor actual, al de hoy. Esa asimetría es lo que hace que el
   * número en dólares diga algo distinto del de pesos: convertir las dos
   * puntas con el mismo dólar daba el mismo porcentaje, que es lo que le
   * pasaba a la planilla.
   */
  hard_currency: string | null;
  hard_cost_basis: string | null;
  hard_current_value: string | null;
  hard_unrealized_pnl: string | null;
  hard_motivo: string | null;
}

/**
 * Total de la cartera con su declaración de completitud.
 *
 * `total` viene en `null` cuando a alguna posición le falta el precio o lo
 * tiene viejo. `motivo` explica por qué, para poder decirlo en pantalla en
 * lugar de dejar un hueco.
 */
export interface Total {
  total: string | null;
  currency: string;
  es_completo: boolean;
  es_estimado: boolean;
  motivo: string | null;
  posiciones_totales: number;
  posiciones_sin_precio: number;
  posiciones_con_precio_viejo: number;
  posiciones_estimadas: number;
}

export interface PositionsResponse {
  positions: Position[];
  total: Total;
}

export interface NuevaOperacion {
  portfolio_id: string;
  asset_id?: string | null;
  account_id?: string | null;
  tx_type: TxType;
  quantity: string;
  unit_price: string;
  price_currency: string;
  settlement_currency?: string | null;
  commission?: string;
  taxes?: string;
  executed_at: string;
  notes?: string | null;
}

export const fetchAssets = () => api.get<Asset[]>("/assets");
export const fetchAccounts = () => api.get<Account[]>("/accounts");
export const fetchPortfolios = () => api.get<Portfolio[]>("/portfolios");

export const crearAsset = (body: {
  symbol: string;
  name: string;
  asset_type: AssetType;
  currency: string;
  market?: string | null;
  sector?: string | null;
  price_factor?: string;
}) => api.post<Asset>("/assets", body, true);

/**
 * Edita un activo del catálogo.
 *
 * El símbolo, el mercado y el tipo no se pueden cambiar: forman la clave
 * natural y el activo puede tener operaciones asociadas.
 */
export const editarAsset = (
  id: string,
  body: {
    name?: string;
    sector?: string | null;
    display_precision?: number;
    price_factor?: string;
    is_active?: boolean;
  },
) => api.patch<Asset>(`/assets/${id}`, body, true);

export const crearAccount = (body: {
  name: string;
  account_type: AccountType;
  default_currency: string;
}) => api.post<Account>("/accounts", body, true);

export const crearPortfolio = (body: { name: string; base_currency: string }) =>
  api.post<Portfolio>("/portfolios", body, true);

export const fetchTransactions = (portfolioId: string, incluirAnuladas = false) =>
  api.get<Transaction[]>(
    `/transactions?portfolio_id=${portfolioId}` +
      (incluirAnuladas ? "&incluir_anuladas=true" : ""),
  );

export const crearOperacion = (body: NuevaOperacion) =>
  api.post<Transaction>("/transactions", body, true);

export const anularOperacion = (id: string, motivo: string) =>
  api.post<Transaction>(`/transactions/${id}/void`, { motivo }, true);

export interface Movimiento {
  tx_id: string;
  tx_type: TxType;
  fecha: string;
  monto: string;
  saldo_posterior: string;
  currency: string;
  descripcion: string;
}

/** Saldo de caja con su desglose. El total solo no explica de dónde sale. */
export interface Saldo {
  currency: string;
  saldo: string;
  depositos: string;
  retiros: string;
  invertido: string;
  recuperado: string;
  dividendos: string;
  comisiones: string;
  aporte_neto: string;
  es_negativo: boolean;
  movimientos: Movimiento[];
}

export const fetchSaldo = (portfolioId: string, currency = "ARS") =>
  api.get<Saldo>(`/cash?portfolio_id=${portfolioId}&currency=${currency}`);

export const crearMovimiento = (body: {
  portfolio_id: string;
  account_id?: string | null;
  tx_type: TxType;
  monto: string;
  currency: string;
  executed_at: string;
  notes?: string | null;
}) => api.post<Transaction>("/cash", body, true);

export interface Roi {
  symbol: string;
  open_cost_basis: string;
  valor_actual: string | null;
  no_realizado: string | null;
  /** Fracción, no porcentaje: "0.25" es 25%. */
  roi: string | null;
}

/**
 * Rendimiento de la cartera.
 *
 * `xirr_anual` viene en `null` con `xirr_motivo` explicando por qué, en vez de
 * un cero que se leería como "no rindió nada".
 */
/**
 * Rendimiento de la cartera aislando el efecto de los aportes.
 *
 * Nunca viene un número pelado: `desde`, `hasta` y `subperiodos` dicen sobre
 * qué tramo se calculó. `corte` avisa que la serie se partió por un día sin
 * valuar, y `advertencia` que el número es correcto pero se lee mal.
 *
 * `anualizado` queda en `null` mientras la serie sea corta: elevar unos pocos
 * días a 365/n produce tasas de miles por ciento que no describen ningún año.
 */
export interface Twr {
  /** Fracción, no porcentaje: "0.25" es 25%. */
  acumulado: string | null;
  anualizado: string | null;
  desde: string | null;
  hasta: string | null;
  dias: number;
  subperiodos: number;
  motivo: string | null;
  corte: string | null;
  advertencia: string | null;
}

export interface Rendimiento {
  currency: string;
  posiciones: Roi[];
  realizado: string;
  no_realizado: string | null;
  resultado_total: string | null;
  valor_actual: string | null;
  aporte_neto: string;
  xirr_anual: string | null;
  xirr_motivo: string | null;
  twr: Twr;
}

/**
 * Un punto de la evolución de la cartera.
 *
 * `total_value` puede venir en `null`: ese día faltó alguna cotización. El
 * gráfico corta ahí en vez de interpolar.
 */
export interface Punto {
  snapshot_date: string;
  total_value: string | null;
  open_cost_basis: string;
  unrealized_pnl: string | null;
  realized_pnl: string;
  cash_balance: string;
  currency: string;
  is_estimated: boolean;
  motivo: string | null;
}

export interface Historial {
  puntos: Punto[];
  currency: string;
  desde: string | null;
  nota: string | null;
}

export const fetchHistorial = (portfolioId: string) =>
  api.get<Historial>(`/history?portfolio_id=${portfolioId}`);

export const fetchRendimiento = (portfolioId: string, currency = "ARS") =>
  api.get<Rendimiento>(
    `/performance?portfolio_id=${portfolioId}&currency=${currency}`,
  );

/**
 * Posiciones de un portfolio.
 *
 * `assetType` filtra en el servidor, no en el cliente: así el total que vuelve
 * es el de lo filtrado. Recortar la lista acá dejaría un total que no
 * corresponde con lo que se ve, y retotalizarlo en el navegador sería
 * calcular plata del lado equivocado.
 */
export const fetchPositions = (
  portfolioId: string,
  hardCurrency?: string,
  assetType?: string,
) =>
  api.get<PositionsResponse>(
    `/positions?portfolio_id=${portfolioId}` +
      (hardCurrency ? `&hard_currency=${hardCurrency}` : "") +
      (assetType ? `&asset_type=${assetType}` : ""),
  );

export type { ApiResult };
