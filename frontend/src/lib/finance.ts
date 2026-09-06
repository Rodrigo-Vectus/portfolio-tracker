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

export type AssetType = "CEDEAR" | "CRYPTO" | "CASH";
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
}) => api.post<Asset>("/assets", body, true);

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

export const fetchPositions = (portfolioId: string) =>
  api.get<PositionsResponse>(`/positions?portfolio_id=${portfolioId}`);

export type { ApiResult };
