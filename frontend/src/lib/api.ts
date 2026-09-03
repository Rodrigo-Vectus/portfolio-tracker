/**
 * Cliente HTTP de la API.
 *
 * Devuelve siempre un resultado explicito en lugar de lanzar: en esta
 * plataforma una falla de red tiene que poder mostrarse como estado, no
 * romper la pantalla. Es la misma regla que despues va a aplicar a las
 * cotizaciones (regla I.2: los errores se registran, no se ocultan).
 */

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export async function apiGet<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { Accept: "application/json" },
    });
    const data = (await res.json()) as T;
    // 503 en /health/ready es una respuesta valida con cuerpo util.
    if (!res.ok && res.status !== 503) {
      return { ok: false, error: `HTTP ${res.status}` };
    }
    return { ok: true, data };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Error de red" };
  }
}

export type CheckState = "ok" | "error";

export interface ReadyResponse {
  status: "ok" | "degraded";
  checks: Record<string, { status: CheckState; detail: string }>;
}

export interface MetaResponse {
  name: string;
  version: string;
  environment: string;
  phase: string;
  defaults: {
    display_currency: string;
    fx_source_equity: string;
    fx_source_crypto: string;
    cost_basis_method: string;
    timezone: string;
  };
}
